"""Format-agnostic waveform operations used by the MCP tools.

VCD is read in-process (``vcd.py``); FST is transparently converted to a temp
VCD via ``fst.py`` first. No GUI is ever launched.
"""

from __future__ import annotations

import fnmatch
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Iterator

from . import fst, vcd

VCD_EXTS = {".vcd", ".gz"}   # .vcd or .vcd.gz
FST_EXTS = {".fst"}


def detect_format(path: str | Path) -> str:
    suf = Path(path).suffix.lower()
    if suf == ".fst":
        return "fst"
    if suf in (".vcd", ".gz"):
        return "vcd"
    raise ValueError(f"unsupported/unknown waveform extension: {Path(path).name}")


@contextmanager
def _as_vcd(path: str | Path) -> Iterator[Path]:
    """Yield a readable VCD path for either a VCD or an FST input."""
    fmt = detect_format(path)
    if fmt == "vcd":
        with nullcontext(Path(path)) as p:
            yield p
    else:
        with fst.converted_vcd(path) as p:
            yield p


# --------------------------------------------------------------------------- #
# Signal-name resolution
# --------------------------------------------------------------------------- #

def _strip_range(name: str) -> str:
    i = name.find("[")
    return name[:i] if i != -1 else name


def resolve_signals(header: vcd.Header, requested: list[str]) -> dict[str, str | None]:
    """Map each requested signal name to a VCD id code (or ``None``).

    Matching is forgiving: exact full name, then range-stripped, then a unique
    suffix (basename) match.
    """
    by_full: dict[str, str] = {}
    by_stripped: dict[str, str] = {}
    by_suffix: dict[str, list[str]] = {}
    for v in header.vars:
        by_full[v.name] = v.id_code
        by_stripped.setdefault(_strip_range(v.name), v.id_code)
        base = v.name.rsplit(".", 1)[-1]
        by_suffix.setdefault(base, []).append(v.id_code)
        by_suffix.setdefault(_strip_range(base), []).append(v.id_code)

    out: dict[str, str | None] = {}
    for req in requested:
        if req in by_full:
            out[req] = by_full[req]
        elif _strip_range(req) in by_stripped:
            out[req] = by_stripped[_strip_range(req)]
        elif req in by_suffix and len(set(by_suffix[req])) == 1:
            out[req] = by_suffix[req][0]
        else:
            out[req] = None
    return out


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #

def info(path: str | Path) -> dict:
    fmt = detect_format(path)
    with _as_vcd(path) as vpath:
        header = vcd.parse_header(vpath)
        lo, hi = vcd.time_range(vpath)
    return {
        "path": str(path),
        "format": fmt,
        "timescale": header.timescale,
        "date": header.date,
        "version": header.version,
        "num_signals": header.num_signals,
        "num_scopes": header.num_scopes(),
        "start_time": lo,
        "end_time": hi,
    }


def list_signals(
    path: str | Path,
    scope: str | None = None,
    pattern: str | None = None,
    limit: int = 500,
) -> dict:
    # Always derive names from the VCD view (native for VCD, fst2vcd for FST)
    # so the result is identical across formats and consistent with
    # list_scopes/waveform_info. `fstminer -n` is NOT used here: it collapses
    # aliased nets (the same signal referenced under multiple hierarchical port
    # names), yielding a different, smaller list. That collapsed view is still
    # available via mine_values(names_only=True).
    with _as_vcd(path) as vpath:
        names = [v.name for v in vcd.parse_header(vpath).vars]

    if scope:
        prefix = scope if scope.endswith(".") else scope + "."
        names = [n for n in names if n.startswith(prefix) or n == scope]
    if pattern:
        names = [n for n in names if fnmatch.fnmatch(n, pattern)]

    total = len(names)
    return {
        "path": str(path),
        "count": total,
        "truncated": total > limit,
        "signals": names[:limit],
    }


def list_scopes(path: str | Path) -> dict:
    with _as_vcd(path) as vpath:
        header = vcd.parse_header(vpath)
    return {"path": str(path), "hierarchy": header.root.to_dict()["scopes"]}


def get_values(
    path: str | Path,
    signals: list[str],
    start: int | None = None,
    end: int | None = None,
    clock: str | None = None,
    cycle_start: int | None = None,
    cycle_end: int | None = None,
    limit: int = 1000,
) -> dict:
    with _as_vcd(path) as vpath:
        header = vcd.parse_header(vpath)
        resolved = resolve_signals(header, signals)
        targets: dict[str, list[str]] = {}
        for name, id_code in resolved.items():
            if id_code is not None:
                targets.setdefault(id_code, []).append(name)
        unresolved = [n for n, i in resolved.items() if i is None]

        # Translate a cycle window (relative to a clock) into a time window.
        cycle_info = None
        if clock is not None and (cycle_start is not None or cycle_end is not None):
            clk_id = resolve_signals(header, [clock])[clock]
            if clk_id is None:
                raise ValueError(f"clock signal not found: {clock}")
            edges = vcd.clock_edges(vpath, clk_id, edge="rising")
            cs = cycle_start or 0
            start = edges[cs] if cs < len(edges) else None
            if cycle_end is not None and cycle_end + 1 < len(edges):
                end = edges[cycle_end + 1]  # inclusive last cycle
            cycle_info = {"clock": clock, "num_cycles": len(edges),
                          "cycle_start": cs, "cycle_end": cycle_end}

        series: dict[str, list[dict]] = {n: [] for n in signals}
        latest: dict[str, str] = {}
        started: set[str] = set()
        count = 0
        for time, id_code, value in vcd.iter_changes(
            vpath, ids=set(targets), start=None, end=end
        ):
            if start is not None and time < start:
                latest[id_code] = value
                continue
            if start is not None and id_code not in started:
                started.add(id_code)
                if time > start and id_code in latest:
                    for nm in targets[id_code]:
                        series[nm].append({"time": start, "value": latest[id_code]})
                        count += 1
            for nm in targets[id_code]:
                series[nm].append({"time": time, "value": value})
                count += 1
            started.add(id_code)
            if count >= limit:
                break

        # Signals constant across the whole window: surface their entry value.
        if start is not None and count < limit:
            for id_code, names in targets.items():
                if id_code not in started and id_code in latest:
                    for nm in names:
                        series[nm].append({"time": start, "value": latest[id_code]})

    return {
        "path": str(path),
        "window": {"start": start, "end": end},
        "cycles": cycle_info,
        "unresolved": unresolved,
        "truncated": count >= limit,
        "values": series,
    }

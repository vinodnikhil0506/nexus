"""Native, dependency-free VCD (Value Change Dump) reader.

Handles the definition header (timescale, scope hierarchy, signal declarations)
and streams the value-change body. Nothing here launches a GUI; it is pure
text parsing and works on any host. Transparently reads ``.vcd.gz``.

The same logic serves FST files after conversion to VCD via ``fst2vcd`` (see
``fst.py``).
"""

from __future__ import annotations

import gzip
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class Var:
    id_code: str          # VCD identifier code, e.g. "!" or "#$"
    name: str             # fully-qualified, e.g. "top.data[7:0]"
    var_type: str         # "wire", "reg", "integer", ...
    width: int            # bit width


@dataclass
class Scope:
    name: str
    scope_type: str
    scopes: list["Scope"] = field(default_factory=list)
    vars: list[str] = field(default_factory=list)  # fully-qualified var names

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.scope_type,
            "signals": self.vars,
            "scopes": [s.to_dict() for s in self.scopes],
        }


@dataclass
class Header:
    timescale: str
    date: str
    version: str
    root: Scope
    vars: list[Var]
    id_to_names: dict[str, list[str]]  # id code -> [fully-qualified names]

    @property
    def num_signals(self) -> int:
        return len(self.vars)

    def num_scopes(self) -> int:
        def count(s: Scope) -> int:
            return len(s.scopes) + sum(count(c) for c in s.scopes)
        return count(self.root)


def _open_text(path: str | Path) -> io.TextIOBase:
    p = Path(path)
    if p.suffix == ".gz":
        return gzip.open(p, "rt", encoding="utf-8", errors="replace")
    return open(p, "rt", encoding="utf-8", errors="replace")


def _tokens_until_end(first: list[str], stream: Iterator[str]) -> list[str]:
    """Collect whitespace tokens of a ``$keyword ... $end`` command, following
    continuation lines until ``$end`` is seen."""
    toks = list(first)
    while "$end" not in toks:
        line = next(stream, None)
        if line is None:
            break
        toks.extend(line.split())
    toks = toks[: toks.index("$end")] if "$end" in toks else toks
    return toks


def parse_header(path: str | Path) -> Header:
    """Parse the VCD definition section (everything up to ``$enddefinitions``)."""
    timescale = date = version = ""
    root = Scope(name="", scope_type="root")
    stack: list[Scope] = [root]
    vars: list[Var] = []
    id_to_names: dict[str, list[str]] = {}

    with _open_text(path) as fh:
        it = iter(fh)
        for raw in it:
            toks = raw.split()
            if not toks:
                continue
            kw = toks[0]

            if kw == "$enddefinitions":
                break
            elif kw == "$timescale":
                body = _tokens_until_end(toks[1:], it)
                timescale = " ".join(body).strip()
            elif kw == "$date":
                date = " ".join(_tokens_until_end(toks[1:], it)).strip()
            elif kw == "$version":
                version = " ".join(_tokens_until_end(toks[1:], it)).strip()
            elif kw == "$comment":
                _tokens_until_end(toks[1:], it)  # discard
            elif kw == "$scope":
                # $scope <type> <name> $end
                body = _tokens_until_end(toks[1:], it)
                s_type = body[0] if body else "module"
                s_name = body[1] if len(body) > 1 else ""
                node = Scope(name=s_name, scope_type=s_type)
                stack[-1].scopes.append(node)
                stack.append(node)
            elif kw == "$upscope":
                _tokens_until_end(toks[1:], it)
                if len(stack) > 1:
                    stack.pop()
            elif kw == "$var":
                # $var <type> <width> <id> <name> [range] $end
                body = _tokens_until_end(toks[1:], it)
                if len(body) < 4:
                    continue
                v_type = body[0]
                try:
                    width = int(body[1])
                except ValueError:
                    width = 1
                id_code = body[2]
                name = body[3]
                if len(body) > 4:  # bit range emitted as a separate token
                    name += body[4]
                prefix = ".".join(sc.name for sc in stack[1:] if sc.name)
                full = f"{prefix}.{name}" if prefix else name
                vars.append(Var(id_code=id_code, name=full, var_type=v_type, width=width))
                id_to_names.setdefault(id_code, []).append(full)
                stack[-1].vars.append(full)

    return Header(
        timescale=timescale,
        date=date,
        version=version,
        root=root,
        vars=vars,
        id_to_names=id_to_names,
    )


def _normalize(value_token: str) -> str:
    """Normalize a raw VCD value token to a bare value string."""
    c = value_token[0]
    if c in "bB":
        return value_token[1:]  # bit string
    if c in "rR":
        return value_token[1:]  # real, as text
    return value_token  # scalar char (0/1/x/z/...)


def iter_changes(
    path: str | Path,
    ids: set[str] | None = None,
    start: int | None = None,
    end: int | None = None,
) -> Iterator[tuple[int, str, str]]:
    """Yield ``(time, id_code, value)`` triples from the value-change body.

    ``ids`` filters to those identifier codes (``None`` = all). ``start``/``end``
    bound the simulation time (inclusive/exclusive respectively). Streams the
    file line by line — never materializes the whole dump.
    """
    time = 0
    in_defs = True
    with _open_text(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if in_defs:
                if line.startswith("$enddefinitions"):
                    in_defs = False
                continue

            first = line[0]
            if first == "#":
                time = int(line[1:])
                if end is not None and time >= end:
                    return
                continue
            if first == "$":
                continue  # $dumpvars/$dumpall/$dumpoff/$end markers

            if first in "bBrR":
                parts = line.split()
                if len(parts) < 2:
                    continue
                value = _normalize(parts[0])
                id_code = parts[1]
            else:
                value = first
                id_code = line[1:]

            if ids is not None and id_code not in ids:
                continue
            if start is not None and time < start:
                continue
            yield time, id_code, value


def time_range(path: str | Path) -> tuple[int | None, int | None]:
    """Return ``(min_time, max_time)`` by scanning only ``#`` lines."""
    lo: int | None = None
    hi: int | None = None
    in_defs = True
    with _open_text(path) as fh:
        for raw in fh:
            if in_defs:
                if raw.startswith("$enddefinitions"):
                    in_defs = False
                continue
            if raw and raw[0] == "#":
                try:
                    t = int(raw[1:].strip())
                except ValueError:
                    continue
                if lo is None:
                    lo = t
                hi = t
    return lo, hi


def clock_edges(path: str | Path, clock_id: str, edge: str = "rising") -> list[int]:
    """Times at which ``clock_id`` transitions to 1 (rising) or 0 (falling)."""
    want = "1" if edge == "rising" else "0"
    edges: list[int] = []
    prev: str | None = None
    for time, _id, value in iter_changes(path, ids={clock_id}):
        if value == want and prev != want:
            edges.append(time)
        prev = value
    return edges

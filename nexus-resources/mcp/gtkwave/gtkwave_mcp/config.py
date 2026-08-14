"""Locate GTKWave's non-GUI helper binaries.

Only headless converters/miners are ever resolved here (``fst2vcd``,
``vcd2fst``, ``fstminer``, ...). The ``gtkwave`` GUI binary is deliberately
never looked up or executed — this server never opens a window.

Resolution order (first hit wins), cached per name:
  1. ``$GTKWAVE_HOME/build/src/helpers``
  2. ``$PATH`` (``shutil.which``)
  3. the in-tree fallback ``~/Workspace/Tools/gtkwave/build/src/helpers``
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# Headless helpers we are willing to invoke. Note the intentional absence of
# "gtkwave": launching the GUI is out of scope.
HELPERS = {
    "fst2vcd",
    "vcd2fst",
    "fstminer",
    "vcd2lxt2",
    "lxt2vcd",
    "vcd2vzt",
    "vzt2vcd",
    "evcd2vcd",
    "vztminer",
    "lxt2miner",
}

_DEFAULT_TREE = Path.home() / "Workspace" / "Tools" / "gtkwave"


def _helper_dirs() -> list[Path]:
    dirs: list[Path] = []
    home = os.environ.get("GTKWAVE_HOME")
    if home:
        base = Path(home).expanduser()
        dirs += [base / "build" / "src" / "helpers", base / "build" / "src", base]
    dirs.append(_DEFAULT_TREE / "build" / "src" / "helpers")
    return dirs


# Only *successful* resolutions are memoized. Caching a miss (None) would be
# wrong: a helper built after the first lookup — or hidden by a transient env —
# must still be found later. This also keeps tests isolated.
_CACHE: dict[str, str] = {}


def resolve(name: str) -> str | None:
    """Return an absolute path to helper ``name``, or ``None`` if not found."""
    if name == "gtkwave":  # guard against accidental GUI launch
        raise ValueError("the gtkwave GUI binary is not resolvable (headless-only server)")

    if name in _CACHE:
        return _CACHE[name]

    # 1. explicit build dirs from GTKWAVE_HOME / in-tree fallback
    for d in _helper_dirs():
        cand = d / name
        if cand.is_file() and os.access(cand, os.X_OK):
            _CACHE[name] = str(cand)
            return _CACHE[name]

    # 2. PATH
    found = shutil.which(name)
    if found:
        _CACHE[name] = found
        return found

    return None


def _cache_clear() -> None:
    _CACHE.clear()


# Preserve the ``config.resolve.cache_clear()`` API used elsewhere/in tests.
resolve.cache_clear = _cache_clear  # type: ignore[attr-defined]


def require(name: str) -> str:
    """Resolve ``name`` or raise a message telling the user how to fix it."""
    path = resolve(name)
    if path:
        return path
    raise FileNotFoundError(
        f"GTKWave helper '{name}' not found. Build the helpers "
        f"(`meson setup build && ninja -C build` in the gtkwave source tree) "
        f"and set GTKWAVE_HOME to that tree, or put '{name}' on PATH."
    )

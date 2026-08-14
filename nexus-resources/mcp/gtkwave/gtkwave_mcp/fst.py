"""FST access via GTKWave's non-GUI helper binaries.

FST is a binary random-access format, so unlike VCD we cannot parse it in pure
Python. We shell out to ``fst2vcd`` (full conversion, streamed to a temp file so
the VCD reader can process it lazily) and ``fstminer -n`` (fast signal-name
listing without a full conversion). No GUI is involved.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import config
from .process import HelperError, run_checked


def signal_names(fst_path: str | Path) -> list[str]:
    """List fully-qualified signal names using ``fstminer -n`` (names only).

    ``fstminer -n`` emits a GTKWave-savefile-formatted list; we keep the plain
    name lines and drop directive lines (``@flags``, ``[...]``, ``*``, ``-``).
    """
    exe = config.require("fstminer")
    out = run_checked([exe, "-n", "-d", str(fst_path)])
    names: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line[0] in "@[*-":
            continue
        names.append(line)
    return names


@contextmanager
def converted_vcd(fst_path: str | Path) -> Iterator[Path]:
    """Yield a path to a temporary VCD produced from ``fst_path`` by ``fst2vcd``.

    Streams the helper's stdout straight to disk (no full in-memory copy) and
    removes the temp file on exit.
    """
    exe = config.require("fst2vcd")
    fd, tmp = tempfile.mkstemp(suffix=".vcd", prefix="gtkwave_mcp_")
    try:
        with os.fdopen(fd, "wb") as out:
            proc = subprocess.run(
                [exe, str(fst_path)], stdout=out, stderr=subprocess.PIPE
            )
        if proc.returncode != 0:
            detail = (proc.stderr or b"").decode("utf-8", "replace").strip()
            raise HelperError(f"fst2vcd failed: {detail or proc.returncode}")
        yield Path(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def mine(
    fst_path: str | Path,
    match: str | None = None,
    hex_value: str | None = None,
    names_only: bool = False,
) -> str:
    """Run ``fstminer`` to data-mine an FST file.

    ``match`` → ``-m`` (bitwise binary/real/string), ``hex_value`` → ``-x``
    (hex auto-converted to binary), ``names_only`` → ``-n``. Returns the raw
    GTKWave-savefile-formatted output.
    """
    exe = config.require("fstminer")
    argv = [exe, "-d", str(fst_path)]
    if names_only:
        argv.append("-n")
    if match is not None:
        argv += ["-m", match]
    if hex_value is not None:
        argv += ["-x", hex_value]
    return run_checked(argv)

"""Format conversion between waveform dump types via non-GUI helpers.

Dispatches on the (input, output) extension pair to the correct GTKWave helper
binary. Only conversions the bundled helpers support are offered.
"""

from __future__ import annotations

from pathlib import Path

from . import config
from .process import run

# (input_ext, output_ext) -> helper binary name
_MATRIX = {
    ("vcd", "fst"): "vcd2fst",
    ("fst", "vcd"): "fst2vcd",
    ("vcd", "lxt2"): "vcd2lxt2",
    ("lxt2", "vcd"): "lxt2vcd",
    ("vcd", "vzt"): "vcd2vzt",
    ("vzt", "vcd"): "vzt2vcd",
    ("evcd", "vcd"): "evcd2vcd",
}


def _ext(path: str | Path) -> str:
    return Path(path).suffix.lstrip(".").lower()


def supported() -> list[str]:
    return [f"{i} -> {o}" for (i, o) in _MATRIX]


def convert(input_path: str | Path, output_path: str | Path | None = None) -> dict:
    """Convert ``input_path`` to ``output_path``.

    If ``output_path`` is omitted, the output extension defaults to ``fst`` for
    a VCD input and ``vcd`` otherwise, alongside the input file.
    """
    in_ext = _ext(input_path)
    if output_path is None:
        out_ext = "fst" if in_ext == "vcd" else "vcd"
        output_path = Path(input_path).with_suffix(f".{out_ext}")
    out_ext = _ext(output_path)

    helper = _MATRIX.get((in_ext, out_ext))
    if helper is None:
        raise ValueError(
            f"unsupported conversion {in_ext} -> {out_ext}. "
            f"Supported: {', '.join(supported())}"
        )

    exe = config.require(helper)
    # fst2vcd writes VCD to stdout; the converters take two positional args.
    if helper == "fst2vcd":
        res = run([exe, str(input_path)])
        if res.ok:
            Path(output_path).write_text(res.stdout)
    else:
        res = run([exe, str(input_path), str(output_path)])

    return {
        "ok": res.ok,
        "helper": helper,
        "input": str(input_path),
        "output": str(output_path) if res.ok else None,
        "stderr": res.stderr.strip(),
    }

"""GTKWaveMCP — FastMCP server exposing headless waveform-inspection tools.

No tool launches a GUI. VCD files are parsed in-process; FST files go through
GTKWave's non-GUI helper binaries (`fst2vcd`, `fstminer`).
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from . import convert as _convert
from . import fst as _fst
from . import resources, waveform
from .process import HelperError

mcp = FastMCP(
    name="gtkwave-mcp",
    instructions=(
        "Headless inspection of VCD/FST waveform dumps for hardware debugging. "
        "Read signal hierarchy, list signals, and extract values over the whole "
        "dump or a specific time/cycle range. No GUI is ever opened."
    ),
)


def _guard(fn, *args, **kwargs):
    """Convert helper/IO errors into a structured error payload."""
    try:
        return fn(*args, **kwargs)
    except (HelperError, FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}


# The FST-format tools (convert_waveform, mine_values) depend on GTKWave's non-GUI helper
# binaries (fst2vcd / vcd2fst / fstminer), and convert_waveform writes a file to disk.
# They are HIDDEN from the exposed tool list by default — the implementations remain
# defined below and are re-enabled by setting GTKWAVE_ENABLE_FST_TOOLS=1 in the server's
# environment. The VCD-only inspection tools are always exposed (VCD is parsed in-process;
# no binaries needed).
_EXPOSE_FST_TOOLS = os.environ.get("GTKWAVE_ENABLE_FST_TOOLS", "").strip().lower() in (
    "1", "true", "yes", "on",
)


@mcp.tool
def waveform_info(path: str) -> dict:
    """Summarize a waveform file: format, timescale, signal/scope counts, and
    the simulation start/end time. Accepts .vcd, .vcd.gz, or .fst."""
    return _guard(waveform.info, path)


@mcp.tool
def list_signals(
    path: str,
    scope: str | None = None,
    pattern: str | None = None,
    limit: int = 500,
) -> dict:
    """List fully-qualified signal names. Optionally restrict to a `scope`
    prefix (e.g. "top.cpu") and/or a glob `pattern` (e.g. "top.*clk*")."""
    return _guard(waveform.list_signals, path, scope, pattern, limit)


@mcp.tool
def list_scopes(path: str) -> dict:
    """Return the module/scope hierarchy of the waveform as a nested tree."""
    return _guard(waveform.list_scopes, path)


@mcp.tool
def get_signal_values(
    path: str,
    signals: list[str],
    start: int | None = None,
    end: int | None = None,
    clock: str | None = None,
    cycle_start: int | None = None,
    cycle_end: int | None = None,
    limit: int = 1000,
) -> dict:
    """Extract value changes for the named `signals`.

    Windowing (all optional; whole file if omitted):
      - `start`/`end`: raw simulation-time bounds (in the file's timescale).
      - `clock` + `cycle_start`/`cycle_end`: sample the rising edges of `clock`
        to bound the query to an inclusive cycle range instead of raw time.

    Returns, per signal, a list of {time, value}. The value entering the window
    is included so the state is well-defined at `start`."""
    return _guard(
        waveform.get_values, path, signals, start, end,
        clock, cycle_start, cycle_end, limit,
    )


def convert_waveform(input_path: str, output_path: str | None = None) -> dict:
    """Convert between waveform formats (e.g. VCD<->FST) using non-GUI helpers.
    Output extension defaults to .fst for a VCD input, .vcd otherwise."""
    return _guard(_convert.convert, input_path, output_path)


def mine_values(
    path: str,
    match: str | None = None,
    hex_value: str | None = None,
    names_only: bool = False,
) -> dict:
    """Data-mine an FST file with `fstminer`: find signals carrying a bitwise
    (`match`) or hex (`hex_value`) value, or just list names (`names_only`)."""
    def _run():
        return {"output": _fst.mine(path, match, hex_value, names_only)}
    return _guard(_run)


# Hidden by default; expose only when a maintainer opts in (GTKWAVE_ENABLE_FST_TOOLS=1).
if _EXPOSE_FST_TOOLS:
    mcp.tool(convert_waveform)
    mcp.tool(mine_values)


@mcp.resource("gtkwave://formats")
def formats_doc() -> str:
    """Reference: supported waveform formats."""
    return resources.FORMATS


@mcp.resource("gtkwave://helper-tools")
def helpers_doc() -> str:
    """Reference: the non-GUI helper binaries this server uses."""
    return resources.HELPER_TOOLS


def main() -> None:
    mcp.run()  # stdio transport (standard for local MCP clients)


if __name__ == "__main__":
    main()

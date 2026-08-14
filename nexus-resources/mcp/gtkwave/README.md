# gtkwave — MCP server

Headless inspection of **VCD / .vcd.gz / FST** waveform dumps for hardware debugging.
No GUI is ever opened: VCD is parsed in-process; FST goes through GTKWave's non-GUI
helper binaries (`fst2vcd`, `fstminer`, …).

## What it does
Read the signal hierarchy, list/search signals, and extract signal values over the whole
run or a specific time / clock-cycle window — plus convert between waveform formats and
data-mine FST files. Implemented as the `gtkwave_mcp` package (beside `main.py`).

## Transport
stdio (FastMCP default). Launched by nexus as `uv --directory <this dir> run main.py`.
The runtime dependency (`fastmcp`) installs into the per-user venv via
`UV_PROJECT_ENVIRONMENT`; the committed `uv.lock` is read-only.

## Tools
| tool | access | purpose |
|---|---|---|
| `waveform_info` | read-only | format, timescale, signal/scope counts, start/end time (call first) |
| `list_scopes` | read-only | module/scope hierarchy as a nested tree |
| `list_signals` | read-only | fully-qualified signal names (optional `scope` prefix / glob `pattern`) |
| `get_signal_values` | read-only | `{time, value}` series over the whole file, a time window, or a clock-cycle window |
| `mine_values` | read-only | FST-only: find signals carrying a bitwise/hex value (`fstminer`) — *hidden by default* |
| `convert_waveform` | mutating | convert VCD⇄FST (etc.) — **writes a new file to disk** — *hidden by default* |

`mine_values` and `convert_waveform` depend on GTKWave helper binaries (and
`convert_waveform` writes files), so they are **hidden from the tool list by default**.
Their implementations remain in the package; launch the server with
`GTKWAVE_ENABLE_FST_TOOLS=1` to expose them. The four VCD-only inspection tools are always
available.

Access is declared authoritatively in `pyproject.toml [tool.nexus.tools]`; nexus reads
that to pre-approve only the read-only tools in `~/.claude/settings.json`. Every tool
returns `{"error": ...}` instead of raising.

## Environment variables
| var | kind | required | meaning |
|---|---|---|---|
| `GTKWAVE_HOME` | path | no | where GTKWave's helper binaries live (`$GTKWAVE_HOME/build/src/helpers`). Only needed for FST/convert; VCD needs nothing. Falls back to `PATH`, then an in-tree default. |
| `GTKWAVE_ENABLE_FST_TOOLS` | flag | no | set to `1` to expose the hidden FST tools (`mine_values`, `convert_waveform`). Unset by default → those two tools are hidden. |

No credentials. The server starts and answers `initialize` / `tools/list` anywhere
(nexus Verify passes with no env at all); FST tools return a clear missing-helper error
if the binaries aren't built/on `PATH`.

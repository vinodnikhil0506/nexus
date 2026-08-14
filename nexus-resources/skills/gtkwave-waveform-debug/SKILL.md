---
name: gtkwave-waveform-debug
description: Use this skill when you need to inspect or debug a digital hardware waveform dump (VCD, .vcd.gz, FST) headlessly — read the signal hierarchy, list/search signals, extract signal values over the whole run or a specific time/clock-cycle range, compare expected vs actual behavior in a simulation dump, or convert between waveform formats. Trigger it whenever the user asks to look at a waveform, trace a signal, or check a value at a time or cycle. No GUI is ever opened.
---

# GTKWave waveform debugging

Inspect VCD/FST simulation dumps through the **gtkwave** MCP server. All operations are
headless (no `gtkwave` window). VCD is parsed in-process; FST is read through GTKWave's
non-GUI helper binaries (`fst2vcd`, `fstminer`).

## When to use

- "What signals / modules are in this dump?"
- "What is `<signal>` doing between time X and Y" or "during cycles N..M?"
- "Trace the reset / a bus / an FSM state through the run."
- "Why is `<output>` wrong at this point?" (compare expected vs observed values)
- Convert VCD ⇄ FST, or data-mine an FST for a specific value.

## Tools (all take a file `path`)

| Tool | Use it to |
|------|-----------|
| `waveform_info(path)` | Get format, timescale, signal/scope counts, start/end time. **Call this first.** |
| `list_scopes(path)` | See the module hierarchy as a tree. |
| `list_signals(path, scope=None, pattern=None, limit=500)` | Find signal names. Filter by `scope` prefix (`"top.cpu"`) and/or glob `pattern` (`"*alu*"`, `"top.*clk*"`). |
| `get_signal_values(path, signals, start=None, end=None, clock=None, cycle_start=None, cycle_end=None, limit=1000)` | Extract `{time, value}` series for one or more signals. |
| `convert_waveform(input_path, output_path=None)` | VCD⇄FST (and LXT2/VZT/EVCD). **Writes a file** — confirm before overwriting. *Hidden unless the server sets `GTKWAVE_ENABLE_FST_TOOLS=1`.* |
| `mine_values(path, match=None, hex_value=None, names_only=False)` | FST-only: find signals carrying a bitwise (`match`) or hex (`hex_value`) value. *Hidden unless the server sets `GTKWAVE_ENABLE_FST_TOOLS=1`.* |

> `convert_waveform` and `mine_values` are **hidden by default** (they depend on GTKWave
> helper binaries and `convert_waveform` writes to disk). If they don't appear in the tool
> list, they're disabled — use the VCD-only tools above.

## Standard workflow

1. **Orient** — `waveform_info(path)` for the timescale, time bounds, and size.
2. **Locate** — `list_scopes` for hierarchy, then `list_signals` with a `pattern`
   or `scope` to pin down the exact fully-qualified names you need. Do this before
   guessing signal names — matching is forgiving but the qualified name is safest.
3. **Extract** — `get_signal_values` with the resolved names and a window (below).
4. **Interpret** — reason over the returned `{time, value}` series against expected
   behavior; report the specific time/cycle and value where it diverges.

Before `convert_waveform` (the one mutating tool — it writes a new file), state the
output path and confirm you won't clobber something wanted.

## Windowing (in `get_signal_values`)

- **Whole run:** omit all window args.
- **Time window:** `start=`/`end=` in the file's timescale units (see `waveform_info`).
- **Cycle window:** pass `clock="<clock signal>"` plus `cycle_start`/`cycle_end`
  (inclusive). The server samples the clock's rising edges to map cycles → time.
  Prefer this when the user speaks in cycles.

The value *entering* the window is always included, so a signal's state is
well-defined at `start` even if it last changed earlier. `limit` caps returned
points (`truncated: true` if hit — narrow the window or raise the limit).

## Reading the results

- Values: scalar `0/1/x/z`; vectors as bit strings (`b1010` → returned as `1010`);
  reals as decimals. Widths/ranges come from the names (`bus[31:0]`).
- `unresolved` in the response lists requested names that didn't match — re-check
  with `list_signals`.
- Every tool returns `{"error": "..."}` instead of raising; if an FST tool errors
  with a missing-helper message, the GTKWave helper binaries aren't built/on PATH
  (VCD still works with no binaries at all).

## Tips

- Signal names are **fully qualified and dotted** (`stimulus.test_processor.alu.result[31:0]`).
- To trace an FSM/bus over cycles: resolve the clock name once, then use it as the
  `clock=` for cycle-windowed queries.
- Large FST reads convert to a temp VCD internally — keep windows tight.
- `mine_values(names_only=True)` gives FST's alias-collapsed net view (smaller than
  `list_signals`); use `list_signals` for the canonical, format-consistent list.

## Setup / config

- The server is the nexus-registered **gtkwave** MCP (stdio transport); nexus installs and
  launches it — no manual venv or client wiring is needed.
- FST support needs GTKWave's helper binaries, resolved from
  `$GTKWAVE_HOME/build/src/helpers`, then `PATH`, then an in-tree fallback. Set
  `GTKWAVE_HOME` if they live elsewhere. VCD needs nothing built.

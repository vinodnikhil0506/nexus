"""Static reference documents exposed as MCP resources."""

FORMATS = """# Waveform formats (GTKWave 4.0)

- **VCD** (.vcd, .vcd.gz) — IEEE-1364 text dump. Read natively, no external
  tools required. Slowest / largest but universally supported.
- **FST** (.fst) — GTKWave's fast random-access binary format; the recommended
  default. Read here via the `fst2vcd` / `fstminer` helper binaries.
- **LXT2 / VZT** — legacy compressed formats. Convertible via helpers, but
  **planned for removal in GTKWave 4** — prefer FST.
- **EVCD** — extended VCD; convert to plain VCD with `evcd2vcd`.

This server is headless: it never launches the `gtkwave` GUI.
"""

HELPER_TOOLS = """# GTKWave non-GUI helper binaries

- `vcd2fst <in.vcd> <out.fst>`  — VCD to FST
- `fst2vcd <in.fst>`            — FST to VCD (on stdout)
- `fstminer -n -d <in.fst>`     — list all signal names (fast, no conversion)
- `fstminer -m <value> -d <f>`  — bitwise value data-mining
- `fstminer -x <hex> -d <f>`    — hex value data-mining
- `vcd2lxt2` / `lxt2vcd`        — VCD <-> LXT2
- `vcd2vzt`  / `vzt2vcd`        — VCD <-> VZT
- `evcd2vcd <in.evcd>`          — extended VCD to VCD

Resolved from `$GTKWAVE_HOME/build/src/helpers`, then PATH, then the in-tree
`~/Workspace/Tools/gtkwave/build/src/helpers` fallback.
"""

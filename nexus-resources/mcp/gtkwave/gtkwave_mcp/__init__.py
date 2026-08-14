"""GTKWaveMCP — a headless MCP server for inspecting digital waveform files.

Reads hierarchy, signals, and values from VCD / FST dumps for hardware
debugging. No GUI is ever launched: VCD is parsed in-process, FST is handled
via GTKWave's non-GUI helper binaries (``fst2vcd``, ``fstminer``).
"""

__version__ = "0.1.0"

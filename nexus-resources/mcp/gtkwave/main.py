#!/usr/bin/env python3
"""gtkwave — nexus MCP entry point.

Thin stdio launcher for the ``gtkwave_mcp`` package (a FastMCP server for headless
VCD/FST waveform inspection). The package lives alongside this file, so
``uv run main.py`` imports it via the script directory on ``sys.path``.
"""
from gtkwave_mcp.server import main

if __name__ == "__main__":
    main()

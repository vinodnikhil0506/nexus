#!/usr/bin/env python3
"""verisight — Nexus MCP wrapper around the VeriSight RTL/UVM debugging framework.

VeriSight (shipped read-only under ip/VeriSight/) is an argparse **CLI**, not an MCP
server, so nexus cannot launch it directly over stdio. This thin FastMCP stdio wrapper
exposes it as MCP tools WITHOUT modifying VeriSight: it locates the VeriSight checkout
plus a Python that has VeriSight's dependencies installed, invokes `main.py` as a
subprocess (read-only w.r.t. the checkout), and returns the structured report VeriSight
writes to its output directory.

Transport: stdio (FastMCP default). Configuration comes ONLY from the environment:

  VERISIGHT_HOME    (path)     the VeriSight checkout; default: ${NEXUS_ROOT}/ip/VeriSight
  VERISIGHT_PYTHON  (path,opt) a Python that has VeriSight's deps installed;
                               default: $VERISIGHT_HOME/.venv/bin/python, else 'python3'
  ANTHROPIC_API_KEY  (credential) passed through to VeriSight's LLM (provider=anthropic;
                     Gemini is not used by this nexus wiring). Reused from the engineer's
                     shell env if already set, else collected by nexus at init.

Credentials/tools are validated lazily so the server still answers initialize/tools-list
(nexus Verify passes) with nothing configured.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

mcp = FastMCP(
    name="verisight",
    instructions=(
        "Wrapper for VeriSight, an AI multi-agent RTL/UVM failure debugger. Given a "
        "simulation log (plus optional spec/RTL/testbench), it classifies the failure "
        "and reports a root cause. `analyze_failure` runs the LLM pipeline (outward, "
        "costs an API call and writes a report dir); `list_examples` is read-only."
    ),
)


def _home() -> Path:
    h = os.environ.get("VERISIGHT_HOME")
    # default: the IP under the workspace's ip/ tree (mcp/verisight -> workspace -> ip/VeriSight)
    return Path(h) if h else (Path(__file__).resolve().parent.parent.parent / "ip" / "VeriSight")


def _python() -> str:
    p = os.environ.get("VERISIGHT_PYTHON")
    if p:
        return p
    venv = _home() / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else "python3"


@mcp.tool
def list_examples() -> dict:
    """List the example / project input sets bundled with VeriSight (READ-ONLY).

    Use this to discover ready-made spec/RTL/testbench/log paths to feed to
    `analyze_failure`. Returns {verisight_home, examples: {subdir: [files]}, projects: [names]}.
    """
    home = _home()
    if not (home / "main.py").is_file():
        return {"error": f"VeriSight not found at {home} (set VERISIGHT_HOME)"}
    out: dict = {"verisight_home": str(home), "examples": {}, "projects": []}
    ex = home / "examples"
    if ex.is_dir():
        for sub in sorted(p for p in ex.iterdir() if p.is_dir()):
            out["examples"][sub.name] = sorted(
                str(p.relative_to(home)) for p in sub.glob("*") if p.is_file()
            )
    pr = home / "projects"
    if pr.is_dir():
        out["projects"] = sorted(p.name for p in pr.iterdir() if p.is_dir())
    return out


@mcp.tool
def analyze_failure(
    log: str,
    spec: Optional[str] = None,
    rtl: Optional[str] = None,
    tb: Optional[str] = None,
    coverage: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    no_rag: bool = False,
    output_dir: Optional[str] = None,
) -> dict:
    """Run the VeriSight pipeline on a failing run (MUTATING / outward).

    This calls an LLM provider (Gemini or Anthropic — an outward, billable action) and
    writes a report directory, so it stays confirm-on-use in nexus.

    Arguments:
      log:        path to the simulation log (required).
      spec/rtl/tb/coverage: optional input paths (files or dirs) for richer analysis.
      provider:   'gemini' | 'anthropic' (default: VeriSight's own default / env).
      model:      LLM model name override.
      no_rag:     disable the ChromaDB RAG knowledge base.
      output_dir: where VeriSight writes reports (default: a fresh temp dir).
    Returns: {success, output_dir, error_report (parsed error.json), reports: {name: path}}
      or {success: false, error}.
    """
    home = _home()
    if not (home / "main.py").is_file():
        return {"success": False, "error": f"VeriSight not found at {home} (set VERISIGHT_HOME)"}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"success": False,
                "error": "ANTHROPIC_API_KEY is not set — export it (nexus injects it "
                         "per-launch, or reuses it from your shell) before running VeriSight"}
    out = output_dir or tempfile.mkdtemp(prefix="verisight-")
    cmd = [_python(), "main.py", "--log", log, "--output", out]
    for flag, val in (("--spec", spec), ("--rtl", rtl), ("--tb", tb),
                      ("--coverage", coverage), ("--provider", provider), ("--model", model)):
        if val:
            cmd += [flag, val]
    if no_rag:
        cmd.append("--no-rag")
    try:
        proc = subprocess.run(cmd, cwd=str(home), capture_output=True, text=True, timeout=1200)
    except FileNotFoundError:
        return {"success": False,
                "error": f"python '{_python()}' not found — set VERISIGHT_PYTHON to a "
                         "Python that has VeriSight's dependencies installed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "VeriSight timed out (>20 min)"}
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-6:])
        return {"success": False, "error": f"VeriSight failed (exit {proc.returncode}): {tail}"}
    result: dict = {"success": True, "output_dir": out, "reports": {}}
    errj = Path(out) / "error.json"
    if errj.is_file():
        try:
            result["error_report"] = json.loads(errj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    for name in ("error.json", "summary.json", "report.md", "report.html", "summary.txt"):
        p = Path(out) / name
        if p.is_file():
            result["reports"][name] = str(p)
    return result


if __name__ == "__main__":
    mcp.run()

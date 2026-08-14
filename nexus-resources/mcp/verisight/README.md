# verisight — MCP server (wrapper for the VeriSight IP)

A thin FastMCP stdio **wrapper** that exposes the **VeriSight** RTL/UVM debugging
framework (shipped read-only under `ip/VeriSight/`) as nexus MCP tools. VeriSight is an
argparse **CLI**, not an MCP server, so nexus cannot launch it directly — this wrapper
invokes VeriSight's `main.py` as a subprocess and returns its structured report. The
VeriSight checkout is never modified.

## What it does
- `list_examples` (read-only) — enumerate the example / project input sets bundled with
  VeriSight, so you can point `analyze_failure` at ready-made spec/RTL/TB/log paths.
- `analyze_failure` (mutating) — run VeriSight's multi-agent pipeline on a failing run
  (needs a sim `log`; optional `spec`/`rtl`/`tb`/`coverage`). VeriSight classifies the
  failure and writes `error.json`/`report.md`/`report.html`/`summary.txt`; this tool
  returns the parsed `error.json` and the report paths. It calls an LLM provider
  (Gemini/Anthropic) and writes a report dir → outward, confirm-on-use.

## Transport
stdio (FastMCP default). Launched by nexus as `uv --directory <this dir> run main.py`.
Only `fastmcp` installs into the wrapper's per-user venv (from the committed `uv.lock`).

## Environment variables
| var | kind | required | meaning |
|---|---|---|---|
| `VERISIGHT_HOME` | path | no (injected per-user by nexus) | the VeriSight checkout |
| `VERISIGHT_PYTHON` | path | no | a Python that has VeriSight's deps installed; default `$VERISIGHT_HOME/.venv/bin/python`, else `python3` |
| `VERISIGHT_PROVIDER` | path | no (nexus sets `anthropic`) | pins the LLM provider to Anthropic |
| `ANTHROPIC_API_KEY` | credential | required at run time | Anthropic key. nexus reuses it from your shell env if already set (bash/csh), else collects it at init. Gemini is not used by this wiring. |

## Runtime prerequisites (installed once, shared by all engineers)
VeriSight has heavy deps (`chromadb`, `google-generativeai`, `anthropic`, …) and **no
committed `uv.lock`**, so nexus doesn't auto-provision it during a per-engineer init.
Instead it is a **one-time shared install** into `.nexus-shared/verisight/` (the path
`nexus.toml` points `VERISIGHT_PYTHON` at), done once by a maintainer:

```sh
UV=implement/toolchain/bin/uv
export UV_PYTHON_INSTALL_DIR=$PWD/implement/toolchain/python
export UV_CACHE_DIR=$PWD/.nexus-shared/uv_cache
$UV venv .nexus-shared/verisight
$UV pip install --python .nexus-shared/verisight ./ip/VeriSight   # non-editable: no writes into the IP
```

That venv is then shared read-only by every engineer (execution is concurrency-safe).
Each engineer's runs stay isolated via per-user `VERISIGHT_CHROMA_PATH`
(`${HOME}/.nexus/verisight_chroma`) and a per-run `--output` dir, so VeriSight never
writes into `ip/VeriSight/` and concurrent runs don't collide. Also provide a
`ANTHROPIC_API_KEY`. Until the venv + key exist, `analyze_failure`
returns a clear one-line error; `list_examples` and the MCP handshake work regardless.

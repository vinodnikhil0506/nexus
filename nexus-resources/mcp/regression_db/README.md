# regression_db — MCP server

An authenticated client for the **Hardware Regression Database** — the REST
dashboard backend under `nexus-resources/maintainer/regression_db/webpage`. It lets an
agent see the regressions assigned to it for debugging and record debug metadata back to
the central DB.

## What it does
- Reads the regressions currently **assigned** to a user (`debug_status == "Assigned"` and
  `debug_owner == you`), grouped by block.
- Updates a regression's **debug metadata** (`debug_status`, `debug_owner`,
  `issue_tracker_id`). Test-result data itself is read-only through this server — the
  update re-sends every other field unchanged so the record is preserved.

All I/O goes through the Regression Database REST API; no local files are touched.

## Transport
stdio (FastMCP default). Launched by nexus as `uv --directory <this dir> run main.py`.
The runtime dependency (`fastmcp`) installs into the per-user venv via
`UV_PROJECT_ENVIRONMENT`; the committed `uv.lock` is read-only.

## Tools
| tool | access | purpose |
|---|---|---|
| `get_my_assigned_regressions` | read-only | list regressions assigned to you (optional `username`, `block` filters) |
| `update_debug_signature` | mutating | set `debug_status`/`debug_owner`/`issue_tracker_id` on a regression (outward; confirm-on-use) |

Access is declared authoritatively in `pyproject.toml [tool.nexus.tools]`; nexus reads
that to pre-approve only the read-only tool in `~/.claude/settings.json`.

## Environment variables
| var | kind | required | meaning |
|---|---|---|---|
| `REGRESSION_DB_API_URL` | path | no (default `http://localhost:8000/api`) | base REST URL of the Regression Database backend |
| `REGRESSION_DB_API_KEY` | credential | required by every tool (validated lazily) | sent as the `X-API-Key` header; stays `${VAR}`-literal in config, injected per-launch |

The credential is validated **lazily**, inside each tool, so the server still starts and
answers `initialize` / `tools/list` (nexus Verify passes) with no secret present. When a
tool runs without `REGRESSION_DB_API_KEY`, or the backend is unreachable, it returns a single-line
`{"error": ...}` payload rather than crashing.

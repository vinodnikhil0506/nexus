# issue_tracker — MCP server

An authenticated client for the **Hardware Issue Tracker** — the REST dashboard backend
under `nexus-resources/maintainer/issue-tracker/webpage`. It lets an agent read, create,
update, comment on, and delete hardware project issues.

## What it does
- Reads/filters issues by `status` and/or `component`.
- Creates new tickets, updates fields, appends debug comments, and deletes issues.
- All mutations go through the real REST verbs (POST/PUT/DELETE) so they actually persist
  to the backend's `issues.json`. (This fixes an older bug where mutations silently no-op'd.)

All I/O goes through the Issue Tracker REST API; no local files are touched.

## Transport
stdio (FastMCP default). Launched by nexus as `uv --directory <this dir> run main.py`.
The runtime dependency (`fastmcp`) installs into the per-user venv via
`UV_PROJECT_ENVIRONMENT`; the committed `uv.lock` is read-only.

## Tools
| tool | access | purpose |
|---|---|---|
| `get_issues` | read-only | list/filter issues by `status` / `component` |
| `create_issue` | mutating | create a ticket (`title`, `component`, `severity` required) |
| `update_issue` | mutating | change `status`/`description`/`firmware_version`/`severity` |
| `add_debug_comment` | mutating | append a timestamped debug comment |
| `delete_issue` | mutating | delete an issue permanently (destructive) |

Access is declared authoritatively in `pyproject.toml [tool.nexus.tools]`; nexus reads
that to pre-approve only the read-only tool in `~/.claude/settings.json`. Every mutating
tool stays confirm-on-use.

## Environment variables
| var | kind | required | meaning |
|---|---|---|---|
| `TRACKER_API_URL` | path | no (default `http://localhost:8001/api`) | base REST URL of the tracker backend |
| `TRACKER_API_KEY` | credential | required by every tool (validated lazily) | sent as the `X-API-Key` header; stays `${VAR}`-literal in config, injected per-launch |

The credential is validated **lazily**, inside each tool, so the server still starts and
answers `initialize` / `tools/list` (nexus Verify passes) with no secret present. When a
tool runs without `TRACKER_API_KEY`, or the backend is unreachable, it returns a
single-line `{"error": ...}` / `{"success": false, ...}` payload rather than crashing.

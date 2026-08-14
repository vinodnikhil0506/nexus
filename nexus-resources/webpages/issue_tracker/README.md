# issue_tracker — Issue Tracker dashboard + REST backend

The Hardware Issue Tracker web dashboard and its REST API. This is the **shared
knowledge base** that the `issue_tracker` MCP (under `mcp/issue_tracker/`) reads and
updates on behalf of the agent — the "share the KB to agentic tools" core of nexus.

## Run
```sh
uv --directory webpages/issue_tracker run server.py     # listens on http://localhost:8001
```
(uv installs FastAPI/uvicorn/pydantic from the committed `uv.lock` into a venv.)
Open `index.html` in a browser for the Kanban dashboard.

## Auth / API key (for the MCP)
Login defaults are `admin` / `admin`. Easiest — use the helper (stdlib-only, no venv):
```sh
python webpages/gen_api_key.py issue_tracker     # prints the key + TRACKER_API_KEY=… line
```
Or by hand:
```sh
SID=$(curl -s -XPOST localhost:8001/api/login -H 'Content-Type: application/json' \
      -d '{"username":"admin","password":"admin"}' | python -c 'import sys,json;print(json.load(sys.stdin)["session_id"])')
curl -s -XPOST localhost:8001/api/generate-key -H "Authorization: Bearer $SID"
```
Put the returned `tracker_…` key in the engineer's nexus credential store as
`TRACKER_API_KEY` (nexus injects it into the MCP per-launch; never written raw — R7). The
MCP's `TRACKER_API_URL` (nexus.toml) defaults to `http://localhost:8001/api`.

## Data (the shared KB, versioned with the workspace)
- `issues.json` — issue records; `.issue_counter` — next-id counter (both beside `server.py`).
- `users.json` / `sessions.json` — auth state, created on first run (not committed).

## Endpoints
`GET/POST /api/issues`, `GET/PUT/DELETE /api/issues/{id}`, `POST /api/login`,
`POST /api/generate-key`, `GET /api/health`.

# regression_db — Regression Database dashboard + REST backend

The Hardware Regression Database web dashboard and its REST API. This is the **shared
knowledge base** that the `regression_db` MCP (under `mcp/regression_db/`) reads and
updates on behalf of the agent — the "share the KB to agentic tools" core of nexus.

## Run
```sh
uv --directory webpages/regression_db run server.py     # listens on http://localhost:8000
```
(uv installs FastAPI/uvicorn/pydantic from the committed `uv.lock` into a venv.)

## Auth / API key (for the MCP)
Login defaults are `admin` / `admin`. Easiest — use the helper (stdlib-only, no venv):
```sh
python webpages/gen_api_key.py regression_db     # prints the key + REGRESSION_DB_API_KEY=… line
```
Or by hand:
```sh
SID=$(curl -s -XPOST localhost:8000/api/login -H 'Content-Type: application/json' \
      -d '{"username":"admin","password":"admin"}' | python -c 'import sys,json;print(json.load(sys.stdin)["session_id"])')
curl -s -XPOST localhost:8000/api/generate-key -H "Authorization: Bearer $SID"
```
Put the returned `regression_db_…` key in the engineer's nexus credential store as `REGRESSION_DB_API_KEY`
(nexus injects it into the MCP per-launch; it is never written raw — R7). The MCP's
`REGRESSION_DB_API_URL` (nexus.toml) defaults to `http://localhost:8000/api`.

## Data (the shared KB, versioned with the workspace)
- `regression_db.json` — regression records (status, error signature, debug metadata).
- `projects.json` — hardware blocks.
- `users.json` / `sessions.json` — auth state, created on first run (not committed).

## Endpoints
`GET/POST /api/regressions`, `GET/PUT /api/regressions/{id}`, `GET/POST /api/projects`,
`POST /api/login`, `POST /api/generate-key`, `GET /api/health`, `GET /` (dashboard).

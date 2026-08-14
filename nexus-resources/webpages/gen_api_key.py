#!/usr/bin/env python3
"""Generate an API key for a nexus webpage backend (regression_db or issue_tracker).

Logs in with the dashboard's username/password, asks the backend to mint an API
key, and prints it together with the exact credential env-var name the matching
MCP expects. Stdlib-only — run it directly with the toolchain python; no venv needed.

Usage:
    python gen_api_key.py regression_db          # -> REGRESSION_DB_API_KEY, :8000
    python gen_api_key.py issue_tracker          # -> TRACKER_API_KEY,        :8001
    python gen_api_key.py regression_db --url http://host:8000/api
    python gen_api_key.py issue_tracker --user admin --password admin

The backend must be running (see webpages/<backend>/README.md). The key is printed
to stdout only — store it in your nexus credential store; never commit it (R7).
"""
import json
import sys
import urllib.error
import urllib.request

# backend name -> (default REST base URL, the MCP credential env-var name)
BACKENDS = {
    "regression_db": ("http://localhost:8000/api", "REGRESSION_DB_API_KEY"),
    "issue_tracker": ("http://localhost:8001/api", "TRACKER_API_KEY"),
}


def die(msg):
    print(f"gen_api_key: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_args(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    backend = argv[0]
    if backend not in BACKENDS:
        die(f"unknown backend {backend!r}; choose one of: {', '.join(BACKENDS)}")
    url, env_name = BACKENDS[backend]
    user, password = "admin", "admin"
    rest = argv[1:]
    i = 0
    while i < len(rest):
        flag = rest[i]
        if i + 1 >= len(rest):
            die(f"missing value for {flag}")
        val = rest[i + 1]
        if flag == "--url":
            url = val
        elif flag == "--user":
            user = val
        elif flag == "--password":
            password = val
        else:
            die(f"unknown option {flag}")
        i += 2
    return backend, url.rstrip("/"), env_name, user, password


def post(url, body=None, headers=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, headers=headers or {"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        die(f"{url} -> HTTP {exc.code} {exc.reason}")
    except urllib.error.URLError as exc:
        die(f"cannot reach {url}: {exc.reason} (is the backend server running?)")


def main():
    backend, url, env_name, user, password = parse_args(sys.argv[1:])
    session = post(f"{url}/login", {"username": user, "password": password}).get("session_id")
    if not session:
        die("login did not return a session_id (check username/password)")
    api_key = post(f"{url}/generate-key", None, {"Authorization": f"Bearer {session}"}).get("api_key")
    if not api_key:
        die("generate-key did not return an api_key")
    print(api_key)
    print(f"\n# {backend} @ {url}")
    print(f"# store this in your nexus credential store as the MCP credential {env_name}:")
    print(f'{env_name}={api_key}')


if __name__ == "__main__":
    main()

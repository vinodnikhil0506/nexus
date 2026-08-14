#!/usr/bin/env python3
"""regression_db — Hardware Regression Database MCP server.

Ported to the current FastMCP library (``from fastmcp import FastMCP``) from an
older low-level ``mcp.server.Server`` implementation whose run loop no longer
starts. Behaviour is preserved: this server is a thin, authenticated client of
the Regression Database REST API (the ``regression_db/webpage`` dashboard backend).

Transport: stdio (FastMCP default). Configuration comes ONLY from the
environment — nothing is hardcoded:

  REGRESSION_DB_API_URL   (path,       optional) base REST URL; default http://localhost:8000/api
  REGRESSION_DB_API_KEY   (credential, required by every tool) sent as the X-API-Key header

The credential is validated LAZILY, inside each tool, so the server still starts
and answers ``initialize`` / ``tools/list`` (i.e. nexus Verify passes) without a
secret present. Read-only vs mutating is declared in pyproject.toml
[tool.nexus.tools]; a mutating tool represents an outward action and stays
confirm-on-use in nexus.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from fastmcp import FastMCP

mcp = FastMCP(
    name="regression_db",
    instructions=(
        "Authenticated client for the Hardware Regression Database. "
        "Read the regressions currently assigned to you and update a "
        "regression's debug metadata (status / owner / linked issue). Test "
        "result data itself is read-only through this server."
    ),
)

_DEFAULT_URL = "http://localhost:8000/api"


def _api_url() -> str:
    """Regression Database REST base URL (env, with a localhost default)."""
    return os.environ.get("REGRESSION_DB_API_URL") or _DEFAULT_URL


def _require_key() -> str:
    """Return REGRESSION_DB_API_KEY or raise a single actionable line (validated lazily)."""
    key = os.environ.get("REGRESSION_DB_API_KEY")
    if not key:
        raise ValueError(
            "regression_db: REGRESSION_DB_API_KEY is not set — export it (nexus injects it "
            "per-launch) before using Regression Database tools"
        )
    return key


def _headers() -> dict:
    return {"X-API-Key": _require_key(), "Content-Type": "application/json"}


def _request(method: str, path: str, body: Optional[dict] = None):
    """Issue one REST call; translate transport/HTTP failures into ValueError."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        _api_url() + path, data=data, headers=_headers(), method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        hint = " (authentication failed — check REGRESSION_DB_API_KEY)" if exc.code == 401 else ""
        raise ValueError(f"Regression Database API error {exc.code} {exc.reason}{hint}") from None
    except urllib.error.URLError as exc:
        raise ValueError(
            f"cannot reach Regression Database API at {_api_url()}: {exc.reason} "
            "(is the Regression Database webpage server running?)"
        ) from None


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool
def get_my_assigned_regressions(
    username: Optional[str] = None, block: Optional[str] = None
) -> dict:
    """List regressions assigned to a user for debugging (READ-ONLY).

    Returns only records whose ``debug_status == "Assigned"`` and
    ``debug_owner == username``.

    Arguments:
      username: who to fetch for; defaults to the $USER environment variable.
      block:    optional block_name filter (e.g. "RISCV_CORE").
    Returns: {username, total_assigned, by_block: {block: count}, regressions: [...]}.
    """
    try:
        who = username or os.environ.get("USER", "unknown")
        data = _request("GET", "/regressions")
        assigned = [
            d
            for d in data
            if d.get("debug_status") == "Assigned" and d.get("debug_owner") == who
        ]
        if block:
            assigned = [d for d in assigned if d.get("block_name") == block]
        by_block: dict = {}
        for item in assigned:
            blk = item.get("block_name", "Unknown")
            by_block[blk] = by_block.get(blk, 0) + 1
        return {
            "username": who,
            "total_assigned": len(assigned),
            "by_block": by_block,
            "regressions": assigned,
        }
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool
def update_debug_signature(
    regression_id: str,
    debug_status: Optional[str] = None,
    debug_owner: Optional[str] = None,
    issue_tracker_id: Optional[int] = None,
) -> dict:
    """Update a regression's debug metadata (MUTATING / outward).

    Only ``debug_status``, ``debug_owner`` and ``issue_tracker_id`` are changed;
    every other test-data field is re-sent unchanged so the record is preserved.
    Requires REGRESSION_DB_API_KEY. Because this writes the central regression DB it stays
    confirm-on-use in nexus (never pre-approved).

    Arguments:
      regression_id:    the record's string regression_id (e.g. "REG_2026_M10_04").
      debug_status:     'Assigned' | 'Debugged' | 'Ignored' | '-' (optional).
      debug_owner:      username of the person debugging (optional).
      issue_tracker_id: linked issue-tracker id (optional).
    Returns: {success, message, record} or {success: false, error}.
    """
    try:
        data = _request("GET", "/regressions")
        target = next(
            (r for r in data if r.get("regression_id") == regression_id), None
        )
        if target is None:
            return {"success": False, "error": f"Regression {regression_id} not found"}
        payload = {
            "regression_id": target.get("regression_id"),
            "block_name": target.get("block_name"),
            "test_name": target.get("test_name"),
            "status": target.get("status"),
            "seed": target.get("seed"),
            "simulation_tool": target.get("simulation_tool"),
            "error_signature": target.get("error_signature"),
            "failing_module_hierarchy": target.get("failing_module_hierarchy"),
            "wave_path": target.get("wave_path"),
            "debug_status": debug_status or target.get("debug_status"),
            "debug_owner": debug_owner or target.get("debug_owner"),
            "issue_tracker_id": issue_tracker_id or target.get("issue_tracker_id"),
        }
        record = _request("PUT", f"/regressions/{target.get('id')}", payload)
        return {
            "success": True,
            "message": f"Updated debug metadata for {regression_id}",
            "updated_fields": {
                "debug_status": payload["debug_status"],
                "debug_owner": payload["debug_owner"],
                "issue_tracker_id": payload["issue_tracker_id"],
            },
            "record": record,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()

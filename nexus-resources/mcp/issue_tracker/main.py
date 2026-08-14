#!/usr/bin/env python3
"""issue_tracker — Hardware Issue Tracker MCP server.

Ported to the current FastMCP library (``from fastmcp import FastMCP``) from an
older low-level ``mcp.server.Server`` implementation whose run loop no longer
starts. This server is a thin, authenticated client of the Issue Tracker REST
API (the ``issue-tracker/webpage`` dashboard backend).

Behaviour is preserved AND a persistence bug is fixed: the previous mutating
tools routed through a no-op ``save()`` and silently failed to persist. Here
create/update/comment/delete call the real REST verbs (POST / PUT / DELETE), so
mutations actually reach the backend.

Transport: stdio (FastMCP default). Configuration comes ONLY from the
environment — nothing is hardcoded:

  TRACKER_API_URL  (path,       optional) base REST URL; default http://localhost:8001/api
  TRACKER_API_KEY  (credential, required by every tool) sent as the X-API-Key header

The credential is validated LAZILY, inside each tool, so the server still starts
and answers ``initialize`` / ``tools/list`` (nexus Verify passes) with no secret.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from fastmcp import FastMCP

mcp = FastMCP(
    name="issue_tracker",
    instructions=(
        "Authenticated client for the Hardware Issue Tracker. Read/filter issues, "
        "create new tickets, update fields, append debug comments, and delete "
        "issues. Create/update/delete are outward actions that write the shared "
        "tracker."
    ),
)

_DEFAULT_URL = "http://localhost:8001/api"


def _api_url() -> str:
    """Issue Tracker REST base URL (env, with a localhost default)."""
    return os.environ.get("TRACKER_API_URL") or _DEFAULT_URL


def _require_key() -> str:
    """Return TRACKER_API_KEY or raise a single actionable line (validated lazily)."""
    key = os.environ.get("TRACKER_API_KEY")
    if not key:
        raise ValueError(
            "issue_tracker: TRACKER_API_KEY is not set — export it (nexus injects it "
            "per-launch) before using tracker tools"
        )
    return key


def _headers() -> dict:
    return {"X-API-Key": _require_key(), "Content-Type": "application/json"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request(method: str, path: str, body: Optional[dict] = None):
    """Issue one REST call; translate transport/HTTP failures into ValueError."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        _api_url() + path, data=data, headers=_headers(), method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("not found") from None
        hint = " (authentication failed — check TRACKER_API_KEY)" if exc.code == 401 else ""
        raise ValueError(f"Issue Tracker API error {exc.code} {exc.reason}{hint}") from None
    except urllib.error.URLError as exc:
        raise ValueError(
            f"cannot reach Issue Tracker API at {_api_url()}: {exc.reason} "
            "(is the tracker webpage server running?)"
        ) from None


def _get_issue(issue_id: int) -> Optional[dict]:
    try:
        return _request("GET", f"/issues/{issue_id}")
    except ValueError as exc:
        if str(exc) == "not found":
            return None
        raise


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool
def get_issues(status: Optional[str] = None, component: Optional[str] = None) -> dict:
    """List hardware issues, optionally filtered (READ-ONLY).

    Arguments:
      status:    'todo' | 'in-progress' | 'in-review' | 'done' (optional).
      component: case-insensitive substring match on component (optional).
    Returns: {count, issues: [{id, title, status, component, revision, firmware,
      severity, description, assignee, created_at, comments}, ...]}.
    """
    try:
        issues = _request("GET", "/issues")
        if status:
            issues = [i for i in issues if i.get("status") == status]
        if component:
            c = component.lower()
            issues = [i for i in issues if c in (i.get("component") or "").lower()]
        projected = [
            {
                "id": i.get("id"),
                "title": i.get("title"),
                "status": i.get("status"),
                "component": i.get("component"),
                "revision": i.get("revision"),
                "firmware": i.get("firmware"),
                "severity": i.get("severity"),
                "description": i.get("description"),
                "assignee": i.get("assignee"),
                "created_at": i.get("created_at"),
                "comments": i.get("comments", []),
            }
            for i in issues
        ]
        return {"count": len(projected), "issues": projected}
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool
def create_issue(
    title: str,
    component: str,
    severity: str,
    description: Optional[str] = None,
    rev: Optional[str] = None,
    assignee: Optional[str] = None,
) -> dict:
    """Create a new hardware tracking ticket (MUTATING / outward).

    Arguments:
      title:     brief issue title (required).
      component: hardware component affected, e.g. "DDR Controller" (required).
      severity:  'low' | 'medium' | 'high' | 'critical' (required).
      description, rev, assignee: optional details.
    Returns: {success, issue_id, message, issue} or {success: false, error}.
    """
    try:
        body = {
            "title": title,
            "description": description or "",
            "component": component or "",
            "revision": rev or "",
            "firmware": "",
            "severity": severity,
            "status": "todo",
            "assignee": assignee or "",
            "comments": [],
        }
        rec = _request("POST", "/issues", body)
        return {
            "success": True,
            "issue_id": rec.get("id"),
            "message": f"Created issue HW-{rec.get('id')}: {title}",
            "issue": rec,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}


@mcp.tool
def update_issue(
    issue_id: int,
    status: Optional[str] = None,
    description: Optional[str] = None,
    firmware_version: Optional[str] = None,
    severity: Optional[str] = None,
) -> dict:
    """Modify fields of an existing hardware ticket (MUTATING / outward).

    Loads the current issue, applies only the provided fields, and PUTs the whole
    record back (the backend replaces the object, preserving id/created_at).

    Arguments:
      issue_id: id of the issue to update (required).
      status:   'todo' | 'in-progress' | 'in-review' | 'done' (optional).
      description, firmware_version, severity: optional field updates.
    Returns: {success, issue_id, message, issue} or {success: false, error}.
    """
    try:
        issue = _get_issue(issue_id)
        if issue is None:
            return {"success": False, "error": f"Issue HW-{issue_id} not found"}
        if status:
            issue["status"] = status
        if description is not None:
            issue["description"] = description
        if firmware_version:
            issue["firmware"] = firmware_version
        if severity:
            issue["severity"] = severity
        rec = _request("PUT", f"/issues/{issue_id}", issue)
        return {
            "success": True,
            "issue_id": issue_id,
            "message": f"Updated issue HW-{issue_id}",
            "issue": rec,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}


@mcp.tool
def add_debug_comment(issue_id: int, comment: str) -> dict:
    """Append a debug log entry / comment to an issue (MUTATING / outward).

    Arguments:
      issue_id: id of the issue to comment on (required).
      comment:  the debug comment or log entry (required).
    Returns: {success, issue_id, message, comment_count} or {success: false, error}.
    """
    try:
        issue = _get_issue(issue_id)
        if issue is None:
            return {"success": False, "error": f"Issue HW-{issue_id} not found"}
        comments = issue.get("comments") or []
        comments.append({"text": comment, "timestamp": _now()})
        issue["comments"] = comments
        _request("PUT", f"/issues/{issue_id}", issue)
        return {
            "success": True,
            "issue_id": issue_id,
            "message": f"Added comment to HW-{issue_id}",
            "comment_count": len(comments),
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}


@mcp.tool
def delete_issue(issue_id: int) -> dict:
    """Delete an issue permanently (MUTATING / outward / destructive).

    Arguments:
      issue_id: id of the issue to delete (required).
    Returns: {success, issue_id, message} or {success: false, error}.
    """
    try:
        _request("DELETE", f"/issues/{issue_id}")
        return {
            "success": True,
            "issue_id": issue_id,
            "message": f"Deleted issue HW-{issue_id}",
        }
    except ValueError as exc:
        if str(exc) == "not found":
            return {"success": False, "error": f"Issue HW-{issue_id} not found"}
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()

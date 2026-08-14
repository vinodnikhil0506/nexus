---
name: issue-tracker
description: Use this skill when you need to file, look up, update, comment on, or close a hardware project issue/ticket — e.g. "create a critical issue for the DDR timeout", "what issues are in progress for the PCIe block", "add a debug note to HW-12", "mark HW-3 done", or "delete HW-7". Trigger it whenever the issue_tracker MCP is the right way to read or change tracked hardware issues, before hand-editing any tracker file.
---

# Hardware issue tracking

Read and manage hardware project issues through the **issue_tracker** MCP server (an
authenticated client of the Issue Tracker dashboard). Run this as an ordered procedure,
one step at a time, and PAUSE at the gates before any write — with an explicit stronger
gate before a delete.

Tools: `get_issues` (read-only); `create_issue`, `update_issue`, `add_debug_comment`,
`delete_issue` (all mutating / outward).

1. **Understand the request.** Decide whether this is a read (find/list) or a change
   (create / update / comment / delete). State which, and on which issue(s).

2. **Read first.** For any lookup, call `get_issues(status?, component?)` — `status` is one
   of `todo` / `in-progress` / `in-review` / `done`; `component` is a case-insensitive
   substring. Report the `count` and the matching issues (`id`, `title`, `status`,
   `component`, `severity`). For a change, read the target issue first so you edit the
   right one and preserve its other fields.

3. **Gate — confirm the change.** Creating, updating, or commenting writes the shared
   tracker (confirm-on-use). State exactly what you will do:
   - **create:** `title`, `component`, `severity` (`low`/`medium`/`high`/`critical`) — plus
     optional `description`, `rev`, `assignee`.
   - **update:** the `issue_id` and only the fields you are changing (`status`,
     `description`, `firmware_version`, `severity`).
   - **comment:** the `issue_id` and the exact comment text.
   Wait for the engineer to confirm.

4. **Apply the change.** Call the matching tool and report the result
   (`issue_id`/`message`, or the returned error verbatim).

5. **Delete — hard gate.** `delete_issue(issue_id)` is permanent and destructive. Only
   after the engineer explicitly confirms the specific `issue_id` should you call it; then
   report the outcome. Never batch-delete or infer the target.

Errors (missing `TRACKER_API_KEY`, an unreachable backend, or a not-found id) come back as
a one-line `{"error": ...}` / `{"success": false, ...}` payload — relay it, don't retry blindly.

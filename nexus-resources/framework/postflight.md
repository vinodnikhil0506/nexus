# Mandatory post-flight (run after EVERY debug session)

This is the universal, domain-agnostic post-flight. It is `@import`ed by every
engineer's `~/.claude/CLAUDE.md` and is identical for everyone. Record the outcome of
the session **through the MCP servers** so the next occurrence of this failure is caught
by the pre-flight lookup instead of re-debugged from scratch.

Every write here is an **outward action** — it updates a shared team system (the
regression DB or the issue tracker). State what you are about to write and get the
engineer's confirmation before each write; the mutating tools stay confirm-on-use.

Steps:

1. **Record the debug result on the regression.** With the `regression_db` MCP
   (`update_debug_signature`), set the regression's `debug_status` to reflect what
   happened (`Debugged` if root-caused, `Ignored` if a known non-issue), set
   `debug_owner` to yourself, and link the tracking issue via `issue_tracker_id`. Only
   the debug metadata is written; the test-result fields are preserved.

2. **File or update the tracking issue.** With the `issue_tracker` MCP: if this failure
   is not yet tracked, `create_issue` (title, affected `component`, `severity`); if it
   is, `update_issue` to move its `status` forward and `add_debug_comment` with a concise
   root-cause note. Keep one issue per real failure — read first (`get_issues`) so you
   update the existing ticket rather than creating a duplicate.

3. **Close the loop.** Make sure the regression's `issue_tracker_id` and the issue point
   at each other, so a future pre-flight that hits either surfaces the other.

Keeping the regression DB and issue tracker deduplicated is what keeps the pre-flight
cheap: both are queried on every pre-flight by every engineer, so a duplicate-laden
record set directly costs every future session more — the exact cost this framework
exists to eliminate.

<!-- rendered-from: 9803c5f7e4c68a37e493c02f24e3045f8eec49b83c24bc084668b69d0dc4a6ac -->

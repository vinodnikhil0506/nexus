---
name: regression-db
description: Use this skill when you are triaging or debugging hardware regression failures and need to read which regressions are assigned to you or record debug progress back to the central Regression Database — e.g. "what regressions am I assigned?", "show my failing RISCV_CORE runs", "mark REG_2026_M10_04 as Debugged", or "link this failure to issue 42". Trigger it whenever the regression_db MCP is the right way to read or update regression debug state, before hand-editing any tracker.
---

# Regression Database debug triage

Read and update hardware regression debug state through the **regression_db** MCP server
(an authenticated client of the Regression Database dashboard). Test-result data is read-only through
this server; only *debug metadata* (status, owner, linked issue) can be written. Run this
as an ordered procedure, one step at a time, and PAUSE at the gate (step 4) before any
write.

Tools: `get_my_assigned_regressions` (read-only) and `update_debug_signature` (mutating).

1. **Scope the query.** Confirm whose regressions to look at (defaults to the current
   `$USER`) and whether to narrow to one block. State the scope back before fetching.

2. **Pull the assigned regressions.** Call `get_my_assigned_regressions(username?, block?)`.
   Report the totals and the `by_block` breakdown, then list the candidate records
   (`regression_id`, `block_name`, `test_name`, `status`, `error_signature`). Do not dump
   every field — surface what identifies each failure.

3. **Triage one failure.** Pick the regression to work. Read its `error_signature`,
   `failing_module_hierarchy`, and `wave_path`, and investigate the root cause (use the
   waveform / issue-tracker skills as needed). Summarize your finding in one short
   paragraph.

4. **Gate — confirm the write.** `update_debug_signature` writes the central regression DB
   (an outward, irreversible action; it stays confirm-on-use). State exactly what you will
   set — `regression_id`, the new `debug_status` (`Assigned` / `Debugged` / `Ignored` /
   `-`), `debug_owner`, and any `issue_tracker_id` — and wait for the engineer to confirm.

5. **Record the outcome.** On confirmation, call
   `update_debug_signature(regression_id, debug_status?, debug_owner?, issue_tracker_id?)`.
   Report success and the updated fields; on failure, report the returned error verbatim
   (missing `REGRESSION_DB_API_KEY` or an unreachable backend both surface as a one-line message).

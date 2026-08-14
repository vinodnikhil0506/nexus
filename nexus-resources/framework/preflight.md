# Mandatory pre-flight (run before ANY debug session)

This is the universal, domain-agnostic pre-flight. It is `@import`ed by every engineer's
`~/.claude/CLAUDE.md`, so it contains no per-user path. Check whether the failure is
already known **through the MCP servers** — never by bulk-reading a tracker file.

Run these steps in order before doing any investigation:

1. **Locate the failure artifacts.** If the engineer did not point you at specific
   logs, scan the current working directory for log/trace/waveform files.

2. **Read the logs and characterize the failure.** Identify the primary fault (the
   first real error, not downstream noise), the faulting instruction / time / cycle,
   and the key state at the point of failure. Note the affected block/component.

3. **Check the regression database.** Use the `regression_db` MCP
   (`get_my_assigned_regressions`) to see whether this failure is already a known,
   assigned regression — read its `debug_status`, `debug_owner`, `error_signature`,
   and any linked `issue_tracker_id`. This costs a single scoped query, not a bulk read.

4. **Check the issue tracker.** Use the `issue_tracker` MCP (`get_issues`, filtered by
   `component`/`status`) to see whether an issue already tracks this failure.

5. **If it is already known: STOP.** Report the regression's status and owner and/or the
   existing issue id, and ask the engineer to confirm it is the same failure. Do **not**
   begin a fresh investigation — this is the human gate that turns a repeat failure into
   a cheap lookup instead of a full re-debug.

6. **If it is new: proceed with the full debug** using the domain's artifact reading
   order (see the domain `artifact_order` import below). For waveform evidence, use the
   `gtkwave` MCP (start with `waveform_info`, then narrow with `list_signals` /
   `get_signal_values`). The full cost is paid once here; post-flight then records the
   result so the next occurrence is caught at steps 3–4.

<!-- rendered-from: 9803c5f7e4c68a37e493c02f24e3045f8eec49b83c24bc084668b69d0dc4a6ac -->

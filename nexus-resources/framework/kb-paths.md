# Team knowledge sources — how to read shared debug state

This file describes where the team's shared debug knowledge lives and how to read it. It
is shared verbatim by every engineer, so it carries nothing per-user. Always query these
sources **through their MCP servers** — never bulk-read a backing file.

- **Regression database (`regression_db` MCP).** The shared record of hardware
  regressions and their debug state (status, owner, error signature, linked issue). Ask
  it scoped questions (`get_my_assigned_regressions`) rather than listing everything; it
  returns only the records you asked for, so cost does not grow with total history.

- **Issue tracker (`issue_tracker` MCP).** The shared record of tracked hardware issues.
  Query with `get_issues` filtered by `status`/`component`; read the specific issue you
  care about instead of dumping the whole board.

- **Waveforms (`gtkwave` MCP).** Per-run evidence rather than team state, but read the
  same way: `waveform_info` first, then narrow with `list_signals` / `get_signal_values`
  — never attempt to read a whole dump into context.

> Writing back is an outward action handled in the post-flight step (update the
> regression's debug metadata; file/update the tracking issue). Both the pre-flight
> lookup and the post-flight record go through these same MCP servers, so a
> deduplicated regression DB and issue tracker keep every future pre-flight cheap.

<!-- rendered-from: 9803c5f7e4c68a37e493c02f24e3045f8eec49b83c24bc084668b69d0dc4a6ac -->

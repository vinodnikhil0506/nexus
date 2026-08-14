---
name: verisight-debug
description: Use this skill when a simulation failure needs deep automated RTL/UVM root-cause analysis and you want to run the VeriSight multi-agent debugger — e.g. "run VeriSight on this failing test", "what's the root cause of this sim failure", "classify this UVM scoreboard mismatch", or after the KB/regression pre-flight finds no known match and a fresh RTL investigation is warranted. Trigger it whenever the verisight MCP is the right way to get a classified, evidence-backed root cause from a sim log (+ optional spec/RTL/testbench).
---

# VeriSight RTL/UVM root-cause analysis

Drive the **VeriSight** IP (an autonomous multi-agent RTL/UVM debugger) through the
**`verisight`** MCP server. VeriSight classifies a failure (TB / RTL / Spec / Unknown),
traces a root cause with an evidence chain, and writes JSON/Markdown/HTML reports.

Run this as an ordered procedure and PAUSE at the gate (step 3) before the analysis run —
it calls an LLM provider (billable) and writes a report directory, so it is confirm-on-use.

Tools: `list_examples` (read-only) and `analyze_failure` (mutating / outward).

1. **Confirm scope.** This is heavier than a KB/regression lookup — use it when the
   pre-flight (`regression-db` / `issue-tracker`) found no known match, or when the
   engineer explicitly wants VeriSight's deep analysis. Identify the failing run's inputs:
   the simulation **log** (required) plus any **spec** / **RTL** / **testbench** paths.

2. **Locate inputs (optional).** If you don't have concrete paths, call `list_examples`
   to see the bundled example/project input sets, and confirm which files to analyze.

3. **Gate — confirm the run.** State exactly what you will pass to `analyze_failure`
   (`log`, and any `spec`/`rtl`/`tb`/`coverage`, plus `provider`/`model` if overriding)
   and that it will call the LLM and write a report dir. Wait for the engineer to confirm.

4. **Analyze.** Call `analyze_failure(...)`. On success you get back the parsed
   `error_report` (classification, confidence, root cause, module, category) and the paths
   to `report.md` / `report.html` / `summary.txt`. Summarize the classification, confidence,
   and root cause; point the engineer at the full report path rather than pasting it all.

5. **Fold into the loop.** Treat VeriSight's output as evidence, not gospel — sanity-check
   the root cause against the artifacts. Then close the loop with the post-flight: record
   the outcome on the regression (`regression-db`) and file/annotate the tracking issue
   (`issue-tracker`), linking VeriSight's report.

If a tool returns `{"success": false, "error": ...}`, relay it verbatim. Common causes:
no `ANTHROPIC_API_KEY` set, or VeriSight's own dependencies not installed
(it needs its deps + a working Python; see `mcp/verisight/README.md`). These are runtime
prerequisites of the IP, not a nexus fault.

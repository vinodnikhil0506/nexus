# Hardware-debug router

This file is the minimal session-start policy for hardware debugging. It is imported by
`~/.claude/CLAUDE.md` and intentionally stays short; the detailed implementation lives in
Nexus MCPs, Skills, shared KBs, and VeriSight.

1. Start from the current working directory and inspect only the directory layout needed to
   infer the project/domain: RTL/design, verification, simulation, regression, tests,
   logs/results, config, Nexus resources (`preflight.md`), or VeriSight assets.

2. Never read source code during initial discovery or normal project exploration. Do not do
   a broad recursive scan of the repository. Prefer manifests, names, and targeted search.

3. Classify the failure quickly: RTL/design, SystemVerilog, UVM, testbench, simulation,
   regression, assertion, protocol/interface, configuration/environment, infrastructure/tool,
   or unknown.

4. Identify the minimal evidence: error message, failing testcase/seed, assertion, log,
   waveform, stack trace, source location, regression metadata, or config.

5. Choose the smallest reusable capability: Nexus MCP, Nexus Skill, VeriSight flow, or a
   minimal combination. Prefer existing infrastructure over a new debugging procedure.

6. Search shared knowledge before creating anything new. Reuse a known failure/root cause if
   the signature is sufficiently similar. Report when it is already known, similar, or new.

7. For a new failure, debug from evidence to root cause, distinguishing symptom vs trigger
   vs actual root cause vs proposed fix/workaround.

8. Only create or update persistent shared knowledge/issues after explicit user approval,
   unless existing project policy authorizes it. Read-only investigation can proceed.

9. Keep final output concise: Failure, Classification, Root Cause, Evidence, Known/New,
   Existing Knowledge/Issue, Recommended Fix, Next Action.

The agent is a thin orchestrator: understand the workspace, select the minimum necessary
Nexus/VeriSight capability, reuse shared knowledge, and avoid duplicate analysis or large
context loads.

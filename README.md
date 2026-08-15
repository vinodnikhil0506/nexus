# NEXUS

NEXUS is an AI-powered hardware verification debug framework that brings together **agentic AI, MCPs, Skills, regression analysis, shared knowledge, issue tracking, and specialized verification agents** into a reusable debug workflow.

NEXUS can use **VeriSight as a specialized AI verification-debug capability** to analyze specifications, RTL, UVM testbenches, simulation logs, coverage, and waveforms, identify root causes, generate reports, and propose fixes.

## Overview

Hardware verification debug normally requires engineers to move between many sources of information:

```text
Specification
RTL
SystemVerilog
UVM
Simulation Logs
Regression Results
Coverage
Waveforms
Previous Issues
Previous Debug Results
```

NEXUS brings these resources into a common AI-driven workflow.

Instead of creating one large agent that tries to understand every hardware-debug problem, NEXUS uses a **resource-based architecture**.

The agent first understands the current workspace and failure, then selects the appropriate MCP, Skill, custom hardware agent, or VeriSight analysis flow.

```text
                         Hardware Failure
                                |
                                v
                         NEXUS AI Agent
                                |
                                v
                      Workspace Discovery
                                |
                                v
                       Failure Classification
                                |
              +-----------------+-----------------+
              |                 |                 |
              v                 v                 v
             MCP             Skill        Hardware Agent
              |                 |                 |
              +-----------------+-----------------+
                                |
                                v
                       Existing Knowledge?
                         /               \
                       Yes               No
                        |                 |
                        v                 v
                    Reuse Result     Select Deep
                                     Debug Flow
                                          |
                                          v
                                      VeriSight
                                          |
                                          v
                               Verification Analysis
                                          |
                       +------------------+------------------+
                       |                  |                  |
                       v                  v                  v
                 Root Cause          Waveform/RTL       Candidate Fix
                   Analysis             Analysis
                       |                  |                  |
                       +------------------+------------------+
                                          |
                                          v
                                  NEXUS Shared Knowledge
                                          |
                                          v
                                     Issue / Report
```

The important principle is that **NEXUS and VeriSight work together as parts of the same debug flow**.

---

## Architecture

The system is organized into several layers.

```text
+-----------------------------------------------------------+
|                     Engineer / User                       |
+------------------------------+----------------------------+
                               |
                               v
+-----------------------------------------------------------+
|                    NEXUS AI Orchestrator                  |
|                                                           |
| Workspace Discovery | Failure Triage | Resource Routing  |
+------------------------------+----------------------------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
           NEXUS MCPs     NEXUS Skills    Custom Agents
              |                |                |
              +----------------+----------------+
                               |
                               v
+-----------------------------------------------------------+
|                 Shared Debug Infrastructure                |
|                                                           |
| Regression DB | Knowledge Base | Issue Tracker | Results  |
+------------------------------+----------------------------+
                               |
                               v
+-----------------------------------------------------------+
|                    VeriSight Debug Flow                    |
|                                                           |
| Knowledge Extraction                                      |
|        ↓                                                  |
| Root Cause Classification                                 |
|        ↓                                                  |
| RTL Root Cause Analysis                                   |
|        ↓                                                  |
| Report Generation                                         |
|        ↓                                                  |
| Fix Generation                                            |
+------------------------------+----------------------------+
                               |
                               v
+-----------------------------------------------------------+
|                 Shared NEXUS Results                      |
|                                                           |
| Root Cause | Evidence | Fix | Knowledge | Issue          |
+-----------------------------------------------------------+
```

Each component contributes to the same debugging workflow.

---

## NEXUS as the Debug Entry Point

NEXUS is the common entry point for engineers and AI agents.

When a debug session starts, the agent should first understand the workspace.

For example:

```text
project/
├── rtl/
├── tb/
├── tests/
├── regression/
├── logs/
├── waves/
└── ...
```

The agent determines what type of project and failure it is dealing with.

Possible classifications include:

```text
RTL
SystemVerilog
UVM
Testbench
Simulation
Regression
Assertion
Protocol
Waveform
Configuration
EDA Tool
Infrastructure
Unknown
```

The agent should not immediately start reading every file.

Instead:

```text
Discover
   ↓
Classify
   ↓
Search Existing Knowledge
   ↓
Select Required Capability
```

This keeps the context small and avoids unnecessary token consumption.

---

## NEXUS MCPs and Skills

NEXUS provides reusable **MCPs and Skills** that expose capabilities to the AI agent.

These capabilities can be used for tasks such as:

```text
Regression Analysis
Log Analysis
Waveform Analysis
Issue Tracking
Knowledge Search
Hardware Debug
Verification Analysis
Project Information
```

The agent should dynamically select only the MCPs and Skills required for the current failure.

It should not load every available resource.

For example:

```text
UVM Failure
    |
    +---- Regression MCP
    |
    +---- Log Analysis Skill
    |
    +---- VeriSight
```

While another failure might only require:

```text
Regression Failure
    |
    +---- Regression MCP
    |
    +---- Knowledge Search
```

There is no need to invoke VeriSight when the existing knowledge already explains the failure.

---

## VeriSight as a NEXUS Debug Capability

VeriSight is integrated into NEXUS as a **specialized verification-debug capability**.

It is particularly useful when a failure requires correlation between:

* Design specification
* RTL
* UVM testbench
* Simulation logs
* Coverage
* Waveforms/VCD
* Signal behavior

VeriSight provides a multi-agent debugging pipeline that can build a structured understanding of the failure, classify its root cause, perform deeper RTL analysis when required, generate reports, and propose a source-code fix.

NEXUS does not need to reproduce these capabilities.

Instead, NEXUS determines:

> **"This failure requires deeper verification analysis, so invoke VeriSight."**

---

## Integrated Debug Flow

The complete workflow is:

```text
                         Failure
                            |
                            v
                    NEXUS Discovery
                            |
                            v
                   Failure Triage
                            |
                            v
                  Search Knowledge
                     /          \
                  Found          Not Found
                   |                |
                   v                v
                Reuse          Select Tool
                   |                |
                   |        +-------+-------+
                   |        |       |       |
                   |       v       v       v
                   |      MCP   Skill  VeriSight
                   |                       |
                   |                       v
                   |               Deep Debug Analysis
                   |                       |
                   +-----------+-----------+
                               |
                               v
                         Root Cause
                               |
                               v
                         Evidence Chain
                               |
                               v
                       Shared Knowledge
                               |
                    +----------+----------+
                    |                     |
                    v                     v
               Existing Issue        New Issue
                                          |
                                          v
                                    User Approval
                                          |
                                          v
                                   Create Issue
```

This allows the system to choose the **least expensive path that can reliably solve the problem**.

---

## VeriSight Analysis Pipeline

When NEXUS selects VeriSight, VeriSight performs its specialized analysis.

```text
Specification
RTL
UVM Testbench
Simulation Log
Coverage
Waveform
       |
       v
+-----------------------+
| Knowledge Extraction  |
+-----------+-----------+
            |
            v
+-----------------------+
| Root Cause            |
| Classification        |
+-----------+-----------+
            |
            v
       Is it an RTL Bug?
          /       \
        No         Yes
        |           |
        |           v
        |    +-------------+
        |    | RTL Analysis|
        |    +------+------+
        |           |
        |           v
        |      X-Tracer
        |      Functional
        |      CDC
        |      Lint
        |      Structural
        |      Protocol
        |      Misc
        |           |
        +-----------+
                    |
                    v
             Report Generation
                    |
                    v
              Fix Generation
```

VeriSight's RTL analysis stage contains seven specialized analyzers and runs on the RTL-bug path, avoiding unnecessary analysis for other failure types.

---

## Knowledge Extraction

VeriSight first creates a structured representation of the design and failure.

The framework uses deterministic parsers for:

* RTL
* UVM testbench code
* Simulation logs
* Specifications
* Coverage

This information is then enriched through the AI analysis stage.

The result includes a structured knowledge artifact such as:

```text
knowledge.json
```

The separation between deterministic parsing and AI reasoning is important because basic extraction does not require LLM calls.

NEXUS can then use this result together with its broader shared resources.

---

## Root-Cause Analysis

VeriSight classifies the failure into:

```text
TB Bug
RTL Bug
Spec Bug
Unknown
```

and provides confidence and supporting evidence.

For example:

```text
Failure:
AXI write response timeout

Classification:
RTL Bug

Confidence:
92%

Evidence:
- AWVALID is asserted.
- AWREADY does not respond.
- Timeout begins after reset release.
- RTL state machine remains in the wrong state.

Root Cause:
Incorrect RTL state transition after reset.
```

NEXUS can then correlate this result with previous failures.

---

## RTL Root-Cause Analysis

If the failure is classified as an RTL bug, VeriSight can perform deeper analysis.

The available analyzers include:

```text
X-Tracer
Functional Analysis
CDC Analysis
Lint Analysis
Structural Analysis
Protocol Compliance
Miscellaneous Analysis
```

This can help trace a failure from a high-level symptom to a specific RTL defect.

For example:

```text
Scoreboard Mismatch
        |
        v
Unexpected Data
        |
        v
Incorrect Internal Signal
        |
        v
Incorrect State
        |
        v
RTL Logic
        |
        v
Root Cause
```

---

## Waveform and X-Propagation Debug

Waveform analysis can be used when simulation behavior cannot be understood from logs alone.

VeriSight supports `x-tracer` for signal-level X-propagation analysis over VCD and gate-level netlist information.

Yosys can be used to generate a netlist when required.

The integrated flow can therefore be:

```text
Regression Failure
       |
       v
Simulation Log
       |
       v
Unexpected X
       |
       v
NEXUS selects VeriSight
       |
       v
X-Tracer
       |
       v
Trace Signal Backwards
       |
       v
Identify Source
       |
       v
RTL Root Cause
```

---

## Regression Analysis

Regression data is one of the key inputs to the NEXUS workflow.

Instead of analyzing every failing test independently, NEXUS can group failures and search for existing knowledge.

```text
Regression
    |
    v
100 Failed Tests
    |
    v
Failure Signature Extraction
    |
    v
Group Similar Failures
    |
    v
Search Shared Knowledge
    |
    +---- Known Failure
    |        |
    |        v
    |     Reuse
    |
    +---- New Failure
             |
             v
          VeriSight
```

This is particularly useful when hundreds of regression tests fail because of the same underlying RTL or environment problem.

---

## Shared Knowledge and RAG

The combined system is designed around **knowledge reuse**.

VeriSight already provides a persistent ChromaDB-based RAG layer for historical debugging information.

NEXUS provides the broader shared environment in which this information can be reused by multiple engineers, projects, and domains.

The goal is:

```text
Engineer A
    |
    v
Finds Root Cause
    |
    v
Store Knowledge
    |
    v
Shared Knowledge
    |
    +-------------------+
    |                   |
    v                   v
Engineer B          Engineer C
    |                   |
    v                   v
Reuse Result        Reuse Result
```

A failure solved once should not require the same expensive analysis every time it appears again.

---

## Failure Deduplication

Before invoking an expensive AI analysis, NEXUS should search for an existing failure signature.

Useful information includes:

```text
Test Name
Failure Message
Assertion
Error Code
Module
Interface
Signal
Regression
Seed
Simulation Phase
```

For example:

```text
AXI_WRITE_TIMEOUT
axi_master
AWVALID/AWREADY
write_response
```

can be used as a searchable failure signature.

If a matching historical result exists:

```text
Current Failure
      |
      v
Search Knowledge
      |
      v
Match Found
      |
      v
Reuse Existing Root Cause
```

If no match exists:

```text
Current Failure
      |
      v
Search Knowledge
      |
      v
No Match
      |
      v
Invoke VeriSight
```

This is one of the main ways the combined framework reduces unnecessary token consumption.

---

## Token-Efficient Debugging

The system should follow a simple rule:

> **Do not send more information to an AI model than is required to solve the problem.**

The intended workflow is:

```text
Discover
   |
   v
Extract
   |
   v
Classify
   |
   v
Search Existing Knowledge
   |
   +---- Found ----> Reuse
   |
   +---- Not Found
           |
           v
       Targeted Debug
           |
           v
         Result
```

Instead of:

```text
Read Entire Repository
        |
        v
Read All Logs
        |
        v
Read All RTL
        |
        v
Send Everything to LLM
        |
        v
Analyze From Scratch
```

NEXUS should perform the first-level filtering.

VeriSight should receive the relevant evidence for deeper analysis.

This creates a two-level debug strategy:

```text
Level 1: NEXUS
Fast triage and routing

Level 2: VeriSight
Deep verification analysis
```

---

## Agentic Hardware Verification

The framework can support custom hardware verification agents in addition to VeriSight.

For example:

```text
NEXUS
 |
 +-- RTL Debug Agent
 |
 +-- UVM Debug Agent
 |
 +-- Regression Agent
 |
 +-- Log Analysis Agent
 |
 +-- Waveform Agent
 |
 +-- Protocol Agent
 |
 +-- Issue/Triage Agent
 |
 +-- VeriSight
```

These agents do not need to operate independently.

NEXUS can select the appropriate capability based on the failure.

For example:

```text
UVM Objection Hang
       |
       v
UVM Debug Skill
```

while:

```text
RTL X-Propagation
       |
       v
VeriSight
       |
       v
X-Tracer
```

and:

```text
100 Regression Failures
       |
       v
Regression MCP
       |
       v
Failure Clustering
       |
       v
VeriSight on Representative Failure
```

This allows the framework to scale without creating one oversized agent.

---

## Issue Creation

Issue creation is the final stage of the debug workflow, not the first.

The recommended process is:

```text
Failure
   |
   v
Triage
   |
   v
Knowledge Search
   |
   +---- Existing Issue
   |          |
   |          v
   |       Reuse/Link
   |
   +---- No Existing Issue
              |
              v
          Deep Debug
              |
              v
          Root Cause
              |
              v
        User Approval
              |
              v
         Create Issue
```

A generated issue should contain concise, reusable information:

```text
Failure Signature
Test
Regression
Component
Root Cause
Evidence
Recommended Fix
Relevant VeriSight Report
Related Knowledge
```

Large raw logs should not be copied into every issue when a reference to the original artifact is sufficient.

---

## Fix Generation

When the failure is sufficiently understood, VeriSight can generate a candidate source-code fix.

Its fix-generation stage is designed to read the actual source files and produce a unified diff, while avoiding unsupported or speculative changes. It can also degrade gracefully when the evidence is insufficient.

The combined system should use:

```text
VeriSight
    |
    v
Candidate Fix
    |
    v
NEXUS Review
    |
    v
User Approval
    |
    v
Apply Fix
    |
    v
Regression
    |
    v
Verify Fix
```

The AI should not automatically modify RTL or verification code unless the project explicitly allows it.

---

## Debug Artifacts

VeriSight produces structured artifacts from each analysis.

Typical outputs include:

```text
output/
├── knowledge.json
├── summary.json
├── error.json
├── report.md
├── report.html
├── summary.txt
├── analysis/
│   └── *.json
└── fix/
    └── ...
```

These outputs can be consumed by NEXUS for further processing, knowledge reuse, and issue tracking.

---

## Installation

### Clone NEXUS

```bash
git clone https://github.com/vinodnikhil0506/nexus.git --recursive
```

```bash
cd nexus
```

```bash
source ./init.sh
```

Start NEXUS:

```bash
nexus
```

### Clone VeriSight (Stanalone)

```bash
git clone https://github.com/KITTUV03/VeriSight.git
```

```bash
cd VeriSight
```

Install VeriSight:

```bash
pip install -e ".[dev]"
```

Configure the LLM provider:

```bash
cp .env.example .env
```

For Gemini:

```bash
export GEMINI_API_KEY="your-gemini-key"
```

Or for Anthropic:

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
```

---

## Direct VeriSight Execution

VeriSight can also be executed directly when a user explicitly wants to run the complete verification-debug pipeline.

Example:

```bash
python main.py \
    --spec examples/specs/alu_spec.md \
    --rtl examples/rtl/ \
    --tb examples/tb/ \
    --log examples/logs/sim.log \
    --output output/
```

The resulting artifacts can then be reviewed or consumed by the NEXUS workflow.

---

## NEXUS-Driven Execution

The preferred integrated workflow is to start from NEXUS.

```text
Engineer
   |
   v
NEXUS
   |
   v
Understand Workspace
   |
   v
Understand Failure
   |
   v
Search Existing Knowledge
   |
   +-------------------+
   |                   |
   v                   v
Known              Unknown
   |                   |
   v                   v
Reuse            Select Capability
                       |
              +--------+--------+
              |        |        |
              v        v        v
             MCP     Skill   VeriSight
                                |
                                v
                         Deep Debug
                                |
                                v
                           Root Cause
                                |
                                v
                        Shared Knowledge
                                |
                                v
                         Issue if Needed
```

This makes VeriSight part of the **NEXUS debug ecosystem**, rather than requiring engineers to decide manually which system to use for every failure.

---

## Example

Consider a regression containing:

```text
TEST:
axi_write_test

WAVE:
test.vcd

ERROR:
AXI write response timeout

MODULE:
axi_master
```

The engineer does not need to manually decide how to debug it.

NEXUS can:

```text
1. Identify the workspace.
2. Identify the verification domain.
3. Extract the failure signature.
4. Search previous regression failures.
5. Search shared debug knowledge.
6. Determine whether the failure is already known.
```

If it is known:

```text
Reuse Existing Result
```

If it is new:

```text
NEXUS
  |
  v
Select VeriSight
  |
  v
Specification + RTL + UVM + Log
  |
  v
Knowledge Extraction
  |
  v
Root Cause Classification
  |
  v
RTL Analysis if Required
  |
  v
Report / Candidate Fix
  |
  v
NEXUS
  |
  v
Knowledge / Issue
```

The engineer therefore gets one integrated workflow instead of manually moving between multiple tools.

---

## Repository Model

A typical deployment can look like:

```text
workspace/
│
├── nexus/
│   ├── nexus-resources/
│   │   ├── mcp/
│   │   └── skills/
│   ├── nexus-workspace/
│   ├── init.sh
│   └── ...
│
├── VeriSight/
│   ├── verisight/
│   ├── examples/
│   ├── tests/
│   ├── templates/
│   └── main.py
│
└── project/
    ├── rtl/
    ├── tb/
    ├── specs/
    ├── tests/
    ├── logs/
    ├── waves/
    └── regression/
```

The project remains the source of truth for design and verification files.

NEXUS provides the shared orchestration and reusable resources.

VeriSight provides the specialized verification-debug pipeline.

---

## Design Principles

### One Debug Entry Point

Engineers should start with NEXUS rather than manually selecting individual debug tools.

### Reuse Existing Knowledge

Search before analyzing.

### Route Before Running

Determine which capability is required before invoking it.

### Deep Analysis Only When Required

Use VeriSight when the failure requires its deeper verification analysis.

### Share Results

A successful debug should become reusable knowledge for future failures.

### Avoid Duplicate Analysis

Identical regression failures should not trigger independent AI investigations.

### Preserve Evidence

Root-cause results should contain enough evidence to explain why the conclusion was reached.

### Minimize Tokens

Use deterministic parsing, targeted searches, failure signatures, conditional analysis, and existing knowledge before sending large contexts to an LLM.

### Keep Components Focused

NEXUS coordinates the workflow.

MCPs and Skills provide reusable capabilities.

VeriSight performs specialized verification analysis.

The project provides the actual design and verification data.

---

## Future Vision

The combined system can grow into a common AI debug platform for multiple hardware domains.

```text
                         NEXUS
                           |
       +-------------------+-------------------+
       |                   |                   |
       v                   v                   v
    Domain A            Domain B            Domain C
       |                   |                   |
       +-------------------+-------------------+
                           |
                    Shared Knowledge
                           |
       +-------------------+-------------------+
       |                   |                   |
       v                   v                   v
     MCPs               Skills              Agents
                           |
                           v
                       VeriSight
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
        Logs           Waveforms          RTL/UVM
          |                |                |
          +----------------+----------------+
                           |
                           v
                       Root Cause
                           |
                           v
                    Shared Knowledge
                           |
                           v
                    Issue / Fix / Report
```

The long-term objective is to make hardware debug **cumulative**.

Every new investigation should improve the system's ability to recognize and solve future failures.

## Summary

NEXUS and VeriSight are intended to work together as one hardware-debug workflow.

```text
NEXUS
    |
    |-- Understand the workspace
    |-- Understand the failure
    |-- Search existing knowledge
    |-- Select the right capability
    |-- Coordinate MCPs and Skills
    |-- Manage regression information
    |-- Manage issues
    |-- Reuse results
    |
    v
VERISIGHT
    |
    |-- Extract verification knowledge
    |-- Classify root cause
    |-- Analyze RTL when required
    |-- Analyze X propagation
    |-- Generate reports
    |-- Generate candidate fixes
    |-- Reuse historical debug knowledge
    |
    v
NEXUS
    |
    |-- Correlate results
    |-- Store reusable knowledge
    |-- Link/create issues
    |-- Share results with engineers
    |
    v
Future Debug Sessions
```

The central idea is simple:

> **NEXUS decides how a failure should be debugged. VeriSight provides deep verification analysis when that path is selected. The resulting knowledge becomes reusable through NEXUS.**

This creates a shared hardware-debug system where **MCPs, Skills, custom agents, VeriSight, regression data, issue tracking, and historical knowledge work together instead of operating as separate tools.**

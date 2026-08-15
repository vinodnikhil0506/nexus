# Nexus

**Nexus** is a lightweight AI-powered workspace for debugging hardware and verification failures. It connects **AI agents, MCPs, Skills, shared knowledge, regression data, logs, waveforms, and issue tracking** into one reusable debug workflow.

## Features

* **Agentic AI** — AI agents for hardware debug and verification
* **MCP Integration** — Connect agents to project and debug tools
* **Reusable Skills** — Shared capabilities across projects and engineers
* **Hardware Verification Agents** — Custom agents for RTL, SystemVerilog, UVM, and verification
* **Regression Analysis** — Analyze failures across regression runs
* **Log Debugging** — Extract errors and failure signatures from logs
* **Waveform Debugging** — Investigate simulation behavior and waveform data
* **Root-Cause Analysis** — Trace failures from symptoms to likely root cause
* **Failure Triage** — Classify and prioritize hardware and verification failures
* **Issue Creation** — Create issues from confirmed failures
* **Knowledge Reuse** — Search existing failures before starting a new investigation
* **Shared Debug Framework** — Reuse resources across domains and engineers
* **Token Efficient** — Use targeted tools and existing knowledge instead of repeatedly loading large contexts
* **Local Web Tools** — Issue Tracker and Regression DB services
* **Domain-Aware Setup** — Select the resources and Skills required for a specific hardware domain

## Tech Stack

| Component                   | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| **Python**                  | Project setup and automation                     |
| **Shell**                   | Environment initialization                       |
| **Claude Code**             | AI agent interface                               |
| **MCP**                     | Connect AI agents to external/project tools      |
| **Skills**                  | Reusable AI capabilities                         |
| **NEXUS Resources**         | Shared MCPs, Skills, agents, and debug resources |
| **VeriSight IP/Agent Flow** | Hardware verification and debug analysis         |
| **Issue Tracker**           | Failure and issue management                     |
| **Regression DB**           | Regression results and failure analysis          |
| **SystemVerilog / UVM**     | Hardware verification domains                    |
| **RTL**                     | Hardware design/debug domain                     |

> The exact MCPs, Skills, and domain resources are selected during NEXUS setup. They are maintained as reusable shared resources instead of being duplicated inside individual projects.

## Folder Structure

```text
nexus/
├── nexus-resources/          # Shared resources used across projects/users
│   ├── mcp/                  # MCP servers and configurations
│   ├── skills/               # Reusable AI Skills
│   └── ...                   # Other shared debug resources
│
├── nexus-workspace/          # Workspace/domain configuration
│   └── ...                   # Project-specific workspace setup
│
├── init.sh                   # Environment initialization
├── requirements.txt          # Python dependencies
├── .gitmodules               # Git submodule configuration
└── README.md                 # Project documentation
```

### Shared vs. Workspace Resources

Nexus separates **shared resources** from **workspace configuration**.

```text
Shared Resources
      │
      ├── MCPs
      ├── Skills
      ├── Debug knowledge
      ├── Agents
      └── Common tools
             │
             ▼
      ┌───────────────┐
      │     NEXUS     │
      └───────────────┘
             │
       ┌─────┴─────┐
       ▼           ▼
   Engineer A   Engineer B
       │           │
       ▼           ▼
   Domain A     Domain B
```

This allows multiple engineers and domains to reuse the same debug capabilities and knowledge without maintaining separate copies.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/vinodnikhil0506/nexus.git --recursive
```

### 2. Enter the repository

```bash
cd nexus
```

### 3. Initialize the NEXUS environment

```bash
source ./init.sh
```

The initialization script prepares the environment and makes the NEXUS tools available in the current shell. ([GitHub][1])

### 4. Start NEXUS

```bash
nexus
```

The NEXUS menu guides you through the initial setup. You can select the required **domain, MCP servers, and Skills** for your workflow. ([GitHub][1])

### 5. Start the local debug services (optional)

To start the Issue Tracker:

```bash
issue_tracker_server
```

To start the Regression DB:

```bash
regression_db_server
```

Or start the NEXUS web services together:

```bash
start_nexus_webpages
```

These services provide local tools for working with regression results and issue data. ([GitHub][1])

### 6. Launch Claude with the NEXUS environment

```bash
claude
```

Claude can then use the configured NEXUS resources, MCPs, Skills, and workspace configuration. ([GitHub][1])

## How to Use

A typical NEXUS hardware-debug session follows this flow:

```text
Hardware Failure
      │
      ▼
Workspace Discovery
      │
      ▼
Failure Classification
      │
      ├── RTL
      ├── SystemVerilog
      ├── UVM
      ├── Regression
      ├── Log
      └── Waveform
      │
      ▼
Select MCP / Skill / Agent
      │
      ▼
Debug & Root-Cause Analysis
      │
      ▼
Search Shared Knowledge
      │
      ├── Known Failure
      │       └── Reuse Existing Root Cause
      │
      └── New Failure
              │
              ▼
         User Approval
              │
              ▼
        Create New Issue
```

### Basic workflow

Initialize the environment:

```bash
source ./init.sh
```

Start NEXUS:

```bash
nexus
```

Launch Claude:

```bash
claude
```

For example, an engineer can provide a failure such as:

```text
Regression failure:
TEST: axi_write_error_test
SEED: 184739
ERROR: AXI response timeout
WAVE: test.vcd
```

The agent can then:

1. Identify the project and verification domain.
2. Find the relevant MCP, Skill, or hardware-debug agent.
3. Analyze the regression result and relevant logs.
4. Inspect waveform data when required.
5. Determine the likely root cause.
6. Search the shared knowledge base for previous occurrences.
7. Report whether the failure is **known, similar, or new**.
8. Ask for approval before creating a new persistent issue or knowledge entry.

### Reuse Across Engineers

The main goal of NEXUS is to avoid debugging the same problem repeatedly.

Instead of:

```text
Engineer A → Debug failure → Find root cause
Engineer B → Same failure → Debug again
Engineer C → Same failure → Debug again
```

NEXUS enables:

```text
                  Shared Knowledge
                        ▲
                        │
          ┌─────────────┼─────────────┐
          │             │             │
     Engineer A    Engineer B    Engineer C
          │             │             │
          └─────────────┼─────────────┘
                        │
                 NEXUS Debug Flow
```

A known failure can therefore be identified and reused instead of being analyzed from scratch.

## Design Philosophy

NEXUS follows a simple principle:

> **Discover once. Reuse everywhere.**

The framework keeps detailed capabilities in **MCPs, Skills, agents, and shared resources** instead of putting large amounts of instructions into every project or AI session.

This helps reduce:

* Repeated context
* Token usage
* Duplicate debugging work
* Duplicate knowledge
* Repeated regression analysis
* Repeated issue investigation

The AI agent acts as an **orchestrator**. It selects the smallest set of tools needed for the current failure and uses the shared infrastructure for deeper analysis.

## 🔗 Repository

[NEXUS on GitHub](https://github.com/vinodnikhil0506/nexus?utm_source=chatgpt.com)

[1]: https://github.com/vinodnikhil0506/nexus "GitHub - vinodnikhil0506/nexus · GitHub"

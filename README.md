# Nexus

Nexus is a small project bootstrap for a hardware-debug workflow. It sets up shared resources, a per-user workspace, and local MCP/webpage services so you can run the debug tooling from a consistent environment.

## What it does

- loads the project environment from `init.sh`
- adds project tools to your `PATH`
- keeps a shared resource tree under `nexus-resources/`
- creates per-user config under `~/.nexus` and Claude config under `~/.claude`
- installs selected MCP servers and skills for your session
- helps you run the issue tracker and regression database web apps

## Pull and setup

From a clean shell:

```bash
git pull origin main
cd /path/to/nexus
python3 -m pip install -r requirements.txt
source ./init.sh
```

If `uv` is not installed yet, install it in the default location:

```bash
mkdir -p ~/.local/bin
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

## Basic flow

1. Load the environment

```bash
source ./init.sh
```

2. Start the project helper

```bash
nexus
```

This is the main entry point. It will guide you through the first setup and later menu actions.

3. Typical first-time setup

- choose a domain
- select MCP servers to install
- choose skills
- finish the setup

After that, Nexus creates your local config and Claude integration files.

## Common commands

Start the webpage services:

```bash
issue_tracker_server
regression_db_server
# or
start_nexus_webpages
```

Run Claude using the Nexus environment:

```bash
claude
```

Run the Nexus menu again later:

```bash
nexus
```

## Simple usage summary

- `source ./init.sh` sets up the environment
- `nexus` starts the main workflow
- `claude` launches Claude with the Nexus setup
- `issue_tracker_server` and `regression_db_server` start the local web tools

This is the basic loop:

```bash
source ./init.sh
nexus
claude
```

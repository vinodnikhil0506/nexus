# nexus module wrapper — bash / zsh.  Source this to activate:
#     source /path/to/nexus/init.sh

# Resolve the directory this script lives in (bash: BASH_SOURCE; zsh: $0 when sourced).
export NEXUS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

# shellcheck disable=SC2034
NEXUS_VENV_DIR="$NEXUS_ROOT/.nexus_venv"

# `source init.sh` should be safe and idempotent: it sets the environment, but it
# should not require sudo, and it should only bootstrap the project venv on first use.
if ! command -v python3 >/dev/null 2>&1; then
    echo "Install python3 and python3-venv." >&2
    return 1 2>/dev/null || exit 1
fi

if ! python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
    echo "Python 3.10+ is required for Nexus." >&2
    return 1 2>/dev/null || exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "Install python3-venv" >&2
    return 1 2>/dev/null || exit 1
fi

# Create the project-local venv once, then activate it for the current shell.
if [ ! -x "$NEXUS_VENV_DIR/bin/python" ]; then
    python3 -m venv "$NEXUS_VENV_DIR"
    "$NEXUS_VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
    "$NEXUS_VENV_DIR/bin/python" -m pip install -r "$NEXUS_ROOT/requirements.txt"
fi

if [ -f "$NEXUS_VENV_DIR/bin/activate" ]; then
    source "$NEXUS_VENV_DIR/bin/activate"
else
    echo "Error: Virtual environment activation script missing." >&2
    return 1 2>/dev/null || exit 1
fi

# `nexus` on PATH + uv/uvx. `uv` installs by default under $HOME/.local/bin,
# so put that location on PATH before running any project helpers.
cp -fr $NEXUS_ROOT/nexus-resources/src/3d.flf $NEXUS_VENV_DIR/lib64/python3.12/site-packages/pyfiglet/fonts
mkdir -p "$NEXUS_ROOT/.uv-cache"
export PATH="$NEXUS_VENV_DIR/bin:$HOME/.local/bin:$NEXUS_ROOT/nexus-resources/bin:$PATH"
export VIRTUAL_ENV="$NEXUS_VENV_DIR"
export UV_PYTHON_INSTALL_DIR="$NEXUS_VENV_DIR/bin"
export UV_CACHE_DIR="$NEXUS_ROOT/.uv-cache"

# Per-launch credential injection. Uses an array so values with spaces survive; `command
# claude` avoids recursing into this function. Secrets never touch the shell environment.
claude() {
    local -a _nexus_cred_env=()
    local _line
    while IFS= read -r _line; do
        [ -n "$_line" ] && _nexus_cred_env+=("$_line")
    done < <("$NEXUS_ROOT/nexus-resources/bin/nexus-creds" 2>/dev/null)
    env "${_nexus_cred_env[@]}" command claude "$@"
}

issue_tracker_server() {
    cd "$NEXUS_ROOT" || return
    nohup uv --directory "$NEXUS_ROOT/nexus-resources/webpages/issue_tracker" run --active server.py >/tmp/nexus_issue_tracker.log 2>&1 &
}

regression_db_server() {
    cd "$NEXUS_ROOT" || return
    nohup uv --directory "$NEXUS_ROOT/nexus-resources/webpages/regression_db" run --active server.py >/tmp/nexus_regression_db.log 2>&1 &
}

start_nexus_webpages() {
    echo "Starting Nexus web UIs in the background..."
    issue_tracker_server
    regression_db_server
    echo "Nexus web UIs launched. Logs: /tmp/nexus_issue_tracker.log and /tmp/nexus_regression_db.log"
}

start_nexus_webpages    

cat <<EOF

Nexus environment ready.
  Project root : $NEXUS_ROOT
  Virtual env  : $NEXUS_VENV_DIR
  
  Launcher     : nexus

EOF
# nexus module wrapper — bash / zsh.  Source this to activate:
#     source /path/to/nexus/init.sh

# Resolve the directory this script lives in (bash: BASH_SOURCE; zsh: $0 when sourced).
export NEXUS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

# `nexus` on PATH + uv/uvx. `uv` installs by default under $HOME/.local/bin,
# so put that location on PATH before running any project helpers.
mkdir -p "$NEXUS_ROOT/.uv-cache"
export PATH="$NEXUS_ROOT/nexus-resources/bin:$PATH"
export UV_PYTHON_INSTALL_DIR="$NEXUS_ROOT/.venv/bin"
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

# Convenience wrappers for the shared webpage servers used by the MCPs.
issue_tracker_server() {
    cd "$NEXUS_ROOT" || return
    uv --directory "$NEXUS_ROOT/nexus-resources/webpages/issue_tracker" run server.py
}

regression_db_server() {
    cd "$NEXUS_ROOT" || return
    uv --directory "$NEXUS_ROOT/nexus-resources/webpages/regression_db" run server.py
}

start_nexus_webpages() {
    issue_tracker_server &
    regression_db_server &
    wait
}
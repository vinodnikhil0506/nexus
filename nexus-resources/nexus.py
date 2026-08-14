#!/usr/bin/env python3
"""nexus — bootstrap CLI for the Universal Verification Debug Framework.

Single-file, stdlib-only (R1). Zero-argument, run-from-anywhere: on every invocation it
branches on ~/.nexus/config.toml (init once, else the menu). All shared-tree paths resolve
from $NEXUS_ROOT, never os.getcwd() (R5). Mutating actions hold an fcntl.flock (R4); every
file write is atomic (R2) and backs up a pre-existing ~/.claude/* once (R3).

This file is built up phase by phase. Phase 2 provides: the skeleton + argv guard (08),
atomic-write/backup helpers (09), the lock context manager (10), and config load/validate/
expand (11). Later phases wire init, the menu, and the actions into main().
"""
import os
import sys
import json
import fcntl
import shutil
import getpass
import hashlib
import tempfile
import tomllib
import subprocess
from pathlib import Path

# ~/.nexus is the per-user control dir (config + lock); these are fixed home-dir paths,
# NOT read from nexus.toml (R5 concerns the shared tree, not this control dir).
NEXUS_DIR = Path.home() / ".nexus"
CONFIG_PATH = NEXUS_DIR / "config.toml"
LOCK_PATH = NEXUS_DIR / "config.lock"


# --------------------------------------------------------------------------- #
# Fail-clean (R6): one line to stderr, nonzero exit — never a traceback.
# --------------------------------------------------------------------------- #
def die(msg: str, code: int = 1):
    print(f"nexus: {msg}", file=sys.stderr)
    sys.exit(code)


# --------------------------------------------------------------------------- #
# $NEXUS_ROOT resolver (R5) — never os.getcwd()
# --------------------------------------------------------------------------- #
def nexus_root() -> Path:
    r = os.environ.get("NEXUS_ROOT")
    if not r:
        die("NEXUS_ROOT is not set — load the nexus module first (it exports NEXUS_ROOT).")
    root = Path(r)
    if not root.is_dir():
        die(f"NEXUS_ROOT does not exist or is not a directory: {r}")
    return root


# --------------------------------------------------------------------------- #
# 09 — atomic write + backup/restore helpers (R2, R3)
# --------------------------------------------------------------------------- #
def atomic_write(path, data, mode: int | None = None):
    """Write `data` to `path` atomically: temp file in the SAME directory, then
    os.replace onto the target (same filesystem => atomic; a reader never sees a
    half-written file). `data` may be str or bytes. Optional `mode` chmods the result."""
    path = Path(path)
    binary = isinstance(data, (bytes, bytearray))
    # prefix deliberately avoids the substring 'tmp' so no stray "*tmp*" is ever matched.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".nexus.", suffix=".part")
    try:
        with os.fdopen(fd, "wb" if binary else "w",
                       **({} if binary else {"encoding": "utf-8"})) as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def backup_if_needed(path):
    """Before the FIRST nexus write of a ~/.claude/* file (R3): if `path` exists AND no
    `<path>.bak` exists yet, move it to `<path>.bak` (preserving the engineer's true
    original). If `<path>.bak` already exists, the current file is nexus-managed — no-op,
    so the very first backup is never overwritten."""
    path = Path(path)
    bak = Path(str(path) + ".bak")
    if path.exists() and not bak.exists():
        os.replace(str(path), str(bak))


def restore_or_remove(path):
    """Clean's per-file restore (R3): if `<path>.bak` exists, move it back over `path`
    (returning the engineer to their pre-nexus original); otherwise remove `path` if
    present (it was purely nexus-generated)."""
    path = Path(path)
    bak = Path(str(path) + ".bak")
    if bak.exists():
        os.replace(str(bak), str(path))
    elif path.exists():
        os.unlink(str(path))


# --------------------------------------------------------------------------- #
# 10 — lock context manager (R4): fcntl.flock on ~/.nexus/config.lock
# --------------------------------------------------------------------------- #
class nexus_lock:
    """Exclusive fcntl.flock held for the duration of a `with` block. Every MUTATING
    action (init, Update, Add/change domain, Rotate credentials, Clean, and any
    venv/skill/KB provisioning) runs inside it; read-only actions (Show status, Verify)
    do not. Ensures ~/.nexus/ exists WITHOUT clobbering an existing config.toml."""

    def __enter__(self):
        NEXUS_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)  # never touches config.toml
        # open in append so creating the lock file never truncates anything.
        self._fh = open(LOCK_PATH, "a+")
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)  # blocks until acquired; no busy-poll
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
        return False  # never suppress exceptions


# --------------------------------------------------------------------------- #
# 11 — config load + validate + expand (R5, R6, R7)
# --------------------------------------------------------------------------- #
def _expand_env_vars(value: str, literal_keys=(), environ=None) -> str:
    """Expand ${VAR} occurrences from `environ` (default os.environ). A VAR whose name is
    in `literal_keys` (a collected credential) is left LITERAL as ${VAR} (R7). Any other
    ${VAR} that is unset is a fail-safe BREAKAGE (missing-value error), never leakage."""
    if environ is None:
        environ = os.environ
    out = []
    i = 0
    n = len(value)
    while i < n:
        if value[i] == "$" and i + 1 < n and value[i + 1] == "{":
            end = value.find("}", i + 2)
            if end != -1:
                name = value[i + 2:end]
                if name in literal_keys:
                    out.append("${" + name + "}")
                else:
                    val = environ.get(name)
                    if val is None:
                        die(f"required environment variable {name} is not set "
                            f"(referenced in nexus.toml)")
                    out.append(val)
                i = end + 1
                continue
        out.append(value[i])
        i += 1
    return "".join(out)


def _has_internal_brace(s: str) -> bool:
    """True if `s` contains an internal {key} reference — a '{' NOT part of a ${VAR}
    (i.e. not immediately preceded by '$')."""
    return any(ch == "{" and (i == 0 or s[i - 1] != "$") for i, ch in enumerate(s))


def _resolve_braces(mapping: dict) -> dict:
    """Resolve internal {key} references among a flat str->str mapping to a fixpoint.
    A ${VAR} is left untouched here (handled separately by _expand_env_vars); only a
    '{' not preceded by '$' is treated as an internal reference."""
    resolved = dict(mapping)
    for _ in range(len(resolved) + 2):  # bounded fixpoint
        changed = False
        for k, v in list(resolved.items()):
            if not isinstance(v, str):
                continue
            out = []
            i = 0
            n = len(v)
            vchanged = False
            while i < n:
                ch = v[i]
                if ch == "{" and (i == 0 or v[i - 1] != "$"):
                    rb = v.find("}", i + 1)
                    if rb != -1:
                        ref = v[i + 1:rb]
                        rv = resolved.get(ref)
                        if isinstance(rv, str) and not _has_internal_brace(rv):
                            out.append(rv)
                            i = rb + 1
                            vchanged = True
                            continue
                out.append(ch)
                i += 1
            if vchanged:
                resolved[k] = "".join(out)
                changed = True
        if not changed:
            break
    return resolved


def load_nexus_toml(path=None) -> dict:
    """Read + validate $NEXUS_ROOT/nexus.toml (R6). Fail with ONE line, nonzero, on:
    TOML parse error, missing kb_root, a domain referencing an undefined MCP, or a
    domain whose system_prompt file is absent. Returns the parsed dict."""
    root = nexus_root()
    toml_path = Path(path) if path else (root / "nexus-resources" / "nexus.toml")
    try:
        raw = toml_path.read_bytes()
    except OSError as exc:
        die(f"cannot read nexus.toml at {toml_path}: {exc.strerror or exc}")
    try:
        cfg = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        die(f"nexus.toml is not valid TOML: {exc}")

    fw = cfg.get("framework")
    if not isinstance(fw, dict) or not fw.get("kb_root"):
        die("nexus.toml is missing [framework].kb_root")
    mcps = fw.get("mcps", {})
    domains = cfg.get("domain", [])
    if not domains:
        die("nexus.toml defines no [[domain]] blocks")
    for dom in domains:
        name = dom.get("name", "<unnamed>")
        for m in dom.get("mcps", []):
            if m not in mcps:
                die(f"domain '{name}' references MCP '{m}' not defined in [framework.mcps]")
        sp = dom.get("system_prompt")
        if not sp or not (root / "nexus-resources" / sp).is_file():
            die(f"domain '{name}' system_prompt file is absent: {sp}")
    return cfg


def resolve_framework_paths(cfg: dict) -> dict:
    """Expand the [framework] per-user path chain ({user_root}/{venv_root}/... and the
    canonical {kb_root}/* keys) plus ${USER} / non-credential ${VAR}, from os.environ.
    Returns a dict of fully-resolved absolute path strings — no {...} or ${VAR} left."""
    fw = cfg.get("framework", {})
    # collect only the scalar string path keys (skip the [framework.mcps] table etc.)
    flat = {k: v for k, v in fw.items() if isinstance(v, str)}
    braced = _resolve_braces(flat)
    out = {}
    for k, v in braced.items():
        expanded = _expand_env_vars(v)  # no literal_keys: framework path keys hold no secrets
        if "{" in expanded or "}" in expanded:
            die(f"nexus.toml [framework].{k} has an unresolved placeholder: {expanded}")
        out[k] = expanded
    return out


def load_user_config():
    """Return the parsed ~/.nexus/config.toml, or None if it does not exist (R8: its
    presence is the commit point that distinguishes first-run init from later menu)."""
    if not CONFIG_PATH.is_file():
        return None
    try:
        return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        die(f"~/.nexus/config.toml is unreadable/corrupt: {exc}")


# --------------------------------------------------------------------------- #
# Hashing helpers (pinned formats reused by Update, prompts 25/28)
# --------------------------------------------------------------------------- #
def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hash_dir(path) -> str:
    """Content hash over a directory's files (sorted relpath + bytes). Excludes any
    nexus marker file (name starting with '.nexus_') so a skill's baseline hash is a
    pure function of its real content — the skill three-way sync (28) reuses this."""
    path = Path(path)
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file() and not p.name.startswith(".nexus_")):
        h.update(f.relative_to(path).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Credential-injection helper (Part D #9): load {credentials_file} and pass
# env={**os.environ, **creds} to a specific subprocess.run — used by Verify (24)
# and available for a claude launch. Secrets stay OFF the shell and OFF disk-config.
# --------------------------------------------------------------------------- #
def load_credentials(creds_path) -> dict:
    """Parse a KEY=VALUE credentials file (not TOML; '#' comments, blank lines ok).
    Returns {} if the file is absent. Read by nothing but nexus."""
    creds = {}
    p = Path(creds_path)
    if not p.is_file():
        return creds
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        creds[k.strip()] = v.strip()
    return creds


def env_with_creds(creds: dict) -> dict:
    """Return a subprocess env = os.environ overlaid with credential values, so a
    credentialed MCP subprocess can start. Never mutates os.environ."""
    return {**os.environ, **creds}


# --------------------------------------------------------------------------- #
# nexus.toml lookups
# --------------------------------------------------------------------------- #
def domain_by_name(cfg: dict, name: str) -> dict:
    for d in cfg.get("domain", []):
        if d.get("name") == name:
            return d
    die(f"domain '{name}' is not defined in nexus.toml")


def required_mcps(cfg: dict, domain_names) -> list:
    """Ordered-unique union of the MCPs required by the given domains."""
    out = []
    for dn in domain_names:
        for m in domain_by_name(cfg, dn).get("mcps", []):
            if m not in out:
                out.append(m)
    return out


def mcp_source_dir(cfg: dict, mcp_name: str) -> Path:
    """The shared source dir for an MCP: the value after '--directory' in its args.
    Accepts either the canonical shared tree or the legacy workspace-root layout so
    user installs keep working even when the maintainer config was authored before the
    resources directory was introduced."""
    args = cfg["framework"]["mcps"][mcp_name].get("args", [])
    for i, a in enumerate(args):
        if a == "--directory" and i + 1 < len(args):
            cand = Path(_expand_env_vars(args[i + 1]))
            if cand.is_dir():
                return cand
            legacy = nexus_root() / "nexus-resources" / "mcp" / mcp_name
            if legacy.is_dir():
                return legacy
    alt = nexus_root() / "nexus-resources" / "mcp" / mcp_name
    if alt.is_dir():
        return alt
    die(f"MCP '{mcp_name}' has no --directory in its nexus.toml args")


def read_mcp_meta(cfg: dict, mcp_name: str) -> dict:
    """Return the [tool.nexus] table from an MCP's pyproject.toml ({} if absent)."""
    pj = mcp_source_dir(cfg, mcp_name) / "pyproject.toml"
    if not pj.is_file():
        return {}
    try:
        return tomllib.loads(pj.read_text(encoding="utf-8")).get("tool", {}).get("nexus", {})
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _tool_access_from_toml(tools: dict) -> dict:
    return {t: (v.get("access", "mutating") if isinstance(v, dict) else "mutating")
            for t, v in tools.items()}


def read_tool_access(cfg: dict, mcp_name: str) -> dict:
    """{tool_name: 'read-only'|'mutating'} from the MAINTAINER source [tool.nexus.tools]."""
    return _tool_access_from_toml(read_mcp_meta(cfg, mcp_name).get("tools", {}))


def read_tool_access_dir(mcp_dir: Path) -> dict:
    """{tool_name: access} from a specific MCP dir's pyproject.toml — used to read THIS
    engineer's editable copy ({mcp_root}/<name>) so locally-added tools are reflected in
    settings.json. Falls back to {} if absent/unparseable."""
    pj = mcp_dir / "pyproject.toml"
    if not pj.is_file():
        return {}
    try:
        tools = tomllib.loads(pj.read_text(encoding="utf-8")).get(
            "tool", {}).get("nexus", {}).get("tools", {})
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    return _tool_access_from_toml(tools)


def credential_keys_for_mcps(cfg: dict, mcp_names) -> list:
    """The credential var names for the given MCPs: env vars declared in an MCP's
    [tool.nexus.mcp].env_credentials AND referenced as ${VAR} in its nexus.toml env
    block. These are the names R7 keeps LITERAL in ~/.claude.json (prompt 17)."""
    keys = []
    for m in mcp_names:
        declared = set(read_mcp_meta(cfg, m).get("mcp", {}).get("env_credentials", []))
        env = cfg["framework"]["mcps"][m].get("env", {})
        for v in env.values():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                name = v[2:-1]
                if name in declared and name not in keys:
                    keys.append(name)
    return keys


def credential_keys_for(cfg: dict, domain_names) -> list:
    """Credential var names for the given domains (union across all their MCPs)."""
    return credential_keys_for_mcps(cfg, required_mcps(cfg, domain_names))


# --------------------------------------------------------------------------- #
# ~/.claude reality (R12 / contradiction #6, confirmed against Claude Code 2.1.215):
#   - user-scoped MCP servers live in ~/.claude.json under top-level "mcpServers"
#     (there is NO ~/.claude/mcp.json). nexus MERGES that key, preserving all other
#     state (projects, machineID, ...), else Claude Code would break.
#   - ~/.claude/settings.json "permissions" schema + CLAUDE.md @import DO match spec.
# --------------------------------------------------------------------------- #
CLAUDE_JSON = Path.home() / ".claude.json"
CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
SETTINGS_JSON = Path.home() / ".claude" / "settings.json"
CLAUDE_SKILLS = Path.home() / ".claude" / "skills"   # where Claude Code reads personal skills


# --------------------------------------------------------------------------- #
# 13 — init: domain pick + credential collection
# --------------------------------------------------------------------------- #
def init_pick_domain(cfg: dict) -> str:
    names = [d["name"] for d in cfg.get("domain", [])]
    print("Available domains:")
    for i, n in enumerate(names, 1):
        print(f"  {i}) {n}")
    while True:
        try:
            choice = input("Pick a domain [number]: ").strip()
        except (EOFError, KeyboardInterrupt):
            die("no domain selected (input closed) — re-run nexus to initialize.")
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return names[int(choice) - 1]
        if choice in names:
            return choice
        print("  invalid choice — enter the number or exact name.")


def _parse_selection(raw: str, items):
    """Parse a selection against `items`. NUMBERS ONLY (plus 'all'); names are NOT
    accepted. Returns (ok, chosen_list): 'all'/'*' -> all; empty ('') -> [] (none);
    comma-separated numbers -> that subset. ok is False (with a hint) on any bad token."""
    low = raw.strip().lower()
    if low in ("all", "*"):
        return True, list(items)
    if low == "":
        return True, []                      # Enter = select none
    chosen = []
    for tok in (t.strip() for t in raw.split(",") if t.strip()):
        if tok.isdigit() and 1 <= int(tok) <= len(items):
            pick = items[int(tok) - 1]
        else:
            print(f"  invalid entry: {tok!r} — use numbers 1-{len(items)} or 'all' (Enter = none).")
            return False, []
        if pick not in chosen:
            chosen.append(pick)
    return True, chosen


def _choose_subset(items, kind: str) -> list:
    """Numbered picker (numbers or 'all' only — no names) with a confirmation step.
    Pressing Enter selects NONE and goes to the confirmation; pressing Enter again there
    proceeds (so an empty selection is how you SKIP installing). Re-typing a selection at
    the confirmation makes it final and proceeds. Ctrl+C / closed input quits."""
    if not items:
        print(f"(no {kind} available)")
        return []

    def ask(msg):
        try:
            return input(msg).strip()
        except (EOFError, KeyboardInterrupt):
            die("selection cancelled (Ctrl+C) — re-run nexus to initialize.")

    print(f"Available {kind}:")
    for i, it in enumerate(items, 1):
        print(f"  {i}) {it}")

    # 1) selection — numbers or 'all'; Enter selects none. Only a bad token re-prompts.
    chosen = None
    while chosen is None:
        raw = ask(f"Select {kind} [all / numbers, comma-separated] (Enter to select none): ")
        ok, sel = _parse_selection(raw, items)
        if ok:
            chosen = sel

    # 2) confirm — Enter proceeds (even with none); a fresh selection replaces it & proceeds.
    while True:
        print(f"Selected {kind}: {', '.join(chosen) if chosen else '(none)'}")
        raw = ask("Press Enter to confirm, or re-enter a new selection: ")
        if raw == "":
            return chosen
        ok, sel = _parse_selection(raw, items)
        if ok:
            return sel


def init_select_mcps(cfg: dict, mcps) -> list:
    """Pick MCP servers to install (numbers or 'all'); Enter selects none — which SKIPS
    MCP install and moves on to the skill selection."""
    return _choose_subset(list(mcps), "MCP servers")


def available_skills() -> list:
    """Names of the shared skills (nexus-resources/skills/<name>/ carrying a SKILL.md), sorted."""
    shared = nexus_root() / "nexus-resources" / "skills"
    if not shared.is_dir():
        return []
    return sorted(p.name for p in shared.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def init_select_skills() -> list:
    """Let the engineer install all shared skills or a subset ('none' is allowed)."""
    return _choose_subset(available_skills(), "skills")


def init_collect_credentials(cfg: dict, mcp_names, paths: dict) -> list:
    """Collect each credential the SELECTED MCPs need and write {credentials_file} as
    KEY=VALUE, chmod 600, atomically (R2). If a credential is ALREADY exported in the
    engineer's shell environment (bash or csh — both land in os.environ), reuse that value
    and DON'T prompt again; otherwise prompt via getpass (never echoed)."""
    keys = credential_keys_for_mcps(cfg, mcp_names)
    creds = {}
    for k in keys:
        env_val = os.environ.get(k)
        if env_val:  # already set in the engineer's shell — use it, don't ask
            print(f"  {k}: found in your environment — using it (not prompting).")
            creds[k] = env_val
            continue
        try:
            creds[k] = getpass.getpass(f"Enter value for credential {k}: ")
        except (EOFError, KeyboardInterrupt):
            die(f"credential {k} not provided (input closed) — re-run nexus to initialize.")
    lines = ["# nexus credentials (KEY=VALUE) — chmod 600, never checked in.\n"]
    for k in keys:
        lines.append(f"{k}={creds[k]}\n")
    Path(paths["credentials_file"]).parent.mkdir(parents=True, exist_ok=True)
    atomic_write(paths["credentials_file"], "".join(lines), mode=0o600)
    return keys


# --------------------------------------------------------------------------- #
# 14 — init: per-MCP venv provisioning + sync fingerprint
# --------------------------------------------------------------------------- #
def sync_fingerprint(cfg: dict, mcp_name: str) -> str:
    """Pinned drift fingerprint (spec 'Version drift detection', reused by prompt 25):
    sha256(pyproject.toml bytes) + ':' + mtime(entry file)."""
    src = mcp_source_dir(cfg, mcp_name)
    entry = read_mcp_meta(cfg, mcp_name).get("mcp", {}).get("entry", "main.py")
    return _sha256_bytes((src / "pyproject.toml").read_bytes()) + ":" + str((src / entry).stat().st_mtime)


def provision_mcp_venv(cfg: dict, paths: dict, mcp_name: str):
    """Give this engineer their OWN editable copy of the MCP + a venv, under
    {mcp_root}/<mcp>/, and (re)install it.

    On first install the maintainer's canonical mcp/<name>/ is copied to the per-user
    {mcp_root}/<name>/ (an existing copy is LEFT AS-IS so the engineer's local edits — e.g.
    new test tools — survive). Then `uv sync` builds/updates the copy's own in-tree .venv
    (non-frozen, so newly added tools/deps in the local pyproject are picked up). Re-running
    (init or Update) is a reinstall. The maintainer source tree is never written (R9)."""
    shared_src = mcp_source_dir(cfg, mcp_name)
    if not (shared_src / "uv.lock").is_file():
        print(f"  note: shared MCP source for '{mcp_name}' is missing uv.lock; continuing with a user-local install under {paths['mcp_root']}")
    dest = Path(paths["mcp_root"]) / mcp_name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(shared_src, dest, ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", "*.pyc", ".nexus_sync_fingerprint"))
    Path(paths["uv_cache_dir"]).mkdir(parents=True, exist_ok=True)
    uv = _expand_env_vars(cfg["framework"]["mcps"][mcp_name]["command"])
    env = dict(os.environ)
    env["UV_CACHE_DIR"] = paths["uv_cache_dir"]   # per-user cache; venv defaults to dest/.venv
    try:
        subprocess.run([uv, "sync", "--directory", str(dest)],
                       env=env, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        die(f"uv not found at '{uv}' (from nexus.toml) — cannot provision MCP '{mcp_name}'")
    except subprocess.CalledProcessError as exc:
        last = (exc.stderr or "").strip().splitlines()
        die(f"uv sync failed for MCP '{mcp_name}': {last[-1] if last else exc}")
    atomic_write(dest / ".nexus_sync_fingerprint", sync_fingerprint(cfg, mcp_name))


def provision_verisight(cfg: dict, paths: dict):
    """Give this engineer their OWN editable copy of the VeriSight IP + a venv, under
    {verisight_home}/. Best-effort: VeriSight has heavy deps and no committed lock, so a
    build failure is reported as a warning (the wrapper degrades gracefully) rather than
    failing the whole init. The maintainer IP tree (ip/VeriSight) is never written."""
    src = nexus_root() / "nexus-resources" / "ip" / "VeriSight"
    if not (src / "main.py").is_file():
        print("  note: ip/VeriSight not present — skipping VeriSight install "
              "(the verisight MCP will report it at tool-call time).")
        return
    dest = Path(paths["verisight_home"])
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(
            ".venv", ".git", "__pycache__", "*.pyc", "verisight_knowledge_db", "output"))
    Path(paths["uv_cache_dir"]).mkdir(parents=True, exist_ok=True)
    uv = _expand_env_vars(cfg["framework"]["mcps"]["verisight"]["command"])
    venv = dest / ".venv"
    env = dict(os.environ)
    env["UV_CACHE_DIR"] = paths["uv_cache_dir"]
    try:
        subprocess.run([uv, "venv", str(venv)], env=env, check=True, capture_output=True, text=True)
        subprocess.run([uv, "pip", "install", "--python", str(venv / "bin" / "python"), str(dest)],
                       env=env, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print(f"  WARNING: uv not found at '{uv}' — VeriSight deps not installed.")
    except subprocess.CalledProcessError as exc:
        last = (exc.stderr or "").strip().splitlines()
        print(f"  WARNING: VeriSight deps install failed ({last[-1] if last else exc}). "
              "analyze_failure will report this until it is installed; list_examples still works.")


# --------------------------------------------------------------------------- #
# 15 — init: skills provisioning + baseline hash
# --------------------------------------------------------------------------- #
def provision_skills(cfg: dict, paths: dict, skill_names):
    """Copy the SELECTED shared skills into {skills_root}/ (per-user, editable) and record
    a baseline hash of the shared source at copy time (for the three-way sync). Idempotent:
    an already-copied skill is left as-is (may carry local edits); its baseline is ensured."""
    shared = nexus_root() / "nexus-resources" / "skills"
    dest_root = Path(paths["skills_root"])
    dest_root.mkdir(parents=True, exist_ok=True)
    for name in skill_names:
        sk = shared / name
        if not sk.is_dir():
            continue
        dest = dest_root / name
        if not dest.exists():
            shutil.copytree(sk, dest)
        baseline = dest / ".nexus_skill_baseline"
        if not baseline.exists():
            atomic_write(baseline, _hash_dir(sk))


def place_skills_in_claude(skill_names):
    """Install the SELECTED skills where Claude Code reads them: ~/.claude/skills/<name>/.
    Refreshes an existing copy. Returns the names actually placed."""
    shared = nexus_root() / "nexus-resources" / "skills"
    CLAUDE_SKILLS.mkdir(parents=True, exist_ok=True)
    placed = []
    for name in skill_names:
        sk = shared / name
        if not sk.is_dir():
            continue
        dest = CLAUDE_SKILLS / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(sk, dest, ignore=shutil.ignore_patterns(".nexus_skill_baseline"))
        placed.append(name)
    return placed


def remove_claude_skills(skill_names):
    """Remove nexus-placed skills from ~/.claude/skills/ (used by rollback and Clean).
    Drops the skills dir itself if it ends up empty."""
    for name in skill_names or []:
        shutil.rmtree(CLAUDE_SKILLS / name, ignore_errors=True)
    try:
        if CLAUDE_SKILLS.is_dir() and not any(CLAUDE_SKILLS.iterdir()):
            CLAUDE_SKILLS.rmdir()
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 16 — init: KB dir (empty) + kb/contrib/${USER} symlink
# --------------------------------------------------------------------------- #
def provision_kb(cfg: dict, paths: dict):
    """Create {kb_user_dir}/ (empty, 755 — never seed KB files, R10) and the single
    shared-tree symlink kb/contrib/${USER} -> {kb_user_dir} (idempotent). Requires
    kb/contrib/ to already exist — reports and stops otherwise (R6)."""
    contrib = nexus_root() / "nexus-resources" / "kb" / "contrib"
    if not contrib.is_dir():
        die("workspace not provisioned by maintainer: kb/contrib/ is absent")
    user_root = Path(paths["user_root"])
    user_root.mkdir(parents=True, exist_ok=True)
    os.chmod(user_root, 0o755)  # peers traverse to kb/
    kb_user = Path(paths["kb_user_dir"])
    kb_user.mkdir(parents=True, exist_ok=True)
    os.chmod(kb_user, 0o755)    # peers read it via the symlink
    user = os.environ.get("USER") or getpass.getuser()
    try:
        os.symlink(str(kb_user), str(contrib / user))  # the ONLY shared-tree content write
    except FileExistsError:
        pass


# --------------------------------------------------------------------------- #
# 17 — init: write ~/.claude.json  (merge mcpServers; R12 reality)
# --------------------------------------------------------------------------- #
def write_mcp_json(cfg: dict, paths: dict, installed_mcps, cred_keys, backup: bool = True):
    """Merge an `mcpServers` block into ~/.claude.json (R12: the real MCP config file),
    preserving all other Claude Code state. Rewrite each server's `--directory` to THIS
    engineer's editable copy under {mcp_root}/<m> (so their local tools run; uv uses that
    copy's own .venv). Inject UV_CACHE_DIR, and VERISIGHT_HOME (the per-user VeriSight copy)
    for the verisight wrapper. Expand path ${VAR}; keep credential ${VAR} literal (R7).
    Backup-before-clobber + atomic (R2, R3). `backup` True only on the FIRST nexus write."""
    servers = {}
    for m in installed_mcps:
        spec = cfg["framework"]["mcps"][m]
        per_user_dir = str(Path(paths["mcp_root"]) / m)  # the engineer's editable copy
        args, rewrite_next = [], False
        for a in spec.get("args", []):
            if rewrite_next:
                args.append(per_user_dir)  # point at the per-user copy, not the shared source
                rewrite_next = False
                continue
            ea = _expand_env_vars(a, cred_keys)
            args.append(ea)
            if ea == "--directory":
                rewrite_next = True
        toml_env = {k: _expand_env_vars(v, cred_keys) for k, v in spec.get("env", {}).items()}
        injected = {"UV_CACHE_DIR": paths["uv_cache_dir"]}
        if m == "verisight":
            injected["VERISIGHT_HOME"] = paths["verisight_home"]  # per-user VeriSight copy
        servers[m] = {
            "type": "stdio",
            "command": _expand_env_vars(spec["command"], cred_keys),
            "args": args,
            "env": {**injected, **toml_env},  # nexus.toml env wins; injected fills gaps
        }
    existing = {}
    if CLAUDE_JSON.is_file():
        try:
            existing = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing["mcpServers"] = servers
    if backup:
        backup_if_needed(CLAUDE_JSON)
    atomic_write(CLAUDE_JSON, json.dumps(existing, indent=2) + "\n")


# --------------------------------------------------------------------------- #
# 18 — init: write ~/.claude/CLAUDE.md  (@import composition)
# --------------------------------------------------------------------------- #
def write_claude_md(cfg: dict, paths: dict, active_domains, backup: bool = True):
    """The only per-engineer file. Header + the single per-engineer KB write-path line
    (expanded) + absolute @import lines rooted at the shared NEXUS resource tree.
    kb-paths/preflight/debug-router/postflight appear exactly once; per-domain files
    repeat per active domain. `backup` True only on the first nexus write (init);
    regen passes False (R3)."""
    root = str(nexus_root() / "nexus-resources")
    label = active_domains[0] if len(active_domains) == 1 else ", ".join(active_domains)
    lines = [
        f"# Universal Debug Framework - {label} domain",
        "> Generated by nexus. Do not edit manually - run `nexus` and choose Update to regenerate.",
        "",
        "## KB write path (this engineer only)",
        f"Post-flight writes ONLY under: {paths['kb_user_dir']}",
        "",
        "## Mandatory Framework Context",
        f"@{root}/framework/debug-router.md",
        "",
        "## On-Demand Resources (Read ONLY when explicitly required)",
        f"- Framework Paths: `{root}/framework/kb-paths.md`",
        f"- Preflight Checks: `{root}/framework/preflight.md`",
        f"- Artifact Order: `{root}/domains/{active_domains[0]}/artifact_order.md`",
        f"- Fingerprint Map: `{root}/domains/{active_domains[0]}/fingerprint.md`",
        f"- Resource Map: `{root}/domains/{active_domains[0]}/resource_map.md`",
        f"- Postflight Checks: `{root}/framework/postflight.md`",
        f"- System Prompt: `{root}/domains/{active_domains[0]}/system_prompt.md`",
    ]
    lines.append("")
    CLAUDE_MD.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        backup_if_needed(CLAUDE_MD)
    atomic_write(CLAUDE_MD, "\n".join(lines))


# --------------------------------------------------------------------------- #
# 19 — init: write ~/.claude/settings.json  (pre-approve read-only tools only)
# --------------------------------------------------------------------------- #
def write_settings_json(cfg: dict, paths: dict, active_domains, installed_mcps, backup: bool = True):
    """Pre-approve: Read on the UNION of resource_map paths + kb_root; Read/Edit/Write on
    {kb_user_dir} ONLY; and only the READ-ONLY MCP tools (undeclared => mutating => not
    pre-approved). Merge into existing settings.json (preserve theme/model), backup +
    atomic (R2, R3). `backup` True only on the first nexus write (init); regen False."""
    allow = []
    seen = set()
    for d in active_domains:
        for entry in domain_by_name(cfg, d).get("resource_map", []):
            path = entry.split(":", 1)[1].strip() if ":" in entry else entry.strip()
            path = _expand_env_vars(path)
            if path and path not in seen:
                seen.add(path)
                allow.append(f"Read({path}/**)")
    allow.append(f"Read({paths['kb_root']}/**)")           # whole-team KB read (incl contrib/**)
    kb_user = paths["kb_user_dir"]
    allow.append(f"Read({kb_user}/**)")
    allow.append(f"Edit({kb_user}/**)")                    # the ONLY write paths
    allow.append(f"Write({kb_user}/**)")
    for m in installed_mcps:
        # Prefer THIS engineer's editable copy so locally-added tools are honored;
        # fall back to the maintainer source before the copy exists.
        mcp_dir = Path(paths["mcp_root"]) / m
        access_map = read_tool_access_dir(mcp_dir) or read_tool_access(cfg, m)
        for tool, access in sorted(access_map.items()):
            if access == "read-only":
                allow.append(f"mcp__{m}__{tool}")
    existing = {}
    if SETTINGS_JSON.is_file():
        try:
            existing = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing["permissions"] = {"allow": allow, "deny": [], "ask": []}
    SETTINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        backup_if_needed(SETTINGS_JSON)
    atomic_write(SETTINGS_JSON, json.dumps(existing, indent=2) + "\n")


# --------------------------------------------------------------------------- #
# 20 — init: write ~/.nexus/config.toml (LAST — the commit point) + rollback
# --------------------------------------------------------------------------- #
def write_user_config(cfg: dict, paths: dict, active_domains, mcps=None, skills=None):
    """Record the chosen domain(s) + KB pointer (and, at init, the selected MCPs and
    skills). Written LAST (R8 commit point)."""
    body = ["[nexus]"]
    body.append("domains = [" + ", ".join(f'"{d}"' for d in active_domains) + "]")
    if mcps is not None:
        body.append("mcps = [" + ", ".join(f'"{m}"' for m in mcps) + "]")
    if skills is not None:
        body.append("skills = [" + ", ".join(f'"{s}"' for s in skills) + "]")
    body.append(f'kb_user_dir = "{paths["kb_user_dir"]}"')
    body.append(f'credentials_file = "{paths["credentials_file"]}"')
    body.append("")
    NEXUS_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    atomic_write(CONFIG_PATH, "\n".join(body))


def rollback_init(paths: dict, skills=None):
    """Undo a partially-completed init (R8): restore/remove the ~/.claude/* files, drop
    this engineer's per-user installs (MCP copies, VeriSight copy, skills copy), placed
    ~/.claude/skills, and credentials, and ensure NO config.toml — but NEVER touch
    {kb_user_dir} or the kb/contrib/${USER} symlink (durable KB, R11)."""
    for f in (CLAUDE_JSON, CLAUDE_MD, SETTINGS_JSON):
        try:
            restore_or_remove(f)
        except OSError:
            pass
    remove_claude_skills(skills if skills is not None else available_skills())
    for d in (paths.get("mcp_root"), paths.get("verisight_home"), paths.get("skills_root")):
        if d:
            shutil.rmtree(d, ignore_errors=True)
    try:
        os.unlink(paths["credentials_file"])
    except OSError:
        pass
    try:
        os.unlink(CONFIG_PATH)  # commit point — must be absent after a failed run
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 21 — init: wire up the full init flow under one lock, commit-last
# --------------------------------------------------------------------------- #
def verify_prereqs(cfg: dict, active_domains, installed_mcps):
    """Report-never-create (R6): stop if any shared prerequisite the init needs is
    missing — rendered domain files, framework files, each MCP's uv.lock, kb/contrib/."""
    root = nexus_root()
    paths = resolve_framework_paths(cfg)
    user_root = paths.get("user_root", str(root / "nexus-workspace" / "users" / (os.environ.get("USER") or getpass.getuser())))
    for d in active_domains:
        for f in ("artifact_order.md", "fingerprint.md", "resource_map.md", "system_prompt.md"):
            if not (root / "nexus-resources" / "domains" / d / f).is_file():
                die(f"workspace not provisioned by maintainer: missing domains/{d}/{f} "
                    f"(run nexus-render)")
    for f in ("preflight.md", "postflight.md", "kb-paths.md", "debug-router.md"):
        if not (root / "nexus-resources" / "framework" / f).is_file():
            die(f"workspace not provisioned by maintainer: missing framework/{f} (run nexus-render)")
    if not (root / "nexus-resources" / "kb" / "contrib").is_dir():
        die("workspace not provisioned by maintainer: kb/contrib/ is absent")


def run_init(cfg: dict) -> int:
    paths = resolve_framework_paths(cfg)
    with nexus_lock():
        if CONFIG_PATH.is_file():  # a concurrent run committed first — idempotent
            print("nexus is already initialized — run `nexus` for the menu.")
            return 0
        domain = init_pick_domain(cfg)
        active = [domain]
        mcps = init_select_mcps(cfg, required_mcps(cfg, active))  # list domain MCPs; pick all/subset
        verify_prereqs(cfg, active, mcps)  # before creating anything (R6)
        selected_skills = []
        try:
            cred_keys = init_collect_credentials(cfg, mcps, paths)  # creds for SELECTED mcps only
            for m in mcps:
                provision_mcp_venv(cfg, paths, m)                  # per-user editable copy + venv
            if "verisight" in mcps:
                provision_verisight(cfg, paths)                    # per-user editable VeriSight IP + venv
            selected_skills = init_select_skills()                 # list skills; pick all/subset/none
            provision_skills(cfg, paths, selected_skills)
            place_skills_in_claude(selected_skills)                # install into ~/.claude/skills
            provision_kb(cfg, paths)
            write_mcp_json(cfg, paths, mcps, cred_keys)
            write_claude_md(cfg, paths, active)
            write_settings_json(cfg, paths, active, mcps)
            write_user_config(cfg, paths, active, mcps, selected_skills)  # LAST — commit point (R8)
        except SystemExit:
            rollback_init(paths, selected_skills)
            raise
        except BaseException:
            rollback_init(paths, selected_skills)
            die("init failed — rolled back partial setup; re-run nexus to try again.")
    if mcps:
        print(f"Installed MCP servers (your editable copies under {paths['mcp_root']}): {', '.join(mcps)}")
        print("Add local test tools to a copy, then re-run `nexus` -> Update to reinstall it.")
    else:
        print("Installed MCP servers: (none) — skipped; run `nexus` -> Update to add some later.")
    print(f"Installed skills (in ~/.claude/skills): {', '.join(selected_skills) if selected_skills else '(none)'}")
    print("Setup complete - run `claude` to start.")
    return 0


# --------------------------------------------------------------------------- #
# 12 — init-vs-menu branch; menu is wired in Phase 4.
# --------------------------------------------------------------------------- #
def print_header(user_cfg: dict):
    doms = user_cfg.get("nexus", {}).get("domains", [])
    if len(doms) == 1:
        print(f"nexus - domain: {doms[0]}")
    else:
        print(f"nexus - domains: {', '.join(doms)}")


# --------------------------------------------------------------------------- #
# 23 — menu action 1: Show status (LOCAL ONLY, no lock, no central comparison)
# --------------------------------------------------------------------------- #
def _count_entries(md_path) -> int:
    """Plain count of entries in an agent-authored KB markdown file = number of markdown
    headings; 0 if the file does not exist yet (nexus never seeds it, R10)."""
    p = Path(md_path)
    if not p.is_file():
        return 0
    return sum(1 for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
               if ln.lstrip().startswith("#"))


def action_show_status(cfg: dict, user_cfg: dict):
    """LOCAL ONLY (R9): configured domain(s), the installed-MCP set = subdirs of
    {venv_root} (NO up-to-date/outdated flag), the agent + config paths, kb_root, and
    THIS engineer's own entry counts. Never reads nexus.toml's MCP registry for
    comparison; never computes a fingerprint; never prints an 'updates available' hint."""
    paths = resolve_framework_paths(cfg)  # uses only [framework] path keys, not the MCP list
    domains = user_cfg.get("nexus", {}).get("domains", [])
    venv_root = Path(paths["mcp_root"])
    installed = sorted(p.name for p in venv_root.iterdir() if p.is_dir()) if venv_root.is_dir() else []
    kb_user = paths["kb_user_dir"]

    print("  -- USER --")
    print(f"  domain(s):        {', '.join(domains) if domains else '(none)'}")
    print(f"  installed MCPs:   {', '.join(installed) if installed else '(none)'}")
    print(f"  agent config:     {CLAUDE_MD}")
    print(f"  nexus config:     {CONFIG_PATH}")
    print("  -- SHARED --")
    print(f"  kb_root:          {paths['kb_root']}")
    print(f"  your sig_db.md:   {_count_entries(Path(kb_user) / 'sig_db.md')} entries")
    print(f"  your heuristics:  {_count_entries(Path(kb_user) / 'heuristics.md')} entries")


# --------------------------------------------------------------------------- #
# 24 — menu action 2: Verify installed MCP servers (LOCAL ONLY, no lock)
# --------------------------------------------------------------------------- #
def mcp_launch_env(cfg: dict, paths: dict, mcp_name: str, creds: dict) -> dict:
    """Build the env to actually LAUNCH an MCP subprocess: os.environ + credentials
    (Part D #9) + injected UV_PROJECT_ENVIRONMENT/UV_CACHE_DIR + the server's nexus.toml
    env with ALL ${VAR} expanded (credentials resolved from `creds`, so the real token
    reaches the child)."""
    base = {**os.environ, **creds}
    spec = cfg["framework"]["mcps"][mcp_name]
    env_block = {k: _expand_env_vars(v, environ=base) for k, v in spec.get("env", {}).items()}
    injected = {"UV_CACHE_DIR": paths["uv_cache_dir"]}  # venv defaults to the copy's .venv
    if mcp_name == "verisight":
        injected["VERISIGHT_HOME"] = paths["verisight_home"]  # per-user VeriSight copy
    return {**base, **injected, **env_block}


def ping_mcp(cfg: dict, paths: dict, mcp_name: str, creds: dict) -> bool:
    """Spawn the server briefly (empty JSON-RPC initialize; 3s timeout) and report
    liveness. A server that fails on a missing env/credential exits nonzero => fail
    (the correct, expected result), never a crash of nexus."""
    spec = cfg["framework"]["mcps"][mcp_name]
    per_user_dir = str(Path(paths["mcp_root"]) / mcp_name)  # verify the engineer's actual copy
    cmd, rewrite_next = [_expand_env_vars(spec["command"])], False
    for a in spec.get("args", []):
        if rewrite_next:
            cmd.append(per_user_dir)
            rewrite_next = False
            continue
        ea = _expand_env_vars(a)
        cmd.append(ea)
        if ea == "--directory":
            rewrite_next = True
    env = mcp_launch_env(cfg, paths, mcp_name, creds)
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env)
    except OSError:
        return False
    init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
    try:
        out, _ = proc.communicate(input=init, timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return False
    return proc.returncode == 0 and '"result"' in (out or "")


def action_verify(cfg: dict, user_cfg: dict):
    """Verify installed servers (R9: set = {venv_root}/*). Ping each chosen server, then
    check kb_root readable and {kb_user_dir} writable via a temp probe (removed after).
    Read-only action: no lock (R4)."""
    paths = resolve_framework_paths(cfg)
    venv_root = Path(paths["mcp_root"])
    installed = sorted(p.name for p in venv_root.iterdir() if p.is_dir()) if venv_root.is_dir() else []
    if not installed:
        print("  no MCP servers installed.")
        return
    targets = installed
    ans = input(f"Verify all {len(installed)} installed servers, or just one? [A/number]: ").strip().lower()
    if ans not in ("", "a", "all"):
        for i, n in enumerate(installed, 1):
            print(f"  {i}) {n}")
        pick = input("Which server [number]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(installed):
            targets = [installed[int(pick) - 1]]
        else:
            print("  invalid choice — verifying all.")

    creds = load_credentials(paths["credentials_file"])  # Part D #9: inject per-launch
    for m in targets:
        if m not in cfg["framework"]["mcps"]:
            print(f"  {m}: SKIP (installed but not defined in nexus.toml)")
            continue
        ok = ping_mcp(cfg, paths, m, creds)
        print(f"  {m}: {'PASS' if ok else 'FAIL'}")

    # kb_root readable?
    kb_root = paths["kb_root"]
    print(f"  kb_root readable: {'yes' if os.access(kb_root, os.R_OK | os.X_OK) else 'no'} ({kb_root})")
    # {kb_user_dir} writable via temp probe (only here, removed after) — never shared kb_root
    kb_user = Path(paths["kb_user_dir"])
    writable = False
    if kb_user.is_dir():
        try:
            fd, tmp = tempfile.mkstemp(dir=str(kb_user), prefix=".nexus.probe.")
            os.close(fd)
            os.unlink(tmp)
            writable = True
        except OSError:
            writable = False
    print(f"  {kb_user} writable: {'yes' if writable else 'no'}")


# --------------------------------------------------------------------------- #
# 25 — Update: MCP drift detection (pure hashlib/os.stat, no subprocess, R9)
# --------------------------------------------------------------------------- #
def detect_mcp_drift(cfg: dict, paths: dict) -> list:
    """Return installed MCPs ({venv_root}/*) whose shared-source fingerprint no longer
    matches the stored .nexus_sync_fingerprint. Compare only — never resync here."""
    venv_root = Path(paths["mcp_root"])
    outdated = []
    if not venv_root.is_dir():
        return outdated
    for d in sorted(p for p in venv_root.iterdir() if p.is_dir()):
        m = d.name
        if m not in cfg["framework"]["mcps"]:
            continue
        try:
            current = sync_fingerprint(cfg, m)
        except OSError:
            continue
        marker = d / ".nexus_sync_fingerprint"
        stored = marker.read_text(encoding="utf-8") if marker.is_file() else None
        if stored != current:
            outdated.append(m)
    return outdated


# --------------------------------------------------------------------------- #
# 26 — Update: stale shared-content note (report-only; pinned stamp; no `re`, R1)
# --------------------------------------------------------------------------- #
_STAMP_PREFIX = "<!-- rendered-from: "
_STAMP_SUFFIX = " -->"


def _read_stamp(path) -> str | None:
    """Read the pinned rendered-from stamp (trailing HTML comment) — the ONE format the
    render writer (33) also uses. Returns the 64-hex sha256 or None."""
    p = Path(path)
    if not p.is_file():
        return None
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    while lines and lines[-1].strip() == "":
        lines.pop()
    if not lines:
        return None
    last = lines[-1].strip()
    if last.startswith(_STAMP_PREFIX) and last.endswith(_STAMP_SUFFIX):
        h = last[len(_STAMP_PREFIX):-len(_STAMP_SUFFIX)].strip()
        if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
            return h
    return None


def detect_stale_shared_content(cfg: dict, active_domains):
    """Report-only (R6): if any active domain's rendered files or the framework files
    carry a rendered-from stamp != sha256(current nexus.toml), print ONE informational
    line. Engineer-facing nexus has no write access to the shared tree — never re-render."""
    root = nexus_root()
    cur = _sha256_bytes((root / "nexus-resources" / "nexus.toml").read_bytes())
    files = []
    for d in active_domains:
        for f in ("artifact_order.md", "fingerprint.md", "resource_map.md"):
            files.append(root / "nexus-resources" / "domains" / d / f)
    for f in ("preflight.md", "postflight.md", "kb-paths.md"):
        files.append(root / "nexus-resources" / "framework" / f)
    if any(_read_stamp(f) != cur for f in files):
        print(f"  Note: shared content for domain(s) '{', '.join(active_domains)}' was rendered "
              f"from an older nexus.toml than the current one — your maintainer re-renders it; "
              f"nothing to do here.")


# --------------------------------------------------------------------------- #
# 27 — Update: install newly-added domain MCPs + regenerate the three ~/.claude files
# --------------------------------------------------------------------------- #
def update_install_new_mcps_and_regen(cfg: dict, user_cfg: dict, paths: dict, active_domains):
    """If an ACTIVE domain's mcps now include a server not in {venv_root}, offer to
    install it (only newly-added MCPs of already-active domains — never a new domain).
    Then regenerate ~/.claude.json, CLAUDE.md, settings.json for the current domain(s)."""
    venv_root = Path(paths["mcp_root"])
    installed = set(p.name for p in venv_root.iterdir() if p.is_dir()) if venv_root.is_dir() else set()
    wanted = required_mcps(cfg, active_domains)
    new = [m for m in wanted if m not in installed]
    if new:
        ans = input(f"  {len(new)} new MCP(s) available for your domain: {', '.join(new)} "
                    f"- install now? [y/N]: ").strip().lower()
        if ans in ("y", "yes"):
            for m in new:
                provision_mcp_venv(cfg, paths, m)
                installed.add(m)
                print(f"    installed {m}.")
        else:
            print("  skipped; they remain uninstalled.")
    active_installed = [m for m in wanted if m in installed]
    cred_keys = credential_keys_for(cfg, active_domains)
    write_mcp_json(cfg, paths, active_installed, cred_keys, backup=False)   # regen: never re-backup (R3)
    write_claude_md(cfg, paths, active_domains, backup=False)
    write_settings_json(cfg, paths, active_domains, active_installed, backup=False)
    print("  regenerated ~/.claude.json, CLAUDE.md, settings.json.")


# --------------------------------------------------------------------------- #
# 28 — Update: three-way skill sync (baseline separates local-edit from central-update)
# --------------------------------------------------------------------------- #
def update_sync_skills(cfg: dict, paths: dict):
    """For each skill in {skills_root}, compare shared-now (S), local (L), baseline (B):
      L==B, S!=B -> updated centrally, untouched locally -> offer to pull
      L!=B, S==B -> locally edited, no central change    -> skip, leave as-is
      L!=B, S!=B -> both changed                         -> skip + WARN (would clobber)
      L==B, S==B -> nothing."""
    shared_root = nexus_root() / "nexus-resources" / "skills"
    dest_root = Path(paths["skills_root"])
    if not dest_root.is_dir():
        return
    for dest in sorted(p for p in dest_root.iterdir() if p.is_dir()):
        name = dest.name
        shared = shared_root / name
        if not shared.is_dir():
            continue  # skill removed centrally — leave the local copy alone
        baseline_file = dest / ".nexus_skill_baseline"
        B = baseline_file.read_text(encoding="utf-8").strip() if baseline_file.is_file() else None
        S = _hash_dir(shared)
        L = _hash_dir(dest)
        if B is None:
            print(f"  skill '{name}': no baseline recorded — cannot three-way sync; skipped.")
            continue
        if L == B and S == B:
            continue
        if L == B and S != B:
            ans = input(f"  skill '{name}' updated centrally — pull new version? [y/N]: ").strip().lower()
            if ans in ("y", "yes"):
                shutil.rmtree(dest)
                shutil.copytree(shared, dest)
                atomic_write(dest / ".nexus_skill_baseline", _hash_dir(shared))
                print(f"    pulled '{name}'.")
            else:
                print(f"    left '{name}' as-is.")
        elif L != B and S == B:
            print(f"  skill '{name}': locally edited, no central change — left as-is.")
        else:  # L != B and S != B
            print(f"  skill '{name}': WARNING both local and central changed — a pull would "
                  f"clobber your edits; skipped. Reconcile by hand.")


# --------------------------------------------------------------------------- #
# 29 — assemble menu action 3: Update (the ONLY central-comparison action; under lock)
# --------------------------------------------------------------------------- #
def action_update(cfg: dict, user_cfg: dict):
    """USER-DRIVEN-BY-CENTRAL. Under one lock (R4), run the four sub-behaviors in order.
    Never touches credentials and never changes the configured domain."""
    paths = resolve_framework_paths(cfg)
    active = user_cfg.get("nexus", {}).get("domains", [])
    with nexus_lock():
        # (1) MCP drift — report, then resync only the engineer-selected ones
        outdated = detect_mcp_drift(cfg, paths)
        if outdated:
            print(f"  outdated MCP(s): {', '.join(outdated)}")
            ans = input("  resync which? [all / comma-separated names / none]: ").strip().lower()
            if ans in ("all", "a"):
                sel = outdated
            elif ans in ("none", "n", ""):
                sel = []
            else:
                sel = [x.strip() for x in ans.split(",") if x.strip() in outdated]
            for m in sel:
                provision_mcp_venv(cfg, paths, m)  # re-provision rewrites the marker
                print(f"    resynced {m}.")
        else:
            print("  all installed MCPs are current.")
        # (2) stale shared content — report-only
        detect_stale_shared_content(cfg, active)
        # (3) install newly-added domain MCPs + regenerate the three ~/.claude files
        update_install_new_mcps_and_regen(cfg, user_cfg, paths, active)
        # (4) three-way skill sync
        update_sync_skills(cfg, paths)


# --------------------------------------------------------------------------- #
# Credentials-file writer (shared by init 13, add-domain 30, rotate 31)
# --------------------------------------------------------------------------- #
def write_credentials_file(paths: dict, creds: dict):
    """Rewrite {credentials_file} as KEY=VALUE (sorted), chmod 600, atomically (R2)."""
    lines = ["# nexus credentials (KEY=VALUE) — chmod 600, never checked in.\n"]
    for k in sorted(creds):
        lines.append(f"{k}={creds[k]}\n")
    Path(paths["credentials_file"]).parent.mkdir(parents=True, exist_ok=True)
    atomic_write(paths["credentials_file"], "".join(lines), mode=0o600)


# --------------------------------------------------------------------------- #
# 30 — menu action 4: Add or change domain (additive; multi-domain union; under lock)
# --------------------------------------------------------------------------- #
def action_add_change_domain(cfg: dict, user_cfg: dict):
    """Pick any nexus.toml domain (incl. inactive). Reuse credentials already collected
    for shared MCPs (never re-prompt); prompt only for genuinely-new credentials. Provision
    any not-yet-installed MCPs, then regenerate the three ~/.claude files for the UNION of
    active domains and update the config domain field. Under lock (R4); R6 for missing files."""
    paths = resolve_framework_paths(cfg)
    with nexus_lock():
        active = list(user_cfg.get("nexus", {}).get("domains", []))
        all_domains = [d["name"] for d in cfg.get("domain", [])]
        print("Available domains:")
        for i, n in enumerate(all_domains, 1):
            print(f"  {i}) {n}{' (active)' if n in active else ''}")
        try:
            choice = input("Add/select domain [number]: ").strip()
        except (EOFError, KeyboardInterrupt):
            die("no domain selected — nothing changed.")
        if choice.isdigit() and 1 <= int(choice) <= len(all_domains):
            picked = all_domains[int(choice) - 1]
        elif choice in all_domains:
            picked = choice
        else:
            die(f"invalid domain choice: {choice}")

        # R6: the picked domain's rendered files must already exist — report, never create.
        for f in ("artifact_order.md", "fingerprint.md", "resource_map.md", "system_prompt.md"):
            if not (nexus_root() / "nexus-resources" / "domains" / picked / f).is_file():
                die(f"workspace not provisioned by maintainer: missing domains/{picked}/{f}")

        new_active = active + ([picked] if picked not in active else [])

        # credentials: reuse existing; prompt ONLY for genuinely-new keys
        creds = load_credentials(paths["credentials_file"])
        new_keys = [k for k in credential_keys_for(cfg, new_active) if k not in creds]
        for k in new_keys:
            try:
                creds[k] = getpass.getpass(f"Enter value for credential {k}: ")
            except (EOFError, KeyboardInterrupt):
                die(f"credential {k} not provided — nothing changed.")
        if new_keys:
            write_credentials_file(paths, creds)

        # provision any MCPs not yet installed for the union
        venv_root = Path(paths["mcp_root"])
        installed = set(p.name for p in venv_root.iterdir() if p.is_dir()) if venv_root.is_dir() else set()
        for m in required_mcps(cfg, new_active):
            if m not in installed:
                provision_mcp_venv(cfg, paths, m)
                installed.add(m)

        active_installed = [m for m in required_mcps(cfg, new_active) if m in installed]
        cred_keys = credential_keys_for(cfg, new_active)
        # regen (config already exists): never re-backup nexus's own output (R3)
        write_mcp_json(cfg, paths, active_installed, cred_keys, backup=False)
        write_claude_md(cfg, paths, new_active, backup=False)          # one block/domain; shared once
        write_settings_json(cfg, paths, new_active, active_installed, backup=False)  # read paths = union
        write_user_config(cfg, paths, new_active)        # config lists all active domains
    print(f"  active domain(s): {', '.join(new_active)}")


# --------------------------------------------------------------------------- #
# 31 — menu action 5: Rotate credentials (only {credentials_file}; under lock)
# --------------------------------------------------------------------------- #
def action_rotate_credentials(cfg: dict, user_cfg: dict):
    """List credential names (values MASKED), rotate the selected ones (getpass), rewrite
    {credentials_file} atomically at 600. Touches nothing else. Under lock (R4)."""
    paths = resolve_framework_paths(cfg)
    with nexus_lock():
        creds = load_credentials(paths["credentials_file"])
        if not creds:
            print("  no credentials to rotate.")
            return
        names = sorted(creds)
        print("Credentials (values masked):")
        for i, k in enumerate(names, 1):
            print(f"  {i}) {k} = {'*' * 8}")
        try:
            sel = input("Rotate which? [all / comma-separated names or numbers]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("  aborted — nothing changed.")
            return
        if sel.lower() in ("all", "a"):
            chosen = set(names)
        else:
            chosen = set()
            for tok in sel.split(","):
                tok = tok.strip()
                if tok.isdigit() and 1 <= int(tok) <= len(names):
                    chosen.add(names[int(tok) - 1])
                elif tok in creds:
                    chosen.add(tok)
        ordered = [k for k in names if k in chosen]
        if not ordered:
            print("  nothing selected — nothing changed.")
            return
        for k in ordered:
            try:
                creds[k] = getpass.getpass(f"New value for {k}: ")
            except (EOFError, KeyboardInterrupt):
                die(f"rotation of {k} aborted — nothing written.")
        write_credentials_file(paths, creds)
    print("  credentials rotated (effective on the next claude launch).")


# --------------------------------------------------------------------------- #
# 32 — menu action 6: Clean (typed 'yes'; restore .bak; NEVER delete KB; under lock)
# --------------------------------------------------------------------------- #
def action_clean(cfg: dict, user_cfg: dict):
    """Show exactly what is removed AND preserved, require a typed 'yes', then remove THIS
    engineer's own per-user install + state: MCP copies ({mcp_root}), VeriSight copy
    ({verisight_home}), skills copy, uv cache, placed ~/.claude skills, credentials, config,
    and the ~/.claude/* wiring. NEVER deletes {kb_user_dir} or the kb/contrib/${USER}
    symlink (durable KB, R11). Under lock (R4)."""
    paths = resolve_framework_paths(cfg)
    with nexus_lock():
        print("Clean will REMOVE (this engineer's own install + state):")
        print(f"  - MCP copies:    {paths['mcp_root']}")
        print(f"  - VeriSight:     {paths['verisight_home']}")
        print(f"  - uv cache:      {paths['uv_cache_dir']}")
        print(f"  - skills:        {paths['skills_root']}")
        print(f"  - claude skills: {CLAUDE_SKILLS}/<nexus-placed>")
        print(f"  - credentials:   {paths['credentials_file']}")
        print(f"  - nexus config:  {CONFIG_PATH}")
        print(f"  - ~/.claude:     CLAUDE.md, settings.json, .claude.json (restored from .bak if present)")
        print("Clean will PRESERVE (durable KB — never removed):")
        print(f"  - {paths['kb_user_dir']} + kb/contrib/"
              f"{os.environ.get('USER') or getpass.getuser()} symlink")
        try:
            ans = input('Type "yes" to proceed (anything else aborts): ').strip()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans != "yes":
            print("  aborted — nothing changed.")
            return
        for d in (paths["mcp_root"], paths["verisight_home"], paths["uv_cache_dir"], paths["skills_root"]):
            shutil.rmtree(d, ignore_errors=True)
        placed = user_cfg.get("nexus", {}).get("skills") if user_cfg else None
        remove_claude_skills(placed if placed is not None else available_skills())
        for f in (paths["credentials_file"], str(CONFIG_PATH)):
            try:
                os.unlink(f)
            except OSError:
                pass
        # restore engineer's pre-nexus originals (or remove nexus-generated), R3
        for f in (CLAUDE_MD, SETTINGS_JSON, CLAUDE_JSON):
            restore_or_remove(f)
        # {kb_user_dir} + kb/contrib/${USER} deliberately untouched (R11)
    print("  clean complete — run nexus to re-initialize.")


# --------------------------------------------------------------------------- #
# 22 — menu loop (7 items; read-only actions take no lock)
# --------------------------------------------------------------------------- #
def run_menu(cfg: dict, user_cfg: dict) -> int:
    print_header(user_cfg)
    actions = {
        "1": action_show_status,
        "2": action_verify,
        "3": action_update,
        "4": action_add_change_domain,
        "5": action_rotate_credentials,
        "6": action_clean,
    }
    while True:
        print()
        print("  1) Show status")
        print("  2) Verify")
        print("  3) Update")
        print("  4) Add or change domain")
        print("  5) Rotate credentials")
        print("  6) Clean")
        print("  7) Exit")
        try:
            choice = input("Select [1-7]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice == "7":
            return 0
        fn = actions.get(choice)
        if fn is None:
            print("  invalid choice.")
            continue
        fn(cfg, user_cfg)  # actions loop back to the cheap menu; no auto-recompute


def main() -> int:
    if len(sys.argv) > 1:
        print("nexus takes no arguments — just run `nexus`.")
        return 2
    nexus_root()                 # validate NEXUS_ROOT early (R5)
    cfg = load_nexus_toml()      # validate the shared config (R6)
    user_cfg = load_user_config()
    if user_cfg is None:
        return run_init(cfg)     # first run — reachable only while config.toml is absent
    return run_menu(cfg, user_cfg)  # later runs: header (in run_menu) + the menu


if __name__ == "__main__":
    sys.exit(main())

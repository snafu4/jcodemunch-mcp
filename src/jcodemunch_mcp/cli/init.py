"""jcodemunch-mcp init — one-command onboarding for MCP clients."""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CLAUDE_MD_MARKER = "## Code Exploration Policy"

_CLAUDE_MD_POLICY = """\
## Code Exploration Policy

Always use jCodemunch-MCP tools for code navigation. Never fall back to Read, Grep, Glob, or Bash for code exploration.

**Start any session:**
1. `resolve_repo { "path": "." }` — confirm the project is indexed. If not: `index_folder { "path": "." }`
2. `suggest_queries` — when the repo is unfamiliar

**Finding code:**
- symbol by name → `search_symbols` (add `kind=`, `language=`, `file_pattern=` to narrow)
- string, comment, config value → `search_text` (supports regex, `context_lines`)
- database columns (dbt/SQLMesh) → `search_columns`

**Reading code:**
- before opening any file → `get_file_outline` first
- one or more symbols → `get_symbol_source` (single ID → flat object; array → batch)
- symbol + its imports → `get_context_bundle`
- specific line range only → `get_file_content` (last resort)

**Repo structure:**
- `get_repo_outline` → dirs, languages, symbol counts
- `get_file_tree` → file layout, filter with `path_prefix`

**Relationships & impact:**
- what imports this file → `find_importers`
- where is this name used → `find_references`
- is this identifier used anywhere → `check_references`
- file dependency graph → `get_dependency_graph`
- what breaks if I change X → `get_blast_radius`
- what symbols actually changed since last commit → `get_changed_symbols`
- find unreachable/dead code → `find_dead_code`
- class hierarchy → `get_class_hierarchy`

**After editing a file:** `index_file { "path": "/abs/path/to/file" }` to keep the index fresh.
"""

_MCP_ENTRY = {
    "command": "uvx",
    "args": ["jcodemunch-mcp"],
}

_WORKTREE_HOOKS = {
    "WorktreeCreate": [{
        "matcher": "",
        "hooks": [{"type": "command", "command": "jcodemunch-mcp hook-event create"}],
    }],
    "WorktreeRemove": [{
        "matcher": "",
        "hooks": [{"type": "command", "command": "jcodemunch-mcp hook-event remove"}],
    }],
}


# ---------------------------------------------------------------------------
# Client detection
# ---------------------------------------------------------------------------

class MCPClient:
    """Represents a detected MCP client and how to configure it."""

    def __init__(self, name: str, config_path: Optional[Path], method: str):
        self.name = name
        self.config_path = config_path
        self.method = method  # "cli" | "json_patch"

    def __repr__(self) -> str:
        if self.config_path:
            return f"{self.name} ({self.config_path})"
        return self.name


def _find_executable(name: str) -> Optional[str]:
    """Return path to executable or None."""
    return shutil.which(name)


def _expand_appdata(*parts: str) -> Path:
    """Expand %APPDATA% on Windows, ~/ on others."""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata, *parts)
    return Path.home().joinpath(*parts)


def _detect_clients() -> list[MCPClient]:
    """Detect installed MCP clients."""
    clients: list[MCPClient] = []

    # Claude Code CLI
    if _find_executable("claude"):
        clients.append(MCPClient("Claude Code", None, "cli"))

    # Claude Desktop
    if platform.system() == "Darwin":
        p = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif platform.system() == "Windows":
        p = _expand_appdata("Claude", "claude_desktop_config.json")
    else:
        p = Path.home() / ".config" / "claude" / "claude_desktop_config.json"
    if p.parent.exists():
        clients.append(MCPClient("Claude Desktop", p, "json_patch"))

    # Cursor
    cursor_dir = Path.home() / ".cursor"
    if cursor_dir.exists():
        clients.append(MCPClient("Cursor", cursor_dir / "mcp.json", "json_patch"))

    # Windsurf
    for d in [Path.home() / ".windsurf", Path.home() / ".codeium" / "windsurf"]:
        if d.exists():
            clients.append(MCPClient("Windsurf", d / "mcp_config.json", "json_patch"))
            break

    # Continue
    continue_dir = Path.home() / ".continue"
    if continue_dir.exists():
        clients.append(MCPClient("Continue", continue_dir / "config.json", "json_patch"))

    return clients


# ---------------------------------------------------------------------------
# Config patching
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file, returning {} if it doesn't exist."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: dict[str, Any], *, backup: bool = True) -> None:
    """Write JSON, optionally creating a .bak backup first."""
    if backup and path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _has_jcodemunch_entry(data: dict[str, Any]) -> bool:
    """Check if jcodemunch is already configured in an MCP config."""
    servers = data.get("mcpServers", {})
    return "jcodemunch" in servers


def _patch_mcp_config(path: Path, *, backup: bool = True, dry_run: bool = False) -> str:
    """Add jcodemunch entry to an MCP client JSON config.

    Returns a status message.
    """
    data = _read_json(path)
    if _has_jcodemunch_entry(data):
        return f"  already configured in {path}"

    if dry_run:
        return f"  would add jcodemunch to {path}"

    if "mcpServers" not in data:
        data["mcpServers"] = {}
    data["mcpServers"]["jcodemunch"] = _MCP_ENTRY
    _write_json(path, data, backup=backup)
    return f"  added jcodemunch to {path}"


def _configure_claude_code(*, dry_run: bool = False) -> str:
    """Run `claude mcp add` for Claude Code CLI."""
    if dry_run:
        return "  would run: claude mcp add jcodemunch uvx jcodemunch-mcp"
    try:
        result = subprocess.run(
            ["claude", "mcp", "add", "jcodemunch", "uvx", "jcodemunch-mcp"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return "  ran: claude mcp add jcodemunch uvx jcodemunch-mcp"
        # Already exists or other non-fatal issue
        stderr = result.stderr.strip()
        if "already exists" in stderr.lower():
            return "  already configured in Claude Code"
        return f"  claude mcp add failed: {stderr or result.stdout.strip()}"
    except FileNotFoundError:
        return "  claude CLI not found — skipped"
    except subprocess.TimeoutExpired:
        return "  claude mcp add timed out"


def configure_client(client: MCPClient, *, backup: bool = True, dry_run: bool = False) -> str:
    """Configure a single MCP client. Returns a status message."""
    if client.method == "cli":
        return _configure_claude_code(dry_run=dry_run)
    elif client.method == "json_patch" and client.config_path:
        return _patch_mcp_config(client.config_path, backup=backup, dry_run=dry_run)
    return f"  unknown method for {client.name}"


# ---------------------------------------------------------------------------
# CLAUDE.md injection
# ---------------------------------------------------------------------------

def _claude_md_path(scope: str) -> Path:
    """Return the CLAUDE.md path for the given scope."""
    if scope == "global":
        return Path.home() / ".claude" / "CLAUDE.md"
    return Path.cwd() / "CLAUDE.md"


def _has_policy(path: Path) -> bool:
    """Check if the Code Exploration Policy marker already exists."""
    if not path.exists():
        return False
    return _CLAUDE_MD_MARKER in path.read_text(encoding="utf-8")


def install_claude_md(scope: str = "global", *, dry_run: bool = False, backup: bool = True) -> str:
    """Append the Code Exploration Policy to CLAUDE.md.

    scope: "global" or "project"
    Returns a status message.
    """
    path = _claude_md_path(scope)
    if _has_policy(path):
        return f"  policy already present in {path}"
    if dry_run:
        return f"  would append policy to {path}"

    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(".md.bak"))

    with open(path, "a", encoding="utf-8") as f:
        if path.exists() and path.stat().st_size > 0:
            f.write("\n\n")
        f.write(_CLAUDE_MD_POLICY)

    return f"  appended policy to {path}"


# ---------------------------------------------------------------------------
# Hooks injection
# ---------------------------------------------------------------------------

def _settings_json_path() -> Path:
    """Return the Claude Code settings.json path."""
    if platform.system() == "Windows":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".claude" / "settings.json"
    return Path.home() / ".claude" / "settings.json"


def install_hooks(*, dry_run: bool = False, backup: bool = True) -> str:
    """Merge worktree hooks into ~/.claude/settings.json.

    Returns a status message.
    """
    path = _settings_json_path()
    data = _read_json(path)

    hooks = data.get("hooks", {})
    added = []

    for event_name, event_hooks in _WORKTREE_HOOKS.items():
        if event_name in hooks:
            # Check if jcodemunch hook-event is already present
            existing_cmds = []
            for rule in hooks[event_name]:
                for h in rule.get("hooks", []):
                    existing_cmds.append(h.get("command", ""))
            if any("jcodemunch-mcp hook-event" in c for c in existing_cmds):
                continue
            # Append our rule to the existing list
            hooks[event_name].extend(event_hooks)
        else:
            hooks[event_name] = event_hooks
        added.append(event_name)

    if not added:
        return f"  hooks already present in {path}"
    if dry_run:
        return f"  would add {', '.join(added)} hooks to {path}"

    data["hooks"] = hooks
    _write_json(path, data, backup=backup)
    return f"  added {', '.join(added)} hooks to {path}"


# ---------------------------------------------------------------------------
# Index current directory
# ---------------------------------------------------------------------------

def run_index(*, dry_run: bool = False) -> str:
    """Index the current working directory using index_folder."""
    cwd = os.getcwd()
    if dry_run:
        return f"  would index {cwd}"

    try:
        from ..tools.index_folder import index_folder
        result = index_folder(folder_path=cwd)
        files = result.get("files_indexed", "?")
        symbols = result.get("symbols_indexed", "?")
        return f"  indexed {cwd} ({files} files, {symbols} symbols)"
    except Exception as e:
        return f"  indexing failed: {e}"


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def _prompt_yn(message: str, default: bool = True) -> bool:
    """Prompt for yes/no, with a default."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        answer = input(message + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def _prompt_choice(message: str, options: list[str], allow_all: bool = True) -> list[str]:
    """Prompt user to pick from numbered options. Returns selected option labels."""
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    extra = "/all/none" if allow_all else "/none"
    try:
        raw = input(f"{message} [1-{len(options)}{extra}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return []
    if raw == "none" or raw == "":
        return []
    if raw == "all":
        return options
    selected = []
    for part in raw.replace(",", " ").split():
        try:
            idx = int(part) - 1
            if 0 <= idx < len(options):
                selected.append(options[idx])
        except ValueError:
            continue
    return selected


def _prompt_scope(message: str) -> Optional[str]:
    """Prompt for global/project/skip."""
    try:
        raw = input(f"{message} [global/project/skip]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if raw in ("global", "g"):
        return "global"
    if raw in ("project", "p"):
        return "project"
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_init(
    *,
    clients: Optional[list[str]] = None,
    claude_md: Optional[str] = None,
    hooks: bool = False,
    index: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    no_backup: bool = False,
) -> int:
    """Run the init flow. Returns exit code (0 = success)."""
    backup = not no_backup
    interactive = not yes and sys.stdin.isatty()

    print("\njCodeMunch init -- one-command setup\n")

    # ----- Step 1: MCP client registration -----
    detected = _detect_clients()

    if clients is not None:
        # Explicit --client flag
        if "auto" in clients:
            targets = detected
        elif "none" in clients:
            targets = []
        else:
            name_map = {c.name.lower().replace(" ", "-"): c for c in detected}
            targets = [name_map[n] for n in clients if n in name_map]
    elif interactive and detected:
        print("Detected MCP clients:")
        names = [repr(c) for c in detected]
        selected = _prompt_choice("Configure which?", names)
        targets = [c for c in detected if repr(c) in selected]
    elif detected:
        targets = detected  # non-interactive + no flag = configure all
    else:
        targets = []
        print("No MCP clients detected.\n")

    for client in targets:
        msg = configure_client(client, backup=backup, dry_run=dry_run)
        print(f"  {client.name}:{msg}")

    # ----- Step 2: CLAUDE.md policy -----
    md_scope = claude_md
    if md_scope is None and interactive:
        print()
        md_scope = _prompt_scope("Install CLAUDE.md policy?")
    elif md_scope is None and yes:
        md_scope = "global"  # default for --yes mode

    if md_scope in ("global", "project"):
        msg = install_claude_md(md_scope, dry_run=dry_run, backup=backup)
        print(f"  CLAUDE.md:{msg}")

    # ----- Step 3: Agent hooks -----
    do_hooks = hooks
    if not do_hooks and interactive:
        print()
        do_hooks = _prompt_yn("Install worktree hooks?", default=False)
    if do_hooks:
        msg = install_hooks(dry_run=dry_run, backup=backup)
        print(f"  Hooks:{msg}")

    # ----- Step 4: Index -----
    do_index = index
    if not do_index and interactive:
        print()
        do_index = _prompt_yn(f"Index current directory ({os.getcwd()})?", default=True)
    if do_index:
        msg = run_index(dry_run=dry_run)
        print(f"  Index:{msg}")

    # ----- Done -----
    print()
    if dry_run:
        print("Dry run complete — no changes were made.")
    else:
        print("Done. Restart your MCP client(s) to connect.")
    print()
    return 0

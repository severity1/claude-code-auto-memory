#!/usr/bin/env python3
"""Consolidated trigger hook for PreToolUse, Stop, and SubagentStop events.

Handles three hook events:
- Stop: Blocks Claude at end of turn when dirty files exist
- PreToolUse: In gitmode, denies git commit until dirty files are processed
- SubagentStop: Clears dirty-files after memory-updater agent completes

Stop and PreToolUse outputs instruct Claude to use the Task tool with
run_in_background set to false and mode set to bypassPermissions, ensuring
the agent runs in foreground with full permissions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def plugin_initialized(project_dir: str) -> bool:
    """Return True if the plugin has been initialized for this project.

    The presence of .claude/auto-memory/config.json is the explicit
    opt-in marker - users create it by running /auto-memory:init. On
    projects without config.json we keep the plugin entirely inert:
    no Stop-hook blocking, no PreToolUse interception, no memory-updater
    agent spawn. This prevents auto-memory from intruding on projects
    where the user never opted in (#17).
    """
    return (Path(project_dir) / ".claude" / "auto-memory" / "config.json").exists()


def load_config(project_dir: str) -> dict[str, Any]:
    """Load plugin configuration from .claude/auto-memory/config.json."""
    config_file = Path(project_dir) / ".claude" / "auto-memory" / "config.json"
    if config_file.exists():
        try:
            with open(config_file) as f:
                data: dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"triggerMode": "default"}


def get_memory_files(config: dict[str, Any]) -> list[str]:
    """Return the list of memory file names from config, defaulting to CLAUDE.md."""
    v = config.get("memoryFiles", ["CLAUDE.md"])
    if isinstance(v, str):
        return [v]
    return v if v else ["CLAUDE.md"]


def get_active_memory_file(memory_files: list[str]) -> str:
    """Return the file that receives full content. AGENTS.md wins when both are configured."""
    return "AGENTS.md" if "AGENTS.md" in memory_files else "CLAUDE.md"


def dirty_file_path(project_dir: str, session_id: str = "") -> Path:
    """Return path to session-specific or default dirty-files."""
    base = Path(project_dir) / ".claude" / "auto-memory"
    if session_id:
        return base / f"dirty-files-{session_id}"
    return base / "dirty-files"


def read_dirty_files(project_dir: str, session_id: str = "") -> list[str]:
    """Read and deduplicate dirty files, stripping commit context.

    Returns sorted list of file paths (max 20).
    """
    dirty_file = dirty_file_path(project_dir, session_id)

    if not dirty_file.exists() or dirty_file.stat().st_size == 0:
        return []

    files = set()
    with open(dirty_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Strip inline commit context if present
            if " [" in line:
                line = line.split(" [")[0]
            files.add(line)

    return sorted(files)[:20]


def build_spawn_reason(files: list[str], config: dict[str, Any] | None = None) -> str:
    """Build the agent spawn instruction text with Task tool parameters."""
    files_str = ", ".join(files)
    active = get_active_memory_file(get_memory_files(config or {}))
    return (
        f"Files were modified this turn. Use the Task tool with "
        f"run_in_background set to false and mode set to bypassPermissions "
        f"to spawn 'memory-updater' agent with subagent_type set to "
        f"'auto-memory:memory-updater' and prompt: 'Update {active} for "
        f"changed files: {files_str}'. After the agent completes, use the "
        f"Read tool to read the root {active} file to refresh your memory."
    )


def handle_stop(input_data: dict[str, Any], project_dir: str) -> None:
    """Handle Stop hook event."""
    # Prevent infinite loop when stop_hook_active is set
    if input_data.get("stop_hook_active", False):
        return

    # Skip entirely on projects where the user hasn't run /auto-memory:init
    if not plugin_initialized(project_dir):
        return

    config = load_config(project_dir)
    trigger_mode = config.get("triggerMode", "default")

    # In gitmode, Stop still fires to catch dirty files from the last commit
    # (PreToolUse only intercepts before the next git commit, not after the last one)
    # So we don't skip Stop in gitmode - it acts as the final safety net.

    session_id = input_data.get("session_id", "")
    files = read_dirty_files(project_dir, session_id)
    if not files:
        return

    # In gitmode, only trigger if there are actually dirty files
    # (which means a commit happened but the agent hasn't run yet)
    _ = trigger_mode  # Used for future mode-specific logic

    output = {
        "decision": "block",
        "reason": build_spawn_reason(files, config),
    }
    print(json.dumps(output))


def clear_dirty_files(project_dir: str, session_id: str = "") -> None:
    """Truncate dirty-files to clear processed entries."""
    dirty_file = dirty_file_path(project_dir, session_id)
    if dirty_file.exists():
        dirty_file.write_text("")


def cleanup_stale_session_files(project_dir: str, max_age_hours: int = 24) -> None:
    """Remove session-specific dirty-files older than max_age_hours.

    Only removes files matching dirty-files-* pattern. Never removes
    the plain dirty-files (backwards compatibility).
    """
    auto_memory_dir = Path(project_dir) / ".claude" / "auto-memory"
    if not auto_memory_dir.exists():
        return

    cutoff = time.time() - (max_age_hours * 3600)
    for f in auto_memory_dir.glob("dirty-files-*"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def auto_commit_memory_files(project_dir: str, config: dict[str, Any]) -> bool:
    """Stage and commit modified memory files (CLAUDE.md, AGENTS.md). Returns True on success."""
    memory_files = get_memory_files(config)

    # Find modified tracked files
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=M"],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    if result.returncode != 0:
        return False

    matched = [
        f.strip()
        for f in result.stdout.strip().split("\n")
        if f.strip() and any(f.strip().endswith(name) for name in memory_files)
    ]
    if not matched:
        return False

    # Stage only the matched memory files
    stage = subprocess.run(
        ["git", "add"] + matched,
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    if stage.returncode != 0:
        return False

    # Commit message reflects which files are managed
    if memory_files == ["CLAUDE.md"]:
        msg = "chore: update CLAUDE.md [auto-memory]"
    else:
        msg = "chore: update memory files [auto-memory]"

    commit = subprocess.run(
        ["git", "commit", "-m", msg],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    return commit.returncode == 0


def auto_push(project_dir: str) -> bool:
    """Push current branch to remote. Returns True on success."""
    result = subprocess.run(
        ["git", "push"],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    return result.returncode == 0


def handle_subagent_stop(input_data: dict[str, Any], project_dir: str) -> None:
    """Handle SubagentStop hook event.

    Clears dirty-files after the memory-updater agent completes. Gated on
    dirty-files presence alone - we intentionally do not require
    config.json to exist, because doing so caused an infinite Stop-hook
    loop on uninitialized projects (#17, #25): the Stop hook would
    re-fire every turn on stale dirty-files that never got cleared.

    When autoCommit is enabled, commits modified CLAUDE.md files before
    clearing dirty-files (#18).
    """
    session_id = input_data.get("session_id", "")
    files = read_dirty_files(project_dir, session_id)
    if not files:
        return

    # Auto-commit/push before clearing dirty files
    config = load_config(project_dir)
    if config.get("autoCommit", False):
        if auto_commit_memory_files(project_dir, config):
            if config.get("autoPush", False):
                auto_push(project_dir)

    clear_dirty_files(project_dir, session_id)
    cleanup_stale_session_files(project_dir)


def handle_pre_tool_use(input_data: dict[str, Any], project_dir: str) -> None:
    """Handle PreToolUse hook event.

    Only active in gitmode. Denies git commit commands when dirty files
    exist, forcing the memory-updater to run first.
    """
    # Skip entirely on projects where the user hasn't run /auto-memory:init
    if not plugin_initialized(project_dir):
        return

    config = load_config(project_dir)
    trigger_mode = config.get("triggerMode", "default")

    # Only intercept in gitmode
    if trigger_mode != "gitmode":
        return

    # Check if this is a git commit command
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "").strip()
    if "git commit" not in command:
        return

    session_id = input_data.get("session_id", "")
    files = read_dirty_files(project_dir, session_id)
    if not files:
        return

    active = get_active_memory_file(get_memory_files(config))
    files_str = ", ".join(files)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Files were modified since last memory update. Use the Task tool "
                f"with run_in_background set to false and mode set to "
                f"bypassPermissions to spawn 'memory-updater' agent with subagent_type "
                f"set to 'auto-memory:memory-updater' and prompt: 'Update {active} "
                f"for changed files: {files_str}'. After the agent completes, retry "
                f"the git commit."
            ),
        }
    }
    print(json.dumps(output))


def main() -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    # Read stdin JSON to determine which hook event fired
    input_data: dict[str, Any]
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        input_data = {}

    hook_event = input_data.get("hook_event_name", "")

    if hook_event == "PreToolUse":
        handle_pre_tool_use(input_data, project_dir)
    elif hook_event == "SubagentStop":
        handle_subagent_stop(input_data, project_dir)
    else:
        # Default to Stop behavior (for backwards compatibility and
        # when hook_event_name is missing or "Stop")
        handle_stop(input_data, project_dir)


if __name__ == "__main__":
    main()

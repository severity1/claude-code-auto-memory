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
import sys
from pathlib import Path


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


def load_config(project_dir: str) -> dict:
    """Load plugin configuration from .claude/auto-memory/config.json."""
    config_file = Path(project_dir) / ".claude" / "auto-memory" / "config.json"
    if config_file.exists():
        try:
            with open(config_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"triggerMode": "default"}


def read_dirty_files(project_dir: str) -> list[str]:
    """Read and deduplicate dirty files, stripping commit context.

    Returns sorted list of file paths (max 20).
    """
    dirty_file = Path(project_dir) / ".claude" / "auto-memory" / "dirty-files"

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


def build_spawn_reason(files: list[str]) -> str:
    """Build the agent spawn instruction text with Task tool parameters."""
    files_str = ", ".join(files)
    return (
        f"Files were modified this turn. Use the Task tool with "
        f"run_in_background set to false and mode set to bypassPermissions "
        f"to spawn 'memory-updater' agent with prompt: 'Update CLAUDE.md for "
        f"changed files: {files_str}'. After the agent completes, use the "
        f"Read tool to read the root CLAUDE.md file to refresh your memory."
    )


def handle_stop(input_data: dict, project_dir: str) -> None:
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

    files = read_dirty_files(project_dir)
    if not files:
        return

    # In gitmode, only trigger if there are actually dirty files
    # (which means a commit happened but the agent hasn't run yet)
    _ = trigger_mode  # Used for future mode-specific logic

    output = {
        "decision": "block",
        "reason": build_spawn_reason(files),
    }
    print(json.dumps(output))


def clear_dirty_files(project_dir: str) -> None:
    """Truncate dirty-files to clear processed entries."""
    dirty_file = Path(project_dir) / ".claude" / "auto-memory" / "dirty-files"
    if dirty_file.exists():
        dirty_file.write_text("")


def handle_subagent_stop(project_dir: str) -> None:
    """Handle SubagentStop hook event.

    Clears dirty-files after the memory-updater agent completes. Gated on
    dirty-files presence alone - we intentionally do not require
    config.json to exist, because doing so caused an infinite Stop-hook
    loop on uninitialized projects (#17, #25): the Stop hook would
    re-fire every turn on stale dirty-files that never got cleared.
    """
    files = read_dirty_files(project_dir)
    if not files:
        return

    clear_dirty_files(project_dir)


def handle_pre_tool_use(input_data: dict, project_dir: str) -> None:
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

    files = read_dirty_files(project_dir)
    if not files:
        return

    files_str = ", ".join(files)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Files were modified since last memory update. Use the Task tool "
                f"with run_in_background set to false and mode set to "
                f"bypassPermissions to spawn 'memory-updater' agent with prompt: "
                f"'Update CLAUDE.md for changed files: {files_str}'. After the "
                f"agent completes, retry the git commit."
            ),
        }
    }
    print(json.dumps(output))


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    # Read stdin JSON to determine which hook event fired
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        input_data = {}

    hook_event = input_data.get("hook_event_name", "")

    if hook_event == "PreToolUse":
        handle_pre_tool_use(input_data, project_dir)
    elif hook_event == "SubagentStop":
        handle_subagent_stop(project_dir)
    else:
        # Default to Stop behavior (for backwards compatibility and
        # when hook_event_name is missing or "Stop")
        handle_stop(input_data, project_dir)


if __name__ == "__main__":
    main()

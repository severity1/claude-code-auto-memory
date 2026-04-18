#!/usr/bin/env python3
"""PostToolUse hook - tracks edited files for CLAUDE.md updates.

Fires after Edit, Write, or Bash tool execution. Appends changed file
paths to .claude/auto-memory/dirty-files for batch processing at turn end.
Produces no output to maintain zero token cost (critical for performance).

Supports configurable trigger modes:
- default: Track Edit/Write/Bash operations (current behavior)
- gitmode: Only track git commits

In gitmode, when a git commit is detected, enriches each file path with
inline commit context: /path/to/file [hash: commit message]
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


def plugin_initialized(project_dir: str) -> bool:
    """Return True if the plugin has been initialized for this project.

    The presence of .claude/auto-memory/config.json is the explicit
    opt-in marker - users create it by running /auto-memory:init. On
    projects without config.json we keep the plugin entirely inert:
    PostToolUse does not track any file edits, so dirty-files never
    gets created and the downstream Stop hook never spawns memory-updater
    (#17).
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


def handle_git_commit(project_dir: str) -> tuple[list[str], dict[str, str] | None]:
    """Extract context from a git commit.

    Returns: (files, commit_context) where commit_context is {"hash": ..., "message": ...}
    """
    # Get commit info (hash and message)
    result = subprocess.run(
        ["git", "log", "-1", "--format=%h %s"],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    if result.returncode != 0:
        return [], None

    parts = result.stdout.strip().split(" ", 1)
    commit_hash = parts[0]
    commit_message = parts[1] if len(parts) > 1 else ""

    # Get list of committed files
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    if result.returncode != 0:
        return [], {"hash": commit_hash, "message": commit_message}

    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

    # Resolve to absolute paths
    files = [str((Path(project_dir) / f).resolve()) for f in files]

    return files, {"hash": commit_hash, "message": commit_message}


def dirty_file_path(project_dir: str, session_id: str = "") -> Path:
    """Return path to session-specific or default dirty-files."""
    base = Path(project_dir) / ".claude" / "auto-memory"
    if session_id:
        return base / f"dirty-files-{session_id}"
    return base / "dirty-files"


def should_track(file_path: str, project_dir: str, memory_files: list[str] | None = None) -> bool:
    """Check if file should be tracked for memory file updates."""
    path = Path(file_path)

    # Only track files within the project directory
    try:
        relative = path.relative_to(project_dir)
    except ValueError:
        return False  # File outside project - don't track

    # Exclude .claude/ directory (plugin state files)
    if relative.parts and relative.parts[0] == ".claude":
        return False

    # Exclude memory files anywhere (prevents infinite loops when they are updated)
    names = memory_files if memory_files is not None else ["CLAUDE.md"]
    if path.name in names:
        return False

    return True


def extract_files_from_bash(command: str, project_dir: str) -> list[str]:
    """Extract file paths from Bash commands that modify files.

    Detects file-modifying commands: rm, rm -rf, mv, git rm, git mv, unlink.
    Returns list of absolute file paths that should be tracked.
    """
    if not command:
        return []

    # Normalize command (strip leading/trailing whitespace)
    command = command.strip()

    # Skip commands that don't modify files
    skip_prefixes = (
        "ls",
        "cat",
        "echo",
        "grep",
        "find",
        "head",
        "tail",
        "less",
        "more",
        "cd",
        "pwd",
        "which",
        "whereis",
        "type",
        "file",
        "stat",
        "wc",
        "git status",
        "git log",
        "git diff",
        "git show",
        "git branch",
        "git fetch",
        "git pull",
        "git push",
        "git clone",
        "git checkout",
        "git stash",
        "git remote",
        "git tag",
        "git rev-parse",
        "npm ",
        "yarn ",
        "pnpm ",
        "node ",
        "python",
        "pip ",
        "uv ",
        "cargo ",
        "go ",
        "make",
        "cmake",
        "docker ",
        "kubectl ",
        "curl ",
        "wget ",
        "ssh ",
        "scp ",
        "rsync ",
    )
    if command.startswith(skip_prefixes):
        return []

    def is_shell_op(token: str) -> bool:
        """Return True if token is a pure shell operator or redirect."""
        return token in {"&&", "||", ";", "|"} or token.startswith((">", "<", "2>", "1>", "&>"))

    def process_token(token: str, files: list[str]) -> bool:
        """Append token to files (stripping trailing semicolon) and return True to stop."""
        stop = token.endswith(";")
        clean = token[:-1] if stop else token
        if clean and not clean.startswith("-"):
            files.append(clean)
        return stop

    files: list[str] = []

    try:
        # Parse command into tokens
        tokens = shlex.split(command)
        if not tokens:
            return []

        cmd = tokens[0]

        # Handle: rm, rm -rf, rm -f, etc.
        if cmd == "rm":
            # Skip flags, collect file arguments until shell operator
            for token in tokens[1:]:
                if is_shell_op(token):
                    break  # Stop at command chaining operator
                if process_token(token, files):
                    break

        # Handle: git rm
        elif cmd == "git" and len(tokens) > 1 and tokens[1] == "rm":
            for token in tokens[2:]:
                if is_shell_op(token):
                    break
                if process_token(token, files):
                    break

        # Handle: mv (track source file only)
        elif cmd == "mv" and len(tokens) >= 3:
            # Skip flags, get first non-flag arg (source)
            for token in tokens[1:]:
                if is_shell_op(token):
                    break
                if not token.startswith("-"):
                    clean = token[:-1] if token.endswith(";") else token
                    if clean:
                        files.append(clean)
                    break  # Only track source, not destination

        # Handle: git mv (track source file only)
        elif cmd == "git" and len(tokens) > 2 and tokens[1] == "mv":
            for token in tokens[2:]:
                if is_shell_op(token):
                    break
                if not token.startswith("-"):
                    clean = token[:-1] if token.endswith(";") else token
                    if clean:
                        files.append(clean)
                    break

        # Handle: unlink
        elif cmd == "unlink" and len(tokens) > 1:
            t = tokens[1]
            if not is_shell_op(t):
                files.append(t[:-1] if t.endswith(";") else t)

    except ValueError:
        # shlex.split failed (unbalanced quotes, etc.) - skip
        return []

    # Resolve paths relative to project directory
    resolved = []
    for f in files:
        path = Path(f)
        if not path.is_absolute():
            path = Path(project_dir) / path
        resolved.append(str(path.resolve()))

    return resolved


def main() -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")

    # CLAUDE_PROJECT_DIR is required - don't use cwd fallback as it may be wrong
    # (e.g., plugin cache directory instead of user's project)
    if not project_dir:
        return

    # Skip entirely on projects where the user hasn't run /auto-memory:init
    if not plugin_initialized(project_dir):
        return

    # Read tool input from stdin (JSON format)
    tool_input: dict[str, Any]
    try:
        stdin_data = sys.stdin.read()
        tool_input = json.loads(stdin_data) if stdin_data else {}
    except json.JSONDecodeError:
        tool_input = {}

    tool_name = tool_input.get("tool_name", "")
    tool_input_data = tool_input.get("tool_input", {})
    session_id = tool_input.get("session_id", "")

    # Load configuration
    config = load_config(project_dir)
    trigger_mode = config.get("triggerMode", "default")

    # Check if this is a git commit (anywhere in the command, handles chained commands)
    is_git_commit = False
    command = ""
    if tool_name == "Bash":
        command = tool_input_data.get("command", "").strip()
        is_git_commit = "git commit" in command

    # In gitmode, only process git commits
    if trigger_mode == "gitmode" and not is_git_commit:
        return

    # In default mode, skip git commits (files already tracked via Edit/Write hooks)
    if trigger_mode == "default" and is_git_commit:
        return

    files_to_track = []
    commit_context = None

    # Handle git commit specially - extract commit context
    if is_git_commit:
        files, commit_context = handle_git_commit(project_dir)
        files_to_track.extend(files)

    # Handle Edit/Write tools - extract file_path directly
    elif tool_name in ("Edit", "Write"):
        file_path = tool_input_data.get("file_path", "")
        if file_path:
            files_to_track.append(file_path)

    # Handle Bash tool - parse command for file operations
    elif tool_name == "Bash":
        files_to_track = extract_files_from_bash(command, project_dir)

    # Legacy support: if no tool_name, try file_path directly
    elif not tool_name:
        file_path = tool_input_data.get("file_path", "")
        if file_path:
            files_to_track.append(file_path)

    if not files_to_track:
        return

    # Filter to only trackable files
    memory_files = get_memory_files(config)
    trackable = [f for f in files_to_track if should_track(f, project_dir, memory_files)]

    if not trackable:
        return

    # Read existing dirty files into a dict (path -> full line)
    dirty_file = dirty_file_path(project_dir, session_id)
    dirty_file.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if dirty_file.exists():
        with open(dirty_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Extract path (strip commit context if present)
                path = line.split(" [")[0] if " [" in line else line
                existing[path] = line

    # Update or add entries
    for file_path in trackable:
        if commit_context:
            # Always use commit context version (overwrites plain path)
            ctx = f"[{commit_context['hash']}: {commit_context['message']}]"
            existing[file_path] = f"{file_path} {ctx}"
        elif file_path not in existing:
            # Only add if not already tracked
            existing[file_path] = file_path

    # Write back all entries
    with open(dirty_file, "w") as f:
        for line in existing.values():
            f.write(line + "\n")

    # NO output - zero token cost


if __name__ == "__main__":
    main()

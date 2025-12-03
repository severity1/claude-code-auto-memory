#!/usr/bin/env python3
"""PostToolUse hook - tracks edited files for CLAUDE.md updates.

Fires after Edit, Write, or Bash tool execution. Appends changed file
paths to .claude/auto-memory/dirty-files for batch processing at turn end.
Produces no output to maintain zero token cost.

Supports configurable trigger modes:
- default: Track Edit/Write/Bash operations (current behavior)
- gitmode: Only track git commits

When a git commit is detected, enriches each file path with inline commit
context: /path/to/file [hash: commit message]
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


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


def handle_git_commit(project_dir: str) -> tuple[list[str], dict | None]:
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


def should_track(file_path: str, project_dir: str) -> bool:
    """Check if file should be tracked for CLAUDE.md updates."""
    path = Path(file_path)

    # Only track files within the project directory
    try:
        relative = path.relative_to(project_dir)
    except ValueError:
        return False  # File outside project - don't track

    # Exclude .claude/ directory (plugin state files)
    if relative.parts and relative.parts[0] == ".claude":
        return False

    # Exclude CLAUDE.md files anywhere (prevents infinite loops)
    if path.name == "CLAUDE.md":
        return False

    return True


def extract_files_from_bash(command: str, project_dir: str) -> list[str]:
    """Extract file paths from Bash commands that modify files.

    Detects: rm, rm -rf, mv, git rm, git mv, unlink
    Returns list of file paths that should be tracked.
    """
    if not command:
        return []

    # Normalize command (strip leading/trailing whitespace)
    command = command.strip()

    # Skip commands that don't modify files
    skip_prefixes = (
        "ls", "cat", "echo", "grep", "find", "head", "tail", "less", "more",
        "cd", "pwd", "which", "whereis", "type", "file", "stat", "wc",
        "git status", "git log", "git diff", "git show", "git branch",
        "git fetch", "git pull", "git push", "git clone", "git checkout",
        "git stash", "git remote", "git tag", "git rev-parse",
        "npm ", "yarn ", "pnpm ", "node ", "python", "pip ", "uv ",
        "cargo ", "go ", "make", "cmake", "docker ", "kubectl ",
        "curl ", "wget ", "ssh ", "scp ", "rsync ",
    )
    if command.startswith(skip_prefixes):
        return []

    # Shell operators that chain commands - stop parsing at these
    shell_operators = ("&&", "||", ";", "|", ">", ">>", "<", "2>", "2>&1")

    files = []

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
                if token in shell_operators:
                    break  # Stop at command chaining operator
                if not token.startswith("-"):
                    files.append(token)

        # Handle: git rm
        elif cmd == "git" and len(tokens) > 1 and tokens[1] == "rm":
            for token in tokens[2:]:
                if token in shell_operators:
                    break
                if not token.startswith("-"):
                    files.append(token)

        # Handle: mv (track source file only)
        elif cmd == "mv" and len(tokens) >= 3:
            # Skip flags, get first non-flag arg (source)
            for token in tokens[1:]:
                if token in shell_operators:
                    break
                if not token.startswith("-"):
                    files.append(token)
                    break  # Only track source, not destination

        # Handle: git mv (track source file only)
        elif cmd == "git" and len(tokens) > 2 and tokens[1] == "mv":
            for token in tokens[2:]:
                if token in shell_operators:
                    break
                if not token.startswith("-"):
                    files.append(token)
                    break

        # Handle: unlink
        elif cmd == "unlink" and len(tokens) > 1:
            if tokens[1] not in shell_operators:
                files.append(tokens[1])

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


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    if not project_dir:
        return

    # Read tool input from stdin (JSON format)
    try:
        stdin_data = sys.stdin.read()
        tool_input = json.loads(stdin_data) if stdin_data else {}
    except json.JSONDecodeError:
        tool_input = {}

    tool_name = tool_input.get("tool_name", "")
    tool_input_data = tool_input.get("tool_input", {})

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
    trackable = [f for f in files_to_track if should_track(f, project_dir)]

    if not trackable:
        return

    # Ensure auto-memory directory exists
    auto_memory_dir = Path(project_dir) / ".claude" / "auto-memory"
    auto_memory_dir.mkdir(parents=True, exist_ok=True)

    # Read existing dirty files into a dict (path -> full line)
    dirty_file = auto_memory_dir / "dirty-files"
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
            existing[file_path] = f"{file_path} [{commit_context['hash']}: {commit_context['message']}]"
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

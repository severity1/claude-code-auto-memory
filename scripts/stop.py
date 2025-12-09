#!/usr/bin/env python3
"""Stop hook - triggers memory-updater agent spawn when dirty files exist.

This hook fires at the end of Claude's turn. If files were modified
during the turn (tracked in .claude/auto-memory/dirty-files), it blocks
and instructs Claude to spawn the memory-updater agent for CLAUDE.md updates.

The hook outputs JSON with decision: "block" to prevent Claude from stopping
until the memory update is complete.
"""

import json
import os
import sys
from pathlib import Path


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    # Read stdin (JSON with stop_hook_active flag)
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        input_data = {}

    # Pass through if already processing (prevent infinite loop)
    if input_data.get("stop_hook_active", False):
        return

    dirty_file = Path(project_dir) / ".claude" / "auto-memory" / "dirty-files"

    # Pass through if no dirty files
    if not dirty_file.exists() or dirty_file.stat().st_size == 0:
        return

    # Get unique file list (max 20 files in message)
    # Lines may have inline commit context: /path/to/file [hash: message]
    with open(dirty_file) as f:
        files = set()
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Strip inline commit context if present
            if " [" in line:
                line = line.split(" [")[0]
            files.add(line)
        files = sorted(files)[:20]

    if not files:
        return

    files_str = ", ".join(files)

    # Output block decision
    output = {
        "decision": "block",
        "reason": (
            f"Files were modified this turn. Use the Task tool to spawn "
            f"'memory-updater' agent with prompt: 'Update CLAUDE.md for "
            f"changed files: {files_str}'. After the agent completes, use the "
            f"Read tool to read the root CLAUDE.md file to refresh your memory."
        ),
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()

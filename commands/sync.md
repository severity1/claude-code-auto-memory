---
description: Sync CLAUDE.md with manual file changes detected by git
---

Detect files changed outside Claude Code and update CLAUDE.md incrementally.

Use this when you've edited files manually (outside Claude Code) and want to update CLAUDE.md without a full recalibration.

## Workflow

1. **Check if git repo**: Run `git rev-parse --is-inside-work-tree`
   - If not a git repo: Report error and suggest `/auto-memory:calibrate` instead

2. **Detect changed files using git**:
   ```bash
   git diff --name-only HEAD                    # Modified tracked files
   git diff --cached --name-only                # Staged files
   git ls-files --others --exclude-standard     # New untracked files
   ```

3. **Filter files** (exclude from processing):
   - Files in `.claude/` directory
   - Memory files: read `memoryFiles` from `.claude/auto-memory/config.json` (default `["CLAUDE.md"]`) and exclude any file whose name appears in that list
   - Files outside project directory

4. **If no changes detected**: Report "Already in sync - no manual changes found"

5. **If changes found**:
   - Convert paths to absolute paths
   - Write to `.claude/auto-memory/dirty-files` (one path per line, or `dirty-files-{session_id}` if session_id is available from the environment)
   - Use the Task tool to spawn the `memory-updater` agent with prompt:
     "Update [active memory file] for manually changed files: [file list]" (use AGENTS.md or CLAUDE.md per the memoryFiles config)

6. **Report summary**: List files that were processed

## Notes

- Requires a git repository for change detection
- For non-git projects or full recalibration, use `/auto-memory:calibrate` instead
- The memory-updater agent handles the actual CLAUDE.md updates

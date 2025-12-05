# scripts/CLAUDE.md

Subtree memory for Python hook scripts.

<!-- AUTO-MANAGED: purpose -->
## Purpose

This directory contains Python hook scripts that integrate with Claude Code's hook system. These scripts fire on specific events and must follow strict output conventions to minimize token consumption.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: files -->
## Files

- **post-tool-use.py** - PostToolUse hook that tracks file changes after Edit/Write/Bash tool execution. Appends paths to `.claude/auto-memory/dirty-files`. Detects git commits and enriches file paths with commit context.
- **stop.py** - Stop hook that fires at turn end. If dirty files exist, blocks and instructs Claude to spawn the memory-updater agent.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Script Patterns

- **Zero stdout**: Scripts produce no output on success (token cost optimization)
- **JSON stdin**: Read tool input as JSON from stdin
- **Exit codes**: 0 for success/pass-through, non-zero for errors
- **Environment**: Use `CLAUDE_PROJECT_DIR` env var for project root
- **Deduplication**: Use dict-based deduplication when writing dirty-files
- **Config loading**: Read trigger mode from `.claude/auto-memory/config.json`
- **Git detection**: Check for `git commit` in Bash commands to trigger enrichment

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Conventions

- Use `from __future__ import annotations` for forward references
- Import order: stdlib, third-party (none currently), local
- Use `Path` from pathlib for all file operations
- Use `shlex.split()` for parsing shell commands
- Handle `json.JSONDecodeError` gracefully
- Document each function with docstrings

<!-- END AUTO-MANAGED -->

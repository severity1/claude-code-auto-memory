# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- AUTO-MANAGED: project-description -->
## Overview

**claude-code-auto-memory** - A Claude Code plugin that automatically maintains CLAUDE.md files as codebases evolve. Tracks file changes via hooks, spawns agents to update memory, and provides skills for codebase analysis.

Key features:
- Real-time file tracking via PostToolUse hooks
- Stop hook integration to trigger memory updates
- Codebase analyzer skill for initial setup
- Memory processor skill for ongoing updates

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->
## Build & Development Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run single test file
uv run pytest tests/test_hooks.py -v

# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Type check
uv run mypy scripts/
```

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Architecture

```
.claude-plugin/          # Plugin manifest
  plugin.json            # Plugin metadata and version
agents/
  memory-updater.md      # Agent that updates CLAUDE.md files
commands/
  init.md                # /auto-memory:init command
  calibrate.md           # /auto-memory:calibrate command
  status.md              # /auto-memory:status command
  sync.md                # /auto-memory:sync command
hooks/
  hooks.json             # Hook registration
scripts/
  post-tool-use.py       # Tracks file edits to dirty-files
  trigger.py             # Consolidated handler for PreToolUse, Stop, and SubagentStop
skills/
  codebase-analyzer/     # Initial CLAUDE.md generation
  memory-processor/      # Ongoing CLAUDE.md updates
  shared/                # Shared references
tests/
  test_hooks.py          # PostToolUse hook behavior tests
  test_trigger.py        # trigger.py unit tests
  test_integration.py    # Plugin structure tests
  test_skills.py         # Skill validation tests
```

Data flow:
1. User edits files via Edit/Write tools or git operations (rm, mv)
2. PostToolUse hook appends paths to `.claude/auto-memory/dirty-files`
3. PreToolUse hook (gitmode only) denies git commit until dirty files processed
4. Stop hook detects dirty files, blocks Claude, requests agent spawn
5. memory-updater agent processes files and updates CLAUDE.md
6. SubagentStop hook clears dirty-files after agent completes

Configuration:
- Trigger modes: `default` (after every turn) or `gitmode` (only after git commits)
- Config stored in `.claude/auto-memory/config.json`

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Code Conventions

- **Python**: 3.9+ with type hints, snake_case naming
- **Imports**: Group stdlib, then third-party, then local
- **Docstrings**: Module-level docstrings explain purpose
- **Hooks**: Zero output for PostToolUse/SubagentStop (token cost), JSON output for Stop/PreToolUse
- **Hook routing**: Use hook_event_name from stdin JSON to differentiate behavior
- **Hook commands**: Use python3 with fallback (`python3 script.py || python script.py`) for cross-platform compatibility
- **Skills/Commands**: YAML frontmatter with name/description
- **Line length**: 100 characters (ruff config)
- **Testing**: pytest with descriptive test names (test_verb_condition)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Detected Patterns

- **Hook Consolidation Pattern**: Single trigger.py handles PreToolUse, Stop, and SubagentStop hooks, routing based on hook_event_name
- **Hook Lifecycle Pattern**: PostToolUse tracks → Stop/PreToolUse blocks → Agent spawns → SubagentStop cleans up
- **Separation of Concerns**: PostToolUse (silent tracking) vs Stop/PreToolUse (blocking with output) vs SubagentStop (cleanup)
- **Dirty File Pattern**: Append-only tracking, batch processing at turn end
- **Skill Pattern**: YAML frontmatter + markdown body with algorithm sections
- **Template Pattern**: AUTO-MANAGED markers for updatable sections
- **Config Pattern**: JSON config in `.claude/auto-memory/config.json`
- **Inline Commit Context**: Commit hash and message stored inline with file paths in dirty-files (`/path/to/file [hash: message]`)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->
## Git Insights

Recent design decisions from commit history:
- Hook consolidation: stop.py removed, functionality merged into trigger.py for simpler maintenance
- SubagentStop hook added to automate dirty-files cleanup after agent completion
- Agent simplification: memory-updater.md no longer handles cleanup (delegated to SubagentStop)
- PreToolUse hook added for gitmode to intercept commits before they happen
- Template enforcement added to ensure consistent CLAUDE.md structure
- Git commit context enrichment for better change tracking
- Configurable trigger modes (default vs gitmode)
- Windows compatibility: python3/python fallback pattern in hook commands
- Default mode optimization: Skip git commit tracking (files already tracked via Edit/Write)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->
## Best Practices

From Claude Code documentation:
- Keep CLAUDE.md concise and focused on actionable guidance
- Use AUTO-MANAGED markers for sections that should be auto-updated
- Use MANUAL section for custom notes that persist across updates
- Subtree CLAUDE.md files inherit from root and add module-specific context

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Custom Notes

Add project-specific notes here. This section is never auto-modified.

<!-- END MANUAL -->

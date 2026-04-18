# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- AUTO-MANAGED: project-description -->
## Overview

**claude-code-auto-memory** - A Claude Code plugin that automatically maintains CLAUDE.md files (or AGENTS.md for multi-agent repos) as codebases evolve. Tracks file changes via hooks, spawns agents to update memory, and provides skills for codebase analysis.

Key features:
- Real-time file tracking via PostToolUse hooks
- Stop hook integration to trigger memory updates
- Codebase analyzer skill for initial setup
- Memory processor skill for ongoing updates
- AGENTS.md support for multi-agent workflows (OpenAI Codex, Gemini, etc.)

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
2. PostToolUse hook appends paths to session-specific `.claude/auto-memory/dirty-files-{session_id}` (falls back to `dirty-files` without session_id)
3. PreToolUse hook (gitmode only) denies git commit until dirty files processed
4. Stop hook detects dirty files, blocks Claude, requests agent spawn
5. memory-updater agent processes files and updates CLAUDE.md
6. SubagentStop hook auto-commits CLAUDE.md (if configured), clears dirty-files, cleans up stale session files

Configuration:
- Trigger modes: `default` (after every turn) or `gitmode` (only after git commits)
- `memoryFiles`: Array specifying which memory file(s) to maintain - `["CLAUDE.md"]` (default), `["AGENTS.md"]`, or `["CLAUDE.md", "AGENTS.md"]` (AGENTS.md holds content, CLAUDE.md redirects)
- `autoCommit`: When true, auto-commits memory file changes after memory-updater completes
- `autoPush`: When true (requires autoCommit), pushes commits to remote
- Config stored in `.claude/auto-memory/config.json`
- Init wizard interactively configures triggerMode, memoryFiles, autoCommit, and autoPush, then updates `.gitignore` to exclude `dirty-files*` tracking files

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
- **Initialization Guard Pattern**: `plugin_initialized()` in post-tool-use.py, handle_stop(), and handle_pre_tool_use() gates all activity on config.json existence — projects that never ran /auto-memory:init are fully inert
- **Hook Lifecycle Pattern**: PostToolUse tracks → Stop/PreToolUse blocks → Agent spawns → SubagentStop cleans up (cleanup gated on dirty-files only, not config.json, to prevent infinite loops)
- **Separation of Concerns**: PostToolUse (silent tracking) vs Stop/PreToolUse (blocking with output) vs SubagentStop (cleanup)
- **Dirty File Pattern**: Dict-keyed deduplication (path as key), batch processing at turn end, session-isolated via `dirty-files-{session_id}`; commit context entries overwrite plain path entries when present
- **Skill Pattern**: YAML frontmatter + markdown body with algorithm sections
- **Template Pattern**: AUTO-MANAGED markers for updatable sections
- **Config Pattern**: JSON config in `.claude/auto-memory/config.json` with `triggerMode`, `autoCommit`, `autoPush`
- **Inline Commit Context**: Commit hash and message stored inline with file paths in dirty-files (`/path/to/file [hash: message]`)
- **Session Isolation Pattern**: `session_id` from hook stdin JSON used to scope dirty-files per session, with fallback to shared file for backwards compatibility
- **Stale Session Cleanup Pattern**: `cleanup_stale_session_files()` removes orphaned session dirty-files older than 24h on each SubagentStop
- **Dirty-Files Read Order**: memory-updater reads plain `dirty-files` first; checks session-specific `dirty-files-*` files only if plain file is empty or missing
- **Gitignore Management Pattern**: `/auto-memory:init` appends `.claude/auto-memory/dirty-files*` to `.gitignore` (creates file if absent) so tracking files are never committed
- **Bash Tracking Scope Pattern**: `extract_files_from_bash()` only tracks explicit file-destructive commands (rm, git rm, mv, git mv, unlink); all other Bash commands (read-only, build tools, package managers) are skipped; parser stops at shell operators (`&&`, `||`, `;`, `|`) and redirects
- **Test Init Helper Pattern**: `_init_config(tmp_path)` creates `.claude/auto-memory/config.json` in tests to satisfy the `plugin_initialized()` guard; tests that verify inert behavior deliberately omit this call
- **Memory File Selection Pattern**: `memoryFiles` in config.json determines active memory file; memory-updater reads config to find `AGENTS.md` or `CLAUDE.md` instances; skills and commands all respect this config rather than hardcoding CLAUDE.md
- **AGENTS.md Redirect Pattern**: When both CLAUDE.md and AGENTS.md are configured, CLAUDE.md contains a single-line redirect (`Read AGENTS.md in this directory for project context.`); memory-processor skips updating redirect files
- **Multi-Agent Memory Pattern**: AGENTS.md support enables shared memory across Claude Code, OpenAI Codex, Gemini, and other agents that read AGENTS.md; auto-commit message uses `chore: update memory files [auto-memory]` when AGENTS.md is involved

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
- SubagentStop cleanup gated on dirty-files only (not config.json): requiring config.json caused infinite Stop-hook loops on uninitialized projects where dirty-files never got cleared
- Initialization guard added (#17): plugin_initialized() check in PostToolUse, Stop, and PreToolUse keeps the plugin fully inert on projects that never ran /auto-memory:init
- Type annotations tightened: dict[str, Any] generics, typed main() -> None, narrowed handle_git_commit return type
- Session-aware dirty-files (#16): session_id from hook stdin JSON scopes dirty-files per session, preventing cross-session interference in concurrent workflows
- Auto-commit/push toggle (#18): autoCommit and autoPush config options in SubagentStop handler, commits only CLAUDE.md files with graceful failure handling
- handle_subagent_stop signature changed from (project_dir) to (input_data, project_dir) to receive session_id and support auto-commit config loading
- SubagentStop cleanup fix (#28/#29): build_spawn_reason() now explicitly passes subagent_type='auto-memory:memory-updater' in Task tool spawn instructions - omitting it caused SubagentStop to not fire and dirty-files to never be cleared
- AGENTS.md support added (#14, v0.9.2): `memoryFiles` config option enables maintaining AGENTS.md instead of or alongside CLAUDE.md; init wizard, status, sync, codebase-analyzer, and memory-processor all updated to respect this config; CLAUDE.md redirect file generated when both are configured

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

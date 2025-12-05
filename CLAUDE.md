# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- AUTO-MANAGED: project-description -->
## Overview

**auto-memory** - Automatically maintains CLAUDE.md files as codebases evolve. Tagline: "Your CLAUDE.md, always in sync. Minimal tokens. Zero config. Just works."

Watches what Claude Code edits, deletes, and moves - then quietly updates project memory in the background. Uses PostToolUse hooks to track Edit/Write/Bash operations (including rm, mv, git rm, git mv, unlink), stores changes in .claude/auto-memory/dirty-files, then triggers isolated memory-updater agent to process and update memory sections. Processing runs in separate context window, consuming no main session tokens.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->
## Build & Development Commands

- `uv sync` - Install dependencies (uses uv package manager)
- `uv run pytest` - Run full test suite
- `uv run pytest tests/test_hooks.py -v` - Run specific test file with verbose output
- `uv run ruff check .` - Lint code (E, F, I, N, W, UP rules, 100 char line length)
- `uv run ruff format .` - Format code to style standards
- `uv run mypy .` - Type checking in strict mode

**Package**: Published as `claude-code-auto-memory` on PyPI with minimal dependencies

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Architecture

```
claude-code-auto-memory/
├── scripts/           # Python hook scripts (see scripts/CLAUDE.md)
│   ├── post-tool-use.py  # Tracks edited files; detects git commits for context enrichment
│   └── stop.py           # Blocks stop if dirty files exist, triggers memory-updater
├── skills/            # Skill definitions (SKILL.md files)
│   ├── codebase-analyzer/  # Analyzes codebase, generates CLAUDE.md templates
│   ├── memory-processor/   # Processes file changes, updates CLAUDE.md sections
│   └── shared/references/  # Shared reference files for skills
├── commands/          # Slash commands (markdown files)
│   ├── init.md               # /auto-memory:init - Initialize auto-memory plugin
│   ├── calibrate.md          # /auto-memory:calibrate - Full codebase recalibration
│   ├── sync.md               # /auto-memory:sync - Sync manual file changes
│   └── status.md             # /auto-memory:status - Show memory status
├── agents/            # Agent definitions
│   └── memory-updater.md  # Orchestrates CLAUDE.md updates with 6-phase workflow
├── hooks/             # Hook configuration
│   └── hooks.json        # PostToolUse and Stop hook definitions
└── tests/             # pytest test suite (see tests/CLAUDE.md)
```

**Data Flow**: Edit/Write/Bash -> post-tool-use.py -> .claude/auto-memory/dirty-files -> stop.py -> memory-updater agent -> memory-processor skill -> CLAUDE.md updates

**State Files** (in `.claude/auto-memory/`):
- `dirty-files` - Pending file list with optional inline commit context: `/path [hash: message]`
- `config.json` - Trigger mode configuration (default or gitmode)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Code Conventions

- **Python**: Target Python 3.9+, use type hints, strict mypy mode
- **Line length**: 100 characters max (ruff configuration)
- **Linting**: Use ruff (E, F, I, N, W, UP rules)
- **Imports**: Sorted alphabetically (ruff I rules)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Docstrings**: Triple-quoted, describe purpose at module/function level
- **Testing**: pytest with test_ prefix (see tests/CLAUDE.md)
- **Command YAML**: Frontmatter requires `description` field; `name` is optional

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Detected Patterns

- **Hook Scripts**: Produce no stdout output (minimal token cost design)
- **File Filtering**: Exclude `.claude/` directory and CLAUDE.md files to prevent infinite loops
- **Bash Operation Tracking**: Detects rm, mv, git rm, git mv, unlink; use `shlex.split()` for parsing
- **Command Skip List**: Filter read-only commands before processing
- **Path Resolution**: Convert relative paths to absolute, then resolve symlinks
- **CLAUDE.md Markers**: Use `<!-- AUTO-MANAGED: section-name -->` and `<!-- END AUTO-MANAGED -->`
- **Manual Sections**: Use `<!-- MANUAL -->` markers for user-editable content
- **Dirty File Format**: One path per line, optional inline commit context: `/path [hash: message]`
- **Deduplication**: Read into dict (path -> full line), commit context overwrites plain paths
- **Trigger Modes**: `default` tracks all operations; `gitmode` only triggers on git commits
- **Git Commit Enrichment**: Enrich paths with inline commit context for semantic updates

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Custom Notes

Add project-specific notes here. This section is never auto-modified.

<!-- END MANUAL -->

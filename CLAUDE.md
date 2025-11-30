# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- AUTO-MANAGED: project-description -->
## Overview

**auto-memory** - automatically maintains CLAUDE.md files as codebases evolve. Tagline: "Your CLAUDE.md, always in sync. Minimal tokens. Zero config. Just works."

Watches what Claude Code edits, deletes, and moves - then quietly updates project memory in the background. Uses PostToolUse hooks to track Edit/Write/Bash operations (including rm, mv, git rm, git mv, unlink), stores changes in .dirty-files, then triggers isolated memory-updater agent to process and update memory sections with detected patterns, conventions, and architecture insights. Processing runs in separate context window, consuming no main session tokens.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->
## Build & Development Commands

- `uv sync` - Install dependencies (uses uv package manager)
- `uv run pytest` - Run full test suite
- `uv run pytest tests/test_hooks.py -v` - Run specific test file with verbose output
- `uv run ruff check .` - Lint code (E, F, I, N, W, UP rules, 100 char line length)
- `uv run ruff format .` - Format code to style standards
- `uv run mypy .` - Type checking in strict mode

**Package**: Published as `claude-code-auto-memory` on PyPI with minimal dependencies (dev dependencies: pytest, pyyaml, ruff, mypy)
**Plugin**: Version 0.4.0, plugin.json defines commands namespace at `./commands/auto-memory/`

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Architecture

```
claude-code-auto-memory/
├── scripts/           # Python hook scripts
│   ├── post-tool-use.py  # Tracks edited files to .claude/.dirty-files
│   └── stop.py           # Blocks stop if dirty files exist, triggers memory-updater
├── skills/            # Skill definitions (SKILL.md files)
│   ├── codebase-analyzer/  # Analyzes codebase, generates CLAUDE.md templates
│   └── memory-processor/   # Processes file changes, updates CLAUDE.md sections
├── commands/          # Slash commands (markdown files)
│   └── auto-memory/      # Namespaced commands (/auto-memory:*)
│       ├── init.md          # Initialize CLAUDE.md structure
│       ├── calibrate.md     # Force recalibration
│       └── status.md        # Show sync status
├── agents/            # Agent definitions
│   └── memory-updater.md  # Orchestrates CLAUDE.md updates
├── hooks/             # Hook configuration
│   └── hooks.json        # PostToolUse and Stop hook definitions
└── tests/             # pytest test suite
```

**Data Flow**: Edit/Write/Bash (rm, mv, git rm, git mv, unlink) -> post-tool-use.py -> .dirty-files -> stop.py -> memory-updater agent -> memory-processor skill -> CLAUDE.md updates

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Code Conventions

- **Python**: Target Python 3.9+, use type hints, strict mypy mode
- **Line length**: 100 characters max (ruff configuration)
- **Linting**: Use ruff (E, F, I, N, W, UP rules)
- **Imports**: Sorted alphabetically (ruff I rules)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Docstrings**: Triple-quoted, describe purpose at module/function level
- **Testing**: pytest with test_ prefix and `test_*` function names, fixtures in conftest or test class methods
- **Type checking**: Enabled with mypy in strict mode

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Detected Patterns

- **Hook Scripts**: Produce no stdout output (minimal token cost design)
- **File Filtering**: Exclude `.claude/` directory and CLAUDE.md files to prevent tracking and infinite loops
- **Bash Operation Tracking**: Detects rm, mv, git rm, git mv, unlink commands to track file deletions/moves; use `shlex.split()` for robust command tokenization
- **Command Skip List**: Filter read-only commands (ls, git diff, npm, etc.) before processing to reduce noise
- **Path Resolution**: Convert relative paths to absolute using project_dir context, then resolve symlinks
- **CLAUDE.md Markers**: Use `<!-- AUTO-MANAGED: section-name -->` and `<!-- END AUTO-MANAGED -->` for auto-updated sections
- **Manual Sections**: Use `<!-- MANUAL -->` markers for user-editable content
- **Skill Templates**: Use `{{PLACEHOLDER}}` syntax for variable substitution
- **File Tracking**: Dirty files stored in `.claude/.dirty-files`, one path per line
- **Test Coverage**: Use subprocess to invoke hooks, verify zero output behavior, test file filtering logic

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->
## Git Insights

- Main branch workflow
- Feature branches for new functionality
- Commit messages describe the change purpose

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->
## Best Practices

- Run `uv run pytest` before committing changes
- Keep hook scripts silent (no output) to minimize token usage
- Use AUTO-MANAGED markers for sections that should be auto-updated
- Keep CLAUDE.md under 500 lines; use imports for detailed specs
- Test hook scripts with subprocess to verify zero output behavior

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Custom Notes

Add project-specific notes here. This section is never auto-modified.

<!-- END MANUAL -->

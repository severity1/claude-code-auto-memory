# tests/CLAUDE.md

Subtree memory for pytest test suite.

<!-- AUTO-MANAGED: purpose -->
## Purpose

This directory contains pytest tests for the auto-memory plugin. Tests verify hook script behavior, skill processing, and integration flows.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: files -->
## Test Files

- **test_hooks.py** - Tests for hook scripts (post-tool-use.py, stop.py). Uses subprocess to invoke scripts and verify behavior.
- **test_integration.py** - Integration tests for end-to-end workflows
- **test_skills.py** - Tests for skill definitions and processing logic

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Test Patterns

- **subprocess invocation**: Use `subprocess.run()` to test hook scripts as black boxes
- **tmp_path fixture**: Use pytest's `tmp_path` for isolated test directories
- **Class-based tests**: Group related tests in classes (e.g., `TestPostToolUseHook`, `TestGitCommitContext`)
- **JSON input helpers**: Use `_make_tool_input()` and `_make_bash_input()` helper methods
- **Environment setup**: Set `CLAUDE_PROJECT_DIR` via env dict passed to subprocess
- **Zero output assertion**: Verify hooks produce no stdout (token cost validation)
- **Git test setup**: Initialize test git repos with initial commit for diff-tree tests

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Conventions

- Test files: `test_*.py` prefix
- Test functions: `test_*` prefix
- Test classes: `Test*` prefix (no inheritance needed)
- Fixtures: Use pytest fixtures or class methods for setup
- Assertions: Use plain `assert` statements
- Environment isolation: Always use `tmp_path`, never modify real project state

<!-- END AUTO-MANAGED -->

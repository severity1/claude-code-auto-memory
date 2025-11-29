# claude-code-auto-memory

**Your CLAUDE.md, always in sync.** Minimal tokens. Zero config. Just works.

A Claude Code plugin that watches what Claude Code edits, deletes, and moves - then quietly updates your project documentation in the background. No manual maintenance needed.

[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-blueviolet)](https://claude.ai/code)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Config](https://img.shields.io/badge/setup-zero--config-brightgreen)]()
[![Token Efficient](https://img.shields.io/badge/tokens-minimal--overhead-blue)]()

## The Problem

CLAUDE.md files become stale as codebases evolve:

- Build commands change but documentation stays outdated
- Architecture shifts go unrecorded
- Code conventions drift without documentation
- New team members get incorrect context

**Manual maintenance is tedious and often forgotten.**

## The Solution

claude-code-auto-memory automatically updates CLAUDE.md when Claude Code makes changes. Processing happens in an isolated agent, so it doesn't consume your main conversation's context window.

```
Claude Code edits code -> Plugin tracks changes -> Isolated agent updates docs -> Context stays fresh
```

## Features

- **Automatic sync**: Tracks Edit/Write/Bash operations and updates CLAUDE.md at end of turn
- **Bash operation tracking**: Detects rm, mv, git rm, git mv, unlink commands
- **Minimal-token tracking**: PostToolUse hook has no output; stop hook triggers isolated agent
- **Isolated processing**: Agent runs in separate context window, doesn't consume main session tokens
- **Marker-based updates**: Only modifies AUTO-MANAGED sections, preserves manual content
- **Subtree support**: Hierarchical CLAUDE.md for monorepos

## Installation

### From Marketplace

```bash
claude plugin marketplace add severity1/claude-code-marketplace
claude plugin install auto-memory@claude-code-marketplace
```

### Local Development

```bash
# Add local marketplace
claude plugin marketplace add /path/to/claude-code-auto-memory/.dev-marketplace/.claude-plugin/marketplace.json

# Install from local
claude plugin install auto-memory@local-dev
```

## Commands

### `/memory-init`

Initialize CLAUDE.md structure for your project with an interactive wizard.

```
/memory-init
```

The wizard will:
1. Analyze your codebase structure
2. Detect frameworks and build commands
3. Identify subtree candidates (for monorepos)
4. Present findings for your approval
5. Generate CLAUDE.md with auto-managed sections

### `/memory-calibrate`

Force a full recalibration of all CLAUDE.md files.

```
/memory-calibrate
```

### `/memory-status`

Show current sync status and pending changes.

```
/memory-status
```

## How It Works

```mermaid
sequenceDiagram
    participant User
    participant Claude as Claude Code
    participant PostHook as PostToolUse Hook
    participant DirtyFiles as .dirty-files
    participant StopHook as Stop Hook
    participant Agent as memory-updater Agent
    participant Skill as memory-processor Skill

    User->>Claude: Edit files
    Claude->>PostHook: Edit/Write/Bash operation
    PostHook->>DirtyFiles: Append file path (zero tokens)
    Note over PostHook: No output - pure tracking

    User->>Claude: Continue working...
    Claude->>PostHook: More edits
    PostHook->>DirtyFiles: Append paths

    Note over Claude: Turn ends
    Claude->>StopHook: End of turn
    StopHook->>DirtyFiles: Check for dirty files

    alt Dirty files exist
        StopHook->>Agent: Spawn isolated agent
        Agent->>Skill: Invoke memory-processor
        Skill->>Skill: Analyze changes
        Skill->>Skill: Update CLAUDE.md sections
        Agent-->>StopHook: Complete
        StopHook->>DirtyFiles: Clear processed files
    else No dirty files
        Note over StopHook: No action needed
    end
```

### Architecture Overview

```
PostToolUse Hook (Edit|Write|Bash)
    |
    v (append file paths)
.claude/.dirty-files
    |
    v (end of turn)
Stop Hook
    |
    v (spawn agent)
memory-updater Agent (isolated context)
    |
    v (invoke skill)
memory-processor Skill
    |
    v
CLAUDE.md updated
```

### Token Efficiency

- **PostToolUse hook**: Zero token cost (no output)
- **Stop hook**: Minimal output only when dirty files exist
- **Agent**: Runs in isolated context window - doesn't consume main session tokens
- **Skills**: Progressive disclosure - load only when invoked

## CLAUDE.md Format

Auto-managed sections use HTML comment markers:

```markdown
<!-- AUTO-MANAGED: section-name -->
Content automatically updated by plugin
<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
Content never touched by plugin
<!-- END MANUAL -->
```

### Supported Sections

- `project-description` - Project overview
- `build-commands` - Build, test, lint commands
- `architecture` - Directory structure, components
- `conventions` - Code standards, naming patterns
- `patterns` - AI-detected coding patterns
- `git-insights` - Decisions from commit history
- `best-practices` - From official Claude Code docs

## Development

### Setup

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Type check
uv run mypy .
```

### Project Structure

```
claude-code-auto-memory/
├── .claude-plugin/
│   └── plugin.json           # Plugin metadata
├── hooks/
│   └── hooks.json            # Hook registration
├── scripts/
│   ├── post-tool-use.py      # Track file changes
│   └── stop.py               # End-of-turn trigger
├── agents/
│   └── memory-updater.md     # Orchestrator agent
├── skills/
│   ├── memory-processor/     # Update processing
│   └── codebase-analyzer/    # Init wizard
├── commands/
│   ├── memory-init.md
│   ├── memory-calibrate.md
│   └── memory-status.md
└── tests/
```

## Why claude-code-auto-memory?

| Feature | claude-code-auto-memory | Other Solutions |
|---------|-------------------|-----------------|
| Token overhead | **Minimal** (isolated agent) | Hook output adds tokens |
| External deps | **None** | SQLite, Vector DBs, Workers |
| Processing | **Isolated agent** | Inline or external service |
| Updates | **Marker-based** | Full file regeneration |
| Monorepo | **Subtree CLAUDE.md** | Root only |
| Config required | **None** | Config files needed |

See also: [memory-store-plugin](https://github.com/julep-ai/memory-store-plugin), [claude-mem](https://github.com/thedotmack/claude-mem), [claude-code-branch-memory-manager](https://github.com/Davidcreador/claude-code-branch-memory-manager)

## License

MIT

---

**Keywords**: Claude Code plugin, CLAUDE.md, automatic documentation, memory management, context persistence, token-efficient, zero-config, monorepo, AI coding assistant

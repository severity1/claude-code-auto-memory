# Claude Code Memory Guidelines

Follow the official Claude Code memory documentation:
https://code.claude.com/docs/en/memory

## Memory Scope (This Plugin)

This plugin manages **project-level** CLAUDE.md files only:
- **Project Root**: `./CLAUDE.md` or `./.claude/CLAUDE.md` - team-shared, version controlled
- **Subtree**: `./packages/*/CLAUDE.md`, `./apps/*/CLAUDE.md` - module-specific docs

## Content Rules

- **Be specific**: "Use 2-space indentation" not "Format code properly"
- **Include commands**: Build, test, lint, dev commands
- **Document patterns**: Code style, naming conventions, architectural decisions
- **Keep concise**: Target < 500 lines; use imports for detailed specs
- **Use structure**: Bullet points under descriptive markdown headings
- **Stay current**: Remove outdated information when updating
- **Avoid generic**: No "follow best practices" or "write clean code"
- **Exclude moving targets**: Never include ephemeral data that changes frequently:
  - Version numbers (e.g., "v1.2.3", "0.6.0")
  - Test counts or coverage percentages (e.g., "74 tests", "85% coverage")
  - Progress metrics (e.g., "3/5 complete", "TODO: 12 items")
  - Dates or timestamps (e.g., "last updated 2024-01-15")
  - Line counts or file sizes
  - Any metrics that become stale after each commit

## Marker Format

CLAUDE.md files use HTML comment markers for selective updates:

```markdown
<!-- AUTO-MANAGED: section-name -->
Content that will be automatically updated
<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
Content that will never be touched
<!-- END MANUAL -->
```

**CRITICAL**: Use the EXACT format above. Do NOT use variations:
- `<!-- BEGIN AUTO-MANAGED: name -->` - WRONG (no BEGIN prefix)
- `<!-- END AUTO-MANAGED: name -->` - WRONG (no name in closing tag)
- `<!-- AUTO-MANAGED section-name -->` - WRONG (missing colon after AUTO-MANAGED)

## Import System

- Syntax: `@path/to/import` or `@~/path/from/home`
- Supports relative and absolute paths
- Max 5 recursive import hops
- Not evaluated inside code blocks

## Discovery

- Claude searches recursively from cwd upward to root
- Subtree memories load when accessing files in those directories

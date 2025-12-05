---
name: memory-processor
description: Process file changes and update CLAUDE.md memory sections
---

# Memory Processor

Process changed files and update relevant CLAUDE.md sections following official guidelines.

## Official Guidelines (Primary Reference)

Follow the official Claude Code memory documentation:
https://code.claude.com/docs/en/memory

### Memory Scope (This Plugin)
This plugin manages **project-level** CLAUDE.md files only:
- **Project Root**: `./CLAUDE.md` or `./.claude/CLAUDE.md` - team-shared, version controlled
- **Subtree**: `./packages/*/CLAUDE.md`, `./apps/*/CLAUDE.md` - module-specific docs

### Content Rules
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

### Import System
- Syntax: `@path/to/import` or `@~/path/from/home`
- Supports relative and absolute paths
- Max 5 recursive import hops
- Not evaluated inside code blocks

### Discovery
- Claude searches recursively from cwd upward to root
- Subtree memories load when accessing files in those directories

## Algorithm

1. **Parse context**: Read context provided by memory-updater agent:
   - Changed files with categories
   - File content summaries
   - Detected dependencies
   - Git context (commits, diffs)
   - Target CLAUDE.md files

2. **Categorize changes**: Map files to CLAUDE.md sections:

   **Root CLAUDE.md triggers:**
   - **BUILD**: `package.json`, `Makefile`, `*.config.*`, `Dockerfile`, `pyproject.toml`, `Cargo.toml`, `go.mod`
   - **ARCHITECTURE**: `src/**/*`, `lib/**/*`, new directories, major structural changes
   - **CONVENTIONS**: Source files with new patterns (naming, imports, error handling)

   **Subtree CLAUDE.md triggers:**
   - **MODULE-DESCRIPTION**: Module README, main entry files
   - **ARCHITECTURE**: Files within the module directory
   - **CONVENTIONS**: Module-specific patterns
   - **DEPENDENCIES**: Import statements, local package.json/requirements.txt

3. **Analyze impact**: Determine what needs updating:
   - New build commands added?
   - Architecture changed (new dirs, renamed components)?
   - New coding patterns detected?
   - Dependencies added/removed?

4. **Update CLAUDE.md**: Modify relevant sections:
   - Preserve AUTO-MANAGED markers
   - Never touch MANUAL sections
   - Apply content rules (specific, concise, structured)
   - Remove outdated info when replacing

5. **Validate**: Ensure updates follow guidelines:
   - No generic instructions added
   - Specific and actionable content
   - Proper markdown formatting

## Marker Syntax

CLAUDE.md uses HTML comment markers for selective updates:

```markdown
<!-- AUTO-MANAGED: section-name -->
Content that will be automatically updated
<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
Content that will never be touched
<!-- END MANUAL -->
```

## Section Names

### Root CLAUDE.md Sections

| Section | Purpose | Update Triggers |
|---------|---------|-----------------|
| `project-description` | Project overview | README changes, major refactors |
| `build-commands` | Build, test, lint commands | package.json, Makefile, pyproject.toml |
| `architecture` | Directory structure, components | New dirs, renamed files, structural changes |
| `conventions` | Naming, imports, code standards | Pattern changes in source files |
| `patterns` | AI-detected coding patterns | Repeated patterns across files |
| `git-insights` | Decisions from git history | Significant commits |
| `best-practices` | From official Claude Code docs | Manual updates only |

### Subtree CLAUDE.md Sections

| Section | Purpose | Update Triggers |
|---------|---------|-----------------|
| `module-description` | Module purpose | Module README, major changes |
| `architecture` | Module structure | File changes within module |
| `conventions` | Module-specific conventions | Pattern changes in module |
| `dependencies` | Key module dependencies | Import changes, package updates |

## Token Efficiency

- Keep sections concise - bullet points, not paragraphs
- Remove outdated info rather than appending
- Use imports (`@path/to/file`) for detailed specs
- Target < 500 lines total per CLAUDE.md
- Root CLAUDE.md: 150-200 lines ideal

## Update Rules

1. **Only update relevant sections** - Match file changes to appropriate sections
2. **Preserve manual content** - Never modify `<!-- MANUAL -->` blocks
3. **Be specific** - "Run `npm test`" not "run tests"
4. **Stay concise** - Remove verbose explanations
5. **Maintain formatting** - Consistent markdown style

## Output

Return a brief summary:
- "Updated [section names] in [CLAUDE.md path] based on changes to [file names]"
- "No updates needed - changes do not affect documented sections"

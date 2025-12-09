---
name: memory-processor
description: Process file changes and update CLAUDE.md memory sections. Use when the memory-updater agent needs to analyze dirty files, update AUTO-MANAGED sections, verify content removal, or detect stale commands. Invoked after file edits to keep project memory in sync.
---

# Memory Processor

Process changed files and update relevant CLAUDE.md sections following official guidelines.

## Guidelines

**MANDATORY**: All rules below must be followed exactly. Violations produce incorrect CLAUDE.md content.

@../shared/references/guidelines.md

## Algorithm

1. **Parse context**: Read context provided by memory-updater agent:
   - Changed files with categories
   - File content summaries
   - Detected dependencies
   - Git context (commits, diffs)
   - Target CLAUDE.md files

2. **Categorize changes**: Map files to CLAUDE.md sections using the tables in "Section Names" below. Match changed files to their update triggers.

3. **Analyze impact**: Determine what needs updating:
   - New build commands added?
   - Architecture changed (new dirs, renamed components)?
   - New coding patterns detected?
   - Dependencies added/removed?

4. **Verify and update content**: Before modifying documented content, verify accuracy:

   **Key distinction - conventions vs patterns:**
   - `conventions`: Explicit rules humans decided (naming, imports, formatting)
   - `patterns`: Implicit patterns AI detected from recurring code structures

   **Removal verification:**
   - Read the relevant CLAUDE.md section to get currently documented items
   - For each item that appears missing from changed files:
     - Use Grep to search the codebase for that item
     - Search in relevant directories excluding node_modules, vendor, .git
     - If item exists elsewhere: keep it documented
     - If item is not found anywhere: mark for removal

   **Stale command detection:**
   - Compare documented commands against commands that actually executed successfully
   - If documented command differs from successful execution, update to match what worked
   - Examples:
     - Documented: `python pytest` | Actually worked: `python -m pytest` → Update
     - Documented: `npm test` | Actually worked: `npm run test` → Update
     - Documented: `pytest tests/` | Actually worked: `uv run pytest` → Update
   - Source: Successful Bash tool executions from session context or git commit history

   **Examples:**
   - Pattern: `@decorator` removed → search `grep -r "@decorator" src/`
   - Convention: `async/await` style removed → search for `async function` or `await`
   - Architecture: `utils/` directory deleted → verify no `utils/` references remain
   - Build command: `npm run dev` removed from package.json → verify script is gone

5. **Update CLAUDE.md**: Modify relevant sections:
   - Preserve AUTO-MANAGED markers
   - Never touch MANUAL sections
   - Apply content rules (specific, concise, structured)

6. **Validate**: Ensure updates follow guidelines:
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
- Use imports (`@path/to/file`) for detailed specs
- Follow Content Rules above (< 500 lines, stay current)

## Output

Return a brief summary:
- "Updated [section names] in [CLAUDE.md path] based on changes to [file names]"
- "Removed [pattern] from [section] - no longer used in codebase"
- "No updates needed - changes do not affect documented sections"

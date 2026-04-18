---
description: Show CLAUDE.md memory sync status
---

Display the current status of memory file synchronization.

Check and report:
1. **Pending changes**: Count of files in `.claude/auto-memory/dirty-files` (or session-specific `dirty-files-*` files) awaiting processing
2. **Active memory file**: Determined from `memoryFiles` in `.claude/auto-memory/config.json` - AGENTS.md if present in the list, otherwise CLAUDE.md
3. **Last sync**: Modification timestamp of the active memory file
4. **Memory file locations**: All instances of the active memory file found in the project (search by the active file name)
5. **Configuration**: Current trigger mode, memoryFiles, autoCommit, and autoPush settings from `.claude/auto-memory/config.json`

If there are pending changes, offer to run `/auto-memory:calibrate` to process them.

---
name: memory-status
description: Show CLAUDE.md sync status
---

Display the current status of CLAUDE.md synchronization.

Check and report:
1. **Pending changes**: Count of files in `.claude/.dirty-files` awaiting processing
2. **Last sync**: Modification timestamp of CLAUDE.md
3. **CLAUDE.md locations**: All CLAUDE.md files found in the project

If there are pending changes, offer to run `/memory-calibrate` to process them.

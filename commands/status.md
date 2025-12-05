---
description: Show CLAUDE.md memory sync status
---

Display the current status of CLAUDE.md memory synchronization.

Check and report:
1. **Pending changes**: Count of files in `.claude/auto-memory/dirty-files` awaiting processing
2. **Last sync**: Modification timestamp of CLAUDE.md
3. **CLAUDE.md locations**: All CLAUDE.md files found in the project

If there are pending changes, offer to run `/auto-memory:calibrate` to process them.

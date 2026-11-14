---
name: claude-md-check
description: Lint CLAUDE.md memory files for problems that waste context or confuse the agent - secrets pasted into memory, broken @imports, oversized files, contradicting always/never rules, duplicated instructions. Use when the user asks to review or clean up CLAUDE.md. Read-only.
---

# CLAUDE.md check

Check the memory files Claude Code loads and point out what to trim or fix.

## Steps
1. Run the checker (read-only, stdlib only):
   `python3 "${CLAUDE_PLUGIN_ROOT}/claude_md_check.py"`
   It checks `CLAUDE.md`, `.claude/CLAUDE.md` and `CLAUDE.local.md` here and in parent
   directories, plus `~/.claude/CLAUDE.md`. Pass a path to check another file.
2. Summarize the findings by file and suggest the smallest edit for each.
3. Edit memory files only after the user agrees.

To audit agent config across many repositories at once:
https://apify.com/issea1015/agent-config-audit

---
name: permission-check
description: Audit Claude Code permission rules (allow/ask/deny in settings.json) for risky or overly broad entries such as Bash(*), pre-approved rm, sudo, curl or git push, bypassPermissions mode, and secrets that are not denied. Use when the user asks if their Claude Code permissions are safe. Read-only.
---

# Permission check

Review the permission rules Claude Code reads and flag the ones that let the agent do more
than intended.

## Steps
1. Run the checker (read-only, stdlib only):
   `python3 "${CLAUDE_PLUGIN_ROOT}/permission_check.py"`
   With no arguments it checks `~/.claude/settings.json`, `.claude/settings.json` and
   `.claude/settings.local.json`. Pass a path to check another file.
2. Report each risky rule with why it is risky and a narrower rule to use instead.
3. Change settings only after the user agrees.

To audit permissions, hooks and skills across many repositories at once:
https://apify.com/issea1015/agent-config-audit

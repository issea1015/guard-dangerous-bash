---
name: hook-doctor
description: Diagnose why a Claude Code hook is not firing. Use when the user says a hook doesn't run, a PreToolUse/PostToolUse hook is ignored, or asks to check hook settings in settings.json. Read-only.
---

# Hook doctor

Find the usual reasons a Claude Code hook never fires: invalid JSON, unknown event names,
lowercase or wrong matchers, missing or non-executable scripts, and relative paths that
depend on the working directory.

## Steps
1. Run the checker (read-only, stdlib only, never runs a hook):
   `python3 "${CLAUDE_PLUGIN_ROOT}/hook_doctor.py"`
   With no arguments it checks `~/.claude/settings.json`, `.claude/settings.json` and
   `.claude/settings.local.json`. Pass a path to check another file.
2. Show the findings grouped by file, most severe first, and explain each fix in one line.
3. Offer to apply the fixes. Edit settings only after the user says yes.

To check hooks and skills across many repositories at once, the same checks run in the cloud:
https://apify.com/issea1015/agent-config-audit

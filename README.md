# guard-dangerous-bash: a Claude Code hook that blocks catastrophic commands

A free, single-file **PreToolUse** hook. Before Claude Code runs a shell command, the hook blocks:

- `rm -rf /`, `rm -rf ~`, `rm -rf $HOME`
- force pushes to `main` / `master`
- `mkfs`, `dd of=/dev/sdX`, redirects onto disk devices
- `curl … | sh` (piping a remote script into a shell)
- fork bombs, `chmod -R 777 /`

Claude sees why the command was blocked and changes its approach. Everything else passes through.

## Install as a plugin (one line)
In Claude Code:
```
/plugin install guard-dangerous-bash --marketplace issea1015/guard-dangerous-bash
```
On older versions: `/plugin marketplace add issea1015/guard-dangerous-bash`, then `/plugin install guard-dangerous-bash@guard-dangerous-bash`.

## Or install by hand (1 minute)
```bash
mkdir -p ~/.claude/hooks
curl -o ~/.claude/hooks/guard-dangerous-bash.py \
  https://raw.githubusercontent.com/issea1015/guard-dangerous-bash/main/guard.py   # or copy guard.py by hand
```
Read the file before you install it; it's about 50 lines of standard-library Python.
Then add this to `~/.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/guard-dangerous-bash.py" }] }
    ]
  }
}
```

## Test it
```bash
python3 -m unittest discover -s tests
```

## Hook not firing? `hook_doctor.py`
A second free, read-only script in this repo. It checks the settings files Claude Code reads for the mistakes that make a hook
silently do nothing: invalid JSON, misspelled event names, lowercase matchers (`bash` never matches `Bash`), missing or
non-executable scripts, and relative paths that break when the working directory changes.
```bash
python3 hook_doctor.py                          # checks ~/.claude/settings.json and .claude/settings*.json
python3 hook_doctor.py path/to/settings.json    # or a specific file
```
```
ERROR .claude/settings.json hooks.PreToolUse[0]: matcher 'bash' never matches: tool names are case-sensitive, use 'Bash'
ERROR .claude/settings.json hooks.PreToolUse[0]: script not found: .claude/hooks/guard.py
```
Full checklist: [Claude Code hook not working?](https://issea1015.github.io/agent-workflow-kit/guides/claude-code-hook-not-working.html?utm_source=guard-readme)

## Too many "don't ask again"s? `permission_check.py`
Free and read-only. Flags permission rules that let the agent run anything (`Bash`, `Bash(*)`), pre-approve risky commands
(`rm`, `sudo`, `curl`, `git push`, ...), `bypassPermissions` mode, and a missing deny rule for `.env`.
```bash
python3 permission_check.py      # checks ~/.claude/settings.json and .claude/settings*.json
```
Guide: [a safe allow list for Claude Code](https://issea1015.github.io/agent-workflow-kit/guides/claude-code-permissions-allow-list.html?utm_source=guard-readme)

## Safety audit
- Reads stdin only. It makes **no network calls, writes no files, and launches no subprocesses**.
- Standard library only (Python 3.8+). On malformed input it lets the command through, so it can't lock up a session.
- It is a safety net, not a sandbox.
- `hook_doctor.py` and `permission_check.py` only read settings files and check whether scripts exist; they never run a hook or a command.

## Want more?
This hook is one of 15 items in the **Agent Workflow Kit**: 3 safety hooks (including one that keeps `.env` and keys out
of the agent's context), 9 workflow skills, 3 CLAUDE.md templates, and `audit.py`, which checks every hook already
configured on your machine for download-and-run, secret access and network calls.
→ **https://issea1015.github.io/agent-workflow-kit/** ($29 launch price)

MIT licensed (this hook only).

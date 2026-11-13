#!/usr/bin/env python3
"""hook_doctor: find out why a Claude Code hook isn't firing.

Checks the hook settings Claude Code reads (user, project, local) for the usual
mistakes: invalid JSON, unknown event names, lowercase matchers, scripts that don't
exist or aren't executable, and relative paths that depend on the working directory.
Read-only: it never runs a hook. Stdlib only.

Usage: python3 hook_doctor.py [settings.json ...]
With no arguments it checks ~/.claude/settings.json, .claude/settings.json and
.claude/settings.local.json (the ones that exist).
"""
import json
import os
import re
import shlex
import sys
from pathlib import Path

EVENTS = {
    "PreToolUse", "PostToolUse", "Notification", "UserPromptSubmit", "Stop",
    "SubagentStop", "PreCompact", "SessionStart", "SessionEnd",
}
TOOLS = {
    "Bash", "Edit", "MultiEdit", "Write", "Read", "Glob", "Grep", "LS", "Task",
    "WebFetch", "WebSearch", "NotebookEdit", "NotebookRead", "TodoWrite",
}
TOOL_EVENTS = {"PreToolUse", "PostToolUse"}
DEFAULT_FILES = ["~/.claude/settings.json", ".claude/settings.json", ".claude/settings.local.json"]
SCRIPT_EXT = (".py", ".sh", ".js", ".ts", ".rb", ".pl", ".bash", ".zsh")
INTERPRETERS = {"python", "python3", "bash", "sh", "zsh", "node", "ruby", "perl", "bun", "deno", "uv", "uvx"}


def check_matcher(where, event, matcher, out):
    if event not in TOOL_EVENTS or matcher in ("", "*", None):
        return
    for part in re.split(r"\|", matcher):
        name = part.strip()
        if not name or not re.fullmatch(r"[A-Za-z_]+", name) or name in TOOLS:
            continue  # regexes and mcp__ names are not checked
        fix = next((t for t in TOOLS if t.lower() == name.lower()), None)
        if fix:
            out.append(("ERROR", where, f"matcher {name!r} never matches: tool names are case-sensitive, use {fix!r}"))
        else:
            out.append(("WARN", where, f"matcher {name!r} is not a built-in tool name (fine if it's an MCP tool)"))


def script_refs(command):
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    refs = []
    for i, w in enumerate(words):
        if w.endswith(SCRIPT_EXT) and "/" in w or (w.endswith(SCRIPT_EXT) and i > 0 and Path(words[i - 1]).name in INTERPRETERS):
            refs.append((w, i == 0))
    return refs


def check_command(where, command, settings_file, out):
    project = settings_file.parent.parent if settings_file.parent.name == ".claude" else Path.cwd()
    for ref, direct in script_refs(command):
        expanded = ref.replace("$CLAUDE_PROJECT_DIR", str(project)).replace("${CLAUDE_PROJECT_DIR}", str(project))
        expanded = os.path.expanduser(os.path.expandvars(expanded))
        path = Path(expanded)
        if not path.is_absolute():
            out.append(("WARN", where, f"{ref} is relative to the working directory; use \"$CLAUDE_PROJECT_DIR\"/{ref[2:] if ref.startswith('./') else ref}"))
            path = project / path
        if "${CLAUDE_PLUGIN_ROOT}" in ref or "$CLAUDE_PLUGIN_ROOT" in ref:
            continue
        if not path.exists():
            out.append(("ERROR", where, f"script not found: {path}"))
        elif direct and not os.access(path, os.X_OK):
            out.append(("ERROR", where, f"{path} is run directly but isn't executable: chmod +x {path}"))


def check_file(path):
    out = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [("ERROR", str(path), f"invalid JSON ({e}); Claude Code ignores the whole file")]
    hooks = data.get("hooks", {}) if isinstance(data, dict) else {}
    if not isinstance(hooks, dict):
        return [("ERROR", str(path), '"hooks" must be an object keyed by event name')]
    for event, groups in hooks.items():
        if event not in EVENTS:
            fix = next((e for e in EVENTS if e.lower() == event.lower()), None)
            hint = f", did you mean {fix!r}?" if fix else ""
            out.append(("ERROR", f"{path} hooks.{event}", f"unknown event name{hint}"))
            continue
        for i, group in enumerate(groups if isinstance(groups, list) else []):
            where = f"{path} hooks.{event}[{i}]"
            check_matcher(where, event, group.get("matcher"), out)
            for h in group.get("hooks", []):
                if h.get("type") == "command" and h.get("command"):
                    check_command(where, h["command"], path, out)
    return out


def main(argv):
    files = [Path(a) for a in argv] or [Path(os.path.expanduser(f)) for f in DEFAULT_FILES]
    files = [f for f in files if f.exists()]
    if not files:
        print("no settings files found")
        return 0
    findings = []
    for f in files:
        findings += check_file(f)
    for sev, where, msg in findings:
        print(f"{sev:5} {where}: {msg}")
    errors = sum(1 for f in findings if f[0] == "ERROR")
    print(f"checked {len(files)} file(s): {errors} error(s), {len(findings) - errors} warning(s)")
    print("Still stuck? Run /hooks inside Claude Code to see what's loaded, or start it with claude --debug.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""PreToolUse hook: block catastrophic Bash commands before Claude Code runs them.

Reads the hook JSON from stdin. If tool_name is Bash and the command matches a
dangerous pattern, prints the reason to stderr and exits 2, which blocks the call and
shows the reason to Claude. Otherwise exits 0. Stdlib only, no network, no writes.
"""
import json
import re
import sys

RULES = [
    (r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*\s+|-[a-zA-Z]*\s+)*(-[a-zA-Z]*[rR][a-zA-Z]*\s+)?(/|~|\$HOME)(\s|/?\*?\s*$|/?$)",
     "recursive delete of the root or home directory"),
    (r"\bgit\s+push\b.*(--force\b|-f\b|--force-with-lease\b).*\b(main|master)\b",
     "force push to main/master"),
    (r"\bgit\s+push\b.*\b(main|master)\b.*(--force\b|-f\b)",
     "force push to main/master"),
    (r"\bmkfs(\.\w+)?\b", "formatting a filesystem"),
    (r"\bdd\b.*\bof=/dev/(sd|nvme|disk|hd)", "raw write to a disk device"),
    (r">\s*/dev/(sd|nvme|disk|hd)\w*", "redirect onto a disk device"),
    (r"(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", "piping a remote script into a shell"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "fork bomb"),
    (r"\bchmod\s+-R\s+0?777\s+/(\s|$)", "chmod 777 on the root directory"),
]


def check(command: str):
    for pattern, reason in RULES:
        if re.search(pattern, command):
            return reason
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # never break the session on malformed input
    if event.get("tool_name") != "Bash":
        return 0
    reason = check(event.get("tool_input", {}).get("command", ""))
    if reason:
        print(f"Blocked by guard-dangerous-bash: {reason}. "
              "If this is really intended, run it yourself outside Claude Code.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""permission_check: flag risky Claude Code permission rules.

Reads the "permissions" block of the settings files Claude Code uses and flags allow
rules that let the agent run anything (Bash, Bash(*)), rules that pre-approve dangerous
commands (rm, sudo, curl, git push, ...), bypassPermissions mode, and secrets that are not
denied. Read-only. Stdlib only.

Usage: python3 permission_check.py [settings.json ...]
With no arguments it checks ~/.claude/settings.json, .claude/settings.json and
.claude/settings.local.json (the ones that exist).
"""
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_FILES = ["~/.claude/settings.json", ".claude/settings.json", ".claude/settings.local.json"]
# Command prefixes that should never be pre-approved for an agent.
RISKY_BASH = {
    "rm": "deletes files", "sudo": "runs as root", "curl": "network access, can exfiltrate or download code",
    "wget": "network access, can download code", "ssh": "remote access", "scp": "copies files off the machine",
    "git push": "publishes code", "chmod": "changes permissions", "dd": "raw disk writes",
    "eval": "runs arbitrary strings", "bash": "runs any script", "sh": "runs any script",
    "python": "runs any code", "python3": "runs any code", "node": "runs any code",
    "npx": "downloads and runs packages", "docker": "root-equivalent on most machines",
    "kubectl": "changes clusters", "terraform": "changes infrastructure", "aws": "cloud account access",
    "gcloud": "cloud account access", "env": "prints secrets", "printenv": "prints secrets",
}
SECRET_READS = ["Read(./.env)", "Read(./.env.*)", "Read(./secrets/**)"]


def bash_prefix(rule):
    m = re.fullmatch(r"Bash\((.*)\)", rule.strip())
    if not m:
        return None
    body = m.group(1).strip()
    body = re.sub(r"(:\*|\s*\*)$", "", body).strip()  # "rm:*" and "rm *" both mean prefix "rm"
    return body


def check_file(path):
    out = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [("ERROR", str(path), f"invalid JSON ({e})")]
    perms = data.get("permissions") or {}
    if perms.get("defaultMode") == "bypassPermissions":
        out.append(("HIGH", str(path), "defaultMode is bypassPermissions: every tool call runs without asking"))
    for rule in perms.get("allow") or []:
        where = f"{path} permissions.allow {rule!r}"
        if rule.strip() in ("Bash", "Bash(*)", "Bash(:*)"):
            out.append(("HIGH", where, "allows every shell command without asking"))
            continue
        prefix = bash_prefix(rule)
        if prefix is not None:
            words = prefix.split()
            for key in (" ".join(words[:2]), words[0] if words else ""):
                if key in RISKY_BASH:
                    out.append(("HIGH" if key in ("rm", "sudo", "curl", "wget", "eval", "bash", "sh", "dd") else "MEDIUM",
                                where, f"pre-approves `{prefix}`: {RISKY_BASH[key]}"))
                    break
        elif rule.strip() in ("WebFetch", "WebFetch(*)"):
            out.append(("MEDIUM", where, "allows fetching any URL; prefer WebFetch(domain:example.com)"))
        elif rule.strip().startswith("mcp__") and "__" not in rule.strip()[5:]:
            out.append(("LOW", where, "allows every tool of this MCP server"))
    return out


def main(argv):
    files = [Path(a) for a in argv] or [Path(os.path.expanduser(f)) for f in DEFAULT_FILES]
    files = [f for f in files if f.exists()]
    if not files:
        print("no settings files found")
        return 0
    findings, denies = [], []
    for f in files:
        findings += check_file(f)
        try:
            denies += (json.loads(f.read_text()).get("permissions") or {}).get("deny") or []
        except (json.JSONDecodeError, AttributeError):
            pass
    if not any(".env" in d for d in denies):
        findings.append(("LOW", "all files", "no deny rule for .env; consider \"deny\": " + json.dumps(SECRET_READS)))
    order = {"ERROR": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    for sev, where, msg in sorted(findings, key=lambda f: order[f[0]]):
        print(f"{sev:6} {where}: {msg}")
    high = sum(1 for f in findings if f[0] in ("ERROR", "HIGH"))
    print(f"checked {len(files)} file(s): {'FAIL' if high else 'PASS'} ({high} high, {len(findings) - high} other)")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

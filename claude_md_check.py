#!/usr/bin/env python3
"""claude_md_check: lint CLAUDE.md memory files before they cost you context or leak a key.

Claude Code loads CLAUDE.md files (and the files they pull in with @path imports) into the
context of every session. This script reads them and flags:
  HIGH   secrets or tokens pasted into the file (API keys, private keys, passwords)
  ERROR  @imports that point at files that don't exist, unreadable files
  WARN   files that are long (lines, estimated tokens), import cycles, imports nested
         deeper than 5 hops, and "always X" / "never X" pairs that contradict each other
  INFO   the same instruction repeated in more than one place
Secrets are printed redacted. Read-only: no network, no writes, no subprocesses. Stdlib only.

Usage: python3 claude_md_check.py [CLAUDE.md ...]
With no arguments it checks CLAUDE.md, .claude/CLAUDE.md and CLAUDE.local.md in the current
directory and its parents, plus ~/.claude/CLAUDE.md (the ones that exist).
Exit code 1 if any HIGH or ERROR finding.
"""
import os
import re
import sys
from pathlib import Path

MAX_LINES = 200          # our threshold: past this, a memory file is usually doing too much
MAX_TOKENS = 5000        # rough estimate, 4 characters per token
MAX_DEPTH = 5            # import hops followed
SECRET_PATTERNS = [
    ("Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI API key", r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    ("AWS access key id", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    ("Stripe secret key", r"\b[rs]k_live_[A-Za-z0-9]{16,}"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("password or secret assignment",
     r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?(?!<|\$|\{|your|xxx|\*)[^\s'\"]{8,}"),
]
IMPORT_RE = re.compile(r"(?:^|(?<=\s))@((?:~|\.{1,2})?/?[^\s`'\"()<>\[\]]+)")
FILE_EXT = re.compile(r"\.(?:md|markdown|txt|json|ya?ml|toml|rst)$", re.I)


def strip_code(text):
    """Blank out fenced code blocks and inline code spans (imports there are not imports)."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else re.sub(r"`[^`]*`", "", line))
    return out


def import_targets(text):
    """Yield (line_no, raw, looks_like_path) for each @import outside code."""
    for no, line in enumerate(strip_code(text), 1):
        for m in IMPORT_RE.finditer(line):
            raw = m.group(1).rstrip(".,;:")
            pathlike = raw.startswith(("~/", "./", "../", "/")) or bool(FILE_EXT.search(raw))
            yield no, raw, pathlike


def resolve(raw, base):
    p = Path(os.path.expanduser(raw))
    return p if p.is_absolute() else (base.parent / p)


def redact(s):
    return s[:6] + "..." + f"({len(s)} chars)" if len(s) > 10 else "***"


def instruction_key(line):
    """'- Always use pnpm.' -> ('+', 'use pnpm'); 'Never use pnpm' -> ('-', 'use pnpm')."""
    s = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line).strip().lower().rstrip(".!")
    s = re.sub(r"\*\*|__", "", s)
    m = re.match(r"(always|never|don't|do not)\s+(.{3,})$", s)
    if not m:
        return None
    return ("+" if m.group(1) == "always" else "-"), m.group(2).strip()


def check_text(path, text):
    """Findings for one file's own content (no import following)."""
    out = []
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        out.append(("WARN", str(path), f"{len(lines)} lines (over {MAX_LINES}); it is loaded every session, "
                                       "move rarely needed detail into a file you @import or link"))
    for no, line in enumerate(lines, 1):
        for name, pat in SECRET_PATTERNS:
            m = re.search(pat, line)
            if m:
                out.append(("HIGH", f"{path}:{no}", f"possible {name} ({redact(m.group(0))}); "
                                                   "remove it and rotate the key"))
                break
    return out


class Checker:
    def __init__(self):
        self.findings, self.seen, self.tokens = [], set(), 0
        self.instructions = {}   # key -> list of (sign, where)

    def visit(self, path, depth=0, stack=()):
        path = Path(path)
        real = path.resolve()
        if real in stack:
            self.findings.append(("WARN", str(path), "import cycle: " + " -> ".join(p.name for p in stack + (real,))))
            return
        if real in self.seen:
            return
        self.seen.add(real)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.findings.append(("ERROR", str(path), f"cannot read ({e.strerror})"))
            return
        self.tokens += len(text) // 4
        self.findings += check_text(path, text)
        for no, line in enumerate(strip_code(text), 1):
            key = instruction_key(line)
            if key:
                self.instructions.setdefault(key[1], []).append((key[0], f"{path}:{no}"))
        for no, raw, pathlike in import_targets(text):
            target = resolve(raw, path)
            if not target.exists():
                if pathlike:
                    self.findings.append(("ERROR", f"{path}:{no}", f"@{raw} imports a file that does not exist "
                                                                   f"({target})"))
                continue
            if target.is_dir():
                continue
            if depth + 1 > MAX_DEPTH:
                self.findings.append(("WARN", f"{path}:{no}", f"@{raw} is nested more than {MAX_DEPTH} "
                                                              "imports deep and may not be loaded"))
                continue
            self.visit(target, depth + 1, stack + (real,))

    def finish(self):
        for text, uses in self.instructions.items():
            signs = {s for s, _ in uses}
            where = ", ".join(w for _, w in uses)
            if signs == {"+", "-"}:
                self.findings.append(("WARN", where, f"contradicting instructions: 'always {text}' and 'never {text}'"))
            elif len(uses) > 1:
                self.findings.append(("INFO", where, f"same instruction repeated {len(uses)} times: "
                                                     f"'{'always' if '+' in signs else 'never'} {text}'"))
        if self.tokens > MAX_TOKENS:
            self.findings.append(("WARN", "all files", f"about {self.tokens} tokens of memory load into every "
                                                       f"session (over {MAX_TOKENS}); trim or split"))
        return self.findings


def default_files(cwd=None, home=None):
    cwd = Path(cwd or os.getcwd()).resolve()
    found = []
    for d in [cwd] + list(cwd.parents):
        for name in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
            if (d / name).is_file():
                found.append(d / name)
    user = Path(home or os.path.expanduser("~")) / ".claude" / "CLAUDE.md"
    if user.is_file() and user.resolve() not in {f.resolve() for f in found}:
        found.append(user)
    return found


def main(argv):
    files = [Path(a) for a in argv] or default_files()
    if not files:
        print("no CLAUDE.md files found")
        return 0
    c = Checker()
    for f in files:
        c.visit(f)
    findings = c.finish()
    order = {"HIGH": 0, "ERROR": 1, "WARN": 2, "INFO": 3}
    for sev, where, msg in sorted(findings, key=lambda f: order[f[0]]):
        print(f"{sev:5} {where}: {msg}")
    bad = sum(1 for f in findings if f[0] in ("HIGH", "ERROR"))
    print(f"checked {len(c.seen)} file(s), ~{c.tokens} tokens: {'FAIL' if bad else 'PASS'} "
          f"({bad} high/error, {len(findings) - bad} other)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hook_doctor  # noqa: E402


def settings(tmp, hooks, raw=None):
    d = Path(tmp) / ".claude"
    d.mkdir(exist_ok=True)
    p = d / "settings.json"
    p.write_text(raw if raw is not None else json.dumps({"hooks": hooks}))
    return p


def msgs(findings):
    return " | ".join(f"{s} {m}" for s, _, m in findings)


class HookDoctorTest(unittest.TestCase):
    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIn("invalid JSON", msgs(hook_doctor.check_file(settings(t, None, '{"hooks": {,}'))))

    def test_event_name_case(self):
        with tempfile.TemporaryDirectory() as t:
            out = msgs(hook_doctor.check_file(settings(t, {"preToolUse": []})))
            self.assertIn("did you mean 'PreToolUse'", out)

    def test_lowercase_matcher(self):
        with tempfile.TemporaryDirectory() as t:
            p = settings(t, {"PreToolUse": [{"matcher": "bash", "hooks": []}]})
            self.assertIn("use 'Bash'", msgs(hook_doctor.check_file(p)))

    def test_missing_and_relative_script(self):
        with tempfile.TemporaryDirectory() as t:
            p = settings(t, {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3 .claude/hooks/guard.py"}]}]})
            out = msgs(hook_doctor.check_file(p))
            self.assertIn("script not found", out)
            self.assertIn("relative to the working directory", out)

    def test_not_executable(self):
        with tempfile.TemporaryDirectory() as t:
            s = Path(t) / "guard.sh"
            s.write_text("#!/bin/sh\nexit 0\n")
            os.chmod(s, 0o644)
            p = settings(t, {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": str(s)}]}]})
            self.assertIn("isn't executable", msgs(hook_doctor.check_file(p)))

    def test_clean_config(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / ".claude" / "hooks"
            d.mkdir(parents=True)
            (d / "guard.py").write_text("")
            p = settings(t, {"PreToolUse": [{"matcher": "Bash|Edit", "hooks": [
                {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.py'}]}]})
            self.assertEqual(hook_doctor.check_file(p), [])


if __name__ == "__main__":
    unittest.main()

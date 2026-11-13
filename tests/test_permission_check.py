import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import permission_check as pc  # noqa: E402


def check(perms):
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "settings.json"
        p.write_text(json.dumps({"permissions": perms}))
        return pc.check_file(p)


class PermissionCheckTest(unittest.TestCase):
    def test_allow_all_bash(self):
        self.assertEqual(check({"allow": ["Bash"]})[0][0], "HIGH")
        self.assertEqual(check({"allow": ["Bash(*)"]})[0][0], "HIGH")

    def test_risky_prefixes(self):
        sev = {f[2].split("`")[1]: f[0] for f in check({"allow": ["Bash(rm:*)", "Bash(git push:*)", "Bash(curl *)"]})}
        self.assertEqual(sev, {"rm": "HIGH", "git push": "MEDIUM", "curl": "HIGH"})

    def test_safe_rules_pass(self):
        self.assertEqual(check({"allow": ["Bash(npm run test:*)", "Bash(git status)", "Read(./src/**)",
                                          "WebFetch(domain:docs.python.org)"]}), [])

    def test_bypass_mode(self):
        self.assertIn("bypassPermissions", check({"defaultMode": "bypassPermissions"})[0][2])

    def test_webfetch_any(self):
        self.assertEqual(check({"allow": ["WebFetch"]})[0][0], "MEDIUM")


if __name__ == "__main__":
    unittest.main()

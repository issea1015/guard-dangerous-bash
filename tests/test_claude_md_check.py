import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import claude_md_check as cm  # noqa: E402


class ClaudeMdCheckTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.dir = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def run_on(self, *paths):
        c = cm.Checker()
        for p in paths:
            c.visit(p)
        return c.finish()

    def sevs(self, findings):
        return sorted(f[0] for f in findings)

    def test_clean_file_passes(self):
        self.write("docs/style.md", "Use 4 spaces.\n")
        p = self.write("CLAUDE.md", "# Project\n- Always run tests before committing.\n- See @docs/style.md\n")
        self.assertEqual(self.run_on(p), [])

    def test_secrets_flagged_and_redacted(self):
        key = "sk-ant-api03-" + "A" * 40
        p = self.write("CLAUDE.md", f"API key: {key}\nAWS AKIAABCDEFGHIJKLMNOP\npassword = hunter2hunter2\n")
        f = self.run_on(p)
        self.assertEqual(self.sevs(f), ["HIGH", "HIGH", "HIGH"])
        self.assertNotIn(key, " ".join(x[2] for x in f))

    def test_placeholders_are_not_secrets(self):
        p = self.write("CLAUDE.md", "password = <set in .env>\napi_key: $API_KEY\n")
        self.assertEqual(self.run_on(p), [])

    def test_broken_import(self):
        p = self.write("CLAUDE.md", "Read @docs/missing.md and @~/nope-xyz-123/x.md\n")
        f = self.run_on(p)
        self.assertEqual(self.sevs(f), ["ERROR", "ERROR"])

    def test_imports_in_code_and_emails_ignored(self):
        p = self.write("CLAUDE.md", "Mail a@b.md\n`@docs/missing.md`\n```\n@other/missing.md\n```\nnpm i @types/node\n")
        self.assertEqual(self.run_on(p), [])

    def test_import_cycle(self):
        a = self.write("CLAUDE.md", "@b.md\n")
        self.write("b.md", "@CLAUDE.md\n")
        self.assertIn("import cycle", self.run_on(a)[0][2])

    def test_depth_limit(self):
        for i in range(7):
            self.write(f"f{i}.md", f"@f{i + 1}.md\n")
        self.write("f7.md", "end\n")
        f = self.run_on(self.dir / "f0.md")
        self.assertEqual([x[0] for x in f], ["WARN"])
        self.assertIn("more than 5", f[0][2])

    def test_long_file(self):
        p = self.write("CLAUDE.md", "line\n" * 250)
        self.assertIn("250 lines", self.run_on(p)[0][2])

    def test_contradiction_and_duplicate(self):
        a = self.write("CLAUDE.md", "- Always use pnpm.\n- Never commit to main\n")
        b = self.write("CLAUDE.local.md", "- **Never** use pnpm\n- never commit to main.\n")
        f = self.run_on(a, b)
        self.assertEqual(self.sevs(f), ["INFO", "WARN"])
        self.assertIn("contradicting", [x for x in f if x[0] == "WARN"][0][2])

    def test_default_files_walks_parents(self):
        self.write("CLAUDE.md", "root\n")
        self.write("sub/.claude/CLAUDE.md", "sub\n")
        names = [str(p.relative_to(self.dir)) for p in cm.default_files(self.dir / "sub", home=self.dir / "nohome")]
        self.assertEqual(names, [str(Path("sub/.claude/CLAUDE.md")), "CLAUDE.md"])

    def test_main_exit_code(self):
        bad = self.write("CLAUDE.md", "@missing.md\n")
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cm.main([str(bad)]), 1)
        self.assertIn("FAIL", out.getvalue())


if __name__ == "__main__":
    unittest.main()

import pathlib, subprocess, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_commit_msg as c


class CommitMsgTests(unittest.TestCase):
    def test_accepts_conventional(self):
        for s in ["feat: add thing", "fix(config): handle empty file", "refactor!: drop old api",
                  "feat(evidence)!: change id format", "docs: update readme", "chore: x",
                  "test(scope-1.x/y): add", "revert: undo feat",
                  "Merge branch 'x' into main", 'Revert "feat: add thing"']:
            self.assertIsNone(c.problem(s + "\n\nbody\n"), s)

    def test_rejects_others(self):
        for s in ["Step 2: add", "add thing", "feat add thing", "feat:no space", "feat: ",
                  "Feat: caps", "feature: x", "feat(): x", "feat(Bad Scope): x", ""]:
            self.assertIsNotNone(c.problem(s + "\n"), repr(s))

    def test_subject_length(self):
        self.assertIsNotNone(c.problem("feat: " + "a" * 70 + "\n"))
        self.assertIsNone(c.problem("feat: " + "a" * 66 + "\n"))

    def test_body_must_be_separated(self):
        self.assertIsNotNone(c.problem("feat: a\nbody right away\n"))

    def test_comment_lines_ignored(self):
        self.assertIsNone(c.problem("# comment\nfeat: a\n# other\n"))

    def test_file_cli_and_hook(self):
        f = pathlib.Path(tempfile.mkdtemp()) / "MSG"
        f.write_text("bad message\n")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_commit_msg.py"), str(f)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("conventional", r.stderr.lower())
        f.write_text("fix: good message\n")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_commit_msg.py"), str(f)])
        self.assertEqual(r.returncode, 0)
        hook = ROOT / ".githooks" / "commit-msg"
        self.assertTrue(hook.exists())
        self.assertTrue(hook.stat().st_mode & 0o111)

    def test_range_check(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_commit_msg.py"), "--range", "HEAD~0..HEAD"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()

import pathlib, shutil, subprocess, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import guard

EXAMPLE_PATTERNS = (ROOT / "templates" / "blocklist.example.txt").read_text()


def make_tree(files=None):
    """A clean temp repo: empty applications/, example blocklist, one harmless doc."""
    root = pathlib.Path(tempfile.mkdtemp())
    (root / "applications").mkdir()
    (root / "applications" / ".gitkeep").touch()
    (root / "templates").mkdir()
    (root / "templates" / "blocklist.example.txt").write_text(EXAMPLE_PATTERNS)
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("Nothing private here.\n")
    for rel, body in (files or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return root


class GuardTests(unittest.TestCase):
    def violations(self, files=None, **kw):
        root = make_tree(files)
        self.addCleanup(shutil.rmtree, root, True)
        return guard.check(root, **kw)

    def test_clean_tree_passes(self):
        self.assertEqual(self.violations(), [])

    def test_stray_file_under_applications(self):
        v = self.violations({"applications/some-offer/fit-table.md": "x"})
        self.assertEqual(len(v), 1)
        self.assertIn("applications", v[0])

    def test_gitkeep_is_allowed_in_applications(self):
        self.assertEqual(self.violations({"applications/.gitkeep": ""}), [])

    def test_sensitive_file_names(self):
        for name in ["blocklist.txt", "config.json", "label-map.json", "evidence.md", "notes.md"]:
            v = self.violations({f"docs/{name}": "x"})
            self.assertEqual(len(v), 1, name)
            self.assertIn(name, v[0])

    def test_example_files_with_other_names_are_fine(self):
        self.assertEqual(self.violations({"examples/evidence.example.md": "x",
                                          "templates/config.example.json": "{}"}), [])

    def test_pdf_bak_log(self):
        for name in ["cv.pdf", "evidence.bak", "run.log"]:
            self.assertEqual(len(self.violations({f"docs/{name}": "x"})), 1, name)

    def test_state_directory(self):
        v = self.violations({"state/readme.txt": "x"})
        self.assertEqual(len(v), 1)

    def test_line_matching_example_pattern_reports_line_not_text(self):
        v = self.violations({"docs/b.md": "ok\nsee ticket://48151 for more\n"})
        self.assertEqual(len(v), 1)
        self.assertIn("docs/b.md:2", v[0])
        self.assertNotIn("48151", v[0])

    def test_custom_blocklist_file(self):
        extra = pathlib.Path(tempfile.mkdtemp()) / "mine.txt"
        extra.write_text("\\bsecretclient\\b\n")
        v = self.violations({"docs/c.md": "worked at SecretClient once"}, blocklist=extra)
        self.assertEqual(len(v), 1)
        self.assertNotIn("secretclient", v[0].lower().replace("docs/c.md", ""))

    def test_tests_dir_skipped_for_example_patterns_but_not_real_blocklist(self):
        files = {"tests/t.py": "x = 'ticket://12345'"}
        self.assertEqual(self.violations(files), [])
        extra = pathlib.Path(tempfile.mkdtemp()) / "mine.txt"
        extra.write_text("ticket://\\d+\n")
        self.assertEqual(len(self.violations(files, blocklist=extra)), 1)

    def test_git_and_node_modules_are_skipped(self):
        self.assertEqual(self.violations({".git/config.json": "x", "scripts/node_modules/evidence.md": "x"}), [])

    def test_binary_files_do_not_crash(self):
        root = make_tree()
        self.addCleanup(shutil.rmtree, root, True)
        (root / "docs" / "img.png").write_bytes(b"\x89PNG\xff\xfe\x00")
        self.assertEqual(guard.check(root), [])


class GuardCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "pipeline.py"), "guard", *args],
                              capture_output=True, text=True)

    def test_ok_and_fail_exit_codes(self):
        clean = make_tree()
        r = self.run_cli(str(clean))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "OK"))
        dirty = make_tree({"docs/evidence.md": "x"})
        r = self.run_cli(str(dirty))
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL", r.stdout)

    def test_usage_error(self):
        self.assertEqual(self.run_cli().returncode, 64)

    def test_repo_itself_is_clean(self):
        r = self.run_cli(str(ROOT))
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()

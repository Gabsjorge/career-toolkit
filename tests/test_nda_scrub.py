import io, pathlib, sys, tempfile, unittest, contextlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import nda_scrub

EXAMPLE = ROOT / "templates" / "blocklist.example.txt"

class ScrubTests(unittest.TestCase):
    def setUp(self):
        self.pats = nda_scrub.load_patterns(EXAMPLE)

    def test_clean_text(self):
        self.assertEqual(nda_scrub.scrub("Built REST APIs; contact me by email", self.pats), [])

    def test_ticket_hits(self):
        self.assertTrue(nda_scrub.scrub("see ticket://12345678", self.pats))
        self.assertTrue(nda_scrub.scrub("Ticket #1234567", self.pats))

    def test_case_insensitive(self):
        self.assertTrue(nda_scrub.scrub("ACME-INTERNAL project", self.pats))

    def test_load_patterns_skips_comments_and_blanks(self):
        p = pathlib.Path(tempfile.mkdtemp()) / "b.txt"
        p.write_text("# c\n\nfoo\n")
        self.assertEqual(nda_scrub.load_patterns(p), ["foo"])

    def test_validate_patterns_flags_uncompilable_and_match_all(self):
        pats = ["good", "(unclosed", "trailing|", ".*", r"\bok\b"]
        self.assertEqual(nda_scrub.validate_patterns(pats), [2, 3, 4])
        self.assertEqual(nda_scrub.validate_patterns(self.pats), [])

    def test_cli_rejects_invalid_entries_without_printing_them(self):
        d = pathlib.Path(tempfile.mkdtemp())
        bl = d / "b.txt"; bl.write_text("fine\nsecret(unclosed\n")
        f = d / "f.md"; f.write_text("hello\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(nda_scrub.main(["--blocklist", str(bl), str(f)]), 1)
        self.assertIn("entry #2 is invalid", out.getvalue())
        self.assertNotIn("secret", out.getvalue())

    def test_cli_exit_codes_and_no_content_leak(self):
        d = pathlib.Path(tempfile.mkdtemp())
        bl = d / "b.txt"; bl.write_text("secretword\n")
        good = d / "good.md"; good.write_text("hello\n")
        bad = d / "bad.md"; bad.write_text("ok\nthe SecretWord is here\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(nda_scrub.main(["--blocklist", str(bl), str(good)]), 0)
        self.assertIn("OK", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(nda_scrub.main(["--blocklist", str(bl), str(bad)]), 1)
        self.assertIn("bad.md:2: matches blocklist entry #1", out.getvalue())
        self.assertNotIn("is here", out.getvalue())
        self.assertNotIn("secretword", out.getvalue().lower())

    def run_main(self, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = nda_scrub.main(args)
        return rc, out.getvalue()

    def test_empty_blocklist_and_no_files_fail(self):
        d = pathlib.Path(tempfile.mkdtemp())
        empty = d / "e.txt"; empty.write_text("# only comment\n\n")
        f = d / "f.md"; f.write_text("hello\n")
        rc, out = self.run_main(["--blocklist", str(empty), str(f)])
        self.assertEqual(rc, 1); self.assertIn("FAIL: blocklist has no patterns", out)
        full = d / "b.txt"; full.write_text("x\n")
        rc, out = self.run_main(["--blocklist", str(full)])
        self.assertEqual(rc, 1); self.assertIn("FAIL: no files given", out)

    def test_blocklist_arg_errors(self):
        self.assertEqual(self.run_main(["x.md", "--blocklist"])[0], 64)
        rc, out = self.run_main(["--blocklist", "/nonexistent/b.txt", "x.md"])
        self.assertEqual(rc, 1); self.assertIn("FAIL: blocklist not found", out)

    def test_short_word_boundary(self):
        d = pathlib.Path(tempfile.mkdtemp())
        bl = d / "b.txt"; bl.write_text("\\bconta\\b\n")
        pats = nda_scrub.load_patterns(bl)
        self.assertEqual(nda_scrub.scrub("contact", pats), [])
        self.assertTrue(nda_scrub.scrub("the conta team", pats))

if __name__ == "__main__":
    unittest.main()

import contextlib, io, pathlib, re, shutil, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import bullets_check, draft_check, evidence, fit_status, lang_detect, nda_scrub, pipeline, tags

P = ROOT / "examples" / "persona"
TAGS = ROOT / "templates" / "tags.default.txt"


class DemoPersonaTests(unittest.TestCase):
    def test_evidence_is_well_formed(self):
        self.assertEqual(draft_check.check_lines((P / "evidence.example.md").read_text().splitlines()), [])
        self.assertEqual(len(evidence.load(P / "evidence.example.md")), 7)

    def test_requirements_pass_tags_check(self):
        import json
        t, a = tags.load(TAGS)
        r = tags.check(json.loads((P / "requirements.json").read_text()), t, a)
        self.assertEqual((r["errors"], r["unknown"]), ([], []))

    def test_fit_table_status_is_derived(self):
        fit = P / "output" / "fit-table.md"
        r = fit_status.process(fit, P / "evidence.example.md", TAGS, check=True)
        self.assertEqual(r["mismatch"], [])
        self.assertEqual((r["untagged"], r["unknown_tags"]), ([], []))
        self.assertEqual(r["counts"], {"Yes": 5, "Partial": 2, "No": 1, "Not evidenced": 0})

    def test_cv_has_no_unsourced_bullets(self):
        r = bullets_check.check((P / "output" / "cv-en.md").read_text(), evidence.load(P / "evidence.example.md"))
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["user_approved"], 0)
        self.assertGreater(r["bullets"], 5)

    def test_every_output_exists_and_offer_language_is_english(self):
        for n in ("fit-table.md", "cv-en.md", "cover-letter-en.md"):
            self.assertTrue((P / "output" / n).is_file(), n)
        self.assertEqual(lang_detect.detect((P / "offers" / "offer-01-en.md").read_text()), "en")
        letter = (P / "output" / "cover-letter-en.md").read_text()
        self.assertLess(len(letter.split()), 300)
        self.assertIn("Kubernetes in production", letter)       # the gap is named directly

    def test_persona_passes_example_blocklist(self):
        pats = nda_scrub.load_patterns(ROOT / "templates" / "blocklist.example.txt")
        for f in P.rglob("*.md"):
            self.assertEqual(nda_scrub.scrub(f.read_text(), pats), [], str(f))

    def test_cli_end_to_end_on_a_copy(self):
        d = pathlib.Path(tempfile.mkdtemp())
        shutil.copy(P / "output" / "fit-table.md", d / "fit.md")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = pipeline.main(["fit-status", str(d / "fit.md"), str(P / "evidence.example.md"), str(TAGS), "--check"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

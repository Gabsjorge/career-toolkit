import contextlib, io, pathlib, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import bullets_check, pipeline
from test_evidence_tags import EV, tmp

CV = """# Alex Example

## Experience

<div class="entry">

- Built event consumers for orders. <!-- ev:E0001 -->
- Reduced build time. <!-- ev:E0001, E0002 -->
- Led a team of three. <!-- ev:user -->
- Claimed something with no source.
- Cites a missing item. <!-- ev:E0042 -->
- Weird marker. <!-- ev:banana -->
- Built an event demo as a personal lab. <!-- ev:E0003 -->
- Built an event demo. <!-- ev:E0003 -->
  - Nested bullet without source.

</div>

Plain paragraph, not a bullet.
"""


class BulletsTests(unittest.TestCase):
    def test_problems(self):
        import evidence
        r = bullets_check.check(CV, evidence.load(tmp(EV)))
        self.assertEqual(r["problems"], [(10, "no evidence id"), (11, "unknown evidence id"),
                                         (12, "bad ev marker"), (14, "lab not labeled personal lab"),
                                         (15, "no evidence id")])
        self.assertEqual(r["bullets"], 9)
        self.assertEqual(r["user_approved"], 1)

    def test_clean_cv(self):
        import evidence
        cv = "- A. <!-- ev:E0001 -->\n- B. <!-- ev:user -->\n"
        r = bullets_check.check(cv, evidence.load(tmp(EV)))
        self.assertEqual(r["problems"], [])

    def test_cli_prints_line_numbers_not_text(self):
        cv, ev = tmp(CV, "cv.md"), tmp(EV, "ev.md")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pipeline.main(["bullets-check", str(cv), str(ev)])
        self.assertEqual(code, 1)
        self.assertIn("cv.md:10: no evidence id", out.getvalue())
        self.assertNotIn("Claimed", out.getvalue())
        self.assertIn("FAIL", out.getvalue())


EV2 = """# Evidence
- **E0001** **[high] 2026-09** — Reviewed about 1,800 pull requests and cut build time by 40%. _(tags: code-review)_
- **E0002** **[high] 2026-08** — Led the migration of the billing service. _(tags: migration)_
- **E0003** **[med] 2026-07** — Worked with an offshore team. _(tags: offshore-teams)_
"""
WORDS = ["offshore", "led", "team of"]


class ClaimTests(unittest.TestCase):
    def run_check(self, cv):
        import evidence
        return bullets_check.check(cv, evidence.load(tmp(EV2)), WORDS)["problems"]

    def test_supported_number_passes(self):
        self.assertEqual(self.run_check("- Reviewed ~1,800 pull requests. <!-- ev:E0001 -->\n"), [])
        self.assertEqual(self.run_check("- Cut build time 40%. <!-- ev:E0001 -->\n"), [])

    def test_unsupported_number_is_listed(self):
        self.assertEqual(self.run_check("- Reviewed 5,000 pull requests. <!-- ev:E0001 -->\n"),
                         [(1, "number not in cited evidence")])

    def test_multi_id_passes_when_any_item_has_the_number(self):
        self.assertEqual(self.run_check("- Reviewed 1800 PRs. <!-- ev:E0002, E0001 -->\n"), [])

    def test_user_approved_bullet_is_exempt(self):
        self.assertEqual(self.run_check("- Led a team of 12 offshore. <!-- ev:user -->\n"), [])

    def test_claim_word_unsupported_is_listed(self):
        self.assertEqual(self.run_check("- Led offshore delivery. <!-- ev:E0001 -->\n"),
                         [(1, "claim word not in cited evidence")])

    def test_claim_word_supported_passes(self):
        self.assertEqual(self.run_check("- Led billing migration. <!-- ev:E0002 -->\n"), [])
        self.assertEqual(self.run_check("- Worked offshore. <!-- ev:E0003 -->\n"), [])

    def test_claim_word_is_whole_word(self):
        self.assertEqual(self.run_check("- Handled misled tickets. <!-- ev:E0001 -->\n"), [])

    def test_digits_inside_words_are_not_numbers(self):
        self.assertEqual(self.run_check("- Wrote Jest E2E tests on S3 and OAuth2. <!-- ev:E0002 -->\n"), [])

    def test_year_in_cited_item_date_passes(self):
        self.assertEqual(self.run_check("- Migrated billing in 2026. <!-- ev:E0002 -->\n"), [])

    def test_year_not_in_cited_item_date_is_listed(self):
        self.assertEqual(self.run_check("- Migrated billing in 2019. <!-- ev:E0002 -->\n"),
                         [(1, "number not in cited evidence")])

    def test_number_with_unit_suffix_in_evidence_counts(self):
        import evidence
        ev = "- **E0009** **[high] 2026-01** — Cut each query from ~45s to under 10s. _(tags: performance)_\n"
        cv = "- Cut queries from 45 s to under 10 s. <!-- ev:E0009 -->\n- Wrote E2E tests. <!-- ev:E0009 -->\n"
        self.assertEqual(bullets_check.check(cv, evidence.load(tmp(ev)), WORDS)["problems"], [])

    def test_no_claim_words_means_numbers_only(self):
        import evidence
        r = bullets_check.check("- Led it. <!-- ev:E0001 -->\n", evidence.load(tmp(EV2)))
        self.assertEqual(r["problems"], [])

    def test_default_claim_words_file_is_used_by_cli(self):
        cv, ev = tmp("- Led offshore delivery. <!-- ev:E0001 -->\n", "cv.md"), tmp(EV2, "ev.md")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pipeline.main(["bullets-check", str(cv), str(ev)])
        self.assertEqual(code, 1)
        self.assertIn("cv.md:1: claim word not in cited evidence", out.getvalue())
        self.assertNotIn("offshore", out.getvalue())


if __name__ == "__main__":
    unittest.main()

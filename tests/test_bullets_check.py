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


if __name__ == "__main__":
    unittest.main()

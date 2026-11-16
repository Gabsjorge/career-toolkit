import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import estimate

class EstimateTests(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(estimate.estimate_tokens("a" * 8), 2)
        self.assertEqual(estimate.estimate_tokens("a" * 9), 3)
        self.assertEqual(estimate.estimate_tokens(""), 0)

    def test_estimate_and_cap(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "a.md").write_text("x" * 4000)   # 1000 tokens
        (d / "b.md").write_text("x" * 4000)   # 1000 tokens
        (d / "ignore.txt").write_text("x" * 40000)
        r = estimate.estimate(d, cap_tokens=5000, price_per_mtok=2.0)
        self.assertEqual(r["input_tokens"], 2000)
        self.assertEqual(r["est_output_tokens"], 500)
        self.assertEqual(r["files"], 2)
        self.assertFalse(r["over_cap"])
        self.assertAlmostEqual(r["est_cost_usd"], 0.005, places=4)
        self.assertTrue(estimate.estimate(d, cap_tokens=1500, price_per_mtok=2.0)["over_cap"])

    def test_cli_exit_code(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "a.md").write_text("x" * 4000)
        self.assertEqual(estimate.main([str(d), "5000", "1.0"]), 0)
        self.assertEqual(estimate.main([str(d), "500", "1.0"]), 2)

    def test_output_says_it_is_digest_input_only(self):
        import contextlib, io
        d = pathlib.Path(tempfile.mkdtemp()); (d / "a.md").write_text("x" * 40)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            estimate.main([str(d), "5000", "1.0"])
        self.assertIn("digest input only", out.getvalue())

if __name__ == "__main__":
    unittest.main()

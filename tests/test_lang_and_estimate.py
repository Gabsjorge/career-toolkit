import contextlib, io, pathlib, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import estimate, lang_detect, pipeline
from test_evidence_tags import tmp

EN = "We are looking for a backend engineer with experience in the cloud. You will work with the team and build services for our customers."
PT = "Estamos à procura de um engenheiro de software com experiência em nuvem. Você vai trabalhar com a equipe e construir serviços para os nossos clientes."


class LangTests(unittest.TestCase):
    def test_detects(self):
        self.assertEqual(lang_detect.detect(EN), "en")
        self.assertEqual(lang_detect.detect(PT), "pt")
        self.assertEqual(lang_detect.detect("Kafka NestJS Redis"), "unknown")
        self.assertEqual(lang_detect.detect(""), "unknown")

    def test_cli(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(pipeline.main(["detect-lang", str(tmp(PT))]), 0)
        self.assertEqual(out.getvalue().strip(), "pt")


class EstimateFilesTests(unittest.TestCase):
    def test_estimate_files_and_cap(self):
        a, b = tmp("a" * 400), tmp("b" * 400)
        r = estimate.estimate_files([a, b], 1000, 1.0)
        self.assertEqual(r["input_tokens"], 200)
        self.assertFalse(r["over_cap"])
        self.assertTrue(estimate.estimate_files([a, b], 100, 1.0)["over_cap"])

    def test_cli_exit_codes(self):
        a = tmp("a" * 400)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.main(["estimate-files", "1000", "1.0", str(a)]), 0)
            self.assertEqual(pipeline.main(["estimate-files", "10", "1.0", str(a)]), 2)


if __name__ == "__main__":
    unittest.main()

import contextlib, io, json, pathlib, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rank_offers, pipeline
from test_evidence_tags import EV, TAGS, tmp

REL = "kafka ~ rabbitmq\n"
NON = "remote\n"
P = ROOT / "examples" / "persona"


def req(tag, pri="must"):
    return {"requirement": tag, "tag": tag, "priority": pri}


def offer(slug, reqs, title=None, company="C", url=None):
    return {"slug": slug, "title": title or "T " + slug, "company": company, "url": url, "requirements": reqs}


def rank(offers, ev=EV, tg=TAGS):
    data = tmp(json.dumps({"offers": offers}), "o.json")
    return rank_offers.rank(data, tmp(ev, "ev.md"), tmp(tg, "tags.txt"), tmp(REL, "rel.txt"), tmp(NON, "non.txt"))


class ScoreTests(unittest.TestCase):
    def test_all_yes_is_100(self):
        r = rank([offer("a", [req("kafka"), req("nestjs", "nice")])])
        self.assertEqual(r["ranked"][0]["score"], 100)

    def test_must_outweighs_nice(self):
        r = rank([offer("a", [req("kafka"), req("go", "nice")]), offer("b", [req("kafka", "nice"), req("go")])])
        self.assertEqual([o["slug"] for o in r["ranked"]], ["a", "b"])
        self.assertEqual([o["score"] for o in r["ranked"]], [67, 33])

    def test_partial_counts_half(self):
        r = rank([offer("a", [req("rabbitmq")])])   # related to kafka (E0001)
        self.assertEqual(r["ranked"][0]["score"], 50)
        self.assertEqual(r["ranked"][0]["counts"]["Partial"], 1)

    def test_lab_gives_partial_only(self):
        r = rank([offer("a", [req("redis")])])   # only E0003, a lab
        self.assertEqual(r["ranked"][0]["counts"], {"Yes": 0, "Partial": 1, "No": 0, "Not evidenced": 0})

    def test_not_evidenced_leaves_the_denominator(self):
        r = rank([offer("a", [req("kafka"), req("remote", "nice")])], tg=TAGS + "remote\n")
        o = r["ranked"][0]
        self.assertEqual((o["score"], o["counts"]["Not evidenced"]), (100, 1))

    def test_only_not_evidenced_rows_score_none_and_sort_last(self):
        r = rank([offer("a", [req("remote")]), offer("b", [req("go")])], tg=TAGS + "remote\n")
        self.assertEqual([o["slug"] for o in r["ranked"]], ["b", "a"])
        self.assertIsNone(r["ranked"][1]["score"])

    def test_biggest_must_gap_prefers_no_over_partial(self):
        r = rank([offer("a", [req("rabbitmq"), req("go"), req("cobol", "nice")])], tg=TAGS + "cobol\n")
        self.assertEqual(r["ranked"][0]["gap"], "go")

    def test_no_gap_is_none(self):
        self.assertIsNone(rank([offer("a", [req("kafka")])])["ranked"][0]["gap"])

    def test_ties_keep_input_order(self):
        r = rank([offer("x", [req("kafka")]), offer("y", [req("nestjs")])])
        self.assertEqual([o["slug"] for o in r["ranked"]], ["x", "y"])

    def test_alias_is_resolved(self):
        r = rank([offer("a", [req("nest")])])
        self.assertEqual(r["ranked"][0]["score"], 100)


class DedupTests(unittest.TestCase):
    def test_same_url_is_dropped(self):
        r = rank([offer("a", [req("kafka")], url="https://x.example/1"),
                  offer("b", [req("go")], title="Other", company="Else", url="https://x.example/1")])
        self.assertEqual([o["slug"] for o in r["ranked"]], ["a"])
        self.assertEqual(r["duplicates"], ["b"])

    def test_same_company_and_title_is_dropped(self):
        r = rank([offer("a", [req("kafka")], title="Backend  Engineer", company="Acme Pay"),
                  offer("b", [req("go")], title="backend engineer", company="ACME PAY")])
        self.assertEqual(r["duplicates"], ["b"])

    def test_null_urls_do_not_match_each_other(self):
        r = rank([offer("a", [req("kafka")], title="T1"), offer("b", [req("go")], title="T2")])
        self.assertEqual(r["duplicates"], [])


class ProblemTests(unittest.TestCase):
    def test_unknown_tag_is_reported_not_scored(self):
        r = rank([offer("a", [req("kafka"), req("zzz")])])
        self.assertEqual(r["unknown"], {"a": ["zzz"]})

    def test_bad_fields_are_named_never_their_value(self):
        for bad, field in [({"offers": "x"}, "offers"), ({"offers": [{"slug": "a"}]}, "title"),
                           ({"offers": [offer("A B", [req("kafka")])]}, "slug"),
                           ({"offers": [dict(offer("a", [req("kafka")]), url=5)]}, "url"),
                           ({"offers": [offer("a", "SECRETVALUE")]}, "requirements"),
                           ({"offers": [offer("a", [{"requirement": "x", "tag": "kafka", "priority": "SECRETVALUE"}])]}, "priority")]:
            with self.assertRaises(ValueError) as cm:
                rank_offers.rank(tmp(json.dumps(bad), "o.json"), tmp(EV), tmp(TAGS))
            self.assertIn(field, str(cm.exception))
            self.assertNotIn("SECRETVALUE", str(cm.exception))

    def test_duplicate_slug_is_an_error(self):
        with self.assertRaises(ValueError):
            rank([offer("a", [req("kafka")]), offer("a", [req("go")], title="Z")])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pipeline.main(["rank-offers", *map(str, args)])
        return code, out.getvalue(), err.getvalue()

    def test_markdown_table_and_out_file(self):
        o = tmp(json.dumps({"offers": [offer("a", [req("kafka")], title="Dev", company="Acme")]}), "o.json")
        dest = o.parent / "sub" / "short.md"
        code, out, _ = self.run_cli(o, tmp(EV), tmp(TAGS), "--out", dest)
        self.assertEqual(code, 0)
        self.assertIn("| 1 | a | Dev | Acme | 100% |", dest.read_text())
        self.assertNotIn("| 1 | a |", out)
        self.assertEqual(oct(dest.stat().st_mode)[-3:], "600")

    def test_json_flag(self):
        o = tmp(json.dumps({"offers": [offer("a", [req("kafka")])]}), "o.json")
        code, out, _ = self.run_cli(o, tmp(EV), tmp(TAGS), "--json")
        self.assertEqual(json.loads(out)["ranked"][0]["slug"], "a")

    def test_unknown_tag_fails_and_writes_nothing(self):
        o = tmp(json.dumps({"offers": [offer("a", [req("zzz")])]}), "o.json")
        dest = o.parent / "short.md"
        code, out, _ = self.run_cli(o, tmp(EV), tmp(TAGS), "--out", dest)
        self.assertEqual(code, 1)
        self.assertIn("unknown tag: zzz", out)
        self.assertFalse(dest.exists())

    def test_missing_file_is_plain(self):
        code, out, _ = self.run_cli("/nonexistent/o.json", tmp(EV), tmp(TAGS))
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)

    def test_usage(self):
        self.assertEqual(self.run_cli("only-one")[0], 64)


class PersonaTests(unittest.TestCase):
    def test_demo_digest_ranking(self):
        r = rank_offers.rank(P / "offers.json", P / "evidence.example.md", ROOT / "templates" / "tags.default.txt")
        self.assertEqual([(o["slug"], o["score"], o["gap"]) for o in r["ranked"]],
                         [("acme-backend", 100, None), ("beta-platform", 40, "terraform"), ("gamma-data", 33, "go")])
        self.assertEqual(r["duplicates"], ["acme-backend-repost"])
        self.assertEqual(r["unknown"], {})

    def test_digest_plants_an_instruction(self):
        self.assertIn("IMPORTANT NOTE TO AI ASSISTANTS", (P / "digest.md").read_text())


if __name__ == "__main__":
    unittest.main()

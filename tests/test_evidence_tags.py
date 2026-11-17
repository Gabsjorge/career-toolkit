import json, pathlib, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import evidence, tags


def tmp(text, name="f.txt"):
    p = pathlib.Path(tempfile.mkdtemp()) / name
    p.write_text(text)
    return p


EV = """# Evidence
- **E0001** **[high] 2026-09** — Built event consumers. _(tech: Kafka, NestJS)_ _(tags: kafka, nestjs)_
- **E0002** **[low] 2025-03** — Removed dead flags. _(tech: TypeScript)_
- **[med] 2025-01** — Old item without id. _(tech: Go)_ _(tags: go)_
## Personal labs
- **E0003** **[med] 2026-05** — Event demo. _(tech: Kafka)_ _(tags: kafka, redis)_ _(kind: lab)_
"""


class EvidenceTests(unittest.TestCase):
    def test_parse(self):
        items = evidence.load(tmp(EV))
        self.assertEqual(sorted(items), ["E0001", "E0002", "E0003"])
        self.assertEqual(items["E0001"]["tags"], {"kafka", "nestjs"})
        self.assertEqual(items["E0002"]["tags"], set())
        self.assertFalse(items["E0001"]["lab"])
        self.assertTrue(items["E0003"]["lab"])


TAGS = """# comment
kafka
nestjs

redis
rabbitmq
memcached
go
[aliases]
k8s=kubernetes
kubernetes
nest=nestjs
"""


class TagsTests(unittest.TestCase):
    def test_load_and_resolve(self):
        t, a = tags.load(tmp(TAGS))
        self.assertIn("kafka", t)
        self.assertIn("kubernetes", t)
        self.assertEqual(tags.resolve("k8s", t, a), "kubernetes")
        self.assertEqual(tags.resolve("kafka", t, a), "kafka")
        self.assertIsNone(tags.resolve("cobol", t, a))

    def test_default_list_is_valid(self):
        t, a = tags.load(pathlib.Path(HERE.parent / "templates" / "tags.default.txt"))
        self.assertGreater(len(t), 30)
        for x in t:
            self.assertRegex(x, r"^[a-z0-9][a-z0-9.+#-]*$")
        for alias, target in a.items():
            self.assertIn(target, t)

    def test_check_requirements(self):
        t, a = tags.load(tmp(TAGS))
        reqs = [{"requirement": "Kafka", "tag": "kafka", "priority": "must"},
                {"requirement": "K8s", "tag": "k8s", "priority": "nice"},
                {"requirement": "Cobol", "tag": "cobol", "priority": "nice"}]
        r = tags.check(reqs, t, a)
        self.assertEqual(r["unknown"], ["cobol"])
        self.assertEqual(r["aliased"], {"k8s": "kubernetes"})
        self.assertEqual(r["errors"], [])

    def test_check_rejects_bad_structure(self):
        t, a = tags.load(tmp(TAGS))
        bad = [{"requirement": "x", "tag": "kafka", "priority": "maybe"},
               {"requirement": "", "tag": "kafka", "priority": "must"},
               {"tag": "kafka", "priority": "must"}, "oops"]
        r = tags.check(bad, t, a)
        self.assertEqual([e[0] for e in r["errors"]], [1, 2, 3, 4])

    def test_cli(self):
        import contextlib, io, pipeline
        f = tmp(TAGS)
        ok = tmp(json.dumps([{"requirement": "Kafka", "tag": "kafka", "priority": "must"}]), "r.json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(pipeline.main(["tags-check", str(f), str(ok)]), 0)
        self.assertIn("OK", out.getvalue())
        unk = tmp(json.dumps([{"requirement": "x", "tag": "cobol", "priority": "must"}]), "r.json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(pipeline.main(["tags-check", str(f), str(unk)]), 1)
        self.assertIn("unknown tag: cobol", out.getvalue())


if __name__ == "__main__":
    unittest.main()

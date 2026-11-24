import contextlib, io, json, pathlib, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gap_count, pipeline

TRACKS = """# tag = track, type
kafka = backend, tech
kubernetes = backend+lead, tech
aws = backend, tech
gcp = backend, tech
azure = backend, tech
mentoring = lead, skill
english = lead, language
"""
HEAD = "| Requirement | Tag | Must/Nice | Status | Evidence IDs | Notes | Study recommendations |\n|---|---|---|---|---|---|---|\n"


def table(*rows):
    return "# Fit: X\n\n" + HEAD + "\n".join(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | — |  |  |" for r in rows) + "\n\n## Summary\n"


def apps(tables, tracks=TRACKS):
    root = pathlib.Path(tempfile.mkdtemp())
    for name, text in tables.items():
        d = root / "applications" / name
        d.mkdir(parents=True)
        (d / "fit-table.md").write_text(text)
    tf = root / "tracks.txt"
    tf.write_text(tracks)
    return root / "applications", tf


def run(tables, tracks=TRACKS, groups=None):
    a, t = apps(tables, tracks)
    if groups is None:
        return gap_count.count(a, t)
    g = t.parent / "groups.txt"
    g.write_text(groups)
    return gap_count.count(a, t, g)


def entry(res, track, tag):
    return next(e for e in res["tracks"][track] if e["tag"] == tag)


class CountTests(unittest.TestCase):
    def test_weights_must_two_nice_and_dash_one(self):
        r = run({"a": table(("k", "kafka", "Must", "No"), ("k2", "kafka", "Nice", "No"), ("k3", "kafka", "—", "Partial"))})
        e = entry(r, "backend", "kafka")
        self.assertEqual((e["gaps"], e["no"], e["partial"], e["must_weighted"]), (3, 2, 1, 4))
        self.assertEqual(e["type"], "tech")

    def test_yes_and_not_evidenced_are_not_gaps(self):
        r = run({"a": table(("k", "kafka", "Must", "Yes"), ("e", "english", "Must", "Not evidenced"))})
        self.assertEqual(r["tracks"]["backend"], [])
        self.assertEqual(r["tracks"]["lead"], [])
        self.assertEqual(r["rows"], 2)

    def test_untagged_rows_are_reported_not_counted(self):
        r = run({"a": table(("x", "—", "Must", "—"), ("y", "", "Nice", ""))})
        self.assertEqual(r["untagged_rows"], 2)
        self.assertEqual(r["tracks"]["backend"], [])

    def test_unmapped_tag_listed_not_guessed(self):
        r = run({"a": table(("x", "cobol", "Must", "No"), ("y", "cobol", "Nice", "Partial"))})
        self.assertEqual(r["unmapped_tags"], {"cobol": 2})
        self.assertEqual(r["tracks"]["backend"], [])

    def test_dual_track_tag_appears_in_both(self):
        r = run({"a": table(("k", "kubernetes", "Must", "No"))})
        self.assertEqual(entry(r, "backend", "kubernetes")["must_weighted"], 2)
        self.assertEqual(entry(r, "lead", "kubernetes")["must_weighted"], 2)

    def test_tables_counts_distinct_offers(self):
        r = run({"a": table(("k", "kafka", "Must", "No"), ("k", "kafka", "Nice", "No")),
                 "b": table(("k", "kafka", "Nice", "Partial")),
                 "c": table(("k", "kafka", "Must", "Yes"))})
        self.assertEqual(entry(r, "backend", "kafka")["tables"], 2)
        self.assertEqual(r["tables_read"], 3)

    def test_sorted_by_weight_then_gaps_then_tag(self):
        r = run({"a": table(("m", "mentoring", "Must", "No"), ("k", "kafka", "Nice", "No"), ("k", "kubernetes", "Nice", "No"))})
        self.assertEqual([e["tag"] for e in r["tracks"]["backend"]], ["kafka", "kubernetes"])

    def test_malformed_table_is_skipped_and_named(self):
        bad = "# Fit\n\n" + HEAD + "| only | two |\n"
        r = run({"good": table(("k", "kafka", "Must", "No")), "bad": bad, "nohead": "# nothing here\n"})
        self.assertEqual(sorted(r["tables_skipped"]), ["bad", "nohead"])
        self.assertEqual(r["tables_read"], 1)
        self.assertEqual(entry(r, "backend", "kafka")["gaps"], 1)

    def test_tag_case_is_normalised(self):
        r = run({"a": table(("k", "Kafka", "Must", "No"))})
        self.assertEqual(entry(r, "backend", "kafka")["gaps"], 1)

    def test_unknown_status_skips_table(self):
        r = run({"a": table(("k", "kafka", "Must", "Maybe"))})
        self.assertEqual(r["tables_skipped"], ["a"])


class TracksFileTests(unittest.TestCase):
    def load(self, text):
        p = pathlib.Path(tempfile.mkdtemp()) / "t.txt"
        p.write_text(text)
        return gap_count.load_tracks(p)

    def test_parse(self):
        m = self.load(TRACKS)
        self.assertEqual(m["kubernetes"], (["backend", "lead"], "tech"))

    def test_bad_track_names_line_not_value(self):
        with self.assertRaises(ValueError) as cm:
            self.load("kafka = secret-track, tech\n")
        self.assertIn("line 1", str(cm.exception))
        self.assertNotIn("secret-track", str(cm.exception))

    def test_bad_type_and_missing_equals(self):
        for bad in ("kafka = backend, wizardry\n", "kafka backend tech\n", "kafka = backend\n"):
            with self.assertRaises(ValueError):
                self.load(bad)

    def test_duplicate_tag_rejected(self):
        with self.assertRaises(ValueError):
            self.load("kafka = backend, tech\nkafka = lead, tech\n")


class DefaultFileTests(unittest.TestCase):
    def test_default_map_covers_every_default_tag(self):
        m = gap_count.load_tracks(ROOT / "templates" / "tag-tracks.default.txt")
        tags = {l.strip() for l in (ROOT / "templates" / "tags.default.txt").read_text().splitlines()
                if l.strip() and not l.startswith("#") and not l.startswith("[") and "=" not in l}
        non = {l.strip() for l in (ROOT / "templates" / "non-skill-tags.txt").read_text().splitlines()
               if l.strip() and not l.startswith("#")}
        self.assertEqual(sorted(t for t in tags if t not in m and t not in non), [])
        self.assertEqual(sorted(t for t in m if t not in tags), [])
        self.assertEqual(sorted(t for t in m if t in non), [])


PLAN = """# Study plan

## Gap numbers

| track | tag | gaps | weighted | offers |
|---|---|---|---|---|
| backend | kafka | 3 | 4 | 1 |
| lead | mentoring | 1 | 2 | 1 |
"""


class PlanCheckTests(unittest.TestCase):
    def setUp(self):
        self.res = run({"a": table(("k", "kafka", "Must", "No"), ("k2", "kafka", "Nice", "No"), ("k3", "kafka", "—", "Partial"),
                                   ("m", "mentoring", "Must", "No"))})

    def check(self, plan):
        return gap_count.check_plan(self.res, plan)

    def test_matching_plan_passes(self):
        self.assertEqual(self.check(PLAN), [])

    def test_wrong_number_is_named(self):
        self.assertEqual(self.check(PLAN.replace("| 3 | 4 | 1 |", "| 5 | 4 | 1 |")), ["backend/kafka"])

    def test_tag_not_in_json_is_named(self):
        bad = PLAN + "| backend | cobol | 2 | 2 | 1 |\n"
        self.assertEqual(self.check(bad), ["backend/cobol"])

    def test_track_mismatch_is_named(self):
        self.assertEqual(self.check(PLAN.replace("| lead | mentoring", "| backend | mentoring")), ["backend/mentoring"])

    def test_plan_without_number_rows_fails(self):
        self.assertEqual(self.check("# Study plan\nno table\n"), ["no gap rows found"])

    def test_cli_check(self):
        a, t = apps({"a": table(("k", "kafka", "Must", "No"), ("k2", "kafka", "Nice", "No"), ("k3", "kafka", "—", "Partial"),
                                ("m", "mentoring", "Must", "No"))})
        plan = t.parent / "plan.md"
        plan.write_text(PLAN)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pipeline.main(["gap-count", str(a), str(t), "--check", str(plan)])
        self.assertEqual(code, 0)
        self.assertIn("OK", out.getvalue())
        plan.write_text(PLAN.replace("| 3 | 4 | 1 |", "| 9 | 4 | 1 |"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pipeline.main(["gap-count", str(a), str(t), "--check", str(plan)])
        self.assertEqual(code, 1)
        self.assertIn("backend/kafka", out.getvalue())


class CliTests(unittest.TestCase):
    def cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pipeline.main(["gap-count"] + args)
        return code, out.getvalue(), err.getvalue()

    def test_json_output(self):
        a, t = apps({"a": table(("k", "kafka", "Must", "No"))})
        code, out, _ = self.cli([str(a), str(t)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["tracks"]["backend"][0]["tag"], "kafka")

    def test_usage_is_64(self):
        self.assertEqual(self.cli([])[0], 64)

    def test_missing_folder_is_1(self):
        _, t = apps({})
        self.assertEqual(self.cli(["/nonexistent-dir-xyz", str(t)])[0], 1)

    def test_bad_tracks_file_is_1(self):
        a, t = apps({}, "garbage\n")
        code, out, _ = self.cli([str(a), str(t)])
        self.assertEqual(code, 1)
        self.assertIn("line 1", out)

    def test_demo_persona_table(self):
        persona = ROOT / "examples" / "persona" / "fit-tables"
        code, out, _ = self.cli([str(persona), str(ROOT / "templates" / "tag-tracks.default.txt")])
        self.assertEqual(code, 0)
        r = json.loads(out)
        self.assertEqual(r["tables_read"], 2)
        self.assertEqual(r["tables_skipped"], [])


CLOUD = "cloud = aws, gcp, azure\n"


def group(res, track, name):
    return next(g for g in res["groups"] if g["track"] == track and g["group"] == name)


class GroupTests(unittest.TestCase):
    def two_offers(self):
        return {"a": table(("a1", "aws", "Must", "No"), ("a2", "gcp", "Nice", "Partial")),
                "b": table(("b1", "aws", "Must", "No"), ("b2", "azure", "Nice", "No")),
                "c": table(("c1", "kafka", "Must", "No"))}

    def test_group_sums_rows_and_weights(self):
        g = group(run(self.two_offers(), groups=CLOUD), "backend", "cloud")
        self.assertEqual((g["gaps"], g["no"], g["partial"], g["must_weighted"]), (4, 3, 1, 6))
        self.assertEqual(g["members"], {"aws": 2, "gcp": 1, "azure": 1})
        self.assertEqual(g["type"], "tech")

    def test_offer_naming_two_providers_counts_once(self):
        g = group(run(self.two_offers(), groups=CLOUD), "backend", "cloud")
        self.assertEqual(g["tables"], 2)                 # a and b, not 4

    def test_top_member_by_weight_then_gaps_then_name(self):
        r = run(self.two_offers(), groups=CLOUD)
        self.assertEqual(group(r, "backend", "cloud")["top_member"], "aws")
        tie = run({"a": table(("x", "gcp", "Nice", "No"), ("y", "azure", "Nice", "No"))}, groups=CLOUD)
        self.assertEqual(group(tie, "backend", "cloud")["top_member"], "azure")
        more = run({"a": table(("x", "gcp", "Nice", "No"), ("y", "gcp", "Nice", "No"), ("z", "azure", "Nice", "No"),
                               ("w", "azure", "Nice", "No"))}, groups=CLOUD)
        self.assertEqual(group(more, "backend", "cloud")["top_member"], "azure")   # same weight, same gaps: name

    def test_tracks_output_is_unchanged_by_groups(self):
        plain, grouped = run(self.two_offers()), run(self.two_offers(), groups=CLOUD)
        self.assertEqual(plain["tracks"], grouped["tracks"])
        self.assertEqual(plain["groups"], [])

    def test_group_without_gaps_is_absent(self):
        r = run({"a": table(("a1", "aws", "Must", "Yes"))}, groups=CLOUD)
        self.assertEqual(r["groups"], [])

    def test_group_follows_the_tracks_of_its_members(self):
        tracks = TRACKS + "docker = lead, tech\n"
        r = run({"a": table(("d", "docker", "Must", "No"), ("k", "kubernetes", "Nice", "No"))}, tracks,
                "containers = docker, kubernetes\n")
        self.assertEqual({(g["track"]) for g in r["groups"]}, {"backend", "lead"})
        self.assertEqual(group(r, "backend", "containers")["members"], {"kubernetes": 1})
        self.assertEqual(group(r, "lead", "containers")["members"], {"docker": 1, "kubernetes": 1})

    def test_bad_group_files_name_the_line_not_the_value(self):
        a, t = apps({"a": table(("x", "aws", "Must", "No"))})
        for text, frag in (("cloud aws, gcp\n", "line 1"), ("cloud = aws\n", "line 1"),
                           ("cloud = aws, nope\n", "line 1"), ("# c\ncloud = aws, gcp\ncloud = aws, azure\n", "line 3"),
                           ("kafka = aws, gcp\n", "line 1"), ("c1 = aws, gcp\nc2 = gcp, azure\n", "line 2")):
            g = t.parent / "g.txt"
            g.write_text(text)
            with self.assertRaises(ValueError) as cm:
                gap_count.count(a, t, g)
            self.assertIn(frag, str(cm.exception))
            self.assertNotIn("nope", str(cm.exception))

    def test_default_group_file_members_are_default_tags_and_mapped(self):
        import tags
        known, _ = tags.load(ROOT / "templates" / "tags.default.txt")
        tmap = gap_count.load_tracks(ROOT / "templates" / "tag-tracks.default.txt")
        groups = gap_count.load_groups(ROOT / "templates" / "tag-groups.default.txt", tmap)
        self.assertEqual(groups, {"cloud": ["aws", "gcp", "azure"]})
        self.assertTrue(all(m in known for ms in groups.values() for m in ms))

    def test_check_accepts_a_group_row_and_flags_a_wrong_number(self):
        r = run(self.two_offers(), groups=CLOUD)
        good = "| track | tag | gaps | weighted | offers |\n|---|---|---|---|---|\n| backend | cloud | 4 | 6 | 2 |\n| backend | aws | 2 | 4 | 2 |\n"
        self.assertEqual(gap_count.check_plan(r, good), [])
        bad = good.replace("| cloud | 4 |", "| cloud | 5 |")
        self.assertEqual(gap_count.check_plan(r, bad), ["backend/cloud"])

    def test_cli_groups_flag(self):
        a, t = apps(self.two_offers())
        g = t.parent / "g.txt"
        g.write_text(CLOUD)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pipeline.main(["gap-count", str(a), str(t), "--groups", str(g)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["groups"][0]["group"], "cloud")


if __name__ == "__main__":
    unittest.main()

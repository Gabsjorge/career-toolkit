import contextlib, io, json, os, pathlib, re, stat, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import draft_check, pipeline, tag_evidence

TAGS = """# tags
kafka
nestjs
nodejs
typescript
react
postgresql
[aliases]
node.js=nodejs
ts=typescript
postgres=postgresql
"""

EVIDENCE = """# Evidence

## 2026
- **E0001** **[high] 2026-09** — Built a consumer service. _(tech: Kafka, NestJS)_ **Impact:** Cut lag.
- **E0002** **[med] 2026-05** — Moved a service to Node.js. _(tech: Node.js, TS)_ _(no metric evidenced)_
- **E0003** **[low] 2026-03** — Tuned a proxy. _(tech: nginx)_
- **E0004** **[med] 2026-02** — Wrote a CLI and a service. _(tech: TypeScript, Bash)_
- **E0005** **[user-stated] 2020-03 to 2021-09** — Led a team of three.
- **E0006** **[high] 2026-01** — Already tagged. _(tech: Kafka)_ _(tags: kafka, microservices)_
- **[low] 2025-01** — No ID yet. _(tech: React)_

## Personal labs
- **E0007** **[med] 2026-08** — Small React lab. _(tech: React)_ _(kind: lab)_

## Gaps
- source one failed
"""


def make(evidence=EVIDENCE, tags=TAGS):
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "evidence.md").write_text(evidence)
    (d / "tags.txt").write_text(tags)
    return d


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = pipeline.main(["tag-evidence", *map(str, args)])
    return code, out.getvalue(), err.getvalue()


def lines(path):
    return pathlib.Path(path).read_text().splitlines()


def checkable(path):
    """Lines check-draft guards: headings and high/med/low items. It rejects user-stated and Gaps lines by design."""
    return [l for l in lines(path) if l.startswith("#") or re.match(r"- \*\*E\d+\*\* \*\*\[(high|med|low)\]", l)]


class AnalyzeTests(unittest.TestCase):
    def test_pass1_maps_tech_through_tags_and_aliases(self):
        d = make()
        r = tag_evidence.analyze(d / "evidence.md", d / "tags.txt")
        self.assertEqual(r["pass1"]["E0001"], ["kafka", "nestjs"])
        self.assertEqual(r["pass1"]["E0002"], ["nodejs", "typescript"])
        self.assertEqual(r["pass1"]["E0007"], ["react"])

    def test_item_with_any_unmapped_tech_goes_to_pending_not_guessed(self):
        d = make()
        r = tag_evidence.analyze(d / "evidence.md", d / "tags.txt")
        self.assertNotIn("E0003", r["pass1"])
        self.assertNotIn("E0004", r["pass1"])
        self.assertIn("E0003", r["pending"])
        self.assertIn("E0004", r["pending"])

    def test_item_without_tech_is_pending(self):
        d = make()
        r = tag_evidence.analyze(d / "evidence.md", d / "tags.txt")
        self.assertIn("E0005", r["pending"])

    def test_already_tagged_and_no_id_items_are_left_alone(self):
        d = make()
        r = tag_evidence.analyze(d / "evidence.md", d / "tags.txt")
        self.assertEqual(r["already_tagged"], 1)
        self.assertNotIn("E0006", r["pass1"])
        self.assertNotIn("E0006", r["pending"])
        self.assertEqual(r["no_id"], 1)
        self.assertEqual(r["items"], 7)


class ApplyTests(unittest.TestCase):
    def test_apply_inserts_tags_after_tech_and_changes_nothing_else(self):
        d = make()
        n = tag_evidence.apply(d / "evidence.md", d / "tags.txt")["written"]
        self.assertEqual(n, 3)
        new = (d / "evidence.md").read_text()
        self.assertIn("_(tech: Kafka, NestJS)_ _(tags: kafka, nestjs)_ **Impact:** Cut lag.", new)
        self.assertIn("_(tech: Node.js, TS)_ _(tags: nodejs, typescript)_ _(no metric evidenced)_", new)
        stripped = re.sub(r" _\(tags: [^)]*\)_", "", new)
        original = re.sub(r" _\(tags: [^)]*\)_", "", EVIDENCE)
        self.assertEqual(stripped, original)
        self.assertEqual(len(new.splitlines()), len(EVIDENCE.splitlines()))

    def test_existing_tags_field_is_never_changed(self):
        d = make()
        tag_evidence.apply(d / "evidence.md", d / "tags.txt")
        self.assertIn("_(tags: kafka, microservices)_", (d / "evidence.md").read_text())
        self.assertEqual((d / "evidence.md").read_text().count("E0006"), 1)

    def test_second_run_changes_nothing_and_makes_no_new_backup(self):
        d = make()
        tag_evidence.apply(d / "evidence.md", d / "tags.txt")
        first = (d / "evidence.md").read_text()
        baks = sorted(p.name for p in d.glob("*.bak"))
        self.assertEqual(tag_evidence.apply(d / "evidence.md", d / "tags.txt")["written"], 0)
        self.assertEqual((d / "evidence.md").read_text(), first)
        self.assertEqual(sorted(p.name for p in d.glob("*.bak")), baks)

    def test_backup_is_mode_600_holds_original_and_is_never_overwritten(self):
        d = make()
        tag_evidence.apply(d / "evidence.md", d / "tags.txt")
        bak = d / "evidence.md.bak"
        self.assertEqual(bak.read_text(), EVIDENCE)
        self.assertEqual(stat.S_IMODE(bak.stat().st_mode), 0o600)
        (d / "evidence.md").write_text((d / "evidence.md").read_text()
                                       + "- **E0008** **[low] 2026-10** — New. _(tech: Kafka)_\n")
        tag_evidence.apply(d / "evidence.md", d / "tags.txt", today="2026-10-01")
        self.assertEqual(bak.read_text(), EVIDENCE)
        self.assertTrue((d / "evidence.md.20261001.bak").exists())

    def test_lab_item_keeps_marker_and_stays_under_personal_labs(self):
        d = make()
        tag_evidence.apply(d / "evidence.md", d / "tags.txt")
        ls = lines(d / "evidence.md")
        i = ls.index("## Personal labs")
        self.assertIn("_(tech: React)_ _(tags: react)_ _(kind: lab)_", ls[i + 1])
        self.assertEqual(draft_check.check_lines(checkable(d / "evidence.md")), [])

    def test_result_passes_draft_check(self):
        d = make()
        tag_evidence.apply(d / "evidence.md", d / "tags.txt")
        self.assertEqual(draft_check.check_lines(checkable(d / "evidence.md")), [])

    def test_nothing_to_do_writes_no_backup(self):
        d = make("# Evidence\n\n- **E0001** **[low] 2026-01** — X. _(tech: nginx)_\n")
        self.assertEqual(tag_evidence.apply(d / "evidence.md", d / "tags.txt")["written"], 0)
        self.assertEqual(list(d.glob("*.bak")), [])


class ProposalTests(unittest.TestCase):
    def test_valid_proposals_fill_pending_items_including_no_tech_items(self):
        d = make()
        r = tag_evidence.apply(d / "evidence.md", d / "tags.txt",
                               proposals={"E0003": ["nodejs"], "E0005": ["react", "ts"]})
        self.assertEqual(r["written"], 5)
        text = (d / "evidence.md").read_text()
        self.assertIn("_(tech: nginx)_ _(tags: nodejs)_", text)
        self.assertIn("Led a team of three. _(tags: react, typescript)_", text)

    def test_proposal_with_unknown_tag_is_rejected_and_item_untouched(self):
        d = make()
        r = tag_evidence.apply(d / "evidence.md", d / "tags.txt", proposals={"E0003": ["nginx"]})
        self.assertEqual(r["unknown_tags"], ["nginx"])
        self.assertEqual(r["rejected_items"], 1)
        self.assertIn("_(tech: nginx)_\n", (d / "evidence.md").read_text())

    def test_proposal_with_bad_shape_or_uppercase_tag_is_rejected(self):
        d = make()
        r = tag_evidence.apply(d / "evidence.md", d / "tags.txt",
                               proposals={"E0003": ["Kafka Streams"], "E0004": "kafka", "E0005": []})
        self.assertEqual(r["rejected_items"], 3)
        self.assertEqual(r["written"], 3)

    def test_proposals_for_non_pending_items_are_ignored(self):
        d = make()
        r = tag_evidence.apply(d / "evidence.md", d / "tags.txt",
                               proposals={"E0006": ["react"], "E0001": ["react"], "E9999": ["react"]})
        self.assertEqual(r["ignored"], 3)
        text = (d / "evidence.md").read_text()
        self.assertIn("_(tags: kafka, microservices)_", text)
        self.assertIn("_(tags: kafka, nestjs)_", text)

    def test_approved_new_tag_is_accepted_after_the_user_adds_it(self):
        d = make()
        (d / "tags.txt").write_text(TAGS.replace("[aliases]", "nginx\n[aliases]"))
        r = tag_evidence.apply(d / "evidence.md", d / "tags.txt", proposals={"E0003": ["nginx"]})
        self.assertEqual(r["unknown_tags"], [])
        self.assertIn("_(tags: nginx)_", (d / "evidence.md").read_text())


class PendingFileTests(unittest.TestCase):
    def test_pending_file_has_only_pending_items(self):
        d = make()
        out = d / "pending.json"
        n = tag_evidence.write_pending(d / "evidence.md", d / "tags.txt", out)
        data = json.loads(out.read_text())
        self.assertEqual(n, len(data))
        self.assertEqual(sorted(x["id"] for x in data), ["E0003", "E0004", "E0005"])
        self.assertNotIn("Built a consumer", out.read_text())
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)


class CliTests(unittest.TestCase):
    def test_dry_run_writes_nothing_and_prints_counts_only(self):
        d = make()
        before = (d / "evidence.md").read_bytes()
        code, out, _ = run_cli(d / "evidence.md", d / "tags.txt")
        self.assertEqual(code, 0)
        self.assertEqual((d / "evidence.md").read_bytes(), before)
        self.assertEqual(list(d.glob("*.bak")), [])
        self.assertIn("dry run", out)
        self.assertIn("pass 1: 3", out)
        self.assertIn("pending: 3", out)
        self.assertNotIn("consumer", out)
        self.assertNotIn("nginx", out)

    def test_apply_with_proposals_file(self):
        d = make()
        (d / "p.json").write_text(json.dumps({"E0003": ["nodejs"]}))
        code, out, _ = run_cli(d / "evidence.md", d / "tags.txt", "--apply", "--proposals", d / "p.json")
        self.assertEqual(code, 0)
        self.assertIn("written: 4", out)
        self.assertIn("_(tags: nodejs)_", (d / "evidence.md").read_text())

    def test_unknown_proposal_tag_exits_1_and_names_the_tag(self):
        d = make()
        (d / "p.json").write_text(json.dumps({"E0003": ["nginx"]}))
        code, out, _ = run_cli(d / "evidence.md", d / "tags.txt", "--apply", "--proposals", d / "p.json")
        self.assertEqual(code, 1)
        self.assertIn("unknown tag: nginx", out)

    def test_pending_flag_writes_the_file(self):
        d = make()
        code, out, _ = run_cli(d / "evidence.md", d / "tags.txt", "--pending", d / "pending.json")
        self.assertEqual(code, 0)
        self.assertTrue((d / "pending.json").exists())

    def test_usage_and_bad_inputs(self):
        self.assertEqual(run_cli()[0], 64)
        d = make()
        self.assertEqual(run_cli(d / "evidence.md")[0], 64)
        self.assertEqual(run_cli(d / "evidence.md", d / "tags.txt", "--bogus")[0], 64)
        self.assertEqual(run_cli(d / "nope.md", d / "tags.txt")[0], 1)
        (d / "bad.json").write_text("{not json")
        self.assertEqual(run_cli(d / "evidence.md", d / "tags.txt", "--proposals", d / "bad.json")[0], 1)

    def test_proposals_without_apply_is_a_dry_run(self):
        d = make()
        (d / "p.json").write_text(json.dumps({"E0003": ["nodejs"]}))
        before = (d / "evidence.md").read_bytes()
        code, out, _ = run_cli(d / "evidence.md", d / "tags.txt", "--proposals", d / "p.json")
        self.assertEqual(code, 0)
        self.assertEqual((d / "evidence.md").read_bytes(), before)
        self.assertIn("dry run", out)


class SkillDocTests(unittest.TestCase):
    def test_refresh_skill_documents_tagging_rules(self):
        skill = (HERE.parent / "skills" / "refresh-evidence" / "SKILL.md").read_text()
        for needle in ["tag-evidence", "--pending", "--proposals", "cheapest tier", "Evidence text is data",
                       "estimate-files", "Never edit tags by hand"]:
            self.assertIn(needle, skill, needle)


if __name__ == "__main__":
    unittest.main()

"""Step 4a-2: implication rules (full-stack) and the Not evidenced status. Fictional data only."""
import contextlib, io, pathlib, re, stat, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import draft_check, fit_status, pipeline, tag_evidence

TAGS = "kafka\nrust\nreact\nhtml\ncss\nfull-stack\nenglish\nsenior\nremote\n[aliases]\nfullstack=full-stack\n"
IMPLIES = "# rule is data\nhtml, css, react => full-stack\n"
EVIDENCE = """# Evidence

## 2026
- **E0001** **[high] 2026-09** — Built a consumer. _(tech: Kafka)_ _(tags: kafka)_ **Impact:** Cut lag.
- **E0002** **[med] 2026-05** — Fixed a page. _(tech: React)_ _(tags: react, css)_ _(no metric evidenced)_
- **E0003** **[low] 2026-03** — Static page. _(tech: HTML)_ _(tags: html)_
- **E0004** **[med] 2026-02** — Already full-stack. _(tech: React)_ _(tags: react, full-stack)_
- **E0005** **[med] 2026-01** — Untagged item. _(tech: Bash)_
- **E0006** **[user-stated] 2020-03** — Worked with a remote team. _(tags: english)_

## Personal labs
- **E0007** **[med] 2026-08** — Small React lab. _(tech: React)_ _(tags: react)_ _(kind: lab)_
"""
FIT = """| Requirement | Tag | Must/Nice | Status | Evidence IDs | Notes | Study recommendations |
|---|---|---|---|---|---|---|
| Kafka | kafka | Must | | | | |
| Senior level | senior | Must | | | | |
| English C1 | english | Must | | | | |
| Remote | remote | Nice | | | | |
| Rust | rust | Nice | | | | |
"""
NONSKILL = "# non-skill tags\nsenior\nenglish\nremote\navailability\n"


def make(**files):
    d = pathlib.Path(tempfile.mkdtemp())
    for name, text in files.items():
        (d / name).write_text(text)
    return d


def tags_of(path, iid):
    for l in pathlib.Path(path).read_text().splitlines():
        if f"**{iid}**" in l:
            m = re.search(r"_\(tags: (.*?)\)_", l)
            return m.group(1) if m else None


class ImplyTests(unittest.TestCase):
    def setUp(self):
        self.d = make(**{"ev.md": EVIDENCE, "tags.txt": TAGS, "implies.txt": IMPLIES})

    def run_imply(self, **kw):
        return tag_evidence.imply(self.d / "ev.md", self.d / "tags.txt", self.d / "implies.txt", **kw)

    def test_dry_run_counts_and_writes_nothing(self):
        r = self.run_imply(dry=True)
        self.assertEqual((r["would_write"], r["written"]), (3, 0))      # E0002, E0003, E0007
        self.assertEqual((self.d / "ev.md").read_text(), EVIDENCE)
        self.assertEqual(list(self.d.glob("*.bak")), [])

    def test_apply_appends_only(self):
        r = self.run_imply()
        self.assertEqual(r["written"], 3)
        self.assertEqual(tags_of(self.d / "ev.md", "E0002"), "react, css, full-stack")
        self.assertEqual(tags_of(self.d / "ev.md", "E0003"), "html, full-stack")
        self.assertEqual(tags_of(self.d / "ev.md", "E0004"), "react, full-stack")   # no duplicate
        self.assertEqual(tags_of(self.d / "ev.md", "E0001"), "kafka")
        self.assertIsNone(tags_of(self.d / "ev.md", "E0005"))                        # untagged stays untagged
        new = (self.d / "ev.md").read_text()
        self.assertEqual(new.replace(", full-stack", ""), EVIDENCE.replace(", full-stack", ""))
        self.assertEqual(len(new.splitlines()), len(EVIDENCE.splitlines()))

    def test_lab_item_gets_the_tag_and_stays_a_lab(self):
        self.run_imply()
        self.assertIn("_(tags: react, full-stack)_ _(kind: lab)_", (self.d / "ev.md").read_text())

    def test_idempotent_backup_600_never_overwritten(self):
        self.run_imply()
        first = (self.d / "ev.md").read_text()
        bak = self.d / "ev.md.bak"
        self.assertEqual(bak.read_text(), EVIDENCE)
        self.assertEqual(stat.S_IMODE(bak.stat().st_mode), 0o600)
        self.assertEqual(self.run_imply()["written"], 0)
        self.assertEqual((self.d / "ev.md").read_text(), first)
        self.assertEqual(bak.read_text(), EVIDENCE)

    def test_unknown_target_tag_is_an_error_and_writes_nothing(self):
        (self.d / "implies.txt").write_text("react => mystery\n")
        with self.assertRaisesRegex(ValueError, "mystery"):
            self.run_imply()
        self.assertEqual((self.d / "ev.md").read_text(), EVIDENCE)

    def test_malformed_rule_line_is_an_error(self):
        (self.d / "implies.txt").write_text("react full-stack\n")
        with self.assertRaisesRegex(ValueError, "line 1"):
            self.run_imply()

    def test_result_passes_draft_check(self):
        self.run_imply()
        keep = [l for l in (self.d / "ev.md").read_text().splitlines()
                if l.startswith("#") or re.match(r"- \*\*E\d+\*\* \*\*\[(high|med|low)\]", l)]
        self.assertEqual(draft_check.check_lines(keep), [])

    def test_cli(self):
        out = io.StringIO()
        args = ["tag-evidence", str(self.d / "ev.md"), str(self.d / "tags.txt"), "--implies", str(self.d / "implies.txt")]
        with contextlib.redirect_stdout(out):
            self.assertEqual(pipeline.main(args), 0)
        self.assertIn("would write: 3", out.getvalue())
        self.assertEqual((self.d / "ev.md").read_text(), EVIDENCE)
        with contextlib.redirect_stdout(out):
            self.assertEqual(pipeline.main(args + ["--apply"]), 0)
        self.assertEqual(tags_of(self.d / "ev.md", "E0003"), "html, full-stack")


class NotEvidencedTests(unittest.TestCase):
    def setUp(self):
        self.d = make(**{"ev.md": EVIDENCE, "tags.txt": TAGS, "fit.md": FIT, "rel.txt": "", "ns.txt": NONSKILL})

    def process(self, **kw):
        return fit_status.process(self.d / "fit.md", self.d / "ev.md", self.d / "tags.txt", self.d / "rel.txt",
                                  non_skill_path=self.d / "ns.txt", **kw)

    def statuses(self):
        return [[c.strip() for c in l.strip().strip("|").split("|")][3] for l in
                (self.d / "fit.md").read_text().splitlines()[2:]]

    def test_non_skill_without_evidence_is_not_evidenced_not_no(self):
        r = self.process()
        self.assertEqual(self.statuses(), ["Yes", "Not evidenced", "Yes", "Not evidenced", "No"])
        self.assertEqual(r["counts"], {"Yes": 2, "Partial": 0, "No": 1, "Not evidenced": 2})

    def test_user_stated_item_with_the_tag_gives_yes(self):
        self.process()
        self.assertEqual(self.statuses()[2], "Yes")
        self.assertIn("E0006", (self.d / "fit.md").read_text())

    def test_skill_gap_stays_no_and_check_accepts_new_status(self):
        self.process()
        self.assertEqual(self.process(check=True)["mismatch"], [])

    def test_idempotent(self):
        self.process()
        first = (self.d / "fit.md").read_text()
        self.process()
        self.assertEqual((self.d / "fit.md").read_text(), first)

    def test_default_non_skill_file_exists_and_is_used(self):
        self.assertTrue(fit_status.DEFAULT_NON_SKILL.exists())
        r = fit_status.process(self.d / "fit.md", self.d / "ev.md", self.d / "tags.txt", self.d / "rel.txt")
        self.assertEqual(r["counts"]["Not evidenced"], 2)

    def test_cli_reports_separately(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pipeline.main(["fit-status", str(self.d / "fit.md"), str(self.d / "ev.md"),
                                  str(self.d / "tags.txt"), "--relations", str(self.d / "rel.txt")])
        self.assertEqual(code, 0)
        self.assertIn("yes=2 partial=0 no=1 not_evidenced=2", out.getvalue())

    def test_template_and_skill_know_the_status(self):
        root = HERE.parent
        for f in ("templates/fit-table.template.md", "skills/tailor-offer/SKILL.md"):
            self.assertIn("Not evidenced", (root / f).read_text(), f)

    def test_every_default_non_skill_tag_is_in_the_default_tag_list(self):
        import tags as taglib
        tags, _ = taglib.load(HERE.parent / "templates/tags.default.txt")
        ns = fit_status.load_non_skill(fit_status.DEFAULT_NON_SKILL)
        self.assertEqual(sorted(ns - tags), [])
        self.assertIn("senior", ns)

    def test_default_tag_list_has_full_stack_and_default_rule_exists(self):
        root = HERE.parent
        self.assertIn("full-stack", (root / "templates/tags.default.txt").read_text().split())
        self.assertIn("=> full-stack", (root / "templates/tag-implies.txt").read_text())


if __name__ == "__main__":
    unittest.main()

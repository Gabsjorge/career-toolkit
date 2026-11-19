import contextlib, io, json, os, pathlib, stat, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import backfill_fit, pipeline

TAGS = "kafka\nnestjs\nnodejs\nreact\n[aliases]\nnode.js=nodejs\n"
EVIDENCE = """# Evidence

## 2026
- **E0001** **[high] 2026-09** — Built a consumer. _(tech: Kafka)_ _(tags: kafka)_
- **E0002** **[med] 2026-05** — Service in Nest. _(tech: NestJS)_ _(tags: nestjs, nodejs)_
"""
OLD_EN = """# Fit table: Acme Backend

Legend: text.

| Requirement | Do I have it? | Notes | Study recommendations |
|---|---|---|---|
| Kafka experience | No | Nothing | Learn it |
| NestJS | Yes | Used it | None |
| Unclear thing | Partial | Hmm | Read |
"""
OLD_PT = """# Fit table: Acme PT

| Requisito | Tenho? | Observações | Recomendações de estudo |
|---|---|---|---|
| Node.js | Sim | Usei | Nenhuma |
| Kafka | Não | Nada | Estudar |
| Outro | Parcial | x | y |
"""
NEW = """# Fit: New

| Requirement | Tag | Must/Nice | Status | Evidence IDs | Notes | Study recommendations |
|---|---|---|---|---|---|---|
| Kafka | kafka | Must | Yes | E0001 | n | s |
"""
BROKEN = """# Fit: broken

| Requirement | Do I have it? | Notes | Study recommendations |
|---|---|---|---|
| Kafka | No | only three cells |
"""


def make():
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "evidence.md").write_text(EVIDENCE)
    (d / "tags.txt").write_text(TAGS)
    apps = d / "applications"
    for slug, body in (("acme-en", OLD_EN), ("acme-pt", OLD_PT), ("new-one", NEW), ("broken", BROKEN)):
        (apps / slug).mkdir(parents=True)
        (apps / slug / "fit-table.md").write_text(body)
    return d


def fit(d, slug):
    return (d / "applications" / slug / "fit-table.md").read_text()


def run(d, proposals=None, apply_=False, report=None, pending=None):
    p = None
    if proposals is not None:
        p = d / "proposals.json"
        p.write_text(json.dumps(proposals))
    return backfill_fit.run(d / "applications", d / "evidence.md", d / "tags.txt", proposals=p,
                            apply=apply_, report=report, pending=pending)


PROPOSALS = {"acme-en:1": "kafka", "acme-en:2": "NestJS", "acme-en:3": None,
             "acme-pt:1": "node.js", "acme-pt:2": "kafka", "acme-pt:3": "pulsar"}


class PendingTests(unittest.TestCase):
    def test_pending_lists_old_format_rows_only_with_requirement_text_and_no_status(self):
        d = make()
        out = d / "pending.json"
        r = run(d, pending=out)
        pend = json.loads(out.read_text())
        self.assertEqual(pend["acme-en:1"], "Kafka experience")
        self.assertEqual(len(pend), 6)
        self.assertNotIn("Sim", json.dumps(pend))
        self.assertEqual(r["tables"], 2)
        self.assertEqual(r["skipped"], ["broken"])

    def test_pending_does_not_modify_tables(self):
        d = make()
        before = fit(d, "acme-en")
        run(d, pending=d / "p.json")
        self.assertEqual(fit(d, "acme-en"), before)


class DryRunTests(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        d = make()
        before = {s: fit(d, s) for s in ("acme-en", "acme-pt", "new-one", "broken")}
        r = run(d, PROPOSALS)
        self.assertEqual(before, {s: fit(d, s) for s in before})
        self.assertFalse(list((d / "applications" / "acme-en").glob("*.bak")))
        self.assertFalse(r["applied"])

    def test_counts_tagged_untagged_and_unknown(self):
        r = run(make(), PROPOSALS)
        self.assertEqual(r["rows"], 6)
        self.assertEqual(r["tagged"], 4)
        self.assertEqual(r["untagged"], 2)
        self.assertEqual(r["unknown_tags"], ["pulsar"])

    def test_missing_proposal_leaves_row_untagged(self):
        r = run(make(), {"acme-en:1": "kafka"})
        self.assertEqual(r["tagged"], 1)
        self.assertEqual(r["untagged"], 5)

    def test_differences_between_old_and_derived_status(self):
        d = make()
        report = d / "report.txt"
        r = run(d, PROPOSALS, report=report)
        # differ: en:1 No -> Yes, pt:2 Não -> Yes. same: en:2 Yes, pt:1 Sim.
        self.assertEqual(r["same"], 2)
        self.assertEqual(r["differ"], 2)
        text = report.read_text()
        self.assertIn("acme-en:1", text)
        self.assertIn("acme-pt:2", text)
        self.assertIn("Não -> Yes", text)
        self.assertNotIn("acme-en:2", text)
        self.assertEqual(stat.S_IMODE(report.stat().st_mode), 0o600)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.d = make()
        self.r = run(self.d, PROPOSALS, apply_=True)

    def test_new_columns_and_derived_status(self):
        t = fit(self.d, "acme-en")
        self.assertIn("| Requirement | Tag | Must/Nice | Status | Evidence IDs | Notes | Study recommendations |", t)
        self.assertIn("| Kafka experience | kafka | — | Yes | E0001 | Nothing | Learn it |", t)
        self.assertIn("| NestJS | nestjs | — | Yes | E0002 | Used it | None |", t)
        self.assertIn("| Unclear thing | — | — | — | — | Hmm | Read |", t)

    def test_text_outside_the_table_is_kept(self):
        t = fit(self.d, "acme-en")
        self.assertTrue(t.startswith("# Fit table: Acme Backend\n\nLegend: text.\n\n"))

    def test_alias_is_written_as_canonical_tag(self):
        self.assertIn("| Node.js | nodejs | — | Yes | E0002 |", fit(self.d, "acme-pt"))

    def test_unknown_tag_leaves_row_untagged(self):
        self.assertIn("| Outro | — | — | — | — | x | y |", fit(self.d, "acme-pt"))

    def test_new_format_and_broken_tables_untouched(self):
        self.assertEqual(fit(self.d, "new-one"), NEW)
        self.assertEqual(fit(self.d, "broken"), BROKEN)

    def test_backup_of_every_converted_table_mode_600_and_original_content(self):
        bak = self.d / "applications" / "acme-en" / "fit-table.md.bak"
        self.assertEqual(bak.read_text(), OLD_EN)
        self.assertEqual(stat.S_IMODE(bak.stat().st_mode), 0o600)
        self.assertTrue((self.d / "applications" / "acme-pt" / "fit-table.md.bak").exists())
        self.assertFalse((self.d / "applications" / "new-one" / "fit-table.md.bak").exists())

    def test_second_run_changes_nothing(self):
        before = {s: fit(self.d, s) for s in ("acme-en", "acme-pt")}
        r = run(self.d, PROPOSALS, apply_=True)
        self.assertEqual(r["tables"], 0)
        self.assertEqual(before, {s: fit(self.d, s) for s in before})

    def test_older_backup_is_not_overwritten(self):
        d = make()
        bak = d / "applications" / "acme-en" / "fit-table.md.bak"
        bak.write_text("older")
        run(d, PROPOSALS, apply_=True)
        self.assertEqual(bak.read_text(), "older")
        self.assertEqual(len(list((d / "applications" / "acme-en").glob("fit-table.md.*.bak"))), 1)

    def test_fit_status_check_passes_on_converted_table(self):
        import fit_status
        r = fit_status.process(self.d / "applications" / "acme-pt" / "fit-table.md",
                               self.d / "evidence.md", self.d / "tags.txt", check=True)
        self.assertEqual(r["mismatch"], [])


class CliTests(unittest.TestCase):
    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = pipeline.main(["backfill-fit", *map(str, args)])
        return code, out.getvalue()

    def test_dry_run_prints_counts_only(self):
        d = make()
        (d / "proposals.json").write_text(json.dumps(PROPOSALS))
        code, out = self.cli(d / "applications", d / "evidence.md", d / "tags.txt", "--proposals", d / "proposals.json")
        self.assertEqual(code, 0)
        self.assertIn("rows=6 tagged=4 untagged=2", out)
        self.assertNotIn("Kafka experience", out)
        self.assertNotIn("acme", out)

    def test_usage_error(self):
        self.assertEqual(self.cli("only-one")[0], 64)

    def test_bad_proposals_file(self):
        d = make()
        (d / "p.json").write_text("[1]")
        code, out = self.cli(d / "applications", d / "evidence.md", d / "tags.txt", "--proposals", d / "p.json")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

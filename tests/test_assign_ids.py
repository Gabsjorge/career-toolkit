import contextlib, io, json, os, pathlib, re, stat, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import assign_ids, pipeline

OLD = """# Evidence

## 2026
- **[high] 2026-09** — Fixed a 502 caused by a malformed header. _(tech: nginx)_ **Impact:** Restored availability.
- **[low] 2025-03** — Removed dead flag paths. _(tech: TypeScript)_ _(no metric evidenced)_

## Gaps
- source one failed
- **[med] 2022-2023** — Built CI pipelines. _(tech: CI/CD)_
"""


def make_state(text=OLD):
    sd = pathlib.Path(tempfile.mkdtemp()) / "state"
    sd.mkdir()
    (sd / "evidence.md").write_text(text)
    return sd


def items(text):
    return [l for l in text.splitlines() if re.match(r"- \*\*(E\d+\*\* \*\*)?\[", l)]


class AssignTests(unittest.TestCase):
    def test_assigns_sequential_ids_and_changes_only_the_id(self):
        sd = make_state()
        n = assign_ids.assign(sd)
        self.assertEqual(n, 3)
        new = (sd / "evidence.md").read_text()
        self.assertIn("- **E0001** **[high] 2026-09** — Fixed", new)
        self.assertIn("- **E0003** **[med] 2022-2023**", new)
        stripped = re.sub(r"\*\*E\d{4}\*\* ", "", new)
        self.assertEqual(stripped, OLD)
        self.assertEqual(len(items(new)), len(items(OLD)))
        self.assertIn("- source one failed", new)

    def test_second_run_changes_nothing_and_makes_no_new_backup(self):
        sd = make_state()
        assign_ids.assign(sd)
        first = (sd / "evidence.md").read_text()
        baks = sorted(p.name for p in sd.glob("*.bak"))
        self.assertEqual(assign_ids.assign(sd), 0)
        self.assertEqual((sd / "evidence.md").read_text(), first)
        self.assertEqual(sorted(p.name for p in sd.glob("*.bak")), baks)

    def test_backup_is_mode_600_and_never_overwritten(self):
        sd = make_state()
        assign_ids.assign(sd)
        bak = sd / "evidence.md.bak"
        self.assertEqual(bak.read_text(), OLD)
        self.assertEqual(stat.S_IMODE(bak.stat().st_mode), 0o600)
        (sd / "evidence.md").write_text((sd / "evidence.md").read_text()
                                        + "- **[low] 2026-10** — New item. _(tech: Go)_\n")
        assign_ids.assign(sd, today="2026-10-01")
        self.assertEqual(bak.read_text(), OLD)
        dated = sd / "evidence.md.20261001.bak"
        self.assertTrue(dated.exists())
        self.assertIn("New item", dated.read_text())
        self.assertNotIn("E0004", dated.read_text())

    def test_deleted_item_id_is_not_reused(self):
        sd = make_state()
        assign_ids.assign(sd)
        lines = [l for l in (sd / "evidence.md").read_text().splitlines(True) if "E0003" not in l]
        lines.append("- **[low] 2026-11** — Another. _(tech: Go)_\n")
        (sd / "evidence.md").write_text("".join(lines))
        assign_ids.assign(sd, today="2026-11-01")
        text = (sd / "evidence.md").read_text()
        self.assertIn("**E0004** **[low] 2026-11**", text)
        self.assertNotIn("E0003", text)

    def test_new_item_after_existing_ids_continues_from_highest(self):
        sd = make_state("- **E0007** **[low] 2026-01** — A. _(tech: Go)_\n- **[low] 2026-02** — B. _(tech: Go)_\n")
        assign_ids.assign(sd)
        self.assertIn("**E0008** **[low] 2026-02**", (sd / "evidence.md").read_text())

    def test_user_stated_items_get_ids(self):
        sd = make_state("- **[user-stated] 2020-03 to 2021-09** — Led a team. Team of 3.\n- **[bogus] 2020-01** — Nope.\n")
        self.assertEqual(assign_ids.assign(sd), 1)
        text = (sd / "evidence.md").read_text()
        self.assertIn("- **E0001** **[user-stated] 2020-03", text)
        self.assertIn("- **[bogus]", text)

    def test_counter_file_holds_highest(self):
        sd = make_state()
        assign_ids.assign(sd)
        self.assertEqual(json.loads((sd / "evidence-ids.json").read_text())["highest"], 3)

    def test_untouched_when_nothing_to_do(self):
        sd = make_state("# Evidence\n\nno items\n")
        self.assertEqual(assign_ids.assign(sd), 0)
        self.assertEqual(list(sd.glob("*.bak")), [])

    def test_cli(self):
        sd = make_state()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pipeline.main(["assign-ids", str(sd)])
        self.assertEqual(code, 0)
        self.assertIn("3", out.getvalue())
        self.assertNotIn("Fixed", out.getvalue())

    def test_cli_missing_file(self):
        sd = pathlib.Path(tempfile.mkdtemp())
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.main(["assign-ids", str(sd)]), 1)


if __name__ == "__main__":
    unittest.main()

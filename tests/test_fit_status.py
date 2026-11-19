import contextlib, io, pathlib, re, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import fit_status, pipeline
from test_evidence_tags import EV, TAGS, tmp

REL = "# related tags\nkafka ~ rabbitmq\nredis ~ memcached\n"
TABLE = """# Fit: Acme Backend

| Requirement | Tag | Must/Nice | Status | Evidence IDs | Notes | Study recommendations |
|---|---|---|---|---|---|---|
| Kafka consumers | kafka | Must | Yes | E9999 | model guessed | |
| NestJS services | nestjs | Must | | | | |
| RabbitMQ | rabbitmq | Nice | | | | Do a small lab |
| Memcached | memcached | Nice | | | | |
| Go services | go | Nice | | | | |
| Cobol | cobol | Nice | | | | |
| Something vague | | Nice | | | | |

Notes below the table stay.
"""


def files(table=TABLE, ev=EV, tg=TAGS, rel=REL):
    return tmp(table, "fit.md"), tmp(ev, "ev.md"), tmp(tg, "tags.txt"), tmp(rel, "rel.txt")


def rows(path):
    out = []
    for line in path.read_text().splitlines():
        if line.startswith("|") and not line.startswith("|---") and "Requirement" not in line:
            out.append([c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))])
    return out


class DeriveTests(unittest.TestCase):
    def setUp(self):
        import evidence, tags
        self.ev = evidence.load(tmp(EV))
        self.tags, self.aliases = tags.load(tmp(TAGS))
        self.rel = fit_status.load_relations(tmp(REL))

    def d(self, tag):
        return fit_status.derive(tag, self.ev, self.rel)

    def test_yes_needs_real_work(self):
        self.assertEqual(self.d("kafka"), ("Yes", ["E0001"]))
        self.assertEqual(self.d("nestjs"), ("Yes", ["E0001"]))

    def test_lab_only_is_partial(self):
        self.assertEqual(self.d("redis"), ("Partial", ["E0003"]))

    def test_related_tag_is_partial(self):
        self.assertEqual(self.d("rabbitmq"), ("Partial", ["E0001", "E0003"]))

    def test_related_through_lab_is_partial(self):
        self.assertEqual(self.d("memcached"), ("Partial", ["E0003"]))

    def test_no_evidence_is_no(self):
        self.assertEqual(self.d("go"), ("No", []))     # E-less old item cannot be cited
        self.assertEqual(self.d("cobol"), ("No", []))


class TableTests(unittest.TestCase):
    def test_writes_status_and_ids_only(self):
        fit, ev, tg, rel = files()
        r = fit_status.process(fit, ev, tg, rel)
        r_rows = rows(fit)
        self.assertEqual([x[3] for x in r_rows], ["Yes", "Yes", "Partial", "Partial", "No", "No", "—"])
        self.assertEqual(r_rows[0][4], "E0001")
        self.assertEqual(r_rows[2][4], "E0001, E0003")
        self.assertEqual(r_rows[4][4], "—")
        self.assertEqual(r_rows[0][5], "model guessed")     # notes untouched
        self.assertEqual(r_rows[2][6], "Do a small lab")
        self.assertIn("Notes below the table stay.", fit.read_text())
        self.assertEqual(r["counts"], {"Yes": 2, "Partial": 2, "No": 2, "Not evidenced": 0})
        self.assertEqual(r["untagged"], [7])
        self.assertEqual(r["unknown_tags"], [6])

    def test_idempotent(self):
        fit, ev, tg, rel = files()
        fit_status.process(fit, ev, tg, rel)
        first = fit.read_text()
        fit_status.process(fit, ev, tg, rel)
        self.assertEqual(fit.read_text(), first)

    def test_check_detects_hand_edited_status(self):
        fit, ev, tg, rel = files()
        fit_status.process(fit, ev, tg, rel)
        self.assertEqual(fit_status.process(fit, ev, tg, rel, check=True)["mismatch"], [])
        fit.write_text(fit.read_text().replace("| No | — | ", "| Yes | E0001 | ", 1))
        before = fit.read_text()
        self.assertTrue(fit_status.process(fit, ev, tg, rel, check=True)["mismatch"])
        self.assertEqual(fit.read_text(), before)          # check never writes

    def test_alias_in_row_tag(self):
        table = TABLE.replace("| nestjs |", "| nest |")
        fit, ev, tg, rel = files(table)
        fit_status.process(fit, ev, tg, rel)
        self.assertEqual(rows(fit)[1][3], "Yes")

    def test_missing_columns(self):
        fit, ev, tg, rel = files("| Requirement | Status |\n|---|---|\n| x | Yes |\n")
        with self.assertRaisesRegex(ValueError, "Tag"):
            fit_status.process(fit, ev, tg, rel)

    def test_escaped_pipe_in_requirement(self):
        table = TABLE.replace("Kafka consumers", r"Kafka \| streams")
        fit, ev, tg, rel = files(table)
        fit_status.process(fit, ev, tg, rel)
        self.assertEqual(rows(fit)[0][3], "Yes")

    def test_cli(self):
        fit, ev, tg, rel = files()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pipeline.main(["fit-status", str(fit), str(ev), str(tg), "--relations", str(rel)])
        self.assertEqual(code, 1)                           # untagged / unknown rows
        self.assertIn("yes=2 partial=2 no=2", out.getvalue())
        self.assertIn("untagged rows: 7", out.getvalue())
        self.assertIn("unknown tag rows: 6", out.getvalue())

    def test_cli_clean_table_exit_0(self):
        table = "\n".join(l for l in TABLE.splitlines() if "Cobol" not in l and "vague" not in l)
        fit, ev, tg, rel = files(table)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.main(["fit-status", str(fit), str(ev), str(tg), "--relations", str(rel)]), 0)
            self.assertEqual(pipeline.main(["fit-status", str(fit), str(ev), str(tg), "--relations", str(rel), "--check"]), 0)


class UserStatusTests(unittest.TestCase):
    """A row that mixes things Evidence does and does not show needs a ruling by the user, in the Notes cell."""
    MARK = "| model guessed |"

    def table(self, note):
        return TABLE.replace(self.MARK, f"| {note} |")

    def test_user_status_overrides_derived_status_but_ids_stay_derived(self):
        fit, ev, tg, rel = files(self.table("[user-status: Partial] only one half is evidenced"))
        r = fit_status.process(fit, ev, tg, rel)
        row = rows(fit)[0]
        self.assertEqual((row[3], row[4]), ("Partial", "E0001"))
        self.assertEqual(row[5], "[user-status: Partial] only one half is evidenced")   # notes untouched
        self.assertEqual(r["counts"], {"Yes": 1, "Partial": 3, "No": 2, "Not evidenced": 0})
        self.assertEqual(r["overridden"], [1])

    def test_idempotent_and_check_accepts_the_ruling(self):
        fit, ev, tg, rel = files(self.table("[user-status: Partial] x"))
        fit_status.process(fit, ev, tg, rel)
        first = fit.read_text()
        fit_status.process(fit, ev, tg, rel)
        self.assertEqual(fit.read_text(), first)
        self.assertEqual(fit_status.process(fit, ev, tg, rel, check=True)["mismatch"], [])

    def test_unknown_status_value_is_ignored(self):
        fit, ev, tg, rel = files(self.table("[user-status: Maybe] x"))
        r = fit_status.process(fit, ev, tg, rel)
        self.assertEqual(rows(fit)[0][3], "Yes")
        self.assertEqual(r["overridden"], [])

    def test_rows_without_the_marker_are_unchanged(self):
        fit, ev, tg, rel = files(self.table("[user-status: No] x"))
        fit_status.process(fit, ev, tg, rel)
        self.assertEqual([x[3] for x in rows(fit)][1:], ["Yes", "Partial", "Partial", "No", "No", "—"])

    def test_cli_names_the_overrides_count(self):
        fit, ev, tg, rel = files(self.table("[user-status: Partial] x"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            pipeline.main(["fit-status", str(fit), str(ev), str(tg), "--relations", str(rel)])
        self.assertIn("overridden=1", out.getvalue())


if __name__ == "__main__":
    unittest.main()

import json, os, pathlib, subprocess, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import pipeline, runlog, state
runlog.ECHO = False   # keep test output quiet; test_runlog covers the echo
from test_harvest_git import make_repo, ME

def setup_state(repos, gh_hosts=None, cap=60000):
    sd = pathlib.Path(tempfile.mkdtemp()) / "state"
    state.init_state(sd)
    (sd / "config.json").write_text(json.dumps({
        "authors": [ME], "repos": [{"path": r, "kind": "client"} for r in repos],
        "gh_hosts": gh_hosts or [], "cap_tokens": cap}))
    (sd / "blocklist.txt").write_text("forbiddenterm\n")
    return sd

class PipelineTests(unittest.TestCase):
    def test_digest_writes_labeled_files_and_hides_real_names(self):
        repo = make_repo([("2024-03-01", ME, "Add secretshop endpoint"), ("2024-04-01", ME, "Fix bug")])
        sd = setup_state([repo])
        report = pipeline.run_digest(sd)
        self.assertEqual(report["written"], ["repo-1"])
        text = (sd / "digests" / "repo-1.md").read_text()
        self.assertNotIn("secretshop", text.lower())
        self.assertEqual(json.loads((sd / "label-map.json").read_text()), {"secretshop": "repo-1"})
        self.assertFalse((sd / "last_run.json").exists())

    def test_digest_requires_blocklist(self):
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        (sd / "blocklist.txt").unlink()
        with self.assertRaisesRegex(ValueError, "create state/blocklist.txt"):
            pipeline.run_digest(sd)
        (sd / "blocklist.txt").write_text("# nothing\n")
        with self.assertRaises(ValueError):
            pipeline.run_digest(sd)

    def test_digest_redacts_blocklist_terms(self):
        repo = make_repo([("2024-03-01", ME, "Add forbiddenterm export")])
        sd = setup_state([repo])
        report = pipeline.run_digest(sd)
        text = (sd / "digests" / "repo-1.md").read_text()
        self.assertNotIn("forbiddenterm", text.lower())
        self.assertIn("[redacted]", text)
        self.assertGreaterEqual(report["redacted"], 1)
        self.assertNotIn("forbiddenterm", json.dumps(report))

    def test_report_file_written_and_tracker_survives(self):
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        (sd / "digests").mkdir(exist_ok=True)
        (sd / "digests" / "tracker-1.md").write_text("t")
        report = pipeline.run_digest(sd)
        self.assertEqual(json.loads((sd / "digests" / ".report.json").read_text()), report)
        self.assertTrue((sd / "digests" / "tracker-1.md").exists())

    def test_duplicate_basename_is_a_gap(self):
        a = make_repo([("2024-03-01", ME, "Add a")])
        b = pathlib.Path(tempfile.mkdtemp()) / pathlib.Path(a).name
        b.mkdir()
        sd = setup_state([a, str(b)])
        report = pipeline.run_digest(sd)
        self.assertEqual(report["written"], ["repo-1"])
        self.assertEqual(report["gaps"], ["repo-1: duplicate repo name"])

    def test_cli_mark_run_gaps_and_misc(self):
        script = str(HERE.parent / "scripts" / "pipeline.py")
        run = lambda *a: subprocess.run([sys.executable, script] + list(a), capture_output=True, text=True)
        sd = setup_state(["/nonexistent/repo-x"])
        pipeline.run_digest(sd)
        r = run("mark-run", str(sd))
        self.assertEqual(r.returncode, 3)
        self.assertIn("open gaps: fix the failing sources, or re-run with --accept-gaps", r.stderr + r.stdout)
        self.assertFalse((sd / "last_run.json").exists())
        self.assertEqual(run("mark-run", "--accept-gaps", str(sd)).returncode, 0)
        self.assertTrue((sd / "last_run.json").exists())
        # estimate with no digests
        for f in (sd / "digests").glob("*.md"):
            f.unlink()
        r = run("estimate", str(sd))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no digests", r.stdout)
        self.assertEqual(run().returncode, 64)
        # --full before the state dir
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd2 = setup_state([repo])
        r = run("digest", "--full", str(sd2))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((sd2 / "digests" / "repo-1.md").exists())

    def test_mark_run_refuses_stray_sensitive_files(self):
        script = str(HERE.parent / "scripts" / "pipeline.py")
        run = lambda *a: subprocess.run([sys.executable, script] + list(a), capture_output=True, text=True)
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        pipeline.run_digest(sd)
        (sd.parent / "evidence.md").write_text("copy")
        r = run("mark-run", str(sd))
        self.assertEqual(r.returncode, 4)
        self.assertIn("evidence.md", r.stderr)
        self.assertEqual(run("check-strays", str(sd)).returncode, 1)
        self.assertFalse((sd / "last_run.json").exists())
        self.assertEqual(run("mark-run", "--accept-strays", str(sd)).returncode, 0)
        (sd.parent / "evidence.md").unlink()
        self.assertEqual(run("check-strays", str(sd)).returncode, 0)

    def test_mark_run_uses_digest_date_not_approval_date(self):
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        report = pipeline.run_digest(sd)
        self.assertEqual(report["run_date"], __import__("datetime").date.today().isoformat())
        rp = sd / "digests" / ".report.json"
        data = json.loads(rp.read_text()); data["run_date"] = "2024-05-05"
        rp.write_text(json.dumps(data))
        self.assertEqual(pipeline.main(["mark-run", str(sd)]), 0)
        self.assertEqual(state.read_last_run(sd)["date"], "2024-05-05")
        # old report without run_date falls back to today
        data.pop("run_date"); rp.write_text(json.dumps(data))
        self.assertEqual(pipeline.main(["mark-run", str(sd)]), 0)
        self.assertEqual(state.read_last_run(sd)["date"], __import__("datetime").date.today().isoformat())

    def test_unknown_flags_are_rejected(self):
        script = str(HERE.parent / "scripts" / "pipeline.py")
        run = lambda *a: subprocess.run([sys.executable, script] + list(a), capture_output=True, text=True)
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        r = run("digest", "--ful", str(sd))
        self.assertEqual(r.returncode, 64)
        self.assertIn("unknown flag --ful", r.stderr)
        self.assertIn("--full", r.stderr)
        self.assertFalse((sd / "digests" / "repo-1.md").exists())
        self.assertEqual(run("estimate", "--full", str(sd)).returncode, 64)

    def test_possible_missing_reported_as_count_only(self):
        repo = make_repo([("2024-03-01", ME, "listed", "Ana Dev"),
                          ("2024-03-02", "ana.old@corp.example", "other email", "Ana Dev")])
        sd = setup_state([repo])
        report = pipeline.run_digest(sd)
        self.assertEqual(report["possible_missing"], {"repo-1": 1})
        self.assertNotIn("corp.example", (sd / "digests" / ".report.json").read_text())

    def test_state_files_are_private_when_created_by_the_cli(self):
        script = str(HERE.parent / "scripts" / "pipeline.py")
        d = pathlib.Path(tempfile.mkdtemp()) / "state"
        subprocess.run([sys.executable, script, "init", str(d)], check=True, capture_output=True)
        self.assertEqual(os.stat(d).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(d / "digests").st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(d / "notes.md").st_mode & 0o777, 0o600)

    def test_run_log_has_progress_and_no_names(self):
        repo = make_repo([("2024-03-01", ME, "Fix forbiddenterm checkout")])
        sd = setup_state([repo])
        pipeline.run_digest(sd)
        pipeline.main(["mark-run", str(sd)])
        log = (sd / "run.log").read_text()
        self.assertIn("repo-1\tok\tcommits=1", log)
        self.assertIn("digest\tdone", log)
        self.assertIn("mark-run\tok", log)
        for secret in ("secretshop", "forbiddenterm", "Fix", str(sd)):
            self.assertNotIn(secret, log)
        self.assertEqual(os.stat(sd / "run.log").st_mode & 0o777, 0o600)

    def test_names_redacted_is_reported_and_logged(self):
        repo = make_repo([("2024-03-01", ME, "Pair with Rita Gomes on cache", "Ana Dev"),
                          ("2024-03-02", "rita@corp.example", "Add retry", "Rita Gomes")])
        sd = setup_state([repo])
        report = pipeline.run_digest(sd)
        self.assertEqual(report["names_redacted"], 1)
        self.assertNotIn("Rita", (sd / "digests" / "repo-1.md").read_text())
        self.assertIn("names_redacted=1", (sd / "run.log").read_text())

    def test_unused_blocklist_entries_are_reported_by_number(self):
        repo = make_repo([("2024-03-01", ME, "Fix forbiddenterm checkout")])
        sd = setup_state([repo])
        (sd / "blocklist.txt").write_text("neverappears\nforbiddenterm\nalsonever\n")
        report = pipeline.run_digest(sd)
        self.assertEqual(report["unused_entries"], [1, 3])
        self.assertEqual(report["redacted"], 1)
        self.assertNotIn("neverappears", (sd / "digests" / ".report.json").read_text())

    def test_empty_delta_says_nothing_new(self):
        script = str(HERE.parent / "scripts" / "pipeline.py")
        run = lambda *a: subprocess.run([sys.executable, script] + list(a), capture_output=True, text=True)
        repo = make_repo([("2023-01-01", ME, "old work")])
        sd = setup_state([repo])
        state.write_last_run(sd, "2024-01-01")
        r = run("digest", str(sd))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no new activity since 2024-01-01", r.stderr)
        r = run("estimate", str(sd))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no digests", r.stdout)
        self.assertIn("nothing new", r.stdout)

    def test_run_log_records_gaps_with_class_only(self):
        sd = setup_state(["/nonexistent/repo-x"])
        pipeline.run_digest(sd)
        log = (sd / "run.log").read_text()
        self.assertIn("repo-1\tgap\terror_class=CalledProcessError", log)
        self.assertNotIn("nonexistent", log)

    def test_mark_run_requires_safe_state(self):
        sd = pathlib.Path(tempfile.mkdtemp()) / "state"
        sd.mkdir()
        with self.assertRaises(RuntimeError):
            pipeline.main(["mark-run", str(sd)])

    def test_skips_repo_without_commits_and_logs_gap_for_missing_repo(self):
        empty = make_repo([("2024-03-01", "other@example.com", "x")])
        sd = setup_state([empty, "/nonexistent/path/repo-x"])
        report = pipeline.run_digest(sd)
        self.assertEqual(report["written"], [])
        self.assertEqual(report["skipped"], ["repo-1"])
        self.assertEqual(len(report["gaps"]), 1)
        self.assertTrue(report["gaps"][0].startswith("repo-2:"))

    def test_second_run_clears_old_digests_and_keeps_labels(self):
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        pipeline.run_digest(sd)
        (sd / "digests" / "repo-9.md").write_text("old")
        pipeline.run_digest(sd)
        self.assertFalse((sd / "digests" / "repo-9.md").exists())
        self.assertTrue((sd / "digests" / "repo-1.md").exists())

    def test_invalid_blocklist_entry_aborts_and_keeps_old_digests(self):
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        pipeline.run_digest(sd)
        before = (sd / "digests" / "repo-1.md").read_text()
        (sd / "blocklist.txt").write_text("ok\nsecret(unclosed\n")
        with self.assertRaises(ValueError) as cm:
            pipeline.run_digest(sd)
        self.assertIn("#2", str(cm.exception))
        self.assertNotIn("secret", str(cm.exception))
        self.assertEqual((sd / "digests" / "repo-1.md").read_text(), before)

    def test_crash_mid_run_keeps_old_digests_and_cleans_staging(self):
        from unittest import mock
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        pipeline.run_digest(sd)
        before = (sd / "digests" / "repo-1.md").read_text()
        with mock.patch.object(pipeline.labels, "redact_counted", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                pipeline.run_digest(sd)
        self.assertEqual((sd / "digests" / "repo-1.md").read_text(), before)
        self.assertFalse((sd / "digests" / ".staging").exists())

    def test_success_keeps_previous_generation_and_tracker(self):
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo])
        pipeline.run_digest(sd)
        (sd / "digests" / "tracker-1.md").write_text("tracker")
        old = (sd / "digests" / "repo-1.md").read_text()
        pipeline.run_digest(sd)
        dd = sd / "digests"
        self.assertEqual((dd / ".prev" / "repo-1.md").read_text(), old)
        self.assertTrue((dd / ".prev" / ".report.json").exists())
        self.assertTrue((dd / "tracker-1.md").exists())
        self.assertTrue((dd / ".report.json").exists())
        self.assertFalse((dd / ".staging").exists())
        import estimate
        self.assertEqual(estimate.estimate(dd, 60000, 1.0)["files"], 2)   # repo-1 + tracker-1

    def test_delta_uses_last_run_date(self):
        repo = make_repo([("2023-01-01", ME, "old work"), ("2025-06-01", ME, "new work")])
        sd = setup_state([repo])
        state.write_last_run(sd, "2024-01-01")
        report = pipeline.run_digest(sd)
        self.assertEqual(report["since"], "2024-01-01")
        text = (sd / "digests" / "repo-1.md").read_text()
        self.assertIn("new work", text)
        self.assertNotIn("old work", text)
        full = pipeline.run_digest(sd, full=True)
        self.assertIsNone(full["since"])
        self.assertIn("old work", (sd / "digests" / "repo-1.md").read_text())

    def test_pr_digest_with_fake_runner(self):
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo], gh_hosts=["ghe.example.com"])
        def runner(cmd, env):
            if cmd[:3] == ["gh", "search", "prs"]:
                return json.dumps([{"repository": {"nameWithOwner": "o/r"}, "number": 1,
                                    "createdAt": "2024-03-05T00:00:00Z", "author": {"login": "bob"}}])
            if cmd[:3] == ["gh", "api", "user"]:
                return "me\n"
            return "me\n"
        pipeline.run_digest(sd, pr_runner=runner)
        text = (sd / "digests" / "reviews-1.md").read_text()
        self.assertIn("1 PRs reviewed", text)
        self.assertNotIn("bob", text)

    def test_pr_digest_capped_in_report(self):
        from unittest import mock
        import harvest_prs
        repo = make_repo([("2024-03-01", ME, "Add thing")])
        sd = setup_state([repo], gh_hosts=["ghe.example.com"])
        def runner(cmd, env):
            if cmd[:3] == ["gh", "search", "prs"]:
                return json.dumps([{"repository": {"nameWithOwner": "o/r"}, "number": i,
                                    "createdAt": "2024-03-05T00:00:00Z", "author": {"login": "bob"}}
                                   for i in range(3)])
            return "me\n"
        with mock.patch.object(harvest_prs, "LIMIT", 3):
            report = pipeline.run_digest(sd, pr_runner=runner)
        self.assertTrue(report["capped"])
        self.assertIn("WARNING", (sd / "digests" / "reviews-1.md").read_text())

    def test_cli_init_estimate_scrub_and_mark_run(self):
        script = str(HERE.parent / "scripts" / "pipeline.py")
        sd = pathlib.Path(tempfile.mkdtemp()) / "state"
        run = lambda *a: subprocess.run([sys.executable, script] + list(a), capture_output=True, text=True)
        self.assertEqual(run("init", str(sd)).returncode, 0)
        self.assertTrue((sd / ".gitignore").exists())
        (sd / "digests" / "a.md").write_text("x" * 400)
        (sd / "config.json").write_text(json.dumps({"authors": [ME], "repos": [{"path": "/x", "kind": "client"}], "cap_tokens": 10}))
        r = run("estimate", str(sd))
        self.assertEqual(r.returncode, 2)
        self.assertIn("OVER CAP", r.stdout)
        (sd / "blocklist.txt").write_text("forbidden\n")
        good = sd / "good.md"; good.write_text("fine\n")
        bad = sd / "bad.md"; bad.write_text("a forbidden word\n")
        self.assertEqual(run("scrub", str(sd), str(good)).returncode, 0)
        self.assertEqual(run("scrub", str(sd), str(bad)).returncode, 1)
        self.assertEqual(run("mark-run", str(sd)).returncode, 0)
        self.assertTrue((sd / "last_run.json").exists())

if __name__ == "__main__":
    unittest.main()

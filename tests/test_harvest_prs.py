import datetime, json, pathlib, sys, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import harvest_prs

def pr(n, month, author="bob", repo="org/secret-repo"):
    return {"repository": {"nameWithOwner": repo}, "number": n,
            "createdAt": f"{month}-10T10:00:00Z", "author": {"login": author}}

class PrTests(unittest.TestCase):
    def test_fetch_builds_command_and_env(self):
        seen = {}
        def runner(cmd, env):
            seen["cmd"], seen["env"] = cmd, env
            return json.dumps([pr(1, "2025-01")])
        prs, capped = harvest_prs.fetch_reviewed_prs("ghe.example.com", "2025-01-01", runner,
                                                     today=datetime.date(2025, 2, 1))
        self.assertEqual(len(prs), 1)
        self.assertFalse(capped)
        self.assertIn("2025-01-01..2025-02-01", seen["cmd"])
        self.assertIn("--updated", seen["cmd"])
        self.assertNotIn("--created", seen["cmd"])
        self.assertIn("updatedAt", seen["cmd"][seen["cmd"].index("--json") + 1])
        self.assertEqual(seen["env"]["GH_HOST"], "ghe.example.com")

    def test_delta_includes_pr_opened_before_since_but_updated_after(self):
        old = {"repository": {"nameWithOwner": "o/r"}, "number": 7, "createdAt": "2024-03-01T00:00:00Z",
               "updatedAt": "2024-07-15T00:00:00Z", "author": {"login": "a"}}
        prs, _ = harvest_prs.fetch_reviewed_prs("h", "2024-04-01", self._store_runner([old], []),
                                                today=datetime.date(2024, 8, 1))
        self.assertEqual([p["number"] for p in prs], [7])
        delta = harvest_prs.build_digest(prs, {"sampled": 0, "with_comments": 0, "comments": 0},
                                         "reviews-1", by="updatedAt")
        self.assertIn("(active in period)", delta)
        self.assertIn("- 2024-07: 1", delta)
        full = harvest_prs.build_digest(prs, {"sampled": 0, "with_comments": 0, "comments": 0}, "reviews-1")
        self.assertIn("- 2024-03: 1", full)
        self.assertNotIn("active in period", full)

    def test_fetch_without_since(self):
        seen = {}
        def runner(cmd, env):
            seen["cmd"] = cmd
            return "[]"
        harvest_prs.fetch_reviewed_prs("h", None, runner, today=datetime.date(2025, 2, 1))
        self.assertIn("2008-01-01..2025-02-01", seen["cmd"])

    def _store_runner(self, store, calls):
        def runner(cmd, env):
            calls.append(cmd)
            s, e = cmd[cmd.index("--updated") + 1].split("..")
            lim = int(cmd[cmd.index("--limit") + 1])
            hits = [p for p in store if s <= p.get("updatedAt", p["createdAt"])[:10] <= e]
            return json.dumps(hits[:lim])
        return runner

    def test_bisection_returns_all(self):
        store = []
        for i in range(180):
            d = datetime.date(2022, 1, 1) + datetime.timedelta(days=i * 6)
            store.append({"repository": {"nameWithOwner": "o/r"}, "number": i,
                          "createdAt": d.isoformat() + "T00:00:00Z", "author": {"login": "a"}})
        calls = []
        with mock.patch.object(harvest_prs, "LIMIT", 50):
            prs, capped = harvest_prs.fetch_reviewed_prs(
                "h", None, self._store_runner(store, calls), today=datetime.date(2024, 12, 31))
        self.assertEqual(len(prs), 180)
        self.assertEqual(len({(p["repository"]["nameWithOwner"], p["number"]) for p in prs}), 180)
        self.assertFalse(capped)
        self.assertGreater(len(calls), 1)

    def test_single_day_cap(self):
        store = [{"repository": {"nameWithOwner": "o/r"}, "number": i,
                  "createdAt": "2023-05-05T00:00:00Z", "author": {"login": "a"}} for i in range(60)]
        with mock.patch.object(harvest_prs, "LIMIT", 50):
            prs, capped = harvest_prs.fetch_reviewed_prs(
                "h", None, self._store_runner(store, []), today=datetime.date(2024, 1, 1))
        self.assertTrue(capped)
        self.assertEqual(len(prs), 50)

    def test_empty_store_one_call(self):
        calls = []
        with mock.patch.object(harvest_prs, "LIMIT", 50):
            prs, capped = harvest_prs.fetch_reviewed_prs(
                "h", None, self._store_runner([], calls), today=datetime.date(2024, 1, 1))
        self.assertEqual((prs, capped, len(calls)), ([], False, 1))

    def test_digest_warning_only_when_capped(self):
        stats = {"sampled": 1, "with_comments": 0, "comments": 0}
        w = "WARNING: the search hit its result cap on a single day; some PRs are missing"
        plain = harvest_prs.build_digest([pr(1, "2025-01")], stats, "r")
        capd = harvest_prs.build_digest([pr(1, "2025-01")], stats, "r", capped=True)
        self.assertNotIn("WARNING", plain)
        self.assertEqual(capd.splitlines()[1], w)

    def test_current_login(self):
        self.assertEqual(harvest_prs.current_login("h", lambda c, e: "me\n"), "me")

    def test_sample_comment_counts(self):
        prs = [pr(1, "2025-01"), pr(2, "2025-01"), pr(3, "2025-02")]
        answers = {"repos/org/secret-repo/pulls/1/comments": "me\nother\nme\n",
                   "repos/org/secret-repo/pulls/2/comments": "",
                   "repos/org/secret-repo/pulls/3/comments": "other\n"}
        def runner(cmd, env):
            return answers.get(cmd[2], "")
        stats = harvest_prs.sample_comment_counts(prs, "me", "h", runner, n=40)
        self.assertEqual(stats, {"sampled": 3, "with_comments": 1, "comments": 2,
                                 "inline": 2, "reviews": 0, "conversation": 0})

    def test_review_summaries_and_conversation_count_as_written_feedback(self):
        prs = [pr(1, "2025-01"), pr(2, "2025-01"), pr(3, "2025-02")]
        answers = {"repos/org/secret-repo/pulls/1/reviews": "me\nother\n",
                   "repos/org/secret-repo/issues/2/comments": "me\nme\nme\n",
                   "repos/org/secret-repo/pulls/2/comments": "me\n"}
        seen = []
        def runner(cmd, env):
            seen.append(cmd)
            return answers.get(cmd[2], "")
        stats = harvest_prs.sample_comment_counts(prs, "me", "h", runner)
        self.assertEqual(stats, {"sampled": 3, "with_comments": 2, "comments": 5,
                                 "inline": 1, "reviews": 1, "conversation": 3})
        self.assertEqual(len(seen), 9)                       # three endpoints per sampled PR
        reviews_cmd = [c for c in seen if c[2].endswith("/reviews")][0]
        self.assertIn('select((.body // "") != "")', reviews_cmd[-1])   # empty approvals do not count

    def test_sample_respects_n(self):
        prs = [pr(i, "2025-01") for i in range(100)]
        calls = []
        def runner(cmd, env):
            calls.append(cmd)
            return ""
        stats = harvest_prs.sample_comment_counts(prs, "me", "h", runner, n=10)
        self.assertLessEqual(stats["sampled"], 10)
        self.assertEqual(len(calls), 3 * stats["sampled"])

    def test_sample_uses_ceil_step(self):
        prs = [pr(i, "2025-01") for i in range(79)]
        calls = []
        def runner(cmd, env):
            calls.append(cmd[2])
            return ""
        harvest_prs.sample_comment_counts(prs, "me", "h", runner, n=40)
        self.assertIn("repos/org/secret-repo/pulls/78/comments", calls)  # step 2 reaches the tail

    def test_failing_endpoint_skips_the_whole_pr(self):
        prs = [pr(1, "2025-01"), pr(2, "2025-01")]
        def runner(cmd, env):
            if "/1/" in cmd[2] and cmd[2].endswith("/reviews"):
                raise RuntimeError("403")
            return "me\n"
        stats = harvest_prs.sample_comment_counts(prs, "me", "h", runner)
        self.assertEqual(stats["sampled"], 1)
        self.assertEqual(stats["comments"], 3)     # only PR 2 counted, all three endpoints

    def test_build_digest_has_no_identifiers(self):
        prs = [pr(1, "2025-01", "alice"), pr(2, "2025-01", "bob"), pr(3, "2025-02", "alice")]
        text = harvest_prs.build_digest(prs, {"sampled": 3, "with_comments": 1, "comments": 2}, "reviews-1")
        self.assertIn("3 PRs reviewed", text)
        self.assertIn("2025-01: 2", text)
        self.assertIn("distinct authors: 2", text)
        self.assertIn("sampled 3 PRs; 1 had a written comment", text)
        full = harvest_prs.build_digest(prs, {"sampled": 3, "with_comments": 2, "comments": 5, "inline": 1,
                                              "reviews": 1, "conversation": 3}, "reviews-1")
        self.assertIn("(1 inline, 1 review summaries, 3 conversation)", full)
        for forbidden in ["alice", "bob", "secret-repo", "org/"]:
            self.assertNotIn(forbidden, text)

    def test_build_digest_empty(self):
        self.assertIsNone(harvest_prs.build_digest([], {"sampled": 0, "with_comments": 0, "comments": 0}, "r"))


class RunRateLimitTests(unittest.TestCase):
    def _res(self, rc, out="", err=""):
        return mock.Mock(returncode=rc, stdout=out, stderr=err)

    def test_retry_then_success(self):
        sleeps = []
        with mock.patch.object(harvest_prs, "_sleep", sleeps.append), \
             mock.patch("subprocess.run", side_effect=[self._res(1, err="HTTP 403: API rate limit exceeded"), self._res(0, out="ok")]):
            self.assertEqual(harvest_prs._run(["gh"]), "ok")
        self.assertEqual(sleeps, [65])

    def test_exhausted(self):
        sleeps = []
        with mock.patch.object(harvest_prs, "_sleep", sleeps.append), \
             mock.patch("subprocess.run", return_value=self._res(1, err="API Rate Limit exceeded")):
            with self.assertRaises(RuntimeError) as c:
                harvest_prs._run(["gh"])
        self.assertEqual(len(sleeps), harvest_prs.RATE_LIMIT_RETRIES)
        self.assertEqual(str(c.exception), "gh rate limit: retries exhausted")

    def test_other_error(self):
        sleeps = []
        with mock.patch.object(harvest_prs, "_sleep", sleeps.append), \
             mock.patch("subprocess.run", return_value=self._res(1, err="boom https://ghe.example.com/x")):
            with self.assertRaises(RuntimeError) as c:
                harvest_prs._run(["gh"])
        self.assertEqual(sleeps, [])
        self.assertNotIn("ghe.example", str(c.exception))
        self.assertNotIn("boom", str(c.exception))


if __name__ == "__main__":
    unittest.main()

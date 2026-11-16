import json, pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import state

class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp()) / "state"

    def test_init_creates_gitignore_and_dirs(self):
        created = state.init_state(self.tmp)
        self.assertEqual(created[0].name, ".gitignore")
        self.assertTrue(state.ignore_ok(self.tmp))
        self.assertTrue((self.tmp / "digests").is_dir())
        self.assertTrue((self.tmp / "config.example.json").exists())
        self.assertTrue((self.tmp / "notes.md").exists())
        text = (self.tmp / ".gitignore").read_text()
        for entry in ["config.json", "blocklist.txt", "last_run.json", "notes.md",
                      "digests/", "label-map.json", "evidence.md", "evidence-draft.md", "*.pdf",
                      "!config.example.json"]:
            self.assertIn(entry, text.splitlines())

    def test_init_is_idempotent_and_keeps_edits(self):
        state.init_state(self.tmp)
        gi = self.tmp / ".gitignore"
        gi.write_text(gi.read_text() + "extra.txt\n")
        self.assertEqual(state.init_state(self.tmp), [])
        self.assertIn("extra.txt", gi.read_text())

    def test_find_strays_flags_sensitive_names_outside_state(self):
        state.init_state(self.tmp)
        (self.tmp / "blocklist.txt").write_text("x")            # inside STATE: fine
        parent = self.tmp.parent
        (parent / "evidence.md").write_text("x")
        (parent / "tools").mkdir()
        (parent / "tools" / "blocklist.txt").write_text("x")
        (parent / "node_modules").mkdir()
        (parent / "node_modules" / "config.json").write_text("{}")  # skipped dir
        (parent / "notes.md").write_text("x")                     # generic name, not flagged
        found = sorted(pathlib.Path(p).relative_to(parent.resolve()).as_posix()
                       for p in state.find_strays(self.tmp))
        self.assertEqual(found, ["evidence.md", "tools/blocklist.txt"])

    def test_bak_ignore_entry_is_optional(self):
        state.init_state(self.tmp)
        self.assertIn("*.bak", (self.tmp / ".gitignore").read_text().splitlines())
        gi = self.tmp / ".gitignore"
        gi.write_text("\n".join(l for l in gi.read_text().splitlines() if l != "*.bak"))
        self.assertTrue(state.ignore_ok(self.tmp))

    def test_assert_safe_raises_without_ignore(self):
        self.tmp.mkdir(parents=True)
        (self.tmp / "config.json").write_text("{}")
        with self.assertRaises(RuntimeError):
            state.assert_safe(self.tmp)

    def test_assert_safe_raises_when_entry_missing(self):
        state.init_state(self.tmp)
        gi = self.tmp / ".gitignore"
        gi.write_text("\n".join(l for l in gi.read_text().splitlines() if l != "blocklist.txt"))
        with self.assertRaises(RuntimeError):
            state.assert_safe(self.tmp)

    def test_assert_safe_raises_when_draft_not_ignored(self):
        state.init_state(self.tmp)
        gi = self.tmp / ".gitignore"
        gi.write_text("\n".join(l for l in gi.read_text().splitlines() if l != "evidence-draft.md"))
        with self.assertRaises(RuntimeError):
            state.assert_safe(self.tmp)

    def test_missing_config_is_clean_error(self):
        state.init_state(self.tmp)
        with self.assertRaisesRegex(ValueError, "config.json not found in STATE"):
            state.load_config(self.tmp)

    def test_load_config_defaults(self):
        state.init_state(self.tmp)
        (self.tmp / "config.json").write_text(json.dumps(
            {"authors": ["a@x.com"], "repos": [{"path": "~/r", "kind": "client"}]}))
        cfg = state.load_config(self.tmp)
        self.assertEqual(cfg["cap_tokens"], 60000)
        self.assertEqual(cfg["price_per_mtok"], 1.0)
        self.assertEqual(cfg["gh_hosts"], [])

    def test_load_config_requires_authors_and_repos(self):
        state.init_state(self.tmp)
        (self.tmp / "config.json").write_text(json.dumps({"authors": []}))
        with self.assertRaises(ValueError):
            state.load_config(self.tmp)

    def test_load_config_rejects_wrong_types_naming_only_the_key(self):
        state.init_state(self.tmp)
        base = {"authors": ["a@x.com"], "repos": [{"path": "~/r"}]}
        cases = {"cap_tokens": ["60000", 0, True, 1.5], "price_per_mtok": ["1", -1, True],
                 "gh_hosts": ["github.com", [1]], "authors": [[""], "a@x.com", [1]],
                 "repos": ["~/r", [{"kind": "x"}], [{"path": 3}]]}
        for key, values in cases.items():
            for value in values:
                (self.tmp / "config.json").write_text(json.dumps(dict(base, **{key: value})))
                with self.assertRaisesRegex(ValueError, f"'{key}' must be") as cm:
                    state.load_config(self.tmp)
                self.assertNotIn("60000", str(cm.exception))
        (self.tmp / "config.json").write_text(json.dumps(dict(base, cap_tokens=5000, price_per_mtok=2)))
        self.assertEqual(state.load_config(self.tmp)["cap_tokens"], 5000)

    def test_since_date(self):
        state.init_state(self.tmp)
        self.assertIsNone(state.since_date(self.tmp, full=False))
        self.assertEqual(state.write_last_run(self.tmp, "2026-10-01"), "2026-10-01")
        self.assertEqual(state.since_date(self.tmp, full=False), "2026-10-01")
        self.assertIsNone(state.since_date(self.tmp, full=True))

if __name__ == "__main__":
    unittest.main()

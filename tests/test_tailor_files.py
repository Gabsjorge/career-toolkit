import pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = (ROOT / "skills" / "tailor-offer" / "SKILL.md").read_text()


class TailorSkillTests(unittest.TestCase):
    def test_frontmatter(self):
        m = re.match(r"---\nname: tailor-offer\ndescription: (.+)\n---\n", SKILL)
        self.assertIsNotNone(m)
        self.assertGreater(len(m.group(1)), 40)

    def test_scripts_and_templates_mentioned_exist(self):
        for n in set(re.findall(r"scripts/([\w.-]+\.(?:py|css|swift))", SKILL)):
            self.assertTrue((ROOT / "scripts" / n).exists(), n)
        for n in set(re.findall(r"templates/([\w.-]+)", SKILL)):
            self.assertTrue((ROOT / "templates" / n).exists(), n)

    def test_commands_mentioned_exist_in_usage(self):
        import pipeline
        for cmd in set(re.findall(r"PIPE ([a-z-]+)", SKILL)):
            self.assertIn(cmd, pipeline.USAGE + " scrub", cmd)

    def test_rules_are_stated(self):
        for needle in ["untrusted data", "fetch tool the harness provides", "Never write a fetch script",
                       "fit-status", "bullets-check", "estimate-files", "ev:user", "claim-words.txt", "Always deliver all three files",
                       "stack gap", "cheapest tier", "never set Status", "personal lab", "scrub"]:
            self.assertIn(needle.lower(), SKILL.lower(), needle)

    def test_untagged_evidence_does_not_stop_the_skill(self):
        for needle in ["Evidence without tags is expected", "Do not pause",
                       "never edit `STATE/evidence.md`", "Do not hand-set Status"]:
            self.assertIn(needle, SKILL, needle)

    def test_standing_user_approval_in_notes_is_honored(self):
        for needle in ["Approved without Evidence", "STATE/notes.md", "keep the approved bullet",
                       "never add a line to that list"]:
            self.assertIn(needle, SKILL, needle)

    def test_never_asks_for_paths_or_reads_private_files(self):
        self.assertIn("Never read, print or summarize `STATE/config.json`", SKILL)


if __name__ == "__main__":
    unittest.main()

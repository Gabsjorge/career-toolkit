import pathlib, re, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = (ROOT / "skills" / "search-offers" / "SKILL.md").read_text()
DOC = (ROOT / "docs" / "search-offers.md").read_text()


class SearchSkillTests(unittest.TestCase):
    def test_frontmatter(self):
        m = re.match(r"---\nname: search-offers\ndescription: (.+)\n---\n", SKILL)
        self.assertIsNotNone(m)
        self.assertGreater(len(m.group(1)), 40)

    def test_scripts_and_templates_mentioned_exist(self):
        for n in set(re.findall(r"scripts/([\w.-]+\.(?:py|css|swift))", SKILL)):
            self.assertTrue((ROOT / "scripts" / n).exists(), n)
        for n in set(re.findall(r"templates/([\w.-]+)", SKILL)):
            self.assertTrue((ROOT / "templates" / n).exists(), n)

    def test_commands_mentioned_exist_in_usage(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import pipeline
        for cmd in set(re.findall(r"PIPE ([a-z-]+)", SKILL)):
            self.assertIn(cmd, pipeline.USAGE, cmd)

    def test_rules_are_stated(self):
        for needle in ["untrusted data", "Never search the web", "never fetch a listing site", "Never write a fetch script",
                       "never set Status or a score", "estimate-files", "cheapest tier", "rank-offers", "tailor-offer",
                       "CAREER/offers/", "Not evidenced", "runs on a `client` and a `personal` machine", "Do not call a model without"]:
            self.assertIn(needle.lower(), SKILL.lower(), needle)

    def test_user_approves_tags_and_thin_offers_are_flagged(self):
        for needle in ["Never approve a tag yourself", "one list", "non-skill-tags.txt", "(thin)", "Never invent a company", "or null"]:
            self.assertIn(needle, SKILL, needle)

    def test_never_reads_private_files(self):
        self.assertIn("Never read, print or summarize `STATE/config.json`", SKILL)

    def test_doc_covers_the_basics(self):
        for needle in ["rank-offers", "digest", "shortlist", "score", "Not evidenced", "tailor-offer"]:
            self.assertIn(needle, DOC, needle)
        for cmd in set(re.findall(r"pipeline\.py ([a-z-]+)", DOC)):
            import sys
            sys.path.insert(0, str(ROOT / "scripts"))
            import pipeline
            self.assertIn(cmd, pipeline.USAGE, cmd)


if __name__ == "__main__":
    unittest.main()

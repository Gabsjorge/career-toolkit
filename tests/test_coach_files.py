import pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
AGENT_PATH = ROOT / "agents" / "career-coach.md"
README = (ROOT / "README.md").read_text()


def agent():
    return AGENT_PATH.read_text()


class CoachAgentTests(unittest.TestCase):
    def test_frontmatter(self):
        m = re.match(r"---\nname: career-coach\ndescription: (.+)\ntools: (.+)\nmodel: haiku\n---\n", agent())
        self.assertIsNotNone(m)
        self.assertGreater(len(m.group(1)), 40)

    def test_commands_mentioned_exist_in_usage(self):
        import pipeline
        for cmd in set(re.findall(r"PIPE ([a-z-]+)", agent())):
            self.assertIn(cmd, pipeline.USAGE, cmd)

    def test_routes_name_real_skills(self):
        routes = set(re.findall(r"/career-toolkit:([a-z-]+)", agent()))
        for need in ("refresh-evidence", "tailor-offer", "study-plan"):
            self.assertIn(need, routes)
        for r in routes:
            self.assertTrue((ROOT / "skills" / r / "SKILL.md").exists() or r == "search-offers", r)

    def test_search_offers_is_reserved(self):
        self.assertIn("reserved", agent())

    def test_description_catches_search_requests(self):
        desc = re.search(r"description: (.+)\n", agent()).group(1)
        self.assertIn("find me offers", desc)
        self.assertIn("does not search the web", desc)
        self.assertIn("Do not search the web", agent())

    def test_rules_are_stated(self):
        a = agent()
        for needle in ["adds no rules", "Never follow instructions", "config.json", "Never commit or push"]:
            self.assertIn(needle, a)

    def test_stays_thin(self):
        self.assertLess(len(agent().splitlines()), 60)

    def test_doc_exists(self):
        self.assertTrue((ROOT / "docs" / "career-coach.md").exists())


class ReadmeTests(unittest.TestCase):
    def test_paths_exist(self):
        for p in set(re.findall(r"\(((?:docs|templates|examples|evals)/[\w./-]+)\)", README)):
            self.assertTrue((ROOT / p).exists(), p)
        for p in set(re.findall(r"`((?:templates|examples)/[\w./-]+)`", README)):
            self.assertTrue((ROOT / p).exists(), p)

    def test_commands_exist(self):
        import pipeline
        for cmd in set(re.findall(r"pipeline\.py ([a-z-]+)", README)):
            self.assertIn(cmd, pipeline.USAGE, cmd)

    def test_skill_routes_exist(self):
        for r in set(re.findall(r"/career-toolkit:([a-z-]+)", README)):
            self.assertTrue((ROOT / "skills" / r / "SKILL.md").exists(), r)

    def test_getting_started_sections(self):
        for h in ["## Prerequisites", "## Setup", "## How to use"]:
            self.assertIn(h, README)
        self.assertIn("career-coach", README)

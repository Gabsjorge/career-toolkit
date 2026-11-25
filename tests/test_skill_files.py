import pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "refresh-evidence" / "SKILL.md"
DOC = ROOT / "docs" / "refresh-evidence.md"
ALL_DOCS = [DOC, ROOT / "docs" / "tailor-offer.md", ROOT / "docs" / "study-plan.md", ROOT / "docs" / "evals.md", ROOT / "docs" / "career-coach.md"]
sys.path.insert(0, str(ROOT / "scripts"))
import nda_scrub

SENSITIVE_NAMES = {"blocklist.txt", "config.json", "evidence.md", "last_run.json",
                   "notes.md", "label-map.json"}

class SkillFileTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text()

    def test_frontmatter(self):
        m = re.match(r"---\nname: refresh-evidence\ndescription: (.+)\n---\n", self.skill)
        self.assertIsNotNone(m)
        self.assertGreater(len(m.group(1)), 40)

    def test_every_script_mentioned_exists(self):
        names = set(re.findall(r"scripts/([\w.-]+\.(?:py|css|swift))", self.skill))
        self.assertTrue({"pipeline.py", "render_pdf.py", "nda_scrub.py"} <= names)
        for n in names:
            self.assertTrue((ROOT / "scripts" / n).exists(), n)

    def test_required_sections_present(self):
        for heading in ["## Stage 1", "## Stage 2", "## Stage 3", "## Stage 4",
                        "## Stage 5", "## Stage 6", "## Stage 7", "## Judgment rules"]:
            self.assertIn(heading, self.skill)

    def test_security_steps_are_documented(self):
        for needle in ["untrusted data", "check-draft", "check-strays", "--accept-strays",
                       "evidence.md.bak", "suspect_dropped", "active in period"]:
            self.assertIn(needle, self.skill)
        self.assertLess(self.skill.index("check-draft STATE/evidence-draft.md"),
                        self.skill.index("nda_scrub.py\" --blocklist STATE/blocklist.txt STATE/evidence-draft.md"))

    def test_readme_documents_every_command_and_script(self):
        readme = "\n".join(d.read_text() for d in ALL_DOCS)
        import pipeline
        commands = re.search(r"usage: pipeline.py ([\w|-]+) STATE", pipeline.USAGE).group(1).split("|") + ["check-draft", "guard", "tags-check", "fit-status", "bullets-check", "detect-lang", "estimate-files", "gap-count", "eval-score", "eval-setup"]
        for cmd in commands:
            self.assertIn(f"`{cmd} ", readme + " ", f"README does not document `{cmd}`")
        for script in sorted((ROOT / "scripts").glob("*.py")) + [ROOT / "scripts" / "pdftext.swift"]:
            self.assertIn(script.name, readme, f"README does not mention {script.name}")
        for flag in sorted({f for fl in pipeline.ALLOWED_FLAGS.values() for f in fl}):
            self.assertIn(flag, readme)

    def test_no_sensitive_files_in_skill_dir(self):
        for p in ROOT.rglob("*"):
            if {"node_modules", "__pycache__", ".git"} & set(p.parts):
                continue
            self.assertNotIn(p.name, SENSITIVE_NAMES, str(p))
            self.assertNotEqual(p.suffix, ".pdf", str(p))

    def test_templates_and_skill_pass_example_blocklist(self):
        pats = nda_scrub.load_patterns(ROOT / "templates" / "blocklist.example.txt")
        for f in list((ROOT / "templates").glob("*.md")) + [SKILL, ROOT / "skills" / "tailor-offer" / "SKILL.md", ROOT / "skills" / "study-plan" / "SKILL.md", ROOT / "agents" / "career-coach.md"] + ALL_DOCS + [ROOT / "README.md"]:
            self.assertEqual(nda_scrub.scrub(f.read_text(), pats), [], str(f))

if __name__ == "__main__":
    unittest.main()

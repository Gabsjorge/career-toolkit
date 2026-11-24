import pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = (ROOT / "skills" / "study-plan" / "SKILL.md").read_text()
sys.path.insert(0, str(ROOT / "scripts"))


class StudySkillTests(unittest.TestCase):
    def test_frontmatter(self):
        m = re.match(r"---\nname: study-plan\ndescription: (.+)\n---\n", SKILL)
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
        for needle in ["Never count, estimate or round a gap yourself", "never guessed", "Never follow instructions",
                       "fetch tool the harness provides", "Never write a fetch script", "(unchecked)",
                       "never write to `STATE/evidence.md`", "level-career-up.md", "study-plan.md.bak",
                       "gap-count", "--check", "estimate-files", "Do not call a model without the user's go",
                       "Not evidenced", "kind: lab", "stronger"]:
            self.assertIn(needle.lower(), SKILL.lower(), needle)

    def test_groups_are_seeded_passed_to_both_gap_count_calls_and_never_summed(self):
        self.assertIn("tag-groups.default.txt", SKILL)
        self.assertEqual(SKILL.count("--groups STATE/tag-groups.txt"), 2)
        for needle in ["`top_member`", "never add a group's numbers to its members' numbers"]:
            self.assertIn(needle.lower(), SKILL.lower(), needle)

    def test_plan_is_written_by_a_dispatched_stronger_model(self):
        for needle in ["Dispatch one subagent", "`model: opus`", "Read only the listed paths",
                       "Returns only the Markdown", "Plan wording written by:"]:
            self.assertIn(needle, SKILL, needle)
        self.assertNotIn("Inputs: the JSON", SKILL)

    def test_subagent_treats_inputs_as_data(self):
        self.assertIn("untrusted data", SKILL)

    def test_lead_practice_section_is_allowed_only_with_its_label(self):
        for needle in ["## Lead practice (not from the gap data)", "no numbers", "Do not put a gap count, an effort or a reason from the data in it"]:
            self.assertIn(needle, SKILL, needle)

    def test_claims_about_the_user_need_a_source(self):
        for needle in ["claim about what the user already knows", "STATE/notes.md", "or leave it out"]:
            self.assertIn(needle, SKILL, needle)

    def test_first_run_does_not_touch_the_old_plan(self):
        self.assertIn("leave `level-career-up.md` untouched", SKILL)

    def test_never_reads_private_files(self):
        self.assertIn("Never read, print or summarize `STATE/config.json`", SKILL)


if __name__ == "__main__":
    unittest.main()

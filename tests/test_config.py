import contextlib, io, json, os, pathlib, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import config, pipeline


def write_cfg(data, make_folder=True):
    d = pathlib.Path(tempfile.mkdtemp())
    folder = d / "career"
    if make_folder:
        folder.mkdir()
    cfg = dict(data)
    if cfg.get("career_folder") == "@":
        cfg["career_folder"] = str(folder)
    p = d / "config.json"
    p.write_text(json.dumps(cfg))
    return p


def run(argv, env):
    out, err = io.StringIO(), io.StringIO()
    old = dict(os.environ)
    os.environ.clear(); os.environ.update(env)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pipeline.main(argv)
    finally:
        os.environ.clear(); os.environ.update(old)
    return code, out.getvalue() + err.getvalue()


class LoadTests(unittest.TestCase):
    def test_valid_personal_defaults(self):
        c = config.load(write_cfg({"career_folder": "@", "machine": "personal"}))
        self.assertTrue(c["refresh_enabled"])
        self.assertEqual(c["languages"], ["en", "pt"])
        self.assertEqual(c["state_dir"], str(pathlib.Path(c["career_folder"]) / "state"))

    def test_client_defaults_refresh_off(self):
        c = config.load(write_cfg({"career_folder": "@", "machine": "client"}))
        self.assertFalse(c["refresh_enabled"])

    def test_explicit_values_kept(self):
        c = config.load(write_cfg({"career_folder": "@", "machine": "client",
                                   "refresh_enabled": True, "languages": ["en"]}))
        self.assertTrue(c["refresh_enabled"])
        self.assertEqual(c["languages"], ["en"])

    def test_missing_file(self):
        with self.assertRaisesRegex(config.ConfigError, "not found"):
            config.load(pathlib.Path(tempfile.mkdtemp()) / "nope.json")

    def test_invalid_json_does_not_echo_content(self):
        p = pathlib.Path(tempfile.mkdtemp()) / "c.json"
        p.write_text("{secret-value")
        with self.assertRaises(config.ConfigError) as cm:
            config.load(p)
        self.assertNotIn("secret-value", str(cm.exception))

    def test_bad_fields_named_never_valued(self):
        cases = [
            ({"machine": "work-laptop-xyz"}, "machine"),
            ({"machine": 5}, "machine"),
            ({"refresh_enabled": "yes-secret"}, "refresh_enabled"),
            ({"languages": "en"}, "languages"),
            ({"languages": ["en", 3]}, "languages"),
            ({"languages": []}, "languages"),
            ({"career_folder": 7}, "career_folder"),
        ]
        for patch, field in cases:
            base = {"career_folder": "@", "machine": "personal"}
            base.update(patch)
            with self.assertRaises(config.ConfigError, msg=field) as cm:
                config.load(write_cfg(base))
            msg = str(cm.exception)
            self.assertIn(field, msg)
            for leaked in ("work-laptop-xyz", "yes-secret"):
                self.assertNotIn(leaked, msg)

    def test_missing_required_fields(self):
        for drop in ("career_folder", "machine"):
            base = {"career_folder": "@", "machine": "personal"}
            del base[drop]
            with self.assertRaisesRegex(config.ConfigError, drop):
                config.load(write_cfg(base))

    def test_career_folder_must_exist_and_not_leak_path(self):
        p = write_cfg({"career_folder": "@", "machine": "personal"}, make_folder=False)
        with self.assertRaises(config.ConfigError) as cm:
            config.load(p)
        self.assertIn("career_folder", str(cm.exception))
        self.assertNotIn("career", str(cm.exception).replace("career_folder", ""))

    def test_not_an_object(self):
        p = pathlib.Path(tempfile.mkdtemp()) / "c.json"
        p.write_text("[1]")
        with self.assertRaises(config.ConfigError):
            config.load(p)

    def test_path_comes_from_env_var(self):
        p = write_cfg({"career_folder": "@", "machine": "personal"})
        self.assertEqual(config.config_path({"CAREER_TOOLKIT_CONFIG": str(p)}), p)
        default = config.config_path({"HOME": "/h"})
        self.assertTrue(str(default).endswith(".config/career-toolkit/config.json"))


class CliTests(unittest.TestCase):
    def env(self, data):
        return {"CAREER_TOOLKIT_CONFIG": str(write_cfg(data))}

    def test_config_check_ok_and_problem(self):
        code, out = run(["config-check"], self.env({"career_folder": "@", "machine": "client"}))
        self.assertEqual((code, out.strip()), (0, "OK"))
        code, out = run(["config-check"], self.env({"career_folder": "@", "machine": "x"}))
        self.assertEqual(code, 1)
        self.assertIn("machine", out)

    def test_config_check_missing_file(self):
        code, out = run(["config-check"], {"CAREER_TOOLKIT_CONFIG": "/nonexistent/c.json"})
        self.assertEqual(code, 1)
        self.assertIn("not found", out)

    def test_gate_client_blocked(self):
        code, out = run(["gate", "refresh"], self.env({"career_folder": "@", "machine": "client"}))
        self.assertEqual(code, 1)
        self.assertIn("refresh_enabled", out)

    def test_gate_client_enabled(self):
        code, _ = run(["gate", "refresh"], self.env(
            {"career_folder": "@", "machine": "client", "refresh_enabled": True}))
        self.assertEqual(code, 0)

    def test_gate_personal_allowed(self):
        code, _ = run(["gate", "refresh"], self.env({"career_folder": "@", "machine": "personal"}))
        self.assertEqual(code, 0)

    def test_gate_personal_can_disable(self):
        code, _ = run(["gate", "refresh"], self.env(
            {"career_folder": "@", "machine": "personal", "refresh_enabled": False}))
        self.assertEqual(code, 1)

    def test_gate_bad_config_blocks(self):
        code, _ = run(["gate", "refresh"], {"CAREER_TOOLKIT_CONFIG": "/nonexistent/c.json"})
        self.assertEqual(code, 1)

    def test_gate_unknown_name_is_usage(self):
        code, _ = run(["gate", "tailor"], self.env({"career_folder": "@", "machine": "client"}))
        self.assertEqual(code, 64)

    def test_state_dir_command(self):
        env = self.env({"career_folder": "@", "machine": "personal"})
        code, out = run(["state-dir"], env)
        self.assertEqual(code, 0)
        self.assertTrue(out.strip().endswith("/state"))


if __name__ == "__main__":
    unittest.main()

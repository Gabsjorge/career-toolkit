import contextlib, io, os, pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import runlog


class RunLogTests(unittest.TestCase):
    def setUp(self):
        self.sd = pathlib.Path(tempfile.mkdtemp())
        self._echo, runlog.ECHO = runlog.ECHO, False

    def tearDown(self):
        runlog.ECHO = self._echo

    def test_writes_tab_separated_line_with_private_mode(self):
        runlog.event(self.sd, "repo-3", "ok", commits=12, seconds=1.25, error_class="ValueError")
        line = (self.sd / "run.log").read_text().rstrip("\n").split("\t")
        self.assertEqual(line[1:], ["repo-3", "ok", "commits=12", "error_class=ValueError", "seconds=1.2"])
        self.assertEqual(os.stat(self.sd / "run.log").st_mode & 0o777, 0o600)

    def test_rejects_free_text_paths_and_unknown_fields(self):
        for bad in ({"error_class": "something went wrong"}, {"error_class": "/Users/me/x"},
                    {"commits": True}, {"subject": "Fix login"}, {"commits": [1]}):
            with self.assertRaises(ValueError, msg=str(bad)):
                runlog.event(self.sd, "repo-1", "ok", **bad)
        for source, status in (("my secret repo", "ok"), ("repo-1", "a b"), ("/tmp/x", "ok")):
            with self.assertRaises(ValueError):
                runlog.event(self.sd, source, status)
        self.assertFalse((self.sd / "run.log").exists())

    def test_trims_to_last_lines(self):
        for i in range(runlog.MAX_LINES + 25):
            runlog.event(self.sd, "repo-1", "ok", commits=i)
        lines = (self.sd / "run.log").read_text().splitlines()
        self.assertEqual(len(lines), runlog.MAX_LINES)
        self.assertTrue(lines[-1].endswith(f"commits={runlog.MAX_LINES + 24}"))

    def test_echoes_to_stderr_when_enabled(self):
        runlog.ECHO = True
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            runlog.event(self.sd, "repo-1", "ok", commits=3)
        self.assertIn("repo-1\tok\tcommits=3", err.getvalue())


if __name__ == "__main__":
    unittest.main()

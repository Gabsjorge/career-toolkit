import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import render_pdf

NEEDS_MARKED = unittest.skipUnless(
    (pathlib.Path(render_pdf.__file__).resolve().parent / "node_modules" / "marked").exists(),
    "marked not installed (cd scripts && npm install); CI skips these")


class RenderTests(unittest.TestCase):
    @NEEDS_MARKED
    def test_markdown_with_raw_html_passthrough(self):
        p = pathlib.Path(tempfile.mkdtemp()) / "x.md"
        p.write_text('# Name\n\n<div class="entry">\n\n### Role\n\n- bullet\n\n</div>\n')
        html = render_pdf.md_to_html(p)
        self.assertIn("<h1", html)
        self.assertIn('<div class="entry">', html)
        self.assertIn("<h3", html)
        self.assertIn("<li>bullet</li>", html)

    def test_build_html_puts_csp_before_body(self):
        html = render_pdf.build_html("<h1>x</h1>", "body{}")
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("default-src 'none'", html)
        self.assertLess(html.index("Content-Security-Policy"), html.index("<h1>x</h1>"))

    def test_unsafe_markup_flags_scripts_and_handlers_only(self):
        md = '# Name\n<div class="entry">\nok\n</div>\n<script>x</script>\n<img src=x onerror=alert(1)>\n[a](javascript:x)\n'
        self.assertEqual(render_pdf.unsafe_markup(md), [5, 6, 7])
        self.assertEqual(render_pdf.unsafe_markup('<div class="entry">\n\nBuilt on-call=rota tooling\n</div>'), [])

    @NEEDS_MARKED
    def test_render_refuses_unsafe_markup_and_cleans_temp_file(self):
        from unittest import mock
        d = pathlib.Path(tempfile.mkdtemp())
        bad = d / "bad.md"; bad.write_text("<script>x</script>\n")
        with self.assertRaises(ValueError):
            render_pdf.render(bad, d / "o.pdf", d / "c.css")
        good = d / "good.md"; good.write_text("# Hi\n")
        (d / "c.css").write_text("body{}")
        seen = {}
        def fake_run(cmd, **kw):
            if cmd[0] == "node":
                return mock.Mock(returncode=0, stdout="<h1>Hi</h1>")
            seen["tmp"] = cmd[-1][len("file://"):]
            self.assertTrue(pathlib.Path(seen["tmp"]).exists())
            return mock.Mock(returncode=0, stderr="")
        with mock.patch.object(render_pdf, "CHROME", sys.executable), \
             mock.patch.object(render_pdf.subprocess, "run", side_effect=fake_run):
            render_pdf.render(good, d / "o.pdf", d / "c.css")
        self.assertFalse(pathlib.Path(seen["tmp"]).exists())

    def test_css_keeps_entries_together(self):
        css = (pathlib.Path(render_pdf.__file__).parent / "cv.css").read_text()
        self.assertIn("break-inside: avoid", css)
        self.assertIn(".entry", css)

if __name__ == "__main__":
    unittest.main()

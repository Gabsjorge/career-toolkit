import os, pathlib, re, subprocess, sys, tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
TOOLS_DIR = SCRIPTS_DIR  # marked is installed in scripts/node_modules; raw HTML passes through untouched.

# Raw HTML in the Markdown is rendered by Chrome, so lock the page down: no scripts, no network, no frames.
CSP = ("<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
       "style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'\">")
UNSAFE_MARKUP = re.compile(r"<\s*(script|iframe|object|embed)\b|<[^>]*\son\w+\s*=|javascript:", re.IGNORECASE)

_NODE_SCRIPT = (
    "const fs=require('fs');const {marked}=require('marked');"
    "process.stdout.write(marked.parse(fs.readFileSync(process.argv[1],'utf8'),"
    "{gfm:true,mangle:false,headerIds:false}));"
)


def unsafe_markup(md_text):
    """Line numbers of markup that must not reach the PDF renderer."""
    return [n for n, line in enumerate(md_text.splitlines(), 1) if UNSAFE_MARKUP.search(line)]


def md_to_html(md_path):
    r = subprocess.run(["node", "-e", _NODE_SCRIPT, str(pathlib.Path(md_path).resolve())],
                       cwd=TOOLS_DIR, check=True, capture_output=True, text=True)
    return r.stdout


def build_html(body, css):
    return f"<!doctype html><meta charset='utf-8'>{CSP}<style>{css}</style>{body}"


def render(md_path, pdf_path, css_path):
    lines = unsafe_markup(pathlib.Path(md_path).read_text())
    if lines:
        raise ValueError("unsafe markup (script/iframe/object/embed/on*=/javascript:) at line(s) "
                         + ", ".join(map(str, lines)))
    if not pathlib.Path(CHROME).exists():
        raise FileNotFoundError(f"Chrome not found at {CHROME}")
    if not (SCRIPTS_DIR / "node_modules" / "marked").exists():
        raise FileNotFoundError(f"marked is not installed: cd {SCRIPTS_DIR} && npm install")
    html = build_html(md_to_html(md_path), pathlib.Path(css_path).read_text())
    fd, tmp = tempfile.mkstemp(suffix=".html")  # mode 0600
    try:
        with os.fdopen(fd, "w") as f:
            f.write(html)
        r = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={pathlib.Path(pdf_path).resolve()}", f"file://{tmp}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("Chrome failed: " + (r.stderr or "").strip()[-300:])
    finally:
        os.unlink(tmp)


if __name__ == "__main__":
    md, pdf = sys.argv[1], sys.argv[2]
    css = sys.argv[sys.argv.index("--css") + 1] if "--css" in sys.argv \
        else str(pathlib.Path(__file__).with_name("cv.css"))
    try:
        render(md, pdf, css)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print("render failed:", e, file=sys.stderr)
        sys.exit(1)

"""Boundary guard: fail if private career data is in the repo tree.

Checks (never prints matched text, only paths and line numbers):
  - any file under applications/ other than .gitkeep
  - a state/ directory
  - file names that hold private data (blocklist.txt, config.json, evidence.md, ...)
  - PDF, .bak and .log files
  - lines that match a blocklist pattern (default: templates/blocklist.example.txt;
    pass --blocklist FILE to also check your real private blocklist, kept outside the repo)
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nda_scrub

SENSITIVE_NAMES = {"blocklist.txt", "config.json", "label-map.json", "last_run.json",
                   "evidence.md", "evidence-draft.md", "notes.md", "tags.txt", "tag-tracks.txt", "tag-groups.txt"}
SENSITIVE_SUFFIXES = {".pdf", ".bak", ".log"}
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
SKIP_SCAN_NAMES = {"package-lock.json"}


def _files(root):
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield p, rel


def check(root, blocklist=None):
    """Return a list of violation messages. Empty means clean."""
    root = pathlib.Path(root)
    skip_scan = set()
    if blocklist is None:
        default = root / "templates" / "blocklist.example.txt"
        blocklist = default if default.exists() else None
        # Tests plant example-pattern strings on purpose. A real blocklist scans them too.
        skip_scan = {"tests"}
    pats = nda_scrub.load_patterns(blocklist) if blocklist else []
    bad = nda_scrub.validate_patterns(pats)
    if bad:
        raise ValueError("blocklist entry #" + ", #".join(map(str, bad)) + " is invalid")
    out = []
    for p, rel in _files(root):
        posix = rel.as_posix()
        if p.is_dir():
            if p.name == "state":
                out.append(f"{posix}/: state directory must not be in the repo")
            continue
        if rel.parts[0] == "applications" and p.name != ".gitkeep":
            out.append(f"{posix}: files under applications/ are private (only .gitkeep is allowed)")
        if p.name in SENSITIVE_NAMES:
            out.append(f"{posix}: file name {p.name} is reserved for private data")
        if p.suffix.lower() in SENSITIVE_SUFFIXES:
            out.append(f"{posix}: {p.suffix} files must not be committed")
        if not pats or p.name in SKIP_SCAN_NAMES or rel.parts[0] in skip_scan:
            continue
        try:
            lines = p.read_text().splitlines()
        except (UnicodeDecodeError, OSError):
            continue   # binary or unreadable: name checks above still apply
        for n, line in enumerate(lines, 1):
            for idx, pat in enumerate(pats, 1):
                if re.search(pat, line, re.IGNORECASE):
                    out.append(f"{posix}:{n}: matches blocklist entry #{idx}")
    return out


def main(argv):
    usage = "usage: pipeline.py guard DIR [--blocklist FILE]"
    blocklist, pos, it = None, [], iter(argv)
    for a in it:
        if a == "--blocklist":
            blocklist = next(it, None)
            if blocklist is None:
                print(usage, file=sys.stderr)
                return 64
        elif a.startswith("--"):
            print(f"unknown flag {a}; allowed: --blocklist", file=sys.stderr)
            return 64
        else:
            pos.append(a)
    if len(pos) != 1:
        print(usage, file=sys.stderr)
        return 64
    try:
        violations = check(pos[0], blocklist)
    except (ValueError, OSError) as e:
        print(f"FAIL: {e}")
        return 1
    for v in violations:
        print(v)
    print("FAIL" if violations else "OK")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

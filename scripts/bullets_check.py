"""List CV bullets that do not trace to Evidence. Prints line numbers and reasons, never text.

Every bullet ends with <!-- ev:E0001 --> (several IDs allowed: <!-- ev:E0001, E0002 -->) or
<!-- ev:user --> once the user has approved a bullet that has no Evidence ID.
A bullet that cites a Personal lab ID must say "personal lab".
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import evidence

BULLET = re.compile(r"^\s*[-*+]\s+")
MARKER = re.compile(r"<!--\s*ev:\s*([^>]*?)\s*-->")
ID = re.compile(r"E\d{4,}\Z")


def check(cv_text, items):
    problems, bullets, user = [], 0, 0
    for n, line in enumerate(cv_text.splitlines(), 1):
        if not BULLET.match(line):
            continue
        bullets += 1
        m = MARKER.search(line)
        if not m:
            problems.append((n, "no evidence id"))
            continue
        tokens = [t for t in re.split(r"[\s,]+", m.group(1)) if t]
        if not tokens or any(not (ID.match(t) or t == "user") for t in tokens):
            problems.append((n, "bad ev marker"))
            continue
        ids = [t for t in tokens if t != "user"]
        if any(t not in items for t in ids):
            problems.append((n, "unknown evidence id"))
            continue
        if "user" in tokens:
            user += 1
        if any(items[t]["lab"] for t in ids) and "personal lab" not in line.lower():
            problems.append((n, "lab not labeled personal lab"))
    return {"problems": problems, "bullets": bullets, "user_approved": user}


def main(argv):
    if len(argv) != 2:
        print("usage: pipeline.py bullets-check CV_FILE EVIDENCE_FILE", file=sys.stderr)
        return 64
    try:
        text = pathlib.Path(argv[0]).read_text()
        items = evidence.load(argv[1])
    except OSError:
        print("cannot read the CV or the evidence file")
        return 1
    r = check(text, items)
    name = pathlib.Path(argv[0]).name
    for n, why in r["problems"]:
        print(f"{name}:{n}: {why}")
    print(f"bullets={r['bullets']} problems={len(r['problems'])} user_approved={r['user_approved']}")
    print("FAIL" if r["problems"] else "OK")
    return 1 if r["problems"] else 0

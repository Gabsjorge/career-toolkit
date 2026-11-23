"""List CV bullets that do not trace to Evidence. Prints line numbers and reasons, never text.

Every bullet ends with <!-- ev:E0001 --> (several IDs allowed: <!-- ev:E0001, E0002 -->) or
<!-- ev:user --> once the user has approved a bullet that has no Evidence ID.
A bullet that cites a Personal lab ID must say "personal lab".
A number in a bullet must appear in a cited item, and a claim word (templates/claim-words.txt)
must too, unless the bullet is marked ev:user.
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import evidence

BULLET = re.compile(r"^\s*[-*+]\s+")
MARKER = re.compile(r"<!--\s*ev:\s*([^>]*?)\s*-->")
ID = re.compile(r"E\d{4,}\Z")
NUMBER = re.compile(r"(?<![\w])\d[\d,]*(?:\.\d+)?")
CLAIM_WORDS = pathlib.Path(__file__).resolve().parent.parent / "templates" / "claim-words.txt"


def numbers(text):
    return {n.rstrip(",").replace(",", "") for n in NUMBER.findall(text)}


def load_claim_words(path=CLAIM_WORDS):
    try:
        lines = pathlib.Path(path).read_text().splitlines()
    except OSError:
        return []
    return [w.strip().lower() for w in lines if w.strip() and not w.startswith("#")]


def has_word(word, text):
    return re.search(r"(?<![\w])" + re.escape(word) + r"(?![\w])", text, re.I) is not None


def unsupported(line, ids, items, claim_words):
    """Reasons a bullet claims more than its cited items say. Never returns the claim itself."""
    line = MARKER.sub("", line)
    cited = " ".join(items[t]["text"] for t in ids)
    have = numbers(cited)
    out = []
    if numbers(line) - have:
        out.append("number not in cited evidence")
    if any(has_word(w, line) and not has_word(w, cited) for w in claim_words):
        out.append("claim word not in cited evidence")
    return out


def check(cv_text, items, claim_words=()):
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
        if "user" not in tokens:
            problems += [(n, why) for why in unsupported(line, ids, items, claim_words)]
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
    r = check(text, items, load_claim_words())
    name = pathlib.Path(argv[0]).name
    for n, why in r["problems"]:
        print(f"{name}:{n}: {why}")
    print(f"bullets={r['bullets']} problems={len(r['problems'])} user_approved={r['user_approved']}")
    print("FAIL" if r["problems"] else "OK")
    return 1 if r["problems"] else 0

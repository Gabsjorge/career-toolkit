import pathlib, re, sys


def load_patterns(path):
    lines = pathlib.Path(path).read_text().splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def validate_patterns(patterns):
    """1-based numbers of entries that do not compile or match the empty string (never the text)."""
    bad = []
    for n, p in enumerate(patterns, 1):
        try:
            if re.search(p, "", re.IGNORECASE):
                bad.append(n)
        except re.error:
            bad.append(n)
    return bad


def scrub(text, patterns):
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]


def main(argv):
    blocklist = "state/blocklist.txt"
    files = []
    it = iter(argv)
    for a in it:
        if a == "--blocklist":
            try:
                blocklist = next(it)
            except StopIteration:
                print("usage: nda_scrub.py [--blocklist FILE] FILE...", file=sys.stderr)
                return 64
        else:
            files.append(a)
    if not pathlib.Path(blocklist).exists():
        print("FAIL: blocklist not found")
        return 1
    pats = load_patterns(blocklist)
    if not pats:
        print("FAIL: blocklist has no patterns")
        return 1
    bad_entries = validate_patterns(pats)
    if bad_entries:
        for n in bad_entries:
            print(f"FAIL: blocklist entry #{n} is invalid (does not compile or matches everything)")
        return 1
    if not files:
        print("FAIL: no files given")
        return 1
    bad = False
    for f in files:
        for n, line in enumerate(pathlib.Path(f).read_text().splitlines(), 1):
            for idx, p in enumerate(pats, 1):
                if re.search(p, line, re.IGNORECASE):
                    print(f"{f}:{n}: matches blocklist entry #{idx}")
                    bad = True
    print("FAIL" if bad else "OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

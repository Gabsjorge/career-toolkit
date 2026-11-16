import pathlib, re, sys

# period is YYYY-MM per the Stage 4 prompt, but models also emit YYYY or YYYY-YYYY; accept those
ITEM = re.compile(r"^- \*\*\[(high|med|low)\] \d{4}(?:-\d{2}|-\d{4})?\*\* — .+ _\(tech: .*?\)_")
FORBIDDEN = [("url", re.compile(r"https?://|www\.", re.IGNORECASE)),
             ("path", re.compile(r"~/|/Users/|/home/|\b[A-Za-z]:\\")),
             ("code", re.compile(r"`|\$\(|\|\s*(ba)?sh\b"))]
MAX_LINE = 900


def check_lines(lines):
    """(line number, reason) for every line that is not a well-formed evidence item; never the text."""
    problems = []
    for n, line in enumerate(lines, 1):
        if not line.strip() or line.startswith("#"):
            continue
        if len(line) > MAX_LINE:
            problems.append((n, "too long"))
        for reason, pat in FORBIDDEN:
            if pat.search(line):
                problems.append((n, reason))
        if not ITEM.match(line):
            problems.append((n, "not an evidence item"))
    return problems


def main(argv):
    if not argv:
        print("usage: pipeline.py check-draft FILE", file=sys.stderr)
        return 64
    bad = False
    for f in argv:
        for n, reason in check_lines(pathlib.Path(f).read_text().splitlines()):
            print(f"{f}:{n}: {reason}")
            bad = True
    print("FAIL" if bad else "OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

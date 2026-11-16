import pathlib, re, sys

# period is YYYY-MM per the Stage 4 prompt, but models also emit YYYY or YYYY-YYYY; accept those
# Old format: "- **[high] 2026-09** — ..."; new format adds an ID: "- **E0001** **[high] ..."
ITEM = re.compile(r"^- (?:\*\*E\d{4,}\*\* )?\*\*\[(high|med|low)\] \d{4}(?:-\d{2}|-\d{4})?\*\* — .+ _\(tech: .*?\)_")
ID_FIELD = re.compile(r"^- \*\*([A-Za-z]\w*)\*\* \*\*\[")
GOOD_ID = re.compile(r"E\d{4,}\Z")
TAGS = re.compile(r"_\(tags: (.*?)\)_")
KIND = re.compile(r"_\(kind: (.*?)\)_")
TAG = re.compile(r"[a-z0-9][a-z0-9.+#-]*\Z")
LABS_HEADING = "personal labs"
FORBIDDEN = [("url", re.compile(r"https?://|www\.", re.IGNORECASE)),
             ("path", re.compile(r"~/|/Users/|/home/|\b[A-Za-z]:\\")),
             ("code", re.compile(r"`|\$\(|\|\s*(ba)?sh\b"))]
MAX_LINE = 900


def check_lines(lines):
    """(line number, reason) for every line that is not a well-formed evidence item; never the text."""
    problems = []
    seen_ids = set()
    in_labs = False
    for n, line in enumerate(lines, 1):
        if line.startswith("#"):
            in_labs = line.lstrip("#").strip().lower() == LABS_HEADING
            continue
        if not line.strip():
            continue
        if len(line) > MAX_LINE:
            problems.append((n, "too long"))
        for reason, pat in FORBIDDEN:
            if pat.search(line):
                problems.append((n, reason))
        if not ITEM.match(line):
            problems.append((n, "not an evidence item"))
            if ID_FIELD.match(line):
                problems.append((n, "malformed id"))
            continue
        m = ID_FIELD.match(line)
        if m:
            eid = m.group(1)
            if not GOOD_ID.match(eid):
                problems.append((n, "malformed id"))
            elif eid in seen_ids:
                problems.append((n, "duplicate id"))
            seen_ids.add(eid)
        for tm in TAGS.finditer(line):
            tags = tm.group(1).split(", ")
            if not all(TAG.match(t) for t in tags):
                problems.append((n, "bad tag"))
        kinds = [k.group(1) for k in KIND.finditer(line)]
        if any(k != "lab" for k in kinds):
            problems.append((n, "bad kind"))
        is_lab = "lab" in kinds
        if is_lab and not in_labs:
            problems.append((n, "lab outside personal labs"))
        elif in_labs and not is_lab:
            problems.append((n, "normal item in personal labs"))
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

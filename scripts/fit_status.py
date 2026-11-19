"""Derive Status and Evidence IDs of a Fit table from evidence.md. The model never sets Status.

Yes     at least one Evidence ID (real work) whose tags include the row's tag
Partial no real-work ID, but a Personal lab ID for the tag, or an ID for a related tag
No      no ID at all
Not evidenced  the tag is a non-skill tag (templates/non-skill-tags.txt: seniority, language level, remote...)
        and no ID carries it. Evidence cannot show it, so it is not a skill gap and not counted as No.
A row that mixes things Evidence shows with things it does not (for example "Docker, Kafka") can carry a ruling by the
user in its Notes cell: `[user-status: Partial]`. The ruling replaces the derived Status; Evidence IDs stay derived.
Only the user writes it, never the model.
A Personal lab never makes a row Yes. Evidence items without an ID cannot be cited.
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import evidence, tags as taglib

DEFAULT_RELATIONS = pathlib.Path(__file__).resolve().parent.parent / "templates" / "tag-relations.txt"
DEFAULT_NON_SKILL = pathlib.Path(__file__).resolve().parent.parent / "templates" / "non-skill-tags.txt"
NOT_EVIDENCED = "Not evidenced"
SPLIT = re.compile(r"(?<!\\)\|")
USER_STATUS = re.compile(r"\[user-status: (Yes|Partial|No|Not evidenced)\]")
DASH = "—"


def load_relations(path):
    rel = {}
    for raw in pathlib.Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "~" not in line:
            continue
        a, b = (x.strip() for x in line.split("~", 1))
        rel.setdefault(a, set()).add(b)
        rel.setdefault(b, set()).add(a)
    return rel


def load_non_skill(path):
    return {l.strip().lower() for l in pathlib.Path(path).read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")}


def derive(tag, items, relations, non_skill=frozenset()):
    direct = sorted(i for i, v in items.items() if tag in v["tags"])
    real = [i for i in direct if not items[i]["lab"]]
    if real:
        return "Yes", real
    related = set(relations.get(tag, ()))
    ids = sorted(i for i, v in items.items() if i in direct or (v["tags"] & related))
    if ids:
        return "Partial", ids
    return (NOT_EVIDENCED, []) if tag in non_skill else ("No", [])


def _cells(line):
    return [c.strip() for c in SPLIT.split(line.strip())[1:-1]]


def _line(cells):
    return "| " + " | ".join(cells) + " |"


def process(fit_path, evidence_path, tags_path, relations_path=None, check=False, non_skill_path=None):
    fit = pathlib.Path(fit_path)
    items = evidence.load(evidence_path)
    tags, aliases = taglib.load(tags_path)
    relations = load_relations(relations_path or DEFAULT_RELATIONS)
    non_skill = load_non_skill(non_skill_path or DEFAULT_NON_SKILL)
    lines = fit.read_text().split("\n")
    head = next((i for i, l in enumerate(lines) if l.startswith("|") and "Requirement" in l), None)
    if head is None:
        raise ValueError("Fit table header (with Requirement) not found")
    cols = _cells(lines[head])
    for need in ("Tag", "Status", "Evidence IDs"):
        if need not in cols:
            raise ValueError(f"Fit table has no '{need}' column")
    ti, si, ei = cols.index("Tag"), cols.index("Status"), cols.index("Evidence IDs")
    ni = cols.index("Notes") if "Notes" in cols else None
    res = {"counts": {"Yes": 0, "Partial": 0, "No": 0, NOT_EVIDENCED: 0}, "untagged": [], "unknown_tags": [], "mismatch": [], "overridden": []}
    n = 0
    i = head + 2
    while i < len(lines) and lines[i].startswith("|"):
        cells = _cells(lines[i])
        n += 1
        if len(cells) == len(cols):
            raw_tag = cells[ti].strip().lower()
            if not raw_tag or raw_tag == DASH:
                res["untagged"].append(n)
                status, ids = DASH, []
            else:
                canon = taglib.resolve(raw_tag, tags, aliases)
                if canon is None:
                    res["unknown_tags"].append(n)
                status, ids = derive(canon or raw_tag, items, relations, non_skill)
                ruling = USER_STATUS.search(cells[ni]) if ni is not None else None
                if ruling:
                    status = ruling.group(1)
                    res["overridden"].append(n)
                res["counts"][status] += 1
            want = (status, ", ".join(ids) if ids else DASH)
            if (cells[si], cells[ei]) != want:
                res["mismatch"].append(n)
            cells[si], cells[ei] = want
            lines[i] = _line(cells)
        i += 1
    if not check:
        fit.write_text("\n".join(lines))
    return res


def main(argv):
    rel, check, pos, k = None, False, [], 0
    while k < len(argv):
        if argv[k] == "--relations" and k + 1 < len(argv):
            rel, k = argv[k + 1], k + 2
        elif argv[k] == "--check":
            check, k = True, k + 1
        else:
            pos.append(argv[k])
            k += 1
    if len(pos) != 3:
        print("usage: pipeline.py fit-status FIT_TABLE EVIDENCE_FILE TAGS_FILE [--relations FILE] [--check]",
              file=sys.stderr)
        return 64
    try:
        r = process(pos[0], pos[1], pos[2], rel, check)
    except (OSError, ValueError) as e:
        print(e)
        return 1
    c = r["counts"]
    print(f"yes={c['Yes']} partial={c['Partial']} no={c['No']} not_evidenced={c[NOT_EVIDENCED]}")
    bad = False
    if r["untagged"]:
        print("untagged rows:", ", ".join(map(str, r["untagged"])))
        bad = True
    if r["unknown_tags"]:
        print("unknown tag rows:", ", ".join(map(str, r["unknown_tags"])))
        bad = True
    if check and r["mismatch"]:
        print("Status or Evidence IDs differ from the derived values in rows:", ", ".join(map(str, r["mismatch"])))
        bad = True
    if r["overridden"]:
        print(f"overridden={len(r['overridden'])} (user-status rulings in rows: {', '.join(map(str, r['overridden']))})")
    print("FAIL" if bad else "OK")
    return 1 if bad else 0

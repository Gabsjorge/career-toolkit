"""Count skill gaps across Fit tables, per track, as JSON. No model, read-only.

A gap is a Fit row whose Status is Partial or No. Yes, Not evidenced and untagged rows are not gaps.
Weight: Must counts 2; Nice and an unknown Must/Nice ("—", as in backfilled old tables) count 1.
A tag maps to a track and a type through a user-editable file (templates/tag-tracks.default.txt):
    tag = backend|lead|backend+lead, tech|skill|language
A tag with no line is reported under unmapped_tags and never guessed. A table that cannot be read whole
(no header, a row with the wrong cell count, an unknown Status) is skipped and named.
"""
import json, pathlib, re, sys

SPLIT = re.compile(r"(?<!\\)\|")
TRACKS = ("backend", "lead")
TYPES = ("tech", "skill", "language")
STATUSES = {"yes", "partial", "no", "not evidenced", "—", ""}
GAP = {"partial", "no"}


def load_tracks(path):
    """tag -> (tracks list, type). Errors name the line number, never the value."""
    out = {}
    for n, raw in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line or "," not in line.split("=", 1)[1]:
            raise ValueError(f"tag map line {n}: expected 'tag = track, type'")
        tag, rest = (x.strip() for x in line.split("=", 1))
        track, typ = (x.strip() for x in rest.split(",", 1))
        tracks = track.split("+")
        if not tag or any(t not in TRACKS for t in tracks) or len(set(tracks)) != len(tracks):
            raise ValueError(f"tag map line {n}: track must be backend, lead or backend+lead")
        if typ not in TYPES:
            raise ValueError(f"tag map line {n}: type must be tech, skill or language")
        if tag in out:
            raise ValueError(f"tag map line {n}: tag listed twice")
        out[tag] = (tracks, typ)
    return out


def _cells(line):
    return [c.strip() for c in SPLIT.split(line.strip())[1:-1]]


def read_table(path):
    """List of (tag, must, status) rows, or None when the table is not readable whole."""
    lines = pathlib.Path(path).read_text().split("\n")
    head = next((i for i, l in enumerate(lines) if l.startswith("|") and "Requirement" in l), None)
    if head is None:
        return None
    cols = _cells(lines[head])
    if not all(c in cols for c in ("Tag", "Must/Nice", "Status")):
        return None
    ti, mi, si = cols.index("Tag"), cols.index("Must/Nice"), cols.index("Status")
    rows, i = [], head + 2
    while i < len(lines) and lines[i].startswith("|"):
        cells = _cells(lines[i])
        if len(cells) != len(cols) or cells[si].lower() not in STATUSES:
            return None
        rows.append((cells[ti].strip().lower(), cells[mi].strip().lower(), cells[si].strip().lower()))
        i += 1
    return rows


def count(apps_dir, tracks_path):
    tmap = load_tracks(tracks_path)
    apps = pathlib.Path(apps_dir)
    if not apps.is_dir():
        raise ValueError("applications folder not found")
    res = {"tables_read": 0, "tables_skipped": [], "rows": 0, "untagged_rows": 0, "unmapped_tags": {}, "tracks": {t: [] for t in TRACKS}}
    acc = {}
    for d in sorted(p for p in apps.iterdir() if p.is_dir()):
        f = d / "fit-table.md"
        if not f.is_file():
            continue
        rows = read_table(f)
        if rows is None:
            res["tables_skipped"].append(d.name)
            continue
        res["tables_read"] += 1
        for tag, must, status in rows:
            res["rows"] += 1
            if not tag or tag == "—":
                res["untagged_rows"] += 1
                continue
            if status not in GAP:
                continue
            if tag not in tmap:
                res["unmapped_tags"][tag] = res["unmapped_tags"].get(tag, 0) + 1
                continue
            tracks, typ = tmap[tag]
            for t in tracks:
                e = acc.setdefault((t, tag), {"tag": tag, "type": typ, "gaps": 0, "no": 0, "partial": 0, "must_weighted": 0, "_tables": set()})
                e["gaps"] += 1
                e[status] += 1
                e["must_weighted"] += 2 if must == "must" else 1
                e["_tables"].add(d.name)
    for (t, _), e in acc.items():
        e["tables"] = len(e.pop("_tables"))
        res["tracks"][t].append(e)
    for t in TRACKS:
        res["tracks"][t].sort(key=lambda e: (-e["must_weighted"], -e["gaps"], e["tag"]))
    return res


PLAN_ROW = re.compile(r"^\|\s*(backend|lead)\s*\|\s*([a-z0-9][a-z0-9.+#-]*)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*$")


def check_plan(res, plan_text):
    """Compare the number rows of a generated plan (| track | tag | gaps | weighted | offers |) with the counted JSON.
    Returns the list of 'track/tag' whose numbers differ or that are not in the JSON."""
    seen, bad = 0, []
    for line in plan_text.splitlines():
        m = PLAN_ROW.match(line)
        if not m:
            continue
        seen += 1
        track, tag, gaps, weighted, offers = m.group(1), m.group(2), *(int(x) for x in m.groups()[2:])
        e = next((e for e in res["tracks"][track] if e["tag"] == tag), None)
        if e is None or (e["gaps"], e["must_weighted"], e["tables"]) != (gaps, weighted, offers):
            bad.append(f"{track}/{tag}")
    return bad if seen else ["no gap rows found"]


def main(argv):
    plan, pos, k = None, [], 0
    while k < len(argv):
        if argv[k] == "--check" and k + 1 < len(argv):
            plan, k = argv[k + 1], k + 2
        else:
            pos.append(argv[k])
            k += 1
    if len(pos) != 2:
        print("usage: pipeline.py gap-count APPLICATIONS_DIR TAG_TRACKS_FILE [--check PLAN_FILE]", file=sys.stderr)
        return 64
    try:
        r = count(pos[0], pos[1])
        bad = check_plan(r, pathlib.Path(plan).read_text()) if plan else None
    except (OSError, ValueError) as e:
        print(e)
        return 1
    if plan is None:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    if bad:
        print("plan numbers differ from gap-count for:", ", ".join(bad))
        return 1
    print("OK")
    return 0

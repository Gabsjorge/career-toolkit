"""One-time backfill of the old Fit tables (columns Requirement, Do I have it?, Notes, Study recommendations).

No model call here. The skill's cheap model proposes ONE tag per requirement from a pending file; this script
validates the proposals against the tag list, rewrites each old table to the new columns
(Requirement | Tag | Must/Nice | Status | Evidence IDs | Notes | Study recommendations) and lets fit_status derive
Status and Evidence IDs. Must/Nice stays "—" because the old tables never recorded it.

Dry run by default: nothing is written except the optional --pending and --report files. With --apply every
converted table is backed up first (mode 600, an older backup is never overwritten). Tables that already have a
Tag column are skipped, so a second run changes nothing. A table with a malformed row is skipped whole and listed.
Row keys are "<folder name>:<row number>".
"""
import json, os, pathlib, shutil, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import assign_ids, fit_status, tags as taglib

NEW_COLS = ["Requirement", "Tag", "Must/Nice", "Status", "Evidence IDs", "Notes", "Study recommendations"]
DASH = fit_status.DASH
OLD_STATUS = {"yes": "Yes", "sim": "Yes", "partial": "Partial", "parcial": "Partial",
              "no": "No", "não": "No", "nao": "No"}


def _write_private(path, text):
    p = pathlib.Path(path)
    if p.exists():
        p.unlink()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def _parse(path):
    """None if the table already has a Tag column or has no table. Else {'lines','head','rows'} or {'bad': True}."""
    lines = path.read_text().split("\n")
    head = next((i for i, l in enumerate(lines) if l.startswith("|") and ("Requirement" in l or "Requisito" in l
                                                                         or "Tech / skill" in l)), None)
    if head is None:
        return {"bad": True}
    cols = fit_status._cells(lines[head])
    if "Tag" in cols:
        return None
    if len(cols) != 4 or head + 1 >= len(lines) or not lines[head + 1].startswith("|"):
        return {"bad": True}
    rows, i = [], head + 2
    while i < len(lines) and lines[i].startswith("|"):
        cells = fit_status._cells(lines[i])
        if len(cells) != 4:
            return {"bad": True}
        rows.append(cells)
        i += 1
    return {"lines": lines, "head": head, "rows": rows, "end": i}


def _convert(parsed, tags_for_rows):
    lines, head, end = parsed["lines"], parsed["head"], parsed["end"]
    out = lines[:head] + [fit_status._line(NEW_COLS), "|" + "---|" * len(NEW_COLS)]
    for (req, _old, notes, study), tag in zip(parsed["rows"], tags_for_rows):
        out.append(fit_status._line([req, tag or DASH, DASH, "", "", notes, study]))
    return "\n".join(out + lines[end:])


def run(apps_dir, evidence, tags_file, proposals=None, apply=False, report=None, pending=None, today=None):
    import datetime
    apps = pathlib.Path(apps_dir)
    if apply and proposals is None:
        raise ValueError("--apply needs --proposals")
    tags, aliases = taglib.load(tags_file)
    props = json.loads(pathlib.Path(proposals).read_text()) if proposals else {}
    if not isinstance(props, dict):
        raise ValueError("proposals must be a JSON object")
    res = {"tables": 0, "skipped": [], "rows": 0, "tagged": 0, "untagged": 0, "unknown_tags": [],
           "same": 0, "differ": 0, "applied": False}
    pend, diffs, untagged_rows, work = {}, [], [], []
    for d in sorted(p for p in apps.iterdir() if (p / "fit-table.md").is_file()):
        path = d / "fit-table.md"
        parsed = _parse(path)
        if parsed is None:
            continue
        if parsed.get("bad"):
            res["skipped"].append(d.name)
            continue
        res["tables"] += 1
        chosen = []
        for n, (req, _o, _n, _s) in enumerate(parsed["rows"], 1):
            key = f"{d.name}:{n}"
            pend[key] = req
            res["rows"] += 1
            raw = props.get(key)
            canon = taglib.resolve(raw, tags, aliases) if isinstance(raw, str) and raw.strip() else None
            if isinstance(raw, str) and raw.strip() and canon is None and raw.strip().lower() not in res["unknown_tags"]:
                res["unknown_tags"].append(raw.strip().lower())
            if canon:
                res["tagged"] += 1
            else:
                res["untagged"] += 1
                untagged_rows.append((key, req))
            chosen.append(canon)
        work.append((path, parsed, chosen, d.name))
    res["unknown_tags"].sort()
    if pending:
        _write_private(pending, json.dumps(pend, ensure_ascii=False, indent=1) + "\n")
    if proposals:
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            for path, parsed, chosen, slug in work:
                t = tmp / "fit-table.md"
                t.write_text(_convert(parsed, chosen))
                fit_status.process(t, evidence, tags_file)
                final = t.read_text()
                new_rows = [fit_status._cells(l) for l in final.split("\n")[parsed["head"] + 2:parsed["end"]]]
                for n, (old, new) in enumerate(zip(parsed["rows"], new_rows), 1):
                    if new[1] == DASH:
                        continue
                    raw_old = old[1].strip()
                    norm = OLD_STATUS.get(raw_old.lower().strip("*"))
                    if norm == new[3]:
                        res["same"] += 1
                    else:
                        res["differ"] += 1
                        diffs.append((f"{slug}:{n}", raw_old, new[3], old[0]))
                if apply:
                    assign_ids._backup(path, today or datetime.date.today().isoformat())
                    path.write_text(final)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        res["applied"] = bool(apply)
        if report:
            out = ["# Rows where the old status differs from the derived one", ""]
            out += [f"{k}  {o} -> {n}  | {r}" for k, o, n, r in diffs]
            out += ["", "# Rows left without a tag (rule by hand)", ""]
            out += [f"{k}  | {r}" for k, r in untagged_rows]
            _write_private(report, "\n".join(out) + "\n")
    return res


USAGE = ("usage: pipeline.py backfill-fit APPLICATIONS_DIR EVIDENCE TAGS "
         "[--pending OUT] [--proposals FILE] [--report OUT] [--apply]")


def main(argv):
    pos, opts, apply_, i = [], {}, False, 0
    while i < len(argv):
        a = argv[i]
        if a in ("--pending", "--proposals", "--report") and i + 1 < len(argv):
            opts[a[2:]] = argv[i + 1]
            i += 2
        elif a == "--apply":
            apply_, i = True, i + 1
        else:
            pos.append(a)
            i += 1
    if len(pos) != 3:
        print(USAGE, file=sys.stderr)
        return 64
    try:
        r = run(pos[0], pos[1], pos[2], proposals=opts.get("proposals"), apply=apply_,
                report=opts.get("report"), pending=opts.get("pending"))
    except (OSError, ValueError):
        print("cannot read the applications folder, evidence, tag list or proposals file (proposals must be a JSON object)")
        return 1
    print(f"tables={r['tables']} skipped={len(r['skipped'])} rows={r['rows']} tagged={r['tagged']} "
          f"untagged={r['untagged']} unknown_tags={len(r['unknown_tags'])} same={r['same']} differ={r['differ']} "
          f"applied={str(r['applied']).lower()}")
    if r["skipped"]:
        print("skipped (malformed rows, rule by hand):", ", ".join(r["skipped"]))
    if r["unknown_tags"]:
        print("unknown tags (approve or replace):", ", ".join(r["unknown_tags"]))
    return 0

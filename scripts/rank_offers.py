"""Rank Offers by derived Fit against Evidence. No model, no network. The model never sets Status or a score.

Input JSON: {"offers": [{"slug", "title", "company", "url" (string or null), "requirements": [{"requirement", "tag", "priority"}]}]}
Status per row comes from fit_status.derive. Score = weighted credit over rows whose Status is not "Not evidenced":
weight Must 2, Nice 1; credit Yes 1, Partial 0.5, No 0. A row with an unknown tag stops the run (exit 1) so the user can rule on it.
An Offer scored from fewer than MIN_ROWS rows is "thin" and sorts after the others. company may be missing.
Offers with the same URL, or the same company and title, count once (the first one stays).
"""
import json, math, os, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import evidence, fit_status, tags as taglib

SLUG = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
WEIGHT = {"must": 2, "nice": 1}
CREDIT = {"Yes": 1.0, "Partial": 0.5, "No": 0.0}
MIN_ROWS = 4   # an Offer scored from fewer rows is "thin": its score is a weak signal and it sorts after the others
STATUSES = ("Yes", "Partial", "No", "Not evidenced")


def _norm(s):
    return " ".join(s.lower().split())


def _validate(data):
    """Raise ValueError naming the bad field, never its value."""
    if not isinstance(data, dict) or not isinstance(data.get("offers"), list):
        raise ValueError("field 'offers' must be a list")
    seen = set()
    for n, o in enumerate(data["offers"], 1):
        if not isinstance(o, dict):
            raise ValueError(f"offer {n}: not an object")
        for f in ("slug", "title"):
            if not (isinstance(o.get(f), str) and o[f].strip()):
                raise ValueError(f"offer {n}: field '{f}' must be a non-empty string")
        if not SLUG.match(o["slug"]):
            raise ValueError(f"offer {n}: field 'slug' must use a-z, 0-9 and -")
        if o["slug"] in seen:
            raise ValueError(f"offer {n}: field 'slug' is repeated")
        seen.add(o["slug"])
        if o.get("company") is not None and not (isinstance(o["company"], str) and o["company"].strip()):
            raise ValueError(f"offer {n}: field 'company' must be a non-empty string or null")
        if o.get("url") is not None and not isinstance(o["url"], str):
            raise ValueError(f"offer {n}: field 'url' must be a string or null")
        if not isinstance(o.get("requirements"), list):
            raise ValueError(f"offer {n}: field 'requirements' must be a list")
        for m, r in enumerate(o["requirements"], 1):
            if not isinstance(r, dict):
                raise ValueError(f"offer {n}, requirement {m}: not an object")
            if not (isinstance(r.get("requirement"), str) and r["requirement"].strip()):
                raise ValueError(f"offer {n}, requirement {m}: field 'requirement' missing")
            if r.get("priority") not in taglib.PRIORITIES:
                raise ValueError(f"offer {n}, requirement {m}: field 'priority' must be must or nice")
            if not (isinstance(r.get("tag"), str) and taglib.TAG.match(r["tag"])):
                raise ValueError(f"offer {n}, requirement {m}: field 'tag' must be lowercase, no spaces")


def _percent(x):
    return int(math.floor(x * 100 + 0.5))


def rank(offers_path, evidence_path, tags_path, relations_path=None, non_skill_path=None):
    data = json.loads(pathlib.Path(offers_path).read_text())
    _validate(data)
    items = evidence.load(evidence_path)
    tags, aliases = taglib.load(tags_path)
    relations = fit_status.load_relations(relations_path or fit_status.DEFAULT_RELATIONS)
    non_skill = fit_status.load_non_skill(non_skill_path or fit_status.DEFAULT_NON_SKILL)
    urls, names, kept, duplicates, unknown = set(), set(), [], [], {}
    for o in data["offers"]:
        name = (_norm(o["company"]), _norm(o["title"])) if o.get("company") else None
        url = o.get("url").strip() if o.get("url") else None
        if (url and url in urls) or (name and name in names):
            duplicates.append(o["slug"])
            continue
        if url:
            urls.add(url)
        if name:
            names.add(name)
        kept.append(o)
    ranked = []
    for o in kept:
        counts = dict.fromkeys(STATUSES, 0)
        got = den = 0.0
        rows = 0
        no_gap = partial_gap = None
        for r in o["requirements"]:
            canon = taglib.resolve(r["tag"], tags, aliases)
            if canon is None:
                bad = unknown.setdefault(o["slug"], [])
                if r["tag"] not in bad:
                    bad.append(r["tag"])
                continue
            status, _ids = fit_status.derive(canon, items, relations, non_skill)
            counts[status] += 1
            if status == fit_status.NOT_EVIDENCED:
                continue
            rows += 1
            w = WEIGHT[r["priority"]]
            den += w
            got += w * CREDIT[status]
            if r["priority"] == "must":
                if status == "No" and no_gap is None:
                    no_gap = canon
                elif status == "Partial" and partial_gap is None:
                    partial_gap = canon
        ranked.append({"slug": o["slug"], "title": o["title"], "company": o.get("company"), "url": o.get("url"),
                       "score": _percent(got / den) if den else None, "counts": counts,
                       "rows": rows, "thin": rows < MIN_ROWS,
                       "gap": no_gap or partial_gap})
    ranked.sort(key=lambda x: (x["thin"], x["score"] is None, -(x["score"] or 0)))   # stable: ties keep input order
    return {"ranked": ranked, "duplicates": duplicates, "unknown": unknown}


def _cell(s):
    return " ".join(str(s).split()).replace("|", "\\|")


def render(res):
    lines = ["| Rank | Offer | Title | Company | Score | Rows | Yes | Partial | No | Not evidenced | Biggest Must gap | URL |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, o in enumerate(res["ranked"], 1):
        c = o["counts"]
        score = f"{o['score']}%" if o["score"] is not None else "—"
        if o["thin"]:
            score += " (thin)"
        lines.append("| " + " | ".join(_cell(x) for x in (
            n, o["slug"], o["title"], o["company"] or "—", score, o["rows"], c["Yes"], c["Partial"], c["No"], c["Not evidenced"],
            o["gap"] or "—", o["url"] or "—")) + " |")
    lines += ["", f"{len(res['ranked'])} Offers ranked, {len(res['duplicates'])} duplicates dropped"
              + (f" ({', '.join(res['duplicates'])})" if res["duplicates"] else "") + "."]
    return "\n".join(lines) + "\n"


def main(argv):
    out_path, as_json, pos, k = None, False, [], 0
    while k < len(argv):
        if argv[k] == "--out" and k + 1 < len(argv):
            out_path, k = argv[k + 1], k + 2
        elif argv[k] == "--json":
            as_json, k = True, k + 1
        else:
            pos.append(argv[k])
            k += 1
    if len(pos) != 3:
        print("usage: pipeline.py rank-offers OFFERS_JSON EVIDENCE TAGS [--out FILE] [--json]", file=sys.stderr)
        return 64
    try:
        res = rank(*pos)
    except OSError:
        print("cannot read the offers file, the Evidence or the tag list")
        return 1
    except ValueError as e:   # includes json.JSONDecodeError; messages name a field, never a value
        print("offers file problem: " + (str(e) if not isinstance(e, json.JSONDecodeError) else "not valid JSON"))
        return 1
    if res["unknown"]:
        for slug, tl in sorted(res["unknown"].items()):
            for t in tl:
                print(f"offer {slug}: unknown tag: {t} (ask the user to approve it, or pick an existing tag)")
        print("FAIL")
        return 1
    if as_json:
        print(json.dumps(res, indent=2))
    elif out_path:
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render(res))
        os.chmod(p, 0o600)
        print(f"wrote {p}: {len(res['ranked'])} ranked, {len(res['duplicates'])} duplicates dropped")
    else:
        print(render(res), end="")
    return 0

"""Add `_(tags: ...)_` to Evidence items that have an ID but no tags field.

Pass 1 (no model): map every name in an item's `_(tech: ...)_` field through the tag list and its aliases.
An item is tagged by pass 1 only when ALL its tech names map; otherwise it is pending and nothing is guessed.
Pass 2 (cheap model, run by the skill): proposals {"E0001": ["tag", ...]} for pending items. Each tag must be
in the tag list (aliases allowed). Unknown tags are reported and the item is left alone until the user adds the tag.
Never changes text, an ID or an existing tags field. Backs up first (reuses assign_ids). Idempotent.
Prints counts only.
"""
import datetime, json, os, pathlib, re, sys

import assign_ids, tags as taglib

ITEM = re.compile(r"^- \*\*(E\d{4,})\*\* ")
TECH = re.compile(r"_\(tech: (.*?)\)_")
HAS_TAGS = re.compile(r"_\(tags: (.*?)\)_")
INSERT_BEFORE = (" **Impact:**", " _(no metric evidenced)_", " _(kind: lab)_")


def _tech_tags(line, tags, aliases):
    """Tags for every tech name in the line, or None if there is no tech or any name is unmapped."""
    m = TECH.search(line)
    if not m:
        return None
    names = [n.strip() for n in m.group(1).split(",") if n.strip()]
    if not names:
        return None
    out = []
    for n in names:
        t = taglib.resolve(n, tags, aliases)
        if t is None:
            return None
        if t not in out:
            out.append(t)
    return out


def analyze(evidence, tags_file):
    tags, aliases = taglib.load(tags_file)
    r = {"items": 0, "no_id": 0, "already_tagged": 0, "pass1": {}, "pending": [], "lines": {}}
    for line in pathlib.Path(evidence).read_text().splitlines():
        m = ITEM.match(line)
        if not m:
            if assign_ids.NEEDS_ID.match(line):
                r["no_id"] += 1
            continue
        r["items"] += 1
        if HAS_TAGS.search(line):
            r["already_tagged"] += 1
            continue
        iid = m.group(1)
        found = _tech_tags(line, tags, aliases)
        if found:
            r["pass1"][iid] = found
        else:
            r["pending"].append(iid)
            r["lines"][iid] = line
    return r


def _insert(line, new_tags):
    field = f" _(tags: {', '.join(new_tags)})_"
    nl = "\n" if line.endswith("\n") else ""
    body = line[:-1] if nl else line
    m = TECH.search(body)
    if m:
        return body[:m.end()] + field + body[m.end():] + nl
    cuts = [body.find(k) for k in INSERT_BEFORE if body.find(k) != -1]
    at = min(cuts) if cuts else len(body.rstrip())
    return body[:at] + field + body[at:] + nl


def _validate(proposals, pending, tags, aliases):
    """-> ({id: tags}, rejected_items, unknown_tags, ignored)"""
    good, rejected, unknown, ignored = {}, 0, [], 0
    for iid, val in proposals.items():
        if iid not in pending:
            ignored += 1
            continue
        if not (isinstance(val, list) and val and all(isinstance(t, str) and taglib.TAG.match(t) for t in val)):
            rejected += 1
            continue
        resolved = [taglib.resolve(t, tags, aliases) for t in val]
        bad = [t for t, c in zip(val, resolved) if c is None]
        if bad:
            rejected += 1
            unknown += [t for t in bad if t not in unknown]
            continue
        good[iid] = list(dict.fromkeys(resolved))
    return good, rejected, unknown, ignored


def apply(evidence, tags_file, proposals=None, today=None, dry=False):
    ev = pathlib.Path(evidence)
    tags, aliases = taglib.load(tags_file)
    a = analyze(ev, tags_file)
    good, rejected, unknown, ignored = _validate(proposals or {}, set(a["pending"]), tags, aliases)
    todo = {**a["pass1"], **good}
    result = {"items": a["items"], "no_id": a["no_id"], "already_tagged": a["already_tagged"],
              "pass1": len(a["pass1"]), "pending": len(a["pending"]), "written": len(todo),
              "rejected_items": rejected, "unknown_tags": unknown, "ignored": ignored}
    if dry or not todo:
        if dry:
            result["written"] = 0
            result["would_write"] = len(todo)
        return result
    out = []
    for line in ev.read_text().splitlines(keepends=True):
        m = ITEM.match(line)
        if m and m.group(1) in todo and not HAS_TAGS.search(line):
            line = _insert(line, todo[m.group(1)])
        out.append(line)
    assign_ids._backup(ev, today or datetime.date.today().isoformat())
    ev.write_text("".join(out))
    return result


def load_implies(path, tags, aliases):
    """Rules `a, b => target`. The target must be in the tag list. -> [(set(lhs), target)]"""
    rules = []
    for n, raw in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" not in line:
            raise ValueError(f"implication rule at line {n} needs '=>'")
        lhs, rhs = (x.strip() for x in line.split("=>", 1))
        target = taglib.resolve(rhs, tags, aliases)
        if target is None:
            raise ValueError(f"implication target '{rhs}' (line {n}) is not in the tag list")
        names = {taglib.resolve(x, tags, aliases) or x.strip().lower() for x in lhs.split(",") if x.strip()}
        if not names:
            raise ValueError(f"implication rule at line {n} has no source tags")
        rules.append((names, target))
    return rules


def imply(evidence, tags_file, implies_file, today=None, dry=False):
    """Append the target tag to every item whose tags include a source tag. Appends only. Backs up first."""
    ev = pathlib.Path(evidence)
    tags, aliases = taglib.load(tags_file)
    rules = load_implies(implies_file, tags, aliases)
    out, changed = [], 0
    for line in ev.read_text().splitlines(keepends=True):
        m = ITEM.match(line)
        t = HAS_TAGS.search(line) if m else None
        if t:
            cur = [x.strip() for x in t.group(1).split(",") if x.strip()]
            new = list(cur)
            for names, target in rules:
                if target not in new and names & set(new):
                    new.append(target)
            if new != cur:
                line = line[:t.start(1)] + ", ".join(new) + line[t.end(1):]
                changed += 1
        out.append(line)
    result = {"written": 0, "would_write": changed}
    if dry or not changed:
        return result
    assign_ids._backup(ev, today or datetime.date.today().isoformat())
    ev.write_text("".join(out))
    result["written"] = changed
    return result


def write_pending(evidence, tags_file, out_path):
    a = analyze(evidence, tags_file)
    data = [{"id": i, "line": a["lines"][i]} for i in a["pending"]]
    p = pathlib.Path(out_path)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    os.chmod(p, 0o600)
    return len(data)


USAGE = "usage: pipeline.py tag-evidence EVIDENCE TAGS [--apply] [--pending OUT] [--proposals FILE] | tag-evidence EVIDENCE TAGS --implies FILE [--apply]"


def main(argv):
    pos, apply_, pending, proposals_path, implies, i = [], False, None, None, None, 0
    while i < len(argv):
        a = argv[i]
        if a == "--apply":
            apply_ = True
        elif a in ("--pending", "--proposals", "--implies") and i + 1 < len(argv):
            if a == "--pending":
                pending = argv[i + 1]
            elif a == "--implies":
                implies = argv[i + 1]
            else:
                proposals_path = argv[i + 1]
            i += 1
        elif a.startswith("--"):
            print(USAGE, file=sys.stderr)
            return 64
        else:
            pos.append(a)
        i += 1
    if len(pos) != 2:
        print(USAGE, file=sys.stderr)
        return 64
    if implies:
        try:
            r = imply(pos[0], pos[1], implies, dry=not apply_)
        except OSError:
            print("cannot read the evidence file, the tag list or the implication file")
            return 1
        except ValueError as e:
            print(e)
            return 1
        print("applied" if apply_ else "dry run: nothing written")
        print(f"written: {r['written']}" if apply_ else f"would write: {r['would_write']}")
        return 0
    try:
        proposals = None
        if proposals_path:
            proposals = json.loads(pathlib.Path(proposals_path).read_text())
            if not isinstance(proposals, dict):
                raise ValueError
        r = apply(pos[0], pos[1], proposals, dry=not apply_)
        n_pending = write_pending(pos[0], pos[1], pending) if pending else None
    except (OSError, ValueError):
        print("cannot read the evidence file, the tag list or the proposals file (must be a JSON object)")
        return 1
    print("dry run: nothing written" if not apply_ else "applied")
    print(f"items: {r['items']} (no ID: {r['no_id']})")
    print(f"already tagged: {r['already_tagged']}")
    print(f"pass 1: {r['pass1']}")
    print(f"pending: {r['pending']}")
    if proposals is not None:
        print(f"proposals: rejected {r['rejected_items']}, ignored {r['ignored']}")
    if apply_:
        print(f"written: {r['written']}")
    elif r.get("would_write") is not None:
        print(f"would write: {r['would_write']}")
    if n_pending is not None:
        print(f"pending file: {n_pending} items")
    for t in r["unknown_tags"]:
        print(f"unknown tag: {t} (ask the user to approve it in the tag list, or pick an existing tag)")
    return 1 if r["unknown_tags"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Controlled tag list: one lowercase tag per line, an optional [aliases] section of alias=tag lines."""
import pathlib, re, sys

TAG = re.compile(r"[a-z0-9][a-z0-9.+#-]*\Z")
PRIORITIES = ("must", "nice")


def load(path):
    tags, aliases, in_aliases = set(), {}, False
    for raw in pathlib.Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[aliases]":
            in_aliases = True
            continue
        if in_aliases and "=" in line:
            a, t = (x.strip() for x in line.split("=", 1))
            aliases[a] = t
            tags.add(t)
        else:
            tags.add(line)
    return tags, aliases


def resolve(tag, tags, aliases):
    """Canonical tag, or None if unknown."""
    tag = tag.strip().lower()
    tag = aliases.get(tag, tag)
    return tag if tag in tags else None


def check(reqs, tags, aliases):
    """Validate requirements JSON; report unknown tags and alias rewrites. Never raises."""
    errors, unknown, aliased = [], [], {}
    if not isinstance(reqs, list):
        return {"errors": [(0, "requirements must be a JSON list")], "unknown": [], "aliased": {}}
    for n, r in enumerate(reqs, 1):
        if not isinstance(r, dict):
            errors.append((n, "not an object"))
            continue
        if not (isinstance(r.get("requirement"), str) and r["requirement"].strip()):
            errors.append((n, "requirement missing"))
            continue
        if r.get("priority") not in PRIORITIES:
            errors.append((n, "priority must be must or nice"))
            continue
        tag = r.get("tag")
        if not (isinstance(tag, str) and TAG.match(tag)):
            errors.append((n, "tag must be lowercase, no spaces"))
            continue
        canon = resolve(tag, tags, aliases)
        if canon is None:
            if tag not in unknown:
                unknown.append(tag)
        elif canon != tag:
            aliased[tag] = canon
    return {"errors": errors, "unknown": unknown, "aliased": aliased}


def main(argv):
    import json
    if len(argv) != 2:
        print("usage: pipeline.py tags-check TAGS_FILE REQUIREMENTS_JSON", file=sys.stderr)
        return 64
    try:
        tags, aliases = load(argv[0])
        reqs = json.loads(pathlib.Path(argv[1]).read_text())
    except (OSError, ValueError):
        print("cannot read the tag list or the requirements JSON")
        return 1
    r = check(reqs, tags, aliases)
    for n, why in r["errors"]:
        print(f"requirement {n}: {why}")
    for t in r["unknown"]:
        print(f"unknown tag: {t} (ask the user to approve it, or pick an existing tag)")
    for a, c in r["aliased"].items():
        print(f"alias: {a} -> {c}")
    bad = bool(r["errors"] or r["unknown"])
    print("FAIL" if bad else "OK")
    return 1 if bad else 0

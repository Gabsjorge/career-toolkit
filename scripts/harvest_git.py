import collections, re, subprocess
from labels import (anonymize, looks_injected, person_patterns, redact_people, sanitize_text,
                    strip_identifiers)

SKIP = re.compile(r"^(merge|bump|chore\(deps|typo|wip\b)", re.IGNORECASE)


def _git(repo, args):
    return subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True, check=True).stdout


def _email_pattern(author):
    return author if "<" in author else f"<{author}>"


def _since_arg(since):
    # a bare date means that day at the *current clock time* in git, which skips the day's earlier commits
    return "--since=" + (since + " 00:00:00" if len(since) == 10 else since)


def _filters(authors, since):
    # fixed strings: git's --author is a basic regex by default, where "." and substrings would over-match
    args = ["--fixed-strings", "--regexp-ignore-case"] + ["--author=" + _email_pattern(a) for a in authors]
    if since:
        args.append(_since_arg(since))
    return args


def commits(repo, authors, since):
    out = _git(repo, ["log", "--all", "--no-merges", "--format=%ad|%s", "--date=format:%Y-%m-%d"] + _filters(authors, since))
    rows = []
    for line in out.splitlines():
        if "|" in line:
            date, subject = line.split("|", 1)
            rows.append((date, subject))
    return rows  # newest first


def ext_counts(repo, authors, since):
    out = _git(repo, ["log", "--all", "--no-merges", "--numstat", "--format="] + _filters(authors, since))
    counts = collections.Counter()
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            base = parts[2].rsplit("/", 1)[-1]
            counts[base.rsplit(".", 1)[-1].lower() if "." in base else "none"] += 1
    return counts


def unlisted_identity_commits(repo, authors, since):
    """Commits under one of your author names but with an email that is not in `authors` (count only)."""
    names = {n for n in _git(repo, ["log", "--all", "--no-merges", "--format=%an"]
                             + _filters(authors, None)).splitlines() if n.strip()}   # names: all time
    if not names:
        return 0
    mine = {(re.search(r"<([^>]*)>", a).group(1) if "<" in a else a).lower() for a in authors}
    args = ["log", "--all", "--no-merges", "--format=%an%x00%ae"] + ([_since_arg(since)] if since else [])
    count = 0
    for line in _git(repo, args).splitlines():
        name, _, email = line.partition("\0")
        if name in names and email.lower() not in mine:
            count += 1
    return count


def contributor_identities(repo, authors):
    """(name, email) of everyone who committed, except you. Kept in memory only."""
    mine = {(re.search(r"<([^>]*)>", a).group(1) if "<" in a else a).lower() for a in authors}
    out = _git(repo, ["log", "--all", "--format=%an%x00%ae%x00%cn%x00%ce"])
    found = set()
    for line in out.splitlines():
        f = line.split("\0")
        for name, email in zip(f[0::2], f[1::2]):
            if email.lower() not in mine and (name.strip() or email.strip()):
                found.add((name.strip(), email.strip()))
    return sorted(found)


def build_digest(repo, label, label_map, authors, since, max_chars=6000, stats=None, identities=None):
    rows = commits(repo, authors, since)
    if stats is not None:
        stats["commits"] = len(rows)
    if not rows:
        return None
    kept = []
    people = person_patterns(identities or [])
    for date, subject in rows:
        subject = sanitize_text(subject)
        subject, redacted = redact_people(subject, people)
        if redacted and stats is not None:
            stats["names_redacted"] = stats.get("names_redacted", 0) + redacted
        if SKIP.match(subject):
            continue
        if looks_injected(subject):
            if stats is not None:
                stats["suspect_dropped"] = stats.get("suspect_dropped", 0) + 1
            continue
        cleaned = strip_identifiers(anonymize(subject, label_map))[:110]
        if cleaned:
            kept.append((date, cleaned))
    months = collections.OrderedDict()
    for date, subject in sorted(kept):
        months.setdefault(date[:7], []).append(subject)
    exts = ext_counts(repo, authors, since).most_common(8)
    head = (f"# {label}: {len(rows)} commits, {rows[-1][0]}..{rows[0][0]}\n"
            "file types touched: " + ", ".join(f"{e}={n}" for e, n in exts) + "\n")
    per = 15
    while True:
        body = []
        for month, subs in months.items():
            step = max(1, -(-len(subs) // per))
            picked = subs[::step][:per]
            body.append(f"## {month} ({len(subs)} commits)\n" + "\n".join("- " + s for s in picked))
        text = head + "\n".join(body) + "\n"
        if len(text) <= max_chars:
            return text
        if per == 1:
            return text[:max_chars]
        per -= 1

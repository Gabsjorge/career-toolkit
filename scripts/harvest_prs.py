import collections, datetime, json, os, subprocess, sys, time
from typing import Tuple


RATE_LIMIT_RETRIES = 6
RATE_LIMIT_WAIT_SECONDS = 65
_sleep = time.sleep
on_wait = None   # callback(retry, seconds); pipeline points it at the run log


def _run(cmd, env=None):
    retries = 0
    while True:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if r.returncode == 0:
            return r.stdout
        if "rate limit" in (r.stderr or "").lower():
            if retries >= RATE_LIMIT_RETRIES:
                raise RuntimeError("gh rate limit: retries exhausted")
            retries += 1
            if on_wait:
                on_wait(retries, RATE_LIMIT_WAIT_SECONDS)
            else:
                print(f"gh rate limit: waiting {RATE_LIMIT_WAIT_SECONDS}s (retry {retries}/{RATE_LIMIT_RETRIES})",
                      file=sys.stderr)
            _sleep(RATE_LIMIT_WAIT_SECONDS)
            continue
        raise RuntimeError("gh command failed")


def _env(host):
    return dict(os.environ, GH_HOST=host)


LIMIT = 1000
EPOCH = "2008-01-01"


def _fetch_window(host, start, end, runner=_run) -> list:
    cmd = ["gh", "search", "prs", "--reviewed-by", "@me", "--limit", str(LIMIT),
           "--json", "repository,number,createdAt,updatedAt,author",
           "--updated", f"{start}..{end}"]
    return json.loads(runner(cmd, _env(host)))


def fetch_reviewed_prs(host, since, runner=_run, today=None) -> Tuple[list, bool]:
    start = datetime.date.fromisoformat(since) if since else datetime.date.fromisoformat(EPOCH)
    end = today or datetime.date.today()
    capped = False

    def go(s, e):
        nonlocal capped
        items = _fetch_window(host, s.isoformat(), e.isoformat(), runner)
        if len(items) < LIMIT:
            return items
        if s < e:
            mid = s + (e - s) // 2
            return go(s, mid) + go(mid + datetime.timedelta(days=1), e)
        capped = True
        return items

    out, seen = [], set()
    for p in go(start, end):
        key = (p["repository"]["nameWithOwner"], p["number"])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out, capped


def current_login(host, runner=_run):
    return runner(["gh", "api", "user", "--jq", ".login"], _env(host)).strip()


# Written feedback comes in three places; counting only inline comments undercounts reviewers who
# write their feedback in review summaries or in the conversation.
FEEDBACK_ENDPOINTS = [
    ("inline", "pulls/{n}/comments", ".[].user.login"),
    ("reviews", "pulls/{n}/reviews", '.[] | select((.body // "") != "") | .user.login'),
    ("conversation", "issues/{n}/comments", ".[].user.login"),
]


def sample_comment_counts(prs, me, host, runner=_run, n=40):
    empty = {"sampled": 0, "with_comments": 0, "comments": 0, "inline": 0, "reviews": 0, "conversation": 0}
    if not prs:
        return empty
    step = max(1, -(-len(prs) // n))
    sample = prs[::step][:n]
    stats = dict(empty)
    for p in sample:
        repo = p["repository"]["nameWithOwner"]
        mine = {}
        try:
            for kind, template, jq in FEEDBACK_ENDPOINTS:
                path = f"repos/{repo}/" + template.format(n=p["number"])
                out = runner(["gh", "api", path, "--paginate", "--jq", jq], _env(host))
                mine[kind] = sum(1 for line in out.splitlines() if line.strip() == me)
        except Exception:
            continue  # skipped: not counted as sampled
        stats["sampled"] += 1
        for kind, count in mine.items():
            stats[kind] += count
            stats["comments"] += count
        stats["with_comments"] += 1 if any(mine.values()) else 0
    return stats


def build_digest(prs, stats, label, capped=False, by="createdAt"):
    """by="updatedAt" for delta runs: the search matches PRs active in the period, not only opened in it."""
    if not prs:
        return None
    months = collections.Counter((p.get(by) or p["createdAt"])[:7] for p in prs)
    authors = collections.Counter((p.get("author") or {}).get("login", "?") for p in prs)
    top5 = sum(c for _, c in authors.most_common(5))
    lines = [f"# {label}: {len(prs)} PRs reviewed" + (" (active in period)" if by == "updatedAt" else "")]
    if capped:
        lines.append("WARNING: the search hit its result cap on a single day; some PRs are missing")
    lines += [f"distinct authors: {len(authors)}; top-5 authors account for {top5} of {len(prs)} PRs",
             "## per month"]
    lines += [f"- {m}: {c}" for m, c in sorted(months.items())]
    lines += ["## comment sample",
              f"sampled {stats['sampled']} PRs; {stats['with_comments']} had a written comment from the user; "
              f"{stats['comments']} comments in total "
              f"({stats.get('inline', 0)} inline, {stats.get('reviews', 0)} review summaries, "
              f"{stats.get('conversation', 0)} conversation)"]
    return "\n".join(lines) + "\n"

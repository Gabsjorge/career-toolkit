import datetime, json, os, pathlib, shutil, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import estimate as est
import assign_ids, eval_score, backfill_fit, tag_evidence, bullets_check, config, draft_check, fit_status, gap_count, guard, lang_detect, tags, harvest_git, harvest_prs, labels, nda_scrub, runlog, state


def _swap_in(dd, stage):
    """Replace repo-*/reviews-*/.report.json in dd with the staged ones; keep one previous generation."""
    prev = dd / ".prev"
    shutil.rmtree(prev, ignore_errors=True)
    prev.mkdir()
    for pattern in ("repo-*.md", "reviews-*.md", ".report.json"):
        for old in dd.glob(pattern):
            shutil.move(str(old), str(prev / old.name))
    for new in stage.iterdir():
        shutil.move(str(new), str(dd / new.name))


def run_digest(state_dir, full=False, pr_runner=None):
    sd = pathlib.Path(state_dir)
    cfg = state.load_config(sd)
    bl = sd / "blocklist.txt"
    pats = nda_scrub.load_patterns(bl) if bl.exists() else []
    if not pats:
        raise ValueError("create state/blocklist.txt (see blocklist.example.txt) before digesting")
    bad = nda_scrub.validate_patterns(pats)
    if bad:
        raise ValueError("blocklist entry #" + ", #".join(map(str, bad)) + " is invalid "
                         "(does not compile or matches everything); fix it before digesting")
    since = state.since_date(sd, full)
    dd = sd / "digests"
    dd.mkdir(exist_ok=True)
    stage = dd / ".staging"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir()
    started = time.monotonic()
    runlog.event(sd, "digest", "start")
    harvest_prs.on_wait = lambda n, secs: runlog.event(sd, "gh", "rate_limit_wait", retry=n, seconds=secs)
    try:
        report = _harvest_into(stage, cfg, pats, since, sd, pr_runner)
        _swap_in(dd, stage)
    except BaseException as e:
        runlog.event(sd, "digest", "aborted", error_class=type(e).__name__)
        raise
    finally:
        harvest_prs.on_wait = None
        shutil.rmtree(stage, ignore_errors=True)
    runlog.event(sd, "digest", "done", written=len(report["written"]), skipped=len(report["skipped"]),
                 gaps=len(report["gaps"]), redacted=report["redacted"],
                 suspect_dropped=report["suspect_dropped"], names_redacted=report["names_redacted"], seconds=time.monotonic() - started)
    return report


def _harvest_into(stage, cfg, pats, since, sd, pr_runner):
    repos = [pathlib.Path(r["path"]).expanduser() for r in cfg["repos"]]
    lmap = labels.build_label_map([r.name for r in repos], labels.load_map(sd / "label-map.json"))
    labels.save_map(sd / "label-map.json", lmap)
    report = {"since": since, "run_date": datetime.date.today().isoformat(), "written": [], "skipped": [],
              "gaps": [], "redacted": 0, "suspect_dropped": 0, "names_redacted": 0, "possible_missing": {}}
    hits = [0] * len(pats)

    def emit(label, text):
        if text is None:
            report["skipped"].append(label)
            return
        text, counts = labels.redact_counted(text, pats)
        report["redacted"] += sum(counts)
        for i, c in enumerate(counts):
            hits[i] += c
        (stage / f"{label}.md").write_text(text)
        report["written"].append(label)

    seen = set()
    for r in repos:
        label = lmap[r.name]
        if r.name in seen:
            report["gaps"].append(f"{label}: duplicate repo name")
            continue
        seen.add(r.name)
        t0 = time.monotonic()
        try:
            gstats = {}
            people = harvest_git.contributor_identities(str(r), cfg["authors"])
            text = harvest_git.build_digest(str(r), label, lmap, cfg["authors"], since, stats=gstats,
                                            identities=people)
            report["suspect_dropped"] += gstats.get("suspect_dropped", 0)
            report["names_redacted"] += gstats.get("names_redacted", 0)
            missing = harvest_git.unlisted_identity_commits(str(r), cfg["authors"], since)
            if missing:
                report["possible_missing"][label] = missing
                print(f"{label}: {missing} commits under your name use an email not in authors; "
                      "add it to config.json", file=sys.stderr)
        except Exception as e:
            report["gaps"].append(f"{label}: {type(e).__name__}")
            runlog.event(sd, label, "gap", error_class=type(e).__name__, seconds=time.monotonic() - t0)
            continue
        emit(label, text)
        runlog.event(sd, label, "ok" if text else "skipped", commits=gstats.get("commits", 0),
                     suspect_dropped=gstats.get("suspect_dropped", 0),
                     names_redacted=gstats.get("names_redacted", 0),
                     possible_missing=report["possible_missing"].get(label, 0), seconds=time.monotonic() - t0)
    runner_kw = {"runner": pr_runner} if pr_runner else {}
    for i, host in enumerate(cfg["gh_hosts"], 1):
        label = f"reviews-{i}"
        t0 = time.monotonic()
        try:
            prs, capped = harvest_prs.fetch_reviewed_prs(host, since, **runner_kw)
            me = harvest_prs.current_login(host, **runner_kw)
            stats = harvest_prs.sample_comment_counts(prs, me, host, **runner_kw)
            text = harvest_prs.build_digest(prs, stats, label, capped, by="updatedAt" if since else "createdAt")
        except Exception as e:
            report["gaps"].append(f"{label}: {type(e).__name__}")
            runlog.event(sd, label, "gap", error_class=type(e).__name__, seconds=time.monotonic() - t0)
            continue
        if capped:
            report["capped"] = True
        emit(label, text)
        runlog.event(sd, label, "ok" if text else "skipped", prs=len(prs), seconds=time.monotonic() - t0)
    # numbers only; "unused in this period" is not the same as "dead" (a delta run sees little text)
    report["unused_entries"] = [i for i, c in enumerate(hits, 1) if c == 0]
    (stage / ".report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


ALLOWED_FLAGS = {"digest": {"--full"}, "mark-run": {"--accept-gaps", "--accept-strays"}}
USAGE = ("usage: pipeline.py init|digest|estimate|scrub|mark-run|check-strays STATE [...] | check-draft FILE"
         " | guard DIR [--blocklist FILE] | assign-ids STATE | tag-evidence EVIDENCE TAGS [--apply] [--pending OUT] [--proposals FILE] | backfill-fit APPS EVIDENCE TAGS [--pending OUT] [--proposals FILE] [--report OUT] [--apply] | tags-check TAGS REQS | fit-status FIT EVIDENCE TAGS [--relations F] [--check] | bullets-check CV EVIDENCE | gap-count APPS TRACKS [--groups FILE] [--check PLAN] | eval-score PERSONA RESULTS [--out FILE] | eval-setup PERSONA DEST | detect-lang FILE | estimate-files CAP PRICE FILE... | config-check | gate refresh | state-dir")


def main(argv):
    old = os.umask(0o077)   # state is confidential: files 600, directories 700
    try:
        return _main(argv)
    finally:
        os.umask(old)


def _main(argv):
    if not argv:
        print(USAGE, file=sys.stderr)
        return 64
    cmd, rest = argv[0], argv[1:]
    if cmd == "guard":
        return guard.main(rest)
    simple = {"tags-check": tags.main, "fit-status": fit_status.main, "bullets-check": bullets_check.main,
              "detect-lang": lang_detect.main, "gap-count": gap_count.main, "estimate-files": est.main_files}
    if cmd in simple:
        return simple[cmd](rest)
    if cmd == "eval-score":
        return eval_score.main_score(rest)
    if cmd == "eval-setup":
        return eval_score.main_setup(rest)
    if cmd == "backfill-fit":
        return backfill_fit.main(rest)
    if cmd == "tag-evidence":
        return tag_evidence.main(rest)
    if cmd == "assign-ids":
        return assign_ids.main(rest)
    if cmd in ("config-check", "gate", "state-dir"):
        return config.main(cmd, rest)
    flags = [a for a in rest if a.startswith("--")]
    pos = [a for a in rest if not a.startswith("--")]
    if cmd in ("init", "digest", "estimate", "scrub", "mark-run", "check-strays", "check-draft") and not pos:
        print(USAGE, file=sys.stderr)
        return 64
    unknown = [f for f in flags if f not in ALLOWED_FLAGS.get(cmd, set())]
    if unknown:
        allowed = ", ".join(sorted(ALLOWED_FLAGS.get(cmd, set()))) or "none"
        print(f"unknown flag {' '.join(unknown)} for {cmd}; allowed: {allowed}", file=sys.stderr)
        return 64
    if cmd == "init":
        for p in state.init_state(pos[0]):
            print("created", p)
        return 0
    if cmd == "check-draft":
        return draft_check.main(pos)
    if cmd == "check-strays":
        strays = state.find_strays(pos[0])
        for path in strays:
            print("stray sensitive file:", path)
        print("FAIL" if strays else "OK")
        return 1 if strays else 0
    if cmd == "digest":
        for path in state.find_strays(pos[0]):
            print("WARNING stray sensitive file outside STATE:", path, file=sys.stderr)
        report = run_digest(pos[0], full="--full" in flags)
        print(json.dumps(report, indent=2))
        if report["since"] and not report["written"] and not report["gaps"]:
            print(f"no new activity since {report['since']}: nothing to summarize", file=sys.stderr)
        return 0
    if cmd == "estimate":
        cfg = state.load_config(pos[0])
        dd = pathlib.Path(pos[0]) / "digests"
        if not list(dd.glob("*.md")):
            print("no digests (on a delta run with no gaps this means nothing new since the last run)")
            return 2
        return est.main([str(dd), str(cfg["cap_tokens"]), str(cfg["price_per_mtok"])])
    if cmd == "scrub":
        return nda_scrub.main(["--blocklist", str(pathlib.Path(pos[0]) / "blocklist.txt")] + pos[1:])
    if cmd == "mark-run":
        state.assert_safe(pos[0])
        strays = state.find_strays(pos[0])
        if strays and "--accept-strays" not in flags:
            for path in strays:
                print("stray sensitive file:", path, file=sys.stderr)
            print("stray files outside STATE: remove them, or re-run with --accept-strays", file=sys.stderr)
            runlog.event(pos[0], "mark-run", "refused_strays")
            return 4
        rp = pathlib.Path(pos[0]) / "digests" / ".report.json"
        report = json.loads(rp.read_text()) if rp.exists() else {}
        if report.get("gaps") and "--accept-gaps" not in flags:
            print("open gaps: fix the failing sources, or re-run with --accept-gaps", file=sys.stderr)
            runlog.event(pos[0], "mark-run", "refused_gaps", gaps=len(report["gaps"]))
            return 3
        # the digest day, not today: a later approval must not skip the days in between
        print("last run:", state.write_last_run(pos[0], report.get("run_date")))
        runlog.event(pos[0], "mark-run", "ok")
        return 0
    print(USAGE, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

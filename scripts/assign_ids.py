"""Assign sequential Evidence IDs (E0001, ...) to evidence.md items that lack one.

Idempotent. Never changes an ID, never reuses one (the highest ID ever assigned is kept in
STATE/evidence-ids.json). Backs up evidence.md first (mode 600, an older backup is never overwritten).
Prints counts only.
"""
import datetime, json, os, pathlib, re, shutil, sys

HAS_ID = re.compile(r"^- \*\*E(\d{4,})\*\* ")
NEEDS_ID = re.compile(r"^- (\*\*\[(?:high|med|low)\] )")
COUNTER = "evidence-ids.json"


def _highest(sd, text):
    best = 0
    cp = sd / COUNTER
    if cp.exists():
        try:
            best = int(json.loads(cp.read_text())["highest"])
        except (ValueError, KeyError, TypeError):
            raise ValueError(f"{COUNTER} is not valid; fix or remove it") from None
    for line in text.splitlines():
        m = HAS_ID.match(line)
        if m:
            best = max(best, int(m.group(1)))
    return best


def _backup(ev, today):
    names = [ev.with_name(ev.name + ".bak"), ev.with_name(f"{ev.name}.{today.replace('-', '')}.bak")]
    target = next((p for p in names if not p.exists()), None)
    if target is None:
        stamp = datetime.datetime.now().strftime("%H%M%S")
        target = ev.with_name(f"{ev.name}.{today.replace('-', '')}{stamp}.bak")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(ev.read_bytes())
    shutil.copystat(ev, target)
    os.chmod(target, 0o600)


def assign(state_dir, today=None):
    sd = pathlib.Path(state_dir)
    ev = sd / "evidence.md"
    if not ev.is_file():
        raise ValueError("evidence.md not found in STATE")
    today = today or datetime.date.today().isoformat()
    text = ev.read_text()
    n = _highest(sd, text)
    out, added = [], 0
    for line in text.splitlines(keepends=True):
        if not HAS_ID.match(line):
            m = NEEDS_ID.match(line)
            if m:
                n += 1
                added += 1
                line = f"- **E{n:04d}** " + line[2:]
        out.append(line)
    if added:
        _backup(ev, today)
        ev.write_text("".join(out))
        (sd / COUNTER).write_text(json.dumps({"highest": n}) + "\n")
    return added


def main(argv):
    if len(argv) != 1:
        print("usage: pipeline.py assign-ids STATE", file=sys.stderr)
        return 64
    try:
        added = assign(argv[0])
    except ValueError as e:
        print(e)
        return 1
    print(f"assigned {added} new IDs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

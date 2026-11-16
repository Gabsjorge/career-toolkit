import datetime, os, pathlib, re, sys

# Counts and labels only: subjects, paths, repo names and blocklist terms must never reach the log.
ALLOWED_FIELDS = {"commits", "prs", "written", "skipped", "gaps", "redacted", "suspect_dropped",
                  "possible_missing", "names_redacted", "seconds", "retry", "error_class"}
IDENT = re.compile(r"^[A-Za-z0-9_.:-]{1,40}$")
MAX_LINES = 500
ECHO = True   # also print each line to stderr: doubles as progress output


def _value(key, value):
    if isinstance(value, bool):
        raise ValueError(f"log field {key}: bool not allowed")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, str) and IDENT.match(value):
        return value
    raise ValueError(f"log field {key}: only numbers and short identifiers are allowed")


def event(state_dir, source, status, **fields):
    for name, text in (("source", source), ("status", status)):
        if not IDENT.match(text):
            raise ValueError(f"log {name}: only short identifiers are allowed")
    parts = []
    for key in sorted(fields):
        if key not in ALLOWED_FIELDS:
            raise ValueError(f"log field not allowed: {key}")
        parts.append(f"{key}={_value(key, fields[key])}")
    line = "\t".join([datetime.datetime.now().isoformat(timespec="seconds"), source, status] + parts)
    path = pathlib.Path(state_dir) / "run.log"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(line + "\n")
    lines = path.read_text().splitlines()
    if len(lines) > MAX_LINES:
        path.write_text("\n".join(lines[-MAX_LINES:]) + "\n")
    if ECHO:
        print(line, file=sys.stderr)

import datetime, json, os, pathlib
from typing import Optional

IGNORE_ENTRIES = ["config.json", "blocklist.txt", "last_run.json", "notes.md",
                  "digests/", "label-map.json", "evidence.md", "evidence-draft.md", "*.pdf", "*.bak", "*.log", "evidence-ids.json"]
OPTIONAL_IGNORED = {"*.pdf", "*.bak", "*.log", "evidence-ids.json"}   # not required, so older state/.gitignore files keep working
REQUIRED_IGNORED = [e for e in IGNORE_ENTRIES if e not in OPTIONAL_IGNORED]
SENSITIVE_NAMES = {"blocklist.txt", "config.json", "label-map.json", "last_run.json",
                   "evidence.md", "evidence-draft.md"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git"}
GITIGNORE_BODY = ("# career-toolkit state: derived from confidential work. Never commit.\n"
                  + "\n".join(IGNORE_ENTRIES) + "\n!config.example.json\n")
EXAMPLE_CONFIG = {
    "authors": ["you@example.com"],
    "repos": [{"path": "~/code/some-repo", "kind": "client"}],
    "gh_hosts": ["github.com"],
    "cap_tokens": 60000,
    "price_per_mtok": 1.0,
}
NOTES_TEMPLATE = ("# Persistent rulings (the skill must respect these on every run)\n\n"
                  "- Example: say 'co-designed' for team work, never claim sole authorship.\n")
DEFAULTS = {"gh_hosts": [], "cap_tokens": 60000, "price_per_mtok": 1.0}


def init_state(state_dir):
    d = pathlib.Path(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    created = []
    gi = d / ".gitignore"
    if not gi.exists():                      # always first, before any sensitive file
        gi.write_text(GITIGNORE_BODY)
        created.append(gi)
    (d / "digests").mkdir(exist_ok=True)
    ex = d / "config.example.json"
    if not ex.exists():
        ex.write_text(json.dumps(EXAMPLE_CONFIG, indent=2) + "\n")
        created.append(ex)
    notes = d / "notes.md"
    if not notes.exists():
        notes.write_text(NOTES_TEMPLATE)
        created.append(notes)
    return created


def ignore_ok(state_dir):
    gi = pathlib.Path(state_dir) / ".gitignore"
    if not gi.exists():
        return False
    lines = set(gi.read_text().splitlines())
    return all(e in lines for e in REQUIRED_IGNORED)


def assert_safe(state_dir):
    if not ignore_ok(state_dir):
        raise RuntimeError("state/.gitignore is missing or incomplete; run `pipeline.py init` first")


def find_strays(state_dir):
    """Paths of sensitive-named files outside STATE (filenames only, contents never read)."""
    sd = pathlib.Path(state_dir).resolve()
    found = []
    for dirpath, dirnames, filenames in os.walk(sd.parent):
        here = pathlib.Path(dirpath).resolve()
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and (here / d).resolve() != sd]
        found += [str(here / f) for f in sorted(filenames) if f in SENSITIVE_NAMES]
    return found


def load_config(state_dir):
    assert_safe(state_dir)
    cp = pathlib.Path(state_dir) / "config.json"
    if not cp.exists():
        raise ValueError("config.json not found in STATE")
    cfg = json.loads(cp.read_text())
    if not cfg.get("authors") or not cfg.get("repos"):
        raise ValueError("config.json needs non-empty 'authors' and 'repos'")
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)
    _validate_types(cfg)
    return cfg


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate_types(cfg):
    """Name the offending key only, never its value."""
    def bad(key, want):
        raise ValueError(f"config.json: '{key}' must be {want}")
    if not (isinstance(cfg["authors"], list) and all(isinstance(a, str) and a.strip() for a in cfg["authors"])):
        bad("authors", "a list of non-empty strings")
    if not (isinstance(cfg["repos"], list)
            and all(isinstance(r, dict) and isinstance(r.get("path"), str) and r["path"] for r in cfg["repos"])):
        bad("repos", "a list of objects with a string 'path'")
    if not (isinstance(cfg["gh_hosts"], list) and all(isinstance(h, str) and h for h in cfg["gh_hosts"])):
        bad("gh_hosts", "a list of host names")
    if not (isinstance(cfg["cap_tokens"], int) and not isinstance(cfg["cap_tokens"], bool) and cfg["cap_tokens"] > 0):
        bad("cap_tokens", "a positive whole number")
    if not (_is_number(cfg["price_per_mtok"]) and cfg["price_per_mtok"] >= 0):
        bad("price_per_mtok", "a number of 0 or more")


def read_last_run(state_dir):
    p = pathlib.Path(state_dir) / "last_run.json"
    return json.loads(p.read_text()) if p.exists() else {}


def write_last_run(state_dir, date=None):
    date = date or datetime.date.today().isoformat()
    (pathlib.Path(state_dir) / "last_run.json").write_text(json.dumps({"date": date}) + "\n")
    return date


def since_date(state_dir, full):
    if full:
        return None
    return read_last_run(state_dir).get("date")

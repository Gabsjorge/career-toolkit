"""User config (outside the repo): ~/.config/career-toolkit/config.json or $CAREER_TOOLKIT_CONFIG.

Fields: career_folder (path), machine ("client"|"personal"), refresh_enabled (bool),
languages (list of strings). Errors name the field, never its value or a path.
"""
import json, os, pathlib, sys

MACHINES = ("client", "personal")
GATES = ("refresh",)


class ConfigError(Exception):
    pass


def config_path(env=None):
    env = os.environ if env is None else env
    if env.get("CAREER_TOOLKIT_CONFIG"):
        return pathlib.Path(env["CAREER_TOOLKIT_CONFIG"]).expanduser()
    home = env.get("HOME") or str(pathlib.Path.home())
    return pathlib.Path(home) / ".config" / "career-toolkit" / "config.json"


def load(path=None):
    p = pathlib.Path(path) if path else config_path()
    if not p.is_file():
        raise ConfigError("config file not found (set CAREER_TOOLKIT_CONFIG or create "
                          "~/.config/career-toolkit/config.json; see templates/config.example.json)")
    try:
        raw = json.loads(p.read_text())
    except (ValueError, OSError):
        raise ConfigError("config file is not valid JSON") from None
    if not isinstance(raw, dict):
        raise ConfigError("config file must be a JSON object")
    for key in ("career_folder", "machine"):
        if key not in raw:
            raise ConfigError(f"config: '{key}' is required")
    cf = raw["career_folder"]
    if not (isinstance(cf, str) and cf.strip()):
        raise ConfigError("config: 'career_folder' must be a non-empty string")
    folder = pathlib.Path(cf).expanduser()
    if not folder.is_dir():
        raise ConfigError("config: 'career_folder' does not point to an existing folder")
    if raw["machine"] not in MACHINES:
        raise ConfigError("config: 'machine' must be \"client\" or \"personal\"")
    machine = raw["machine"]
    refresh = raw.get("refresh_enabled", machine == "personal")
    if not isinstance(refresh, bool):
        raise ConfigError("config: 'refresh_enabled' must be true or false")
    langs = raw.get("languages", ["en", "pt"])
    if not (isinstance(langs, list) and langs and all(isinstance(x, str) and x for x in langs)):
        raise ConfigError("config: 'languages' must be a non-empty list of strings")
    return {"career_folder": str(folder), "machine": machine, "refresh_enabled": refresh,
            "languages": langs, "state_dir": str(folder / "state")}


def gate(cfg, name):
    """(allowed, message)."""
    if name == "refresh" and not cfg["refresh_enabled"]:
        if cfg["machine"] == "client":
            return False, ("refresh-evidence is off on a client machine. Set "
                           "\"refresh_enabled\": true in your config only if your client allows it.")
        return False, "refresh-evidence is turned off: \"refresh_enabled\" is false in your config."
    return True, "OK"


def main(cmd, args):
    """config-check | gate NAME | state-dir. Exit 0 OK, 1 problem, 64 usage."""
    if cmd == "gate" and (len(args) != 1 or args[0] not in GATES):
        print("usage: pipeline.py gate refresh", file=sys.stderr)
        return 64
    try:
        cfg = load()
    except ConfigError as e:
        print(e)
        return 1
    if cmd == "config-check":
        print("OK")
    elif cmd == "state-dir":
        print(cfg["state_dir"])
    elif cmd == "gate":
        ok, msg = gate(cfg, args[0])
        print(msg)
        return 0 if ok else 1
    return 0

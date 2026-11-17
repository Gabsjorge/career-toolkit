"""Check commit messages against Conventional Commits (https://www.conventionalcommits.org).

  check_commit_msg.py FILE             check one message file (used by .githooks/commit-msg)
  check_commit_msg.py --range A..B     check every commit in a git range (used by CI)
Exit 0 OK, 1 a message is not conventional, 64 usage.
"""
import re, subprocess, sys

TYPES = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
SUBJECT = re.compile(rf"^(?:{TYPES})(?:\([a-z0-9._/-]+\))?!?: \S")
AUTO = re.compile(r"^(?:Merge |Revert \")")
MAX_SUBJECT = 72
HELP = ("Commit message must follow Conventional Commits: <type>(<scope>)?: <description>\n"
        f"  types: {TYPES.replace('|', ', ')}\n"
        f"  subject up to {MAX_SUBJECT} characters; a blank line before any body.\n"
        "  example: feat(evidence): add Evidence IDs")


def problem(message):
    lines = [l for l in message.splitlines() if not l.startswith("#")]
    if not lines or not lines[0].strip():
        return "empty commit message"
    subject = lines[0]
    if AUTO.match(subject):
        return None
    if not SUBJECT.match(subject):
        return "subject is not a conventional commit"
    if len(subject) > MAX_SUBJECT:
        return f"subject is longer than {MAX_SUBJECT} characters"
    if len(lines) > 1 and lines[1].strip():
        return "leave a blank line between subject and body"
    return None


def main(argv):
    if len(argv) == 1 and not argv[0].startswith("--"):
        msg = open(argv[0]).read()
        p = problem(msg)
        if p:
            print(f"commit-msg: {p}\n{HELP}", file=sys.stderr)
            return 1
        return 0
    if len(argv) == 2 and argv[0] == "--range":
        shas = subprocess.run(["git", "rev-list", argv[1]], capture_output=True, text=True, check=True).stdout.split()
        bad = 0
        for sha in shas:
            body = subprocess.run(["git", "log", "-1", "--format=%B", sha], capture_output=True, text=True,
                                  check=True).stdout
            p = problem(body)
            if p:
                print(f"{sha[:7]}: {p}", file=sys.stderr)
                bad += 1
        if bad:
            print(HELP, file=sys.stderr)
        return 1 if bad else 0
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

import json, pathlib, re, unicodedata

ID_PATTERNS = [r"[a-z][a-z0-9+.-]*://\d+", r"https?://\S+", r"[\w.+-]+@[\w-]+\.[\w.-]+",
               r"(?i:\b[A-Z][A-Z0-9]+-\d{2,}\b)", r"\b\d{8,9}\b", r"#\d+"]


def build_label_map(names, existing=None):
    mapping = dict(existing or {})
    n = len(mapping)
    for name in names:
        if name not in mapping:
            n += 1
            mapping[name] = f"repo-{n}"
    return mapping


def load_map(path):
    p = pathlib.Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def save_map(path, mapping):
    pathlib.Path(path).write_text(json.dumps(mapping, indent=2) + "\n")


def anonymize(text, label_map):
    for name in sorted(label_map, key=len, reverse=True):
        pat = r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"
        text = re.sub(pat, label_map[name], text, flags=re.IGNORECASE)
    return text


def redact_counted(text, patterns):
    """Redact; also return the hit count per pattern (same order), never the matched text."""
    counts = []
    for p in patterns:
        text, n = re.subn(p, "[redacted]", text, flags=re.IGNORECASE)
        counts.append(n)
    return text, counts


def redact(text, patterns):
    text, counts = redact_counted(text, patterns)
    return text, sum(counts)


def strip_identifiers(text):
    for p in ID_PATTERNS:
        text = re.sub(p, "", text)
    return re.sub(r"\s+", " ", text).strip(" -:[]()")


# Commit subjects are written by other people and end up in a model's context: clean them and
# drop the ones that read like instructions. A speed bump only; pipeline.check-draft is the real gate.
INJECTION = re.compile(
    r"ignore\s+(all\s+|the\s+|any\s+|your\s+)?(previous|prior|above|earlier)"
    r"|\bdisregard\b|\byou\s+are\s+(now|a|an)\b|(new|follow|these)\s+instructions\b"
    r"|^\s*(system|assistant)\s*:|<\||\bread\s+\S*(~/|/Users/|/etc/|/home/)",
    re.IGNORECASE)


def sanitize_text(text):
    """Remove control, zero-width, bidi and tag characters (where hidden instructions travel)."""
    return "".join(c for c in text if unicodedata.category(c) not in ("Cc", "Cf"))


def looks_injected(text):
    return bool(INJECTION.search(text))


# Colleagues' names reach the model through commit subjects. Multi-word names only: single words collide
# with tool names ("Jenkins", "Docker"). Add a colleague's first name to blocklist.txt if it matters.
NOT_A_PERSON = {"bot", "actions", "github", "gitlab", "jenkins", "ci", "automation", "service"}


def person_patterns(identities):
    """Regexes (longest first) for emails and multi-word names, plus 'First L', 'First L.' and 'F. Last'."""
    pats = set()
    for name, email in identities:
        if email and "bot" not in email.lower():
            pats.add(re.escape(email))
        tokens = name.split()
        if (len(tokens) >= 2 and all(len(re.sub(r"\W", "", t)) >= 2 for t in tokens)
                and not any(t.lower().strip("[]") in NOT_A_PERSON for t in tokens)):
            first, last = re.escape(tokens[0]), re.escape(tokens[-1])
            pats.add(r"\s+".join(map(re.escape, tokens)))
            pats.add(first + r"\s+" + re.escape(tokens[-1][0]) + r"\.?")
            pats.add(re.escape(tokens[0][0]) + r"\.\s*" + last)
    return sorted(pats, key=len, reverse=True)


def redact_people(text, patterns):
    count = 0
    for p in patterns:
        text, n = re.subn(r"(?<![A-Za-z0-9])" + p + r"(?![A-Za-z0-9])", "[person]", text, flags=re.IGNORECASE)
        count += n
    return text, count

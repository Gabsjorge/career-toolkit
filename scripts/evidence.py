"""Parse evidence.md items that have an Evidence ID. Never prints text."""
import pathlib, re

ITEM = re.compile(r"^- \*\*(E\d{4,})\*\* ")
TAGS = re.compile(r"_\(tags: (.*?)\)_")
LAB = re.compile(r"_\(kind: lab\)_")


def load(path):
    """{id: {"tags": set, "lab": bool}}; items without an ID are not citable and are skipped."""
    items = {}
    for line in pathlib.Path(path).read_text().splitlines():
        m = ITEM.match(line)
        if not m:
            continue
        tm = TAGS.search(line)
        tags = {t.strip() for t in tm.group(1).split(",") if t.strip()} if tm else set()
        items[m.group(1)] = {"tags": tags, "lab": bool(LAB.search(line))}
    return items

"""Cheap English / Portuguese detector (stop-word counts). Prints en, pt or unknown."""
import pathlib, re, sys

EN = set("the and of to in for with you we our your are is a an will be on as at by this that from or have".split())
PT = set("o a os as de da do das dos e em para com você voce nós nos nosso nossa seu sua é são um uma será "
         "por que na no nas nos ao à pela pelo ou tem ter estamos vai".split())
MIN_HITS = 4


def detect(text):
    words = re.findall(r"[a-zà-ú]+", text.lower())
    en = sum(w in EN for w in words)
    pt = sum(w in PT for w in words)
    if max(en, pt) < MIN_HITS or en == pt:
        return "unknown"
    return "en" if en > pt else "pt"


def main(argv):
    if len(argv) != 1:
        print("usage: pipeline.py detect-lang FILE", file=sys.stderr)
        return 64
    print(detect(pathlib.Path(argv[0]).read_text()))
    return 0

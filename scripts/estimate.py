import math, pathlib, sys


def estimate_tokens(text):
    return math.ceil(len(text) / 4)


def estimate(digests_dir, cap_tokens, price_per_mtok):
    files = sorted(pathlib.Path(digests_dir).glob("*.md"))
    total = sum(estimate_tokens(f.read_text()) for f in files)
    out = total // 4
    return {"input_tokens": total, "est_output_tokens": out,
            "est_cost_usd": round((total + out) * price_per_mtok / 1_000_000, 4),
            "cap_tokens": cap_tokens, "over_cap": total > cap_tokens, "files": len(files)}


def estimate_files(files, cap_tokens, price_per_mtok):
    total = sum(estimate_tokens(pathlib.Path(f).read_text()) for f in files)
    out = total // 4
    return {"input_tokens": total, "est_output_tokens": out,
            "est_cost_usd": round((total + out) * price_per_mtok / 1_000_000, 4),
            "cap_tokens": cap_tokens, "over_cap": total > cap_tokens, "files": len(files)}


def main_files(argv):
    """estimate-files CAP PRICE FILE...: input estimate for files a model step will read."""
    if len(argv) < 3:
        print("usage: pipeline.py estimate-files CAP PRICE FILE...", file=sys.stderr)
        return 64
    r = estimate_files(argv[2:], int(argv[0]), float(argv[1]))
    print(f"{r['files']} files, ~{r['input_tokens']} input tokens, ~{r['est_output_tokens']} output tokens, "
          f"est. cost ~${r['est_cost_usd']} (input files only; excludes prompts)")
    if r["over_cap"]:
        print(f"OVER CAP ({r['cap_tokens']} tokens): stop and ask the user before any model call")
        return 2
    print(f"under cap ({r['cap_tokens']} tokens)")
    return 0


def main(argv):
    r = estimate(argv[0], int(argv[1]), float(argv[2]))
    print(f"digests: {r['files']} files, ~{r['input_tokens']} input tokens, "
          f"~{r['est_output_tokens']} output tokens, est. cost ~${r['est_cost_usd']} "
          "(digest input only; excludes the prompts and later stages)")
    if r["over_cap"]:
        print(f"OVER CAP ({r['cap_tokens']} tokens): stop and ask the user before any model call")
        return 2
    print(f"under cap ({r['cap_tokens']} tokens)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

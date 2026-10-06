"""place-art.py: run a recipe and write its output into an art fence of a Markdown file, so the fence is generated,
never retyped.

Usage:
    python place-art.py RECIPE.py FILE.md [--block N]

RECIPE.py is a script that prints the picture (see examples/). FILE.md gets the Nth art fence (``` with no info string
or text/ascii/txt; default N = 1) replaced by that output, nothing else changed. Trailing spaces are stripped from
every output line. Exit 0 on success, 1 when the file has no Nth art fence or the recipe fails, 2 on a usage error.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ART_INFO = ("", "text", "ascii", "txt")


def replace_block(text, n, art):
    """Return text with the contents of its Nth art fence replaced by art, or None when there is no such fence."""
    lines = text.split("\n")
    seen = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            fence_len = len(line) - len(line.lstrip("`"))
            info = line[fence_len:].strip()
            j = i + 1
            while j < len(lines) and not (lines[j] and lines[j].strip("`") == "" and len(lines[j]) >= fence_len):
                j += 1
            if j >= len(lines):
                return None
            if info in ART_INFO:
                seen += 1
                if seen == n:
                    body = [ln.rstrip(" ") for ln in art.rstrip("\n").split("\n")]
                    return "\n".join(lines[:i + 1] + body + lines[j:])
            i = j + 1
            continue
        i += 1
    return None


def main():
    ap = argparse.ArgumentParser(prog="place-art.py")
    ap.add_argument("recipe")
    ap.add_argument("file")
    ap.add_argument("--block", type=int, default=1)
    args = ap.parse_args()
    recipe, target = Path(args.recipe), Path(args.file)
    if not recipe.is_file() or not target.is_file() or args.block < 1:
        print("usage: python place-art.py RECIPE.py FILE.md [--block N]", file=sys.stderr)
        return 2
    run = subprocess.run([sys.executable, str(recipe)], capture_output=True, text=True, encoding="utf-8",
                         env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    if run.returncode != 0:
        print(run.stderr, file=sys.stderr)
        return 1
    text = target.read_text(encoding="utf-8")
    new = replace_block(text, args.block, run.stdout)
    if new is None:
        print(f"{target}: no art fence number {args.block}", file=sys.stderr)
        return 1
    target.write_text(new, encoding="utf-8", newline="\n")
    width = max(len(ln) for ln in run.stdout.rstrip("\n").split("\n"))
    print(f"placed {recipe.name} into {target} block {args.block}: {width} columns")
    return 0


if __name__ == "__main__":
    sys.exit(main())

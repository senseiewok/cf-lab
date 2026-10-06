"""Test for check-ascii.py (rendering and accessibility checks for ASCII art blocks in Markdown).

Usage: python test-check-ascii.py [check-ascii.py]   -> one FAIL line per failing check; prints VERIFIED and exits 0 only when all pass.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

cand = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / "check-ascii.py"
fails = []
TMP = Path(tempfile.mkdtemp(prefix="asciichk "))
N = [0]


def run(md, *args, name=None):
    N[0] += 1
    f = TMP / (name or f"case{N[0]}.md")
    f.write_text(md, encoding="utf-8", newline="")
    p = subprocess.run([sys.executable, str(cand), *args, str(f)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    return f, p


def check(name, ok, detail=""):
    if not ok:
        fails.append(f"FAIL {name} {detail}".strip())


def findings(p, f):
    out = []
    for ln in p.stdout.splitlines():
        m = re.match(r"^(ERROR|WARN) (.+):(\d+): ([a-z-]+): (.+)$", ln)
        if m and m.group(2) == str(f):
            out.append((m.group(1), int(m.group(3)), m.group(4)))
    return out


def summary(p):
    m = re.search(r"^(\d+) art block\(s\) checked: (\d+) error\(s\), (\d+) warning\(s\)$", p.stdout, re.M)
    return tuple(int(x) for x in m.groups()) if m else None


FRAME = "+------------------+\n|  a quiet field   |\n+------------------+"
GOOD = f"# Title\n\n```\n{FRAME}\n```\n\n> A short line that says what the picture shows.\n"

f, p = run(GOOD)
check("clean file exits 0", p.returncode == 0, f"rc={p.returncode} out={p.stdout[:200]!r} err={p.stderr[:100]!r}")
check("clean file summary", summary(p) == (1, 0, 0), str(summary(p)))
check("clean file has no findings", findings(p, f) == [])

f, p = run("```python\n\tprint('x')   \n```\n")
check("non-art fences are skipped", p.returncode == 0 and summary(p) == (0, 0, 0), f"{p.returncode} {summary(p)}")

for tag in ("text", "ascii", "txt"):
    f, p = run(f"```{tag}\n\tx\n```\n\n> says.\n")
    check(f"fence tagged {tag} is checked", summary(p) is not None and summary(p)[0] == 1, str(summary(p)))

f, p = run("```\nab\tcd\n```\n\n> says.\n")
fi = findings(p, f)
check("tab is an error on its own line", p.returncode == 1 and ("ERROR", 2, "tab") in fi, f"{p.returncode} {fi}")

f, p = run("```\nab\x1b[31mcd\n```\n\n> says.\n")
check("escape sequence is a control-char error", p.returncode == 1 and ("ERROR", 2, "control-char") in findings(p, f), str(findings(p, f)))

f, p = run("```\nab\x07cd\n```\n\n> says.\n")
check("bell is a control-char error", ("ERROR", 2, "control-char") in findings(p, f), str(findings(p, f)))

f, p = run("```\n" + "x" * 60 + "\n```\n\n> says.\n")
check("60 columns pass the default", p.returncode == 0 and summary(p) == (1, 0, 0), f"{p.returncode} {summary(p)}")
f, p = run("```\nok\n" + "x" * 61 + "\n```\n\n> says.\n")
check("61 columns is too-wide on its line", p.returncode == 1 and ("ERROR", 3, "too-wide") in findings(p, f), str(findings(p, f)))
f, p = run("```\n" + "x" * 41 + "\n```\n\n> says.\n", "--max-width", "40")
check("--max-width is honoured", ("ERROR", 2, "too-wide") in findings(p, f), str(findings(p, f)))
f, p = run("```\n" + "x" * 41 + "\n```\n\n> says.\n", "--max-width", "41")
check("--max-width 41 accepts 41", not [x for x in findings(p, f) if x[2] == "too-wide"], str(findings(p, f)))

ROSE = "\U0001F339"
f, p = run("```\n" + ROSE * 30 + "\n```\n\n> says.\n")
fi = findings(p, f)
check("30 wide glyphs are 60 columns: no too-wide, but a wide-glyph warning", not [x for x in fi if x[2] == "too-wide"] and ("WARN", 2, "wide-glyph") in fi and p.returncode == 0, f"{fi} rc={p.returncode}")
f, p = run("```\n" + ROSE * 31 + "\n```\n\n> says.\n")
check("31 wide glyphs are 62 columns: too-wide", ("ERROR", 2, "too-wide") in findings(p, f), str(findings(p, f)))
f, p = run("```\n" + "é" * 60 + "\n```\n\n> says.\n")
check("combining marks have zero width", not [x for x in findings(p, f) if x[2] == "too-wide"], str(findings(p, f)))
f, p = run("```\n" + "█" * 60 + "\n```\n\n> says.\n")
check("block elements are one column each and are not wide-glyph", summary(p) == (1, 0, 0), str(summary(p)))

f, p = run("```\n" + FRAME + "\n```\n\n## Next heading\n")
check("art followed by a heading has no description", p.returncode == 1 and ("ERROR", 5, "no-description") in findings(p, f), str(findings(p, f)))
f, p = run("```\n" + FRAME + "\n```\n")
check("art at the end of the file has no description", ("ERROR", 5, "no-description") in findings(p, f), str(findings(p, f)))
f, p = run("```\n" + FRAME + "\n```\nA plain paragraph right after.\n")
check("a paragraph directly after counts", not [x for x in findings(p, f) if x[2] == "no-description"], str(findings(p, f)))
f, p = run("```\n" + FRAME + "\n```\n\n\n> after two blank lines.\n")
check("blank lines before the description are fine", not [x for x in findings(p, f) if x[2] == "no-description"], str(findings(p, f)))
f, p = run("```\n" + FRAME + "\n```\n\n```python\nx = 1\n```\n")
check("a code fence after the art is not a description", ("ERROR", 5, "no-description") in findings(p, f), str(findings(p, f)))
f, p = run("```\n" + FRAME + "\n```\n\n| a | b |\n| - | - |\n")
check("a table is not a description", ("ERROR", 5, "no-description") in findings(p, f), str(findings(p, f)))

BAD_FRAME = "+------------------+\n|  a quiet field  |\n+------------------+"
f, p = run(f"```\n{BAD_FRAME}\n```\n\n> says.\n")
check("ragged frame is an error on the short line", p.returncode == 1 and ("ERROR", 3, "ragged-frame") in findings(p, f), str(findings(p, f)))
BOX = "┌───┐\n│  │\n└───┘"
f, p = run(f"```\n{BOX}\n```\n\n> says.\n")
check("ragged single-line box is detected", ("ERROR", 3, "ragged-frame") in findings(p, f), str(findings(p, f)))
f, p = run("```\n+------+\n|      |\n+-----+\n```\n\n> says.\n")
check("a short bottom edge is a ragged frame on the last line", ("ERROR", 4, "ragged-frame") in findings(p, f), str(findings(p, f)))
f, p = run("```\n+---+\nnot a frame\n```\n\n> says.\n")
check("text that merely starts with a plus is not a frame", not [x for x in findings(p, f) if x[2] == "ragged-frame"], str(findings(p, f)))

f, p = run("```\nabc   \n```\n\n> says.\n")
check("trailing spaces are a warning and exit 0", p.returncode == 0 and ("WARN", 2, "trailing-space") in findings(p, f), f"{p.returncode} {findings(p, f)}")
f, p = run("```\nabc   \n```\n\n> says.\n", "--strict")
check("--strict turns warnings into exit 1", p.returncode == 1, str(p.returncode))

f, p = run("```\nabc\n\n> never closed\n")
check("an unclosed fence is an error on the opening line", p.returncode == 1 and ("ERROR", 1, "unclosed-fence") in findings(p, f), str(findings(p, f)))

f, p = run("````\n```\nx\n```\n````\n\n> says.\n")
check("a longer fence is closed only by an equal or longer fence", summary(p) is not None and summary(p)[0] == 1 and p.returncode == 0, f"{summary(p)} {p.returncode} {findings(p, f)}")

# two blocks, counts add up
two = f"```\n{FRAME}\n```\n\n> one.\n\n```\n\tx   \n```\n"
f, p = run(two)
check("two blocks: counts", summary(p) == (2, 2, 1) or summary(p) == (2, 2, 0) or (summary(p) and summary(p)[0] == 2 and summary(p)[1] >= 2), str(summary(p)))

# command line
f = TMP / "ok.md"
f.write_text(GOOD, encoding="utf-8")
g = TMP / "bad.md"
g.write_text("```\n\tx\n```\n", encoding="utf-8")
p = subprocess.run([sys.executable, str(cand), str(f), str(g)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
check("several files: counts are totals and exit is 1", p.returncode == 1 and summary(p) is not None and summary(p)[0] == 2, f"{p.returncode} {summary(p)}")
p = subprocess.run([sys.executable, str(cand)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
check("no arguments is a usage error (exit 2)", p.returncode == 2, str(p.returncode))
p = subprocess.run([sys.executable, str(cand), str(TMP / "missing.md")], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
check("a missing file is a usage error (exit 2)", p.returncode == 2, str(p.returncode))
crlf = TMP / "crlf.md"
crlf.write_bytes(GOOD.replace("\n", "\r\n").encode("utf-8"))
p = subprocess.run([sys.executable, str(cand), str(crlf)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
check("CRLF files are read like LF files", p.returncode == 0 and summary(p) == (1, 0, 0), f"{p.returncode} {summary(p)} {p.stdout[:150]!r}")

# invisible format characters (added 2026-10-05 after a word joiner was found in a hand-retyped fence)
f, p = run("```\nab⁠cd\n```\n\n> says.\n")
check("a word joiner inside the art is an invisible-char error", p.returncode == 1 and ("ERROR", 2, "invisible-char") in findings(p, f), f"{p.returncode} {findings(p, f)}")
f, p = run("```\n​ab\n```\n\n> says.\n")
check("a zero-width space is an invisible-char error", ("ERROR", 2, "invisible-char") in findings(p, f), str(findings(p, f)))
f, p = run("```\nab­cd\n```\n\n> says.\n")
check("a soft hyphen is an invisible-char error", ("ERROR", 2, "invisible-char") in findings(p, f), str(findings(p, f)))
f, p = run("```\n" + "⠀" * 60 + "\n```\n\n> says.\n")
check("a blank Braille cell U+2800 is visible, one column wide and not wide-glyph", p.returncode == 0 and summary(p) == (1, 0, 0), f"{p.returncode} {summary(p)} {findings(p, f)}")
f, p = run("```\n" + "⠀" * 61 + "\n```\n\n> says.\n")
check("61 Braille cells are too-wide", ("ERROR", 2, "too-wide") in findings(p, f), str(findings(p, f)))
f, p = run("```\n⁠\n```\n\n> says.\n")
check("a line that is only a word joiner is still an error, not blank", ("ERROR", 2, "invisible-char") in findings(p, f), str(findings(p, f)))

# ---- companion scripts next to the checker: place-art.py (generated fences) and preview-ascii.py (rendered preview)
import importlib.util  # noqa: E402


def load(name):
    path = cand.parent / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    place = load("place-art.py")
    MD = "# T\n\n```python\nkeep = 1\n```\n\n```text\nold   \n```\n\n> one.\n\n```\nsecond\n```\n\n> two.\n"
    new = place.replace_block(MD, 1, "a\nbb  \n")
    check("place-art replaces the first art fence only and strips trailing spaces", new == MD.replace("old   ", "a\nbb"), repr(new))
    new2 = place.replace_block(MD, 2, "z")
    check("place-art --block 2 skips the python fence and replaces the second art fence", new2 == MD.replace("second", "z"), repr(new2))
    check("place-art returns None when there is no such fence", place.replace_block(MD, 3, "z") is None and place.replace_block("no fence", 1, "z") is None, "")
    recipe = TMP / "recipe.py"
    recipe.write_text("print('x')\nprint('yy')\n", encoding="utf-8")
    target = TMP / "place.md"
    target.write_text("```text\nold\n```\n\n> says.\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(cand.parent / "place-art.py"), str(recipe), str(target)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    check("place-art writes the recipe's output into the fence and exits 0", p.returncode == 0 and target.read_text(encoding="utf-8") == "```text\nx\nyy\n```\n\n> says.\n", f"{p.returncode} {target.read_text(encoding='utf-8')!r} {p.stderr[:120]!r}")
    nofence = TMP / "nofence.md"
    nofence.write_text("plain\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(cand.parent / "place-art.py"), str(recipe), str(nofence)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    check("place-art exits 1 when the file has no art fence", p.returncode == 1, str(p.returncode))
    p = subprocess.run([sys.executable, str(cand.parent / "place-art.py"), str(recipe), str(TMP / "missing.md")], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    check("place-art exits 2 on a missing file", p.returncode == 2, str(p.returncode))
    bad = TMP / "bad_recipe.py"
    bad.write_text("raise SystemExit(3)\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(cand.parent / "place-art.py"), str(bad), str(target)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    check("place-art exits 1 when the recipe fails and leaves the file alone", p.returncode == 1 and target.read_text(encoding="utf-8") == "```text\nx\nyy\n```\n\n> says.\n", str(p.returncode))
except FileNotFoundError:
    fails.append("FAIL place-art.py is missing next to the checker")

try:
    prev = load("preview-ascii.py")
    blocks = prev.extract_blocks("```python\nz\n```\n\n```text\n art \n```\n\n*alt line*\n> story\n\nnot after\n")
    check("preview extract_blocks skips a python fence and keeps the lines right after the art", len(blocks) == 1 and blocks[0][1] == [" art "] and blocks[0][2] == ["*alt line*", "> story"], repr(blocks))
    page = prev.build_html(blocks)
    check("preview build_html puts the art in a pre and the story in a blockquote", "<pre data-block='1'> art </pre>" in page and "<blockquote>story</blockquote>" in page and "<p>*alt line*</p>" in page, page[-200:])
    check("preview build_html escapes the art", "&lt;" in prev.build_html([(1, ["<x>"], [])]), "")
    src = TMP / "prev.md"
    src.write_text("```text\nab\n```\n\n> says.\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(cand.parent / "preview-ascii.py"), str(src), "--html-only", "--out", str(TMP / "prev-out")], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    check("preview --html-only writes preview.html and exits 0 without a browser", p.returncode == 0 and (TMP / "prev-out" / "preview.html").is_file() and "1 art block(s)" in p.stdout, f"{p.returncode} {p.stdout[:120]!r} {p.stderr[:120]!r}")
    p = subprocess.run([sys.executable, str(cand.parent / "preview-ascii.py"), str(TMP / "missing.md"), "--html-only"], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    check("preview exits 2 on a missing file", p.returncode == 2, str(p.returncode))
    p = subprocess.run([sys.executable, str(cand.parent / "preview-ascii.py"), str(src), "--html-only", "--widths", "a,b"], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    check("preview exits 2 on bad --widths", p.returncode == 2, str(p.returncode))
except FileNotFoundError:
    fails.append("FAIL preview-ascii.py is missing next to the checker")

print("\n".join(fails[:25]))
print("VERIFIED" if not fails else f"{len(fails)} failing check(s)")
sys.exit(1 if fails else 0)

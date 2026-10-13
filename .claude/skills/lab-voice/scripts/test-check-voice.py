"""Tests for check-voice.py (American spelling, long sentences, repetition, label templates, page length).

Usage: python test-check-voice.py [check-voice.py]   -> one FAIL line per failing check; prints VERIFIED and exits 0 only when all pass.
Standard library only; writes only to a temporary folder; reads no repository page.

Every "does not warn / passes" check also asserts exit 0 and a SUMMARY line for the file, so a crash or a changed
output format cannot pass as "no finding".
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

cand = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / "check-voice.py"
fails = []
TMP = Path(tempfile.mkdtemp(prefix="voicechk "))
N = [0, 0]


def write(text, suffix=".html", name=None):
    N[0] += 1
    f = TMP / (name or f"case{N[0]}{suffix}")
    f.write_text(text, encoding="utf-8", newline="")
    return f


def run(*args):
    p = subprocess.run([sys.executable, str(cand), *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    p.files = [str(a) for a in args if isinstance(a, Path) and a.suffix != ".txt"]  # .txt here is an --allow file
    return p


def page(body, lang="en"):
    return f"<!doctype html>\n<html lang=\"{lang}\">\n<head><title>Test page</title></head>\n<body>\n{body}\n</body>\n</html>\n"


def check(name, ok, detail=""):
    N[1] += 1
    if not ok:
        fails.append(f"FAIL {name} {detail}".strip())


def summarized(p):
    """True when every file named got a SUMMARY line and the final count line is present."""
    out = p.stdout
    return (all(re.search(rf"^SUMMARY {re.escape(f)}: \d+ words, \d+ error\(s\), \d+ warning\(s\)$", out, re.M) for f in p.files)
            and re.search(r"^\d+ file\(s\) checked: \d+ error\(s\), \d+ warning\(s\)$", out, re.M) is not None)


def findings(p, level=None, rule=None):
    out = []
    for ln in p.stdout.splitlines():
        m = re.match(r"^(ERROR|WARN) (.+):(\d+): ([a-z-]+): (.+)$", ln)
        if m and (level is None or m.group(1) == level) and (rule is None or m.group(4) == rule):
            out.append((m.group(1), int(m.group(3)), m.group(4), m.group(5)))
    return out


def clean(p, level=None, rule=None):
    """A negative result that counts: exit 0, summary lines present, and no matching finding."""
    return p.returncode == 0 and summarized(p) and not findings(p, level, rule)


def failed_with(p, msgs):
    return p.returncode == 1 and summarized(p) and sorted(x[3] for x in findings(p, "ERROR")) == sorted(msgs)


# --- (a) spelling: prose fails, quotes pass -------------------------------------------------
f = write(page("<blockquote><p>You may not change the licence.</p></blockquote>"))
p = run(f)
check("licence inside a blockquote passes", clean(p, "ERROR"), p.stdout)

f = write(page("<p>You may not change the licence.</p>"))
p = run(f)
e = findings(p, "ERROR", "uk-spelling")
check("licence in prose fails with exit 1", failed_with(p, ["'licence' -> 'license'"]), p.stdout)
check("the error names the line", e and e[0][1] == 5, str(e))

f = write(page("<p>A <q>colour</q> and <cite>Journal of Behaviour</cite>.</p>"))
check("q and cite pass", clean(run(f), "ERROR"))

f = write(page("<p>Use <code>colour</code>.</p>\n<pre>organisation = 1</pre>\n<script>var centre = 1</script>"))
check("code, pre and script pass", clean(run(f), "ERROR"))

f = write(page('<p lang="es-MX">colour organisation</p>\n<div lang="es"><p>centre <span lang="en">grey</span></p></div>'))
check("non-English lang passes, nested lang=en is checked again", failed_with(run(f), ["'grey' -> 'gray'"]))

f = write(page('<p>Abre el archivo en la computadora.</p><blockquote><p>Usa el ordenador.</p></blockquote>', lang="es-MX"))
check("Mexican Spanish (es-MX) prose and Spanish blockquote pass", clean(run(f), "ERROR"))

f = write(page('<p>Abre el fichero en el ordenador para vosotros con teléfono móvil.</p>', lang="es-MX"))
p_es = run(f)
check("Peninsular Spanish in es-MX fails with es-mx-spelling",
      failed_with(p_es, ["'fichero' -> 'archivo'", "'ordenador' -> 'computadora'", "'vosotros' -> 'ustedes'", "'teléfono móvil' -> 'teléfono celular'"])
      and all(x[2] == "es-mx-spelling" for x in findings(p_es, "ERROR")), p_es.stdout)

f = write(page('<p title="organisation"><a href="/centre/licence.html">Read</a> <img alt="colour"></p>'))
check("title and alt are checked; an href is not", failed_with(run(f), ["'organisation' -> 'organization'", "'colour' -> 'color'"]) and not any("centre" in l or "licence" in l for l in run(f).stdout.splitlines()))

f = write(page("<p>See https://example.org/organisation and www.centre.example then licence.txt and organisation_id and data/colour.</p>"))
p = run(f)
check("URLs, file names, identifiers and paths pass", clean(p, "ERROR"), p.stdout)

allow = write("# names that keep their spelling\nWorld Health Organisation\nCystic Fibrosis Trust Centre\n", ".txt")
f = write(page("<p>The World Health Organisation and the Cystic Fibrosis Trust Centre agree, but our colour differs.</p>"))
p = run("--allow", allow, f)
check("--allow phrases pass, other prose still fails", failed_with(p, ["'colour' -> 'color'"]), p.stdout)
p = run(f)
check("without --allow the names are flagged", p.returncode == 1 and summarized(p) and len(findings(p, "ERROR")) == 3, p.stdout)

f = write(page("<p>Ask a carer. The Centre is open. Prices rose 5 per cent.</p>"))
check("carer, capitalized Centre and 'per cent' are caught",
      failed_with(run(f), ["'carer' -> 'caregiver'", "'Centre' -> 'Center'", "'per cent' -> 'percent'"]))

f = write(page("<p>We analyse data, summarised and specialised, labelled towards ageing fibre in metres, a judgement in the catalogue.</p>"))
p = run(f)
got = {re.search(r"'([^']+)' ->", x[3]).group(1) for x in findings(p, "ERROR")}
want = {"analyse", "summarised", "specialised", "labelled", "towards", "ageing", "fibre", "metres", "judgement", "catalogue"}
check("the common UK forms in the table are caught", p.returncode == 1 and summarized(p) and got == want, str(sorted(want ^ got)))

f = write(page("<p>Our analyses show the license, the program, the center, color and gray are fine. Exercise, advise and promise too.</p>"))
p = run(f)
check("US spellings and -ise words that are US too pass", clean(p, "ERROR"), p.stdout)

md = ("---\ntitle: The licence\n---\n# Notes\n\n> The colour was quoted.\n\n```\norganisation\n```\n\n"
      "Inline `centre` code and a [link](https://x.org/licence) are fine.\n\n- A list item with colour\n")
f = write(md, ".md")
p = run(f)
check("markdown: front matter, block quote, fence, inline code and link URL pass; list prose fails",
      failed_with(p, ["'colour' -> 'color'"]) and findings(p, "ERROR")[0][1] == 14, p.stdout)

f = write('# Notes\n\nThe report says "the colour of the centre" and we agree.\n', ".md")
check("markdown: text inside quotation marks in prose passes", clean(run(f), "ERROR"))

# --- Markdown tables: spelling per cell, outside quotation marks ------------------------------
tab = ("| Claim | Source | Quote |\n| --- | --- | --- |\n"
       "| Grade did not matter. | \"The Readability Study: A Randomised Trial\", J Gen Intern Med | \"no evidence of a main effect\" |\n")
f = write("# Sources\n\n" + tab, ".md")
p = run(f)
check("table: 'Randomised' inside a quoted title passes", clean(p, "ERROR"), p.stdout)
f = write("# Sources\n\n" + tab + "\nThe trial was randomised.\n", ".md")
p = run(f)
check("table: the same word in a prose line fails", failed_with(p, ["'randomised' -> 'randomized'"]) and findings(p, "ERROR")[0][1] == 7, p.stdout)
f = write("| Item | Note |\n| --- | --- |\n| A | The colour is wrong |\n", ".md")
p = run(f)
check("table: 'colour' in a plain cell fails", failed_with(p, ["'colour' -> 'color'"]) and findings(p, "ERROR")[0][1] == 3, p.stdout)
f = write("| Item | Note |\n| --- | --- |\n| A | \"The colour is quoted\" |\n| B | “A centre, curly-quoted” |\n", ".md")
check("table: 'colour' in a quoted cell passes (straight and curly quotes)", clean(run(f), "ERROR"))
f = write("| Item | Link |\n| --- | --- |\n| A | https://example.org/colour/centre |\n", ".md")
check("table: URLs in cells pass", clean(run(f), "ERROR"))
f = write("".join(f"## Part {i}\n\n{tab}\n" for i in range(6)), ".md")
p = run(f)
check("table: repeated headers and rows are not label templates or repetition",
      clean(p, "WARN", "label-template") and clean(p, "WARN", "repetition"), p.stdout)

# --- (b) warnings: exit 0 ------------------------------------------------------------------
s30 = "We " + " ".join(f"word{i}" for i in range(28)) + " end."
s29 = "We " + " ".join(f"word{i}" for i in range(27)) + " end."
f = write(page(f"<p>{s30}</p>"))
p = run(f)
w = findings(p, "WARN", "long-sentence")
check("a 30-word sentence warns and exits 0", p.returncode == 0 and summarized(p) and w and "30 words" in w[0][3], p.stdout)
f = write(page(f"<p>{s29}</p>"))
check("a 29-word sentence does not warn", clean(run(f), "WARN", "long-sentence"))
q30 = " ".join(f"quoted{i}" for i in range(30))
f = write(page(f"<p>They wrote <q>{q30}</q> in the paper.</p>"))
check("an inline <q> does not count toward sentence length", clean(run(f), "WARN", "long-sentence"))
f = write(f'# T\n\nThey wrote "{q30}" in the paper.\n', ".md")
check("a Markdown inline quote does not count toward sentence length", clean(run(f), "WARN", "long-sentence"))

A = "Clean the nebulizer cups with warm soapy water after every single use."
B = "After every single use, wash the nebulizer cups in warm soapy water."
FILL = ["Rain fell over the harbor town all through the long night.", "A teacher explained fractions using slices of fresh orange.",
        "Trains to the coast leave twice an hour on summer weekends.", "Library cards are free for anyone who lives in the county.",
        "The violin needs new strings before the concert next month.", "Volunteers painted murals along the river path last spring."]
filler = "".join(f"<p>{s}</p>\n" for s in FILL)
f = write(page(f"<p>{A}</p>\n{filler}<p>{B}</p>"))
p = run(f)
rep = findings(p, "WARN", "repetition")
check("same idea far apart (not adjacent) warns once", p.returncode == 0 and summarized(p) and len(rep) == 1, p.stdout)
check("the repetition warning quotes both sentences", rep and "Clean the nebulizer" in rep[0][3] and "wash the nebulizer" in rep[0][3], str(rep))
f = write(page(f"<p>--json--</p><p>{A}</p>{filler}<p>{B}</p>"))
pj = run("--json", f)
data = json.loads(pj.stdout)
rj = [w for w in data["files"][str(f)]["warnings"] if w["rule"] == "repetition"]
check("--json gives both sentence positions", pj.returncode == 0 and rj and rj[0]["sentence"] < rj[0]["other_sentence"] and rj[0]["other_line"] > rj[0]["line"], str(rj))

f = write(page("<p>Wash cups in water.</p><p>Wash cups in water.</p>"))
check("sentences under 6 words are not compared", clean(run(f), "WARN", "repetition"))
f = write(page("<p>Clean the nebulizer cups with warm soapy water after every use.</p><p>Ask the care team which airway clearance routine fits your day.</p>"))
check("different ideas are not reported", clean(run(f), "WARN", "repetition"))
f = write(page(f"<p>They said <q>{A}</q></p>{filler}<p>{B}</p>"))
check("an inline <q> is not compared for repetition", clean(run(f), "WARN", "repetition"))
f = write(f'# T\n\nThey said "{A}"\n\n' + "\n\n".join(FILL) + f"\n\n{B}\n", ".md")
check("a Markdown inline quote is not compared for repetition", clean(run(f), "WARN", "repetition"))

# deliberate repeats
f = write(page(f"<p>{A}</p>\n{filler}<p data-voice=\"repeat\">{B}</p>"))
check("data-voice=repeat suppresses the repetition warning", clean(run(f), "WARN", "repetition"))
f = write(f"# T\n\n{A}\n\n" + "\n\n".join(FILL) + f"\n\n<!-- voice: repeat -->\n{B}\n", ".md")
check("<!-- voice: repeat --> suppresses the repetition warning", clean(run(f), "WARN", "repetition"))
f = write(f"# T\n\n{A}\n\n" + "\n\n".join(FILL) + f"\n\n<!-- voice: repeat -->\nUnmarked one.\n\n{B}\n", ".md")
p = run(f)
check("the Markdown marker covers only the very next block", len(findings(p, "WARN", "repetition")) == 1 and summarized(p), p.stdout)
f = write(f"# T\n\n{A}\n\n" + "\n\n".join(FILL) + f"\n\n<!-- voice: repeat -->\n\n{B}\n", ".md")
p = run(f)
check("a blank line after the Markdown marker cancels it", len(findings(p, "WARN", "repetition")) == 1 and summarized(p), p.stdout)
f = write(f"# T\n\n{A}\n\n" + "\n\n".join(FILL) + f"\n\n<!-- voice: repeat -->\n```\ncode\n```\n{B}\n", ".md")
p = run(f)
check("a code fence after the Markdown marker cancels it", len(findings(p, "WARN", "repetition")) == 1 and summarized(p), p.stdout)
f = write(page(f"<p>{A} <span data-voice=\"repeat\">See step 2.</span></p>\n{filler}<p>{B}</p>"))
p = run(f)
check("data-voice on an inline span does not exempt its block", len(findings(p, "WARN", "repetition")) == 1 and summarized(p), p.stdout)
f = write(page(f"<p>{A}</p>\n{filler}<div data-voice=\"repeat\"><p>{B}</p></div>"))
p = run(f)
check("data-voice on a parent block does not reach a child block", len(findings(p, "WARN", "repetition")) == 1 and summarized(p), p.stdout)
f = write(page(f"<p>{A}</p>\n{filler}<li data-voice=\"repeat\">{B}</li>"))
check("data-voice on the block element itself (li) exempts it", clean(run(f), "WARN", "repetition"))
f = write("# T\n\n<blockquote>Read the licence first.</blockquote>\n", ".md")
check("markdown: inline <blockquote> is not honored (documented)", failed_with(run(f), ["'licence' -> 'license'"]))

card = "<article><h3>Study {i}</h3><p><strong>How strong:</strong> moderate, one trial number {i}.</p><p><a href='#'>Read the original</a></p></article>\n"
f = write(page("".join(card.format(i=i) for i in range(5))))
p = run(f)
labels = {re.match(r"'([^']+)'", x[3]).group(1) for x in findings(p, "WARN", "label-template")}
check("a label used 5 times warns (colon label and label-only block)", p.returncode == 0 and {"How strong", "Read the original"} <= labels, p.stdout)
f = write(page("".join(card.format(i=i) for i in range(4))))
check("a label used 4 times does not warn", clean(run(f), "WARN", "label-template"))
f = write(page("".join(card.replace("<p><strong>", "<p data-voice=\"repeat\"><strong>").replace("<p><a", "<p data-voice=\"repeat\"><a").format(i=i) for i in range(5))))
check("marked labels (data-voice=repeat) do not warn", clean(run(f), "WARN", "label-template"))
f = write("".join(f"## Study {i}\n\n**How strong:** moderate, trial {i}.\n\n" for i in range(5)), ".md")
p = run(f)
check("markdown bold labels count too", p.returncode == 0 and any("How strong" in x[3] for x in findings(p, "WARN", "label-template")), p.stdout)
f = write("".join(f"## Study {i}\n\n<!-- voice: repeat -->\n**How strong:** moderate, trial {i}.\n\n" for i in range(5)), ".md")
check("markdown marked labels do not warn", clean(run(f), "WARN", "label-template"))

f = write(page("<p>" + "Short plain words here. " * 460 + "</p>"))
p = run(f)
check("over 1,800 words warns by default", p.returncode == 0 and summarized(p) and findings(p, "WARN", "page-length"), p.stdout[-300:])
f = write(page("<p>" + "Short plain words here. " * 100 + "</p>"))
check("400 words is under the default budget", clean(run(f), "WARN", "page-length"))
check("--budget lowers the budget", findings(run("--budget", "300", f), "WARN", "page-length"))

p = run(f)
check("Flesch-Kincaid grade is informational", re.search(r"^INFO .*reading-grade: Flesch-Kincaid -?\d+\.\d", p.stdout, re.M), p.stdout[-300:])
check("per-file summary line", re.search(r"^SUMMARY .+: \d+ words, 0 error\(s\), 0 warning\(s\)$", p.stdout, re.M), p.stdout[-300:])
check("final count line", re.search(r"^1 file\(s\) checked: 0 error\(s\), 0 warning\(s\)$", p.stdout, re.M), p.stdout[-200:])

# --- usage and self-test -------------------------------------------------------------------
p = run(TMP / "missing.html")
check("a missing file is a usage error (exit 2)", p.returncode == 2 and "not a file" in p.stderr, f"rc={p.returncode}")
p = run()
check("no file is a usage error (exit 2)", p.returncode == 2)
p = run("--self-test")
check("--self-test passes", p.returncode == 0 and re.search(r"^(\d+)/\1 passed$", p.stdout, re.M), p.stdout[-300:])

f = write(page('<img src="x.png" alt="A grey bar"><a href="#" aria-label="Open the centre page">go</a><p>Fine words here.</p>'), suffix=".html")
p = run(f)
check("attribute text a reader meets is checked: alt and aria-label", len(findings(p, "ERROR", "uk-spelling")) == 2 and p.returncode == 1, p.stdout)
f = write(page('<p>Fine.</p>').replace("<head>", '<head><meta name="description" content="Help that organisations offer."><meta property="og:image:alt" content="A coloured drawing"><meta name="author" content="colour">'), suffix=".html")
p = run(f)
check("a meta description and social-card text are checked; other meta is not", len(findings(p, "ERROR", "uk-spelling")) == 2, p.stdout)
f = write(page('<p lang="es-MX"><img src="y.png" alt="organización centro"></p><code title="colour">x</code><p>One short sentence.</p>'), suffix=".html")
p = run(f)
check("an attribute in other-language text or code is not checked", p.returncode == 0 and not findings(p, "ERROR"), p.stdout)
f = write(page('<img src="x.png" alt="' + "word " * 40 + '"><p>Four short words.</p>'), suffix=".html")
p = run(f)
check("attribute text does not count as words or sentences", "SUMMARY" in p.stdout and re.search(r"SUMMARY .*: 5 words", p.stdout) and not findings(p, "WARN"), p.stdout)
f = write(page("<p>Read more ↗ on our page about cystic fibrosis.</p>"), suffix=".html")
env = {**os.environ, "PYTHONIOENCODING": "cp1252"}  # a console that cannot encode the arrow
p = subprocess.run([sys.executable, str(cand), str(f)], capture_output=True, encoding="utf-8", errors="replace", env=env, stdin=subprocess.DEVNULL, timeout=60)
check("a character the console cannot encode does not crash the checker", "Traceback" not in p.stderr and p.returncode in (0, 1) and "SUMMARY" in p.stdout, p.stderr[-300:])

shutil.rmtree(TMP, ignore_errors=True)
for x in fails:
    print(x)
if fails:
    print(f"{len(fails)} of {N[1]} checks failed")
    sys.exit(1)
print(f"VERIFIED: {N[1]} checks passed")

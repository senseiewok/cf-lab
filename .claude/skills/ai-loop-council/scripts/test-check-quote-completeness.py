"""Test for check-quote-completeness.py (board T-0028), written before the script. Prints one FAIL line per problem; exit 0 only when none.

Usage: python test-check-quote-completeness.py [SCRIPT.py]   (default: the sibling script)
The fixture text below is SYNTHETIC (invented for this test); it models the 2026-10-04 ECFSPR incident, in which a truncated
prefix of a sentence was supplied as a "verified quote" and two drafts then claimed the definition 'returns to only' the first criterion.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

cand = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / "check-quote-completeness.py"
fails = []

SOURCE = (
    "Definitions\n\n"
    "Registry definitions changed between report years.\n\n"
    "Chronic infection is defined as at least three positive cultures in 12 months\n"
    "(modified Leeds criteria), or one positive culture plus raised antibody titres.\n"
    "The 2020 report used the same definition. Fewer than five centres reported outliers (e.g. when samples were lost). "
    "See Fig. 3 for details.\n\n"
    "The “core” group – adults only – was larger.\n"
)
S = "Chronic infection is defined as at least three positive cultures in 12 months (modified Leeds criteria), or one positive culture plus raised antibody titres."

CASES = [
    ("after-heading", "Registry definitions changed between report years.", "PASS"),
    ("heading-only", "Definitions", "PASS"),
    ("complete", S, "PASS"),
    ("complete-no-final-period", S.rstrip("."), "PASS"),
    ("truncated-prefix", "Chronic infection is defined as at least three positive cultures in 12 months (modified Leeds criteria)", "ends mid-sentence"),
    ("suffix-only", "or one positive culture plus raised antibody titres.", "starts mid-sentence"),
    ("middle-fragment", "at least three positive cultures in 12 months", "mid-sentence"),
    ("two-sentences", "The 2020 report used the same definition. Fewer than five centres reported outliers (e.g. when samples were lost).", "PASS"),
    ("abbreviation-inside", "Fewer than five centres reported outliers (e.g. when samples were lost).", "PASS"),
    ("abbreviation-fig", "See Fig. 3 for details.", "PASS"),
    ("ends-at-abbreviation", "Fewer than five centres reported outliers (e.g.", "ends mid-sentence"),
    ("typographic", 'The "core" group - adults only - was larger.', "PASS"),
    ("not-found", "Chronic infection is defined as two positive cultures.", "not found"),
    ("empty", "", "not found"),
]


def run(args, source_text=SOURCE, quotes=None, raw_quotes=None, source_path=None):
    d = Path(tempfile.mkdtemp(prefix="qc "))
    sp = d / "source.txt"
    sp.write_text(source_text, encoding="utf-8", newline="\n")
    qp = d / "quotes.json"
    qp.write_text(raw_quotes if raw_quotes is not None else json.dumps(quotes), encoding="utf-8")
    cmd = [sys.executable, str(cand)] + [str(source_path or sp), str(qp)] + args
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout, p.stderr


def lines(out):
    return [l.rstrip() for l in out.splitlines() if l.strip()]


try:
    rc, out, err = run([], quotes=[{"id": cid, "text": t} for cid, t, _ in CASES])
    L = lines(out)
    if rc != 1:
        fails.append(f"FAIL with failing quotes the exit code must be 1, got {rc}. stderr: {err.strip()[:200]!r}")
    status = {}
    for l in L:
        for cid, _, _ in CASES:
            if l.startswith(f"PASS {cid}") and (len(l) == len(f"PASS {cid}") or l[len(f"PASS {cid}")] in " :"):
                status[cid] = ("PASS", l)
            elif l.startswith(f"FAIL {cid}:"):
                status[cid] = ("FAIL", l)
    for cid, text, want in CASES:
        got = status.get(cid)
        if got is None:
            fails.append(f"FAIL no output line for quote id '{cid}' (one 'PASS <id>' or 'FAIL <id>: <reason>' line per quote)")
        elif want == "PASS" and got[0] != "PASS":
            fails.append(f"FAIL quote '{cid}' is a complete sentence (or sentences) in the source and must PASS. Your output line was: {got[1]!r}. Quote text: {text[:90]!r}")
        elif want != "PASS" and (got[0] != "FAIL" or want not in got[1]):
            fails.append(f"FAIL quote '{cid}' must FAIL with '{want}' in the reason. Your output line was: {got[1]!r}. Quote text: {text[:90]!r}")
    order = [l.split()[1].rstrip(":") for l in L if l.startswith(("PASS ", "FAIL ")) and len(l.split()) > 1]
    if order != [c[0] for c in CASES]:
        fails.append(f"FAIL output lines must follow the input order of the quotes; got {order}")
    n_ok = sum(1 for _, _, w in CASES if w == "PASS")
    if not L or L[-1] != f"{n_ok} of {len(CASES)} quotes are complete sentences":
        fails.append(f"FAIL the last line must be '{n_ok} of {len(CASES)} quotes are complete sentences', got: {L[-1] if L else '(nothing)'}")

    # all passing -> exit 0
    good = [{"id": cid, "text": t} for cid, t, w in CASES if w == "PASS"]
    rc, out, err = run([], quotes=good)
    if rc != 0:
        fails.append(f"FAIL when every quote passes the exit code must be 0, got {rc}. The candidate printed (first 300 characters, one line): {out.strip()[:300]!r}")

    # usage errors -> exit 2 with an 'error:' line
    rc, out, err = run([], quotes=good, source_path=Path(tempfile.gettempdir()) / "no-such-source-file.txt")
    if rc != 2 or "error:" not in (out + err):
        fails.append(f"FAIL a missing source file must exit 2 with an 'error:' line, got {rc}")
    rc, out, err = run([], raw_quotes="{not json")
    if rc != 2 or "error:" not in (out + err):
        fails.append(f"FAIL invalid JSON must exit 2 with an 'error:' line, got {rc}")
    rc, out, err = run([], raw_quotes='{"id": "a", "text": "x"}')
    if rc != 2 or "error:" not in (out + err):
        fails.append(f"FAIL a JSON object instead of a list must exit 2 with an 'error:' line, got {rc}")

    # the empty list of quotes is a usage error too (a check that checks nothing must not look like a pass)
    rc, out, err = run([], quotes=[])
    if rc != 2:
        fails.append(f"FAIL an empty list of quotes must exit 2, got {rc}")

    # self-test
    p = subprocess.run([sys.executable, str(cand), "--self-test"], capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
    if p.returncode != 0 or "SELF-TEST OK" not in p.stdout:
        fails.append(f"FAIL --self-test must exit 0 and print SELF-TEST OK, got {p.returncode}: {(p.stdout + p.stderr).strip()[-200:]}")
except Exception as e:  # noqa: BLE001
    fails.append(f"FAIL the verifier could not finish: {type(e).__name__}: {e}")

# the frozen fixture folder must agree with the inline cases, and the OLD check must be shown to pass the failure
try:
    cdir = Path(__file__).resolve().parent.parent / "cases" / "truncated-quote"
    if cdir.is_dir():
        d = Path(tempfile.mkdtemp(prefix="qc case "))
        p = subprocess.run([sys.executable, str(cand), str(cdir / "source.txt"), str(cdir / "quotes.json")], capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
        got = {}
        for l in p.stdout.splitlines():
            if l.startswith("PASS "):
                got[l[5:].strip()] = "PASS"
            elif l.startswith("FAIL "):
                cid, _, reason = l[5:].partition(":")
                got[cid.strip()] = "FAIL " + " ".join(reason.split()[:2])
        for line in (cdir / "expected.txt").read_text(encoding="utf-8").splitlines():
            cid, _, want = line.partition("\t")
            if cid and not got.get(cid, "").startswith(want.split(" ")[0] if want == "PASS" else want):
                fails.append(f"FAIL frozen fixture cases/truncated-quote: quote '{cid}' expected {want!r}, got {got.get(cid)!r}")
        # the blind spot that motivated the check: a plain verbatim-substring check PASSES the truncated prefix
        src = " ".join((cdir / "source.txt").read_text(encoding="utf-8").split())
        trunc = next(q for q in json.loads((cdir / "quotes.json").read_text(encoding="utf-8")) if q["id"] == "truncated-prefix")["text"]
        if " ".join(trunc.split()) not in src:
            fails.append("FAIL the fixture is meant to show that the truncated prefix is verbatim in the source, and it is not")
        if got.get("truncated-prefix", "").startswith("PASS"):
            fails.append("FAIL the truncated prefix is verbatim in the source (so a plain substring check passes it) but this checker must reject it")
except Exception as e:  # noqa: BLE001
    fails.append(f"FAIL the fixture check could not finish: {type(e).__name__}: {e}")

for f in fails:
    print(f)
print("VERIFIED" if not fails else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)

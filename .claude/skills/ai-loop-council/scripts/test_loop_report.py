"""Test for loop-report.py (Loop v2.1 V2-05). Usage: python test_loop_report.py [SCRIPT]

Runs the report on the fixtures in loop-report-fixtures/ and compares every printed number with the value worked out by hand in this file.
One FAIL line per failing check; prints VERIFIED and exits 0 when all pass. Standard library only; no network, no model.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FX = HERE / "loop-report-fixtures"
SCRIPT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "loop-report.py"
fails = []


def check(name, ok, detail=""):
    if not ok:
        fails.append(name)
        print(f"FAIL {name}" + (f"  ({detail})" if detail else ""))


def run(args, cwd=None):
    p = subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True, cwd=cwd or tempfile.gettempdir(), timeout=60)
    return p.returncode, p.stdout, p.stderr


def blocks(text):
    """{header: [lines]} from a report: blocks are separated by one blank line."""
    out = {}
    for b in text.strip("\n").split("\n\n"):
        lines = b.split("\n")
        out[lines[0]] = lines[1:]
    return out


def compare(label, got_text, expected):
    got = blocks(got_text)
    check(f"{label}: the groups are {list(expected)} in that order", list(got) == list(expected), f"got {list(got)}")
    for header, want in expected.items():
        have = got.get(header, [])
        for i, w in enumerate(want):
            g = have[i] if i < len(have) else "<missing>"
            check(f"{label} {header} line {i + 1}: expected '{w}'", g == w, f"got '{g}'")
        check(f"{label} {header}: exactly {len(want)} lines", len(have) == len(want), f"got {len(have)}")


EXPECTED_V2 = {
    "== tag: alpha ==": [
        "runs: 3",
        "states: accepted 2, budget exhausted 1, failed 0, cancelled 0, interrupted 0",
        "accepted on attempt: 1:1 2:1 3:0",
        "pass@1: 1 of 3",
        "pass@2: 2 of 3",
        "pass@3: 2 of 3",
        "pass^2: 1 of 1 tasks with 2+ runs had every run accepted",
        "output tokens: 7100",
        "prompt tokens: 850",
        "output tokens per accepted artifact: 3550.0",
        "IDENT attempts: 1",
        "SUSPECT attempts: 1",
        "comparable retries: 3, identical: 1",
        "thinking share of output tokens: 42.3 percent",
        "cap hits: 0",
        "prompt-eval seconds: 10.0",
        "reached attempt 3: runs 1, output tokens 4800 of 7100 (67.6 percent)",
    ],
    "== tag: beta ==": [
        "runs: 2",
        "states: accepted 1, budget exhausted 0, failed 1, cancelled 0, interrupted 0",
        "accepted on attempt: 1:0 2:0 3:1",
        "pass@1: 0 of 2",
        "pass@2: 0 of 2",
        "pass@3: 1 of 2",
        "pass^2: n/a (no task has 2 or more runs)",
        "output tokens: 10192",
        "prompt tokens: 400",
        "output tokens per accepted artifact: 10192.0",
        "IDENT attempts: 0",
        "SUSPECT attempts: 0",
        "comparable retries: 0, identical: 0",
        "thinking share of output tokens: 19.6 percent",
        "cap hits: 1",
        "prompt-eval seconds: 5.0",
        "reached attempt 3: runs 2, output tokens 10192 of 10192 (100.0 percent)",
    ],
    "== tag: (no tag) ==": [
        "runs: 2",
        "states: accepted 0, budget exhausted 0, failed 0, cancelled 1, interrupted 1",
        "accepted on attempt: 1:0 2:0 3:0",
        "pass@1: 0 of 2",
        "pass@2: 0 of 2",
        "pass@3: 0 of 2",
        "pass^2: n/a (no task has 2 or more runs)",
        "output tokens: 400",
        "prompt tokens: 50",
        "output tokens per accepted artifact: n/a (nothing accepted)",
        "IDENT attempts: 0",
        "SUSPECT attempts: 0",
        "comparable retries: 0, identical: 0",
        "thinking share of output tokens: 0.0 percent",
        "cap hits: 0",
        "prompt-eval seconds: 0.5",
        "reached attempt 3: runs 0, output tokens 0 of 400 (0.0 percent)",
    ],
    "== all ==": [
        "runs: 7",
        "states: accepted 3, budget exhausted 1, failed 1, cancelled 1, interrupted 1",
        "accepted on attempt: 1:1 2:1 3:1",
        "pass@1: 1 of 7",
        "pass@2: 2 of 7",
        "pass@3: 3 of 7",
        "pass^2: 1 of 1 tasks with 2+ runs had every run accepted",
        "output tokens: 17692",
        "prompt tokens: 1300",
        "output tokens per accepted artifact: 5897.3",
        "IDENT attempts: 1",
        "SUSPECT attempts: 1",
        "comparable retries: 3, identical: 1",
        "thinking share of output tokens: 28.3 percent",
        "cap hits: 1",
        "prompt-eval seconds: 15.5",
        "reached attempt 3: runs 3, output tokens 14992 of 17692 (84.7 percent)",
    ],
}

EXPECTED_BACKFILL = {
    "== tag: bf-a ==": [
        "runs: 2",
        "states: accepted 1, budget exhausted 1, failed 0, cancelled 0, interrupted 0",
        "accepted on attempt: 1:0 2:1 3:0",
        "pass@1: 0 of 2",
        "pass@2: 1 of 2",
        "pass@3: 1 of 2",
        "pass^2: n/a (no task has 2 or more runs)",
        "output tokens: 6600",
        "prompt tokens: 750",
        "output tokens per accepted artifact: 6600.0",
        "IDENT attempts: 1",
        "SUSPECT attempts: 0",
        "comparable retries: 3, identical: 1",
        "thinking share of output tokens: 45.5 percent",
        "cap hits: 0",
        "prompt-eval seconds: 0.0",
        "reached attempt 3: runs 1, output tokens 4800 of 6600 (72.7 percent)",
    ],
    "== tag: bf-b ==": [
        "runs: 1",
        "states: accepted 1, budget exhausted 0, failed 0, cancelled 0, interrupted 0",
        "accepted on attempt: 1:0 2:0 3:1",
        "pass@1: 0 of 1",
        "pass@2: 0 of 1",
        "pass@3: 1 of 1",
        "pass^2: n/a (no task has 2 or more runs)",
        "output tokens: 10892",
        "prompt tokens: 510",
        "output tokens per accepted artifact: 10892.0",
        "IDENT attempts: 0",
        "SUSPECT attempts: 0",
        "comparable retries: 1, identical: 0",
        "thinking share of output tokens: 18.4 percent",
        "cap hits: 1",
        "prompt-eval seconds: 0.0",
        "reached attempt 3: runs 1, output tokens 10892 of 10892 (100.0 percent)",
    ],
    "== tag: (no tag) ==": [
        "runs: 1",
        "states: accepted 0, budget exhausted 1, failed 0, cancelled 0, interrupted 0",
        "accepted on attempt: 1:0 2:0 3:0",
        "pass@1: 0 of 1",
        "pass@2: 0 of 1",
        "pass@3: 0 of 1",
        "pass^2: n/a (no task has 2 or more runs)",
        "output tokens: 300",
        "prompt tokens: 150",
        "output tokens per accepted artifact: n/a (nothing accepted)",
        "IDENT attempts: 2",
        "SUSPECT attempts: 0",
        "comparable retries: 2, identical: 2",
        "thinking share of output tokens: 0.0 percent",
        "cap hits: 0",
        "prompt-eval seconds: 0.0",
        "reached attempt 3: runs 1, output tokens 300 of 300 (100.0 percent)",
    ],
    "== all ==": [
        "runs: 4",
        "states: accepted 2, budget exhausted 2, failed 0, cancelled 0, interrupted 0",
        "accepted on attempt: 1:0 2:1 3:1",
        "pass@1: 0 of 4",
        "pass@2: 1 of 4",
        "pass@3: 2 of 4",
        "pass^2: n/a (no task has 2 or more runs)",
        "output tokens: 17792",
        "prompt tokens: 1410",
        "output tokens per accepted artifact: 8896.0",
        "IDENT attempts: 3",
        "SUSPECT attempts: 0",
        "comparable retries: 6, identical: 3",
        "thinking share of output tokens: 28.1 percent",
        "cap hits: 1",
        "prompt-eval seconds: 0.0",
        "reached attempt 3: runs 3, output tokens 15992 of 17792 (89.9 percent)",
    ],
}

if not SCRIPT.exists():
    print(f"FAIL the script under test does not exist: {SCRIPT}")
    sys.exit(1)

V2 = FX / "v2-rows.jsonl"
V1 = FX / "backfill" / "delegations-v1.jsonl"

# 1. the v2 report: every number
code, out, err = run([V2])
check("v2 report: exit 0 and nothing on stderr", code == 0 and err == "", f"code={code} stderr={err[:200]!r}")
compare("v2", out, EXPECTED_V2)
check("v2 report: the output ends with a single newline and has no trailing blank line", out.endswith("\n") and not out.endswith("\n\n"))
code2, out2, _ = run([V2])
check("v2 report: running it twice gives byte-identical output", out == out2)
check("v2 report: no path and no work-folder text in the output (the log holds one)", "zzcanarydir" not in out and "work-r" not in out and "\\" not in out and not re.search(r"[A-Za-z]:/|/[A-Za-z0-9_.-]+/", out))

# 2. --k changes pass^k
code, out, err = run([V2, "--k", "3"])
check("--k 3: exit 0", code == 0, err[:200])
b = blocks(out)
check("--k 3: pass^3 is n/a when no task has 3 runs (alpha)", "pass^3: n/a (no task has 3 or more runs)" in b.get("== tag: alpha ==", []), str(b.get("== tag: alpha ==", [])[6:7]))
check("--k 3: the pass^2 line is gone", all("pass^2" not in line for ls in b.values() for line in ls))

# 3. two logs together equal one log (runs split across files)
rows = [json.loads(x) for x in V2.read_text(encoding="utf-8").splitlines() if x.strip()]
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    first = [r for r in rows if r["run"] in ("r1", "r2", "r3")]
    second = [r for r in rows if r["run"] not in ("r1", "r2", "r3")]
    (t / "a.jsonl").write_text("\n".join(json.dumps(r) for r in first) + "\n", encoding="utf-8")
    (t / "b.jsonl").write_text("\n".join(json.dumps(r) for r in second) + "\n", encoding="utf-8")
    code, outab, err = run([t / "a.jsonl", t / "b.jsonl"])
    check("two logs: the same report as the one log", code == 0 and outab == run([V2])[1], err[:200])

    # 4. an unreadable line is skipped and named; the rest is reported
    (t / "junk.jsonl").write_text("this is not json\n" + V2.read_text(encoding="utf-8"), encoding="utf-8")
    code, outj, errj = run([t / "junk.jsonl"])
    check("an unreadable line: skipped, report unchanged, one note on stderr, exit 0", code == 0 and outj == run([V2])[1] and "skipped 1 unreadable line" in errj, errj[:200])

    # 5. errors exit 2 with a message and print no report
    code, out, err = run([])
    check("no arguments: exit 2 and a usage message on stderr, nothing on stdout", code == 2 and out == "" and err.strip() != "", f"code={code}")
    code, out, err = run([t / "does-not-exist.jsonl"])
    check("a missing log: exit 2, a message, nothing on stdout", code == 2 and out == "" and err.strip() != "", f"code={code}")
    (t / "empty.jsonl").write_text("", encoding="utf-8")
    code, out, err = run([t / "empty.jsonl"])
    check("a log with no rows: exit 2 and nothing on stdout", code == 2 and out == "", f"code={code}")
    code, out, err = run([V1])
    check("an old (v1) outcome log given as a plain log: exit 2 and the message points to --backfill", code == 2 and out == "" and "--backfill" in err, err[:200])

    # 6. nothing is written unless --write-rows is given
    before = sorted(p.name for p in t.iterdir())
    run([V2, "--backfill", V1], cwd=t)
    run([V2], cwd=t)
    check("no files are created in the working directory without --write-rows", sorted(p.name for p in t.iterdir()) == before)

# 7. backfill from the old outcome log and the work folders
code, out, err = run(["--backfill", V1])
check("backfill: exit 0", code == 0, err[:200])
compare("backfill", out, EXPECTED_BACKFILL)
check("backfill: the run whose work folder is gone is skipped, and that is said once on stderr", "skipped 1 run" in err and "work folder" in err, err[:200])
check("backfill: no reply text, prompt text, work-folder name or path in the output", all(s not in out for s in ("SECRET-REPLY-TEXT", "PROMPT-TEXT-CANARY", "w1", "w2", "gone", "backfill", "C:/")), out[:100])
check("backfill: the skipped run's tag is not reported", "bf-gone" not in out)

# 8. --write-rows: v2-shaped rows, with the labels the backfill can know, and the same report when read back
with tempfile.TemporaryDirectory() as t:
    rows_out = Path(t) / "rows.jsonl"
    code, out_bf, err = run(["--backfill", V1, "--write-rows", rows_out])
    check("--write-rows: exit 0 and the file exists", code == 0 and rows_out.exists(), err[:200])
    written = [json.loads(x) for x in rows_out.read_text(encoding="utf-8").splitlines() if x.strip()] if rows_out.exists() else []
    attempts = [r for r in written if r.get("kind") == "attempt"]
    runs = [r for r in written if r.get("kind") == "run"]
    check("--write-rows: 11 attempt rows and 4 run rows", len(attempts) == 11 and len(runs) == 4, f"{len(attempts)} {len(runs)}")
    labels = [r.get("label") for r in attempts]
    check("--write-rows: every label is null or matches ^[A-Z]+(:[0-9a-f]{8})?$", all(l is None or re.match(r"^[A-Z]+(:[0-9a-f]{8})?$", l) for l in labels), str(labels))
    counts = {k: labels.count(k) for k in ("IDENT", "NOFENCE", "CAP", "UNKNOWN")}
    check("--write-rows: 3 IDENT, 1 NOFENCE, 1 CAP, 4 UNKNOWN, and 2 accepting attempts with no label", counts == {"IDENT": 3, "NOFENCE": 1, "CAP": 1, "UNKNOWN": 4} and labels.count(None) == 2, str(counts))
    check("--write-rows: states are accepted, accepted, budget exhausted, budget exhausted (a salvaged run counts as accepted)", sorted(r.get("state") for r in runs) == ["accepted", "accepted", "budget exhausted", "budget exhausted"], str([r.get("state") for r in runs]))
    check("--write-rows: a row holds a candidate hash, never reply text", all(("SECRET-REPLY-TEXT" not in json.dumps(r) and "PROMPT-TEXT-CANARY" not in json.dumps(r)) for r in written))
    check("--write-rows: no work-folder path is written", all("work_dir" not in r or r["work_dir"] in (None, "") for r in written), str([r.get("work_dir") for r in runs]))
    code, again, err = run([rows_out])
    check("--write-rows: reading the written rows back gives the same report as the backfill", code == 0 and again == out_bf, err[:200])

# 8b. edge cases, each on a small fixture built here: fences, line endings, blank lines, IDENT across a NOFENCE, K, other states, stray rows, bad input
import hashlib


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def usage_line(out=100, prompt=50, think=False, done="stop"):
    return json.dumps({"output_tokens": out, "prompt_tokens": prompt, "think": think, "done_reason": done})


def make_v1(root, name, usage_lines, replies, outcome="not accepted", attempts=None):
    w = root / name
    w.mkdir()
    (w / "usage.jsonl").write_text("\n".join(usage_lines) + "\n", encoding="utf-8")
    for k, txt in replies.items():
        (w / f"reply-{k}.txt").write_bytes(txt.encode("utf-8"))
    row = {"tag": "edge", "task": "t.md", "outcome": outcome, "attempts": attempts or len(usage_lines), "max_attempts": 3, "seconds": 1, "output_tokens": 1, "work_dir": name}
    (root / f"{name}.v1.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return root / f"{name}.v1.jsonl"


def backfill_rows(v1):
    out = v1.parent / (v1.stem + ".rows.jsonl")
    code, so, se = run(["--backfill", v1, "--write-rows", out])
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()] if out.exists() else []
    return code, so, se, [r for r in rows if r["kind"] == "attempt"], [r for r in rows if r["kind"] == "run"]


F = "```"
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    # adjacent fences: an empty candidate, not "no fence"
    v1 = make_v1(t, "adj", [usage_line(), usage_line()], {1: f"{F}\n{F}\n", 2: f"{F}\n{F}\n"})
    code, so, se, at, rn = backfill_rows(v1)
    check("backfill: two adjacent fences are an EMPTY candidate (the SHA-256 of the empty string), not NOFENCE", code == 0 and [a["candidate_sha256"] for a in at] == [sha(""), sha("")] and [a["label"] for a in at] == ["UNKNOWN", "IDENT"], str([(a["label"], a["candidate_sha256"]) for a in at]))
    check("backfill: an empty candidate repeated counts as a comparable and identical retry", "comparable retries: 1, identical: 1" in so, so[:200])
    # mixed line endings inside one reply
    v1 = make_v1(t, "mixed", [usage_line()], {1: f"x\n{F}\nA\r\nB\n{F}\r\n"})
    code, so, se, at, rn = backfill_rows(v1)
    check("backfill: lines are split on \\r?\\n, so a reply with mixed endings gives the candidate 'A\\nB'", at and at[0]["candidate_sha256"] == sha("A\nB"), str([a["candidate_sha256"] for a in at]))
    # IDENT is against the most recent earlier attempt that HAS a candidate (as delegate.ps1 does); retries are comparable only against attempt n-1
    v1 = make_v1(t, "ident", [usage_line(), usage_line(), usage_line()], {1: f"{F}\nX\n{F}\n", 2: "just prose, no fence", 3: f"{F}\nX\n{F}\n"})
    code, so, se, at, rn = backfill_rows(v1)
    check("backfill: attempt 3 repeats attempt 1 across a NOFENCE attempt: labels UNKNOWN, NOFENCE, IDENT", [a["label"] for a in at] == ["UNKNOWN", "NOFENCE", "IDENT"], str([a["label"] for a in at]))
    check("backfill: a NOFENCE reply is still a reply, so both retries are comparable and neither is identical", "comparable retries: 2, identical: 0" in so, so[:200])
    # a blank line in usage.jsonl does not shift the attempt numbers
    v1 = make_v1(t, "blank", [usage_line(10), "", usage_line(20)], {1: f"{F}\nA\n{F}\n", 2: f"{F}\nB\n{F}\n"})
    code, so, se, at, rn = backfill_rows(v1)
    check("backfill: a blank line in usage.jsonl is not an attempt: the numbers are 1 and 2 and reply-2 is attempt 2's", [a["n"] for a in at] == [1, 2] and at[1]["candidate_sha256"] == sha("B"), str([(a["n"], a["candidate_sha256"]) for a in at]))
    # an accepted run, K from max_attempts, other states, stray rows
    def run_rows(rows):
        p = t / f"rows-{abs(hash(json.dumps(rows)))}.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return p
    two = [{"kind": "attempt", "run": "k1", "tag": "k", "n": 1, "mode": "default", "label": "WRONG:aaaaaaaa", "output_tokens": 10}, {"kind": "attempt", "run": "k1", "tag": "k", "n": 2, "mode": "default", "label": None, "output_tokens": 10},
           {"kind": "run", "run": "k1", "tag": "k", "task": "t.md", "outcome": "accepted", "state": "accepted", "attempts": 2, "max_attempts": 2}]
    code, so, se = run([run_rows(two)])
    b = blocks(so).get("== tag: k ==", [])
    check("K is the largest max_attempts (2 here, not at least 3): two accepted-on-attempt entries and two pass@ lines", "accepted on attempt: 1:0 2:1" in b and "pass@2: 1 of 1" in b and not any(l.startswith("pass@3") for l in b), str(b[:6]))
    nf = [{"kind": "attempt", "run": "n1", "tag": "nf", "n": 1, "mode": "default", "label": "NOFENCE", "output_tokens": 10, "candidate_sha256": None},
          {"kind": "attempt", "run": "n1", "tag": "nf", "n": 2, "mode": "default", "label": "WRONG:aaaaaaaa", "output_tokens": 10, "candidate_sha256": "h1"},
          {"kind": "attempt", "run": "n1", "tag": "nf", "n": 3, "mode": "default", "label": "CAP", "output_tokens": 10, "candidate_sha256": None, "done_reason": "length"},
          {"kind": "run", "run": "n1", "tag": "nf", "task": "t.md", "outcome": "not accepted", "state": "budget exhausted", "attempts": 3, "max_attempts": 3}]
    code, so, se = run([run_rows(nf)])
    check("a retry is comparable when both attempts have a reply (a candidate or a NOFENCE label); a CAP attempt has none: 1 comparable, 0 identical", "comparable retries: 1, identical: 0" in blocks(so).get("== tag: nf ==", []), str(blocks(so).get("== tag: nf ==", [])[10:13]))
    tie = [{"kind": "attempt", "run": "q1", "tag": "tie", "n": 1, "mode": "default", "label": None, "output_tokens": 15, "prompt_tokens": 5},
           {"kind": "attempt", "run": "q1", "tag": "tie", "n": 2, "mode": "thinking", "label": None, "output_tokens": 1, "prompt_tokens": 5},
           {"kind": "run", "run": "q1", "tag": "tie", "task": "t.md", "outcome": "accepted", "state": "accepted", "attempts": 2, "max_attempts": 3}]
    code, so, se = run([run_rows(tie)])
    b = blocks(so).get("== tag: tie ==", [])
    check("rounding is half up on exact decimals: 1 of 16 thinking tokens is 6.25 percent, shown as 6.3 (not the banker's 6.2)", "thinking share of output tokens: 6.3 percent" in b, str([l for l in b if "thinking" in l]))
    check("16 output tokens over 1 accepted run is 16.0 per accepted artifact", "output tokens per accepted artifact: 16.0" in b, str([l for l in b if "per accepted" in l]))
    cap = [{"kind": "attempt", "run": "p1", "tag": "cap", "n": 1, "mode": "default", "label": "CAP", "output_tokens": 1, "done_reason": "stop"},
           {"kind": "attempt", "run": "p1", "tag": "cap", "n": 2, "mode": "default", "label": "WRONG:aaaaaaaa", "output_tokens": 1, "done_reason": "length", "candidate_sha256": "h"},
           {"kind": "attempt", "run": "p1", "tag": "cap", "n": 3, "mode": "thinking", "label": "CAP", "output_tokens": 1, "done_reason": "length"},
           {"kind": "run", "run": "p1", "tag": "cap", "task": "t.md", "outcome": "not accepted", "state": "budget exhausted", "attempts": 3, "max_attempts": 3}]
    code, so, se = run([run_rows(cap)])
    check("cap hits: a CAP label counts, a done_reason of length counts, and an attempt with both counts once (3 attempts, 3 hits)", "cap hits: 3" in blocks(so).get("== tag: cap ==", []), str([l for l in blocks(so).get("== tag: cap ==", []) if "cap" in l]))
    code, so, se = run(["--backfill", V1])
    check("backfill: nothing on stderr names a file, a folder or a path", code == 0 and all(s not in se for s in ("delegations-v1", "loop-report-fixtures", "backfill", "w1", "gone", "/", "\\")), se)
    code, so, se = run([t / "does-not-exist.jsonl"])
    check("an unreadable log: the error message does not repeat the path", "does-not-exist" not in se and "/" not in se and "\\" not in se, se)
    blocked = [{"kind": "run", "run": "z1", "tag": "z", "task": "t.md", "outcome": "x", "state": "blocked", "attempts": 0, "max_attempts": 3}]
    code, so, se = run([run_rows(blocked)])
    b = blocks(so).get("== tag: z ==", [])
    check("a run state this report does not list (blocked) counts as a run but in none of the state counts", "runs: 1" in b and "states: accepted 0, budget exhausted 0, failed 0, cancelled 0, interrupted 0" in b, str(b[:3]))
    check("with the verifier freeze states present, they get their own line (blocked 1, accepted-after-verifier-edit 0)", "verifier freeze: blocked 1, accepted-after-verifier-edit 0 (neither is counted in the states above)" in b, str(b[:4]))
    reverified = blocked + [{"kind": "run", "run": "z2", "tag": "z", "task": "t.md", "outcome": "reverified", "state": "accepted-after-verifier-edit", "attempts": 0, "max_attempts": 3}]
    code, so, se = run([run_rows(reverified)])
    b2 = blocks(so).get("== tag: z ==", [])
    check("a re-verified run is counted on the freeze line, never as accepted", "verifier freeze: blocked 1, accepted-after-verifier-edit 1 (neither is counted in the states above)" in b2 and "states: accepted 0, budget exhausted 0, failed 0, cancelled 0, interrupted 0" in b2, str(b2[:4]))
    code, so, se = run([run_rows(list(two))])
    check("with no freeze states, the report has no freeze line (every earlier report is unchanged)", "verifier freeze" not in so, so[:200])
    stray = [{"kind": "note", "text": "hello"}, {"tag": "old", "outcome": "accepted"}] + two
    code, so, se = run([run_rows(stray)])
    check("rows of another kind, or with no kind, are ignored silently (no stderr note)", code == 0 and se == "" and "== tag: k ==" in so, f"code={code} stderr={se[:120]!r}")
    # input that is not clean text
    bom = t / "bom.jsonl"
    bom.write_bytes(b"\xef\xbb\xbf" + "\n".join(json.dumps(r) for r in two).encode("utf-8") + b"\n")
    code, so, se = run([bom])
    check("a log that starts with a UTF-8 byte order mark is read normally", code == 0 and se == "" and "runs: 1" in so, f"code={code} stderr={se[:120]!r}")
    bad = t / "bad.jsonl"
    bad.write_bytes(b'{"kind":"attempt","run":"q","n":1,"x":"\xff\xfe"}\n' + "\n".join(json.dumps(r) for r in two).encode("utf-8") + b"\n")
    code, so, se = run([bad])
    check("a byte that is not valid UTF-8 never crashes the report", code == 0 and "== tag: k ==" in so and "Traceback" not in se, f"code={code} stderr={se[:200]!r}")
    code, so, se = run([V2, "--k", "0"])
    check("--k 0 is a usage error: exit 2 and nothing on stdout", code == 2 and so == "" and se.strip() != "", f"code={code}")
    code, so, se = run([V2, "--write-rows", t / "x.jsonl"])
    check("--write-rows without --backfill is a usage error: exit 2, nothing on stdout, no file", code == 2 and so == "" and not (t / "x.jsonl").exists(), f"code={code}")

# 9. standard library only, no network, no subprocess
src = SCRIPT.read_text(encoding="utf-8")
mods = set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", src, re.M))
std = set(sys.stdlib_module_names)
check("only standard-library modules are imported", mods <= std, f"not stdlib: {sorted(mods - std)}")
check("no network or process modules are imported", not (mods & {"socket", "urllib", "http", "requests", "subprocess", "ssl", "ftplib", "smtplib", "ctypes"}), str(sorted(mods & {"socket", "urllib", "http", "requests", "subprocess", "ssl", "ftplib", "smtplib", "ctypes"})))
check("it does not call eval or exec", not re.search(r"\b(eval|exec)\s*\(", src))

print(f"{'VERIFIED' if not fails else str(len(fails)) + ' failing check(s)'}")
sys.exit(1 if fails else 0)

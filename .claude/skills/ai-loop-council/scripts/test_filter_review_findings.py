"""Tests for filter-review-findings.py (board T-0089): run each failing input from a local model's review findings against a candidate script
inside a fresh temporary copy of the candidate's folder, and label every finding by what happened. The tool never accepts a finding.
Run: python test_filter_review_findings.py   (standard library only; no model, network or GPU). Set FILTER_REVIEW_FINDINGS_PATH to test another file.
The recorded findings in ../cases/review-findings-filter/findings.json are cut down from real replies of the 2026-10-06 reviewer evaluation; the
candidate they run against is a SYNTHETIC stand-in. Set SEO_A3_PATH to the real original script of that evaluation to run them against it too."""
import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = Path(os.environ.get("FILTER_REVIEW_FINDINGS_PATH") or HERE / "filter-review-findings.py")
CASES = HERE.parent / "cases" / "review-findings-filter"
MINI = CASES / "candidate" / "mini_seo.py"
FINDINGS = CASES / "findings.json"

NSC, DNR, TMO, INV = "needs spec check", "did not reproduce", "timed out", "invalid finding"

ECHO = '''import json, os, sys
data = sys.stdin.read()
print(json.dumps({"argv": sys.argv[1:], "stdin": data, "cwd_files": sorted(os.listdir("."))}, ensure_ascii=False))
'''
HANG = "import time\nprint('started', flush=True)\ntime.sleep(60)\n"
FLOOD = "import sys\nsys.stdout.write('x' * 10000000)\n"
CRASH = "print('before')\nraise RuntimeError('boom')\n"
EXIT3 = "import sys\nprint('three')\nsys.exit(3)\n"
WRITER = '''import os
m = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marker.txt")
print("seen" if os.path.exists(m) else "fresh")
open(m, "w").write("1")
'''
ENVC = 'import json, os\nprint(json.dumps({"keys": sorted(os.environ), "home": os.path.expanduser("~")}))\n'
HELPER_USER = "import helper\nprint('helper says', helper.VALUE)\n"
READ_FILE = "import sys\nprint(open(sys.argv[1], encoding='utf-8').read())\n"
NET = '''import socket
try:
    socket.create_connection(("127.0.0.1", {port}), timeout=2).close()
    print("CONNECTED")
except Exception as e:
    print("BLOCKED", type(e).__name__)
'''
LOGGER = "open({log!r}, 'a').write('ran')\nprint('ran')\n"
REGEX_TEXT = "print('a' * 40 + 'b')\n"


def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def finding(fid, expect, **inp):
    return {"id": fid, "claim": f"claim {fid}", "spec_quote": f"The spec sentence for {fid}.", "failing_input": dict(inp, expect=expect)}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rff-test-"))
        self.addCleanup(self._cleanup)
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.scratch = self.tmp / "scratch"  # TEMP of the tool process, so leftovers can be seen
        self.scratch.mkdir()
        self.cand_dir = self.tmp / "cand"
        self.cand_dir.mkdir()

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def candidate(self, text, name="cand.py"):
        p = self.cand_dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def run_tool(self, findings, cand, *extra, env_extra=None, as_object=True, out=None):
        fpath = self.work / "findings.json"
        fpath.write_text(json.dumps({"findings": findings} if as_object else findings), encoding="utf-8")
        out = out or self.work / "result.json"
        env = dict(os.environ, TEMP=str(self.scratch), TMP=str(self.scratch), TMPDIR=str(self.scratch))
        env.update(env_extra or {})
        args = [sys.executable, str(SCRIPT), str(fpath), str(cand), "--out", str(out)] + list(extra)
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
        result = json.loads(Path(out).read_text(encoding="utf-8")) if Path(out).exists() else None
        return r.returncode, r.stdout + r.stderr, result

    def labels(self, result):
        return {r["id"]: r["label"] for r in result["results"]}

    def one(self, expect, cand_text, *extra, name="cand.py", **inp):
        cand = self.candidate(cand_text, name)
        code, out, res = self.run_tool([finding("f", expect, **inp)], cand, *extra)
        self.assertEqual(code, 0, out)
        return res["results"][0], out


class RecordedFindings(Base):
    expected = {"A3-1": DNR, "A3-2": DNR, "A3-3": NSC, "A3-4": NSC, "A4-1": NSC, "A4-2": DNR, "B1-4": NSC, "B1-10": DNR, "B1-2": DNR, "A1-1": INV}

    def test_recorded_findings_get_the_expected_labels_against_the_stand_in_candidate(self):
        code, out, res = self.run_tool(json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"], MINI)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.labels(res), self.expected, out)

    @unittest.skipUnless(os.environ.get("SEO_A3_PATH") and Path(os.environ.get("SEO_A3_PATH", "")).is_file(), "set SEO_A3_PATH to the original script of the 2026-10-06 evaluation")
    def test_recorded_findings_get_the_same_labels_against_the_real_script(self):
        code, out, res = self.run_tool(json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"], Path(os.environ["SEO_A3_PATH"]), "--timeout", "30")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.labels(res), self.expected, out)

    def test_every_reproducing_finding_carries_its_quoted_spec_sentence_and_is_listed_for_the_controller(self):
        code, out, res = self.run_tool(json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"], MINI)
        want = [i for i, l in self.expected.items() if l == NSC]
        for r in res["results"]:
            if r["id"] in want:
                self.assertTrue(r["spec_quote"].strip(), r)
                self.assertTrue(r["next_step"].strip(), r)
                self.assertIn(r["spec_quote"], out)
            else:
                self.assertFalse(r.get("next_step"), r)
        marked = [l for l in out.splitlines() if l.startswith("CHECK SPEC")]
        self.assertEqual(len(marked), len(want), out)
        for fid in want:
            self.assertTrue(any(fid in l for l in marked), (fid, out))

    def test_the_tool_never_accepts_or_ranks_a_finding(self):
        code, out, res = self.run_tool(json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"], MINI)
        banned = {"accepted", "accept", "verdict", "rank", "score", "confirmed", "true_positive"}
        self.assertFalse(banned & set(res), res.keys())
        for r in res["results"]:
            self.assertFalse(banned & set(r), r.keys())
        self.assertEqual(sum(res["counts"].values()), len(res["results"]))
        self.assertEqual(res["counts"][NSC], 4)

    def test_a_finding_with_no_input_is_a_lead_not_a_finding(self):
        code, out, res = self.run_tool(json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"], MINI)
        r = [x for x in res["results"] if x["id"] == "A1-1"][0]
        self.assertEqual(r["label"], INV)
        self.assertIn("lead", r["reason"].lower())
        self.assertIsNone(r.get("observed"))

    def test_the_table_lists_each_id_with_its_label_and_results_keep_input_order(self):
        findings = json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"]
        code, out, res = self.run_tool(findings, MINI)
        for f in findings:
            line = [l for l in out.splitlines() if f["id"] in l and self.expected[f["id"]] in l]
            self.assertTrue(line, (f["id"], out))
        self.assertEqual([r["id"] for r in res["results"]], [f["id"] for f in findings])

    def test_the_candidate_folder_is_never_modified(self):
        before = tree_hash(MINI.parent)
        self.run_tool(json.loads(FINDINGS.read_text(encoding="utf-8"))["findings"], MINI)
        self.assertEqual(tree_hash(MINI.parent), before)

    def test_the_result_file_default_sits_next_to_the_findings_file(self):
        fpath = self.work / "findings.json"
        fpath.write_text(json.dumps({"findings": [finding("a", {"exit_code": 0}, args=["x"])]}), encoding="utf-8")
        cand = self.candidate("print('hi')\n")
        r = subprocess.run([sys.executable, str(SCRIPT), str(fpath), str(cand)], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        found = [p for p in self.work.iterdir() if p.suffix == ".json" and p.name != "findings.json"]
        self.assertEqual(len(found), 1, list(self.work.iterdir()))
        self.assertEqual(json.loads(found[0].read_text(encoding="utf-8"))["results"][0]["id"], "a")


class SafetyTests(Base):
    def test_shell_metacharacters_are_passed_as_literal_arguments_and_no_shell_runs_them(self):
        args = ["; echo PWNED > pwned.txt", "$(touch subst.txt)", "`id`", "a && b", "x | y > z.txt", "%PATH%"]
        cand = self.candidate(ECHO)
        findings = [
            finding("literal", {"output_regex": r"\$\(touch subst\.txt\)"}, args=args),
            finding("nothing-created", {"output_regex": r'"cwd_files": \[\]'}, args=args),
            finding("literal-percent", {"output_regex": r"%PATH%"}, args=args),
        ]
        code, out, res = self.run_tool(findings, cand)
        self.assertEqual(code, 0, out)
        self.assertEqual(set(self.labels(res).values()), {NSC}, out)
        self.assertEqual(list(self.scratch.iterdir()), [], "temporary folders are removed")
        self.assertEqual([p.name for p in self.work.iterdir()], ["findings.json", "result.json"])

    def test_the_script_never_starts_a_shell(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                self.assertFalse(isinstance(node.value, ast.Constant) and node.value.value is True, "shell=True")
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os":
                self.assertNotIn(node.attr, {"system", "popen", "startfile"}, node.attr)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertFalse(names & {"requests", "urllib", "http", "socket", "ftplib", "smtplib", "numpy", "yaml"}, names)

    def test_a_finding_that_asks_to_run_code_is_rejected_and_nothing_runs(self):
        log = self.tmp / "ran.log"
        cand = self.candidate(LOGGER.format(log=str(log)))
        smuggle = [
            {"id": "cmd", "claim": "c", "spec_quote": "s", "failing_input": {"command": "python -c \"open('smuggled.txt','w')\"", "expect": {"exit_code": 0}}},
            {"id": "code", "claim": "c", "spec_quote": "s", "failing_input": {"code": "import os; os.remove('x')", "expect": {"exit_code": 0}}},
            {"id": "script", "claim": "c", "spec_quote": "s", "failing_input": {"script": "print(1)", "args": [], "expect": {"exit_code": 0}}},
            {"id": "shell", "claim": "c", "spec_quote": "s", "failing_input": {"shell": "rm -rf /", "expect": {"exit_code": 0}}},
            {"id": "top", "claim": "c", "spec_quote": "s", "command": "python evil.py", "failing_input": {"args": [], "expect": {"exit_code": 0}}},
            finding("pyfile", {"exit_code": 0}, files={"evil.py": "print('x')"}),
            finding("sitecustomize", {"exit_code": 0}, files={"sitecustomize.py": "print('x')"}),
            finding("pth", {"exit_code": 0}, files={"x.pth": "import os"}),
            finding("sh", {"exit_code": 0}, files={"run.sh": "echo hi"}),
            finding("bat", {"exit_code": 0}, files={"RUN.BAT": "echo hi"}),
        ]
        code, out, res = self.run_tool(smuggle, cand)
        self.assertEqual(code, 0, out)
        self.assertEqual(set(self.labels(res).values()), {INV}, out)
        self.assertFalse(log.exists(), "an invalid finding must not run the candidate")
        self.assertFalse(any(p.name == "smuggled.txt" for p in self.tmp.rglob("*")))
        for r in res["results"][:5]:
            self.assertIn("code", r["reason"].lower(), r)

    def test_inputs_that_reach_outside_the_copy_are_invalid(self):
        bad_files = ["../x.txt", "/abs.txt", "C:/x.txt", "a/../../x.txt", "a\\..\\..\\x.txt", "", "a//b.txt", "\\\\host\\share\\x.txt", "a\0b.txt"]
        bad_args = ["/etc/passwd", "C:\\Windows\\win.ini", "../up", "--out=/tmp/x", "a/../../b", "\\\\host\\share"]
        findings = [finding(f"file-{i}", {"exit_code": 0}, files={n: "x"}) for i, n in enumerate(bad_files)]
        findings += [finding(f"arg-{i}", {"exit_code": 0}, args=[a]) for i, a in enumerate(bad_args)]
        code, out, res = self.run_tool(findings, self.candidate(ECHO))
        self.assertEqual(code, 0, out)
        self.assertEqual(set(self.labels(res).values()), {INV}, self.labels(res))

    def test_the_environment_is_scrubbed_and_home_is_not_the_real_home(self):
        cand = self.candidate(ENVC)
        home = '"home": ' + re_json_escape(json.dumps(str(Path.home())))  # equality, not a prefix: the sandbox itself sits below TEMP
        findings = [
            finding("secret", {"output_regex": "SECRET_TOKEN_FOR_TEST"}),
            finding("proxy", {"output_regex": "PROXY"}),
            finding("real-home", {"output_regex": home}),
            finding("sanity", {"output_regex": '"keys": \\['}),
        ]
        code, out, res = self.run_tool(findings, cand, env_extra={"SECRET_TOKEN_FOR_TEST": "abc", "HTTPS_PROXY": "http://example.invalid:3128"})
        self.assertEqual(code, 0, out)
        self.assertEqual(self.labels(res), {"secret": DNR, "proxy": DNR, "real-home": DNR, "sanity": NSC}, out)

    def test_the_candidate_cannot_open_a_network_connection(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        self.addCleanup(srv.close)
        port = srv.getsockname()[1]
        cand = self.candidate(NET.format(port=port))
        code, out, res = self.run_tool([finding("connected", {"output_regex": "CONNECTED"}), finding("blocked", {"output_regex": "BLOCKED"})], cand)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.labels(res), {"connected": DNR, "blocked": NSC}, out)

    def test_each_finding_runs_in_a_fresh_copy_and_the_real_folder_is_untouched(self):
        cand = self.candidate(WRITER)
        before = tree_hash(self.cand_dir)
        code, out, res = self.run_tool([finding("one", {"output_regex": "fresh"}), finding("two", {"output_regex": "fresh"}), finding("never", {"output_regex": "seen"})], cand)
        self.assertEqual(self.labels(res), {"one": NSC, "two": NSC, "never": DNR}, out)
        self.assertEqual(tree_hash(self.cand_dir), before)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_the_candidate_can_import_a_sibling_module_from_its_own_folder(self):
        (self.cand_dir / "helper.py").write_text("VALUE = 42\n", encoding="utf-8")
        res, out = self.one({"output_regex": "helper says 42"}, HELPER_USER)
        self.assertEqual(res["label"], NSC, out)


class InputTests(Base):
    def test_files_are_written_below_the_input_folder_and_the_placeholder_names_it(self):
        res, out = self.one({"output_regex": "hello nested"}, READ_FILE, files={"a/b/c.txt": "hello nested"}, args=["{input_dir}/a/b/c.txt"])
        self.assertEqual(res["label"], NSC, out)

    def test_stdin_text_is_delivered_including_non_ascii(self):
        res, out = self.one({"output_regex": "caf\u00e9 \u2713"}, ECHO, stdin="caf\u00e9 \u2713 line\n")
        self.assertEqual(res["label"], NSC, out)

    def test_a_bare_list_of_findings_is_accepted_as_well_as_an_object(self):
        cand = self.candidate("print('hi')\n")
        code, out, res = self.run_tool([finding("a", {"output_regex": "hi"})], cand, as_object=False)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.labels(res), {"a": NSC})


class ExpectationTests(Base):
    def test_exit_code_is_compared_exactly(self):
        self.assertEqual(self.one({"exit_code": 3}, EXIT3)[0]["label"], NSC)
        self.assertEqual(self.one({"exit_code": 0}, EXIT3)[0]["label"], DNR)

    def test_all_stated_conditions_must_hold(self):
        self.assertEqual(self.one({"exit_code": 3, "output_regex": "three"}, EXIT3)[0]["label"], NSC)
        self.assertEqual(self.one({"exit_code": 3, "output_regex": "four"}, EXIT3)[0]["label"], DNR)
        self.assertEqual(self.one({"exit_code": 0, "output_regex": "three"}, EXIT3)[0]["label"], DNR)
        self.assertEqual(self.one({"output_regex": "three", "output_not_regex": "four"}, EXIT3)[0]["label"], NSC)
        self.assertEqual(self.one({"output_regex": "three", "output_not_regex": "thr"}, EXIT3)[0]["label"], DNR)

    def test_a_regex_sees_standard_error_as_well_as_standard_output(self):
        res, out = self.one({"output_regex": "to-stderr"}, "import sys\nprint('to-stderr', file=sys.stderr)\n")
        self.assertEqual(res["label"], NSC, out)

    def test_a_crashing_candidate_is_reported_as_a_crash_and_proves_no_absence(self):
        cand = self.candidate(CRASH)
        findings = [
            finding("wants-ok", {"exit_code": 0}),
            finding("wants-crash", {"output_regex": "RuntimeError: boom"}),
            finding("absence-only", {"output_not_regex": "SEO030"}),
        ]
        code, out, res = self.run_tool(findings, cand)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.labels(res), {"wants-ok": DNR, "wants-crash": NSC, "absence-only": DNR}, out)
        by = {r["id"]: r for r in res["results"]}
        self.assertIn("crash", by["wants-ok"]["reason"].lower())
        self.assertIn("crash", by["absence-only"]["reason"].lower())
        self.assertEqual(by["wants-ok"]["observed"]["exit_code"], 1)

    def test_an_input_that_hangs_is_labelled_timed_out_and_the_next_finding_still_runs(self):
        cand = self.candidate(HANG)
        findings = [finding("slow", {"exit_code": 0}), finding("slow-regex", {"output_regex": "started"}), finding("claims-hang", {"hangs": True})]
        code, out, res = self.run_tool(findings, cand, "--timeout", "1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.labels(res), {"slow": TMO, "slow-regex": TMO, "claims-hang": NSC}, out)

    def test_a_finding_that_claims_a_hang_does_not_reproduce_when_the_candidate_exits(self):
        self.assertEqual(self.one({"hangs": True}, "print('done')\n")[0]["label"], DNR)

    def test_output_beyond_the_cap_stops_the_run_and_is_not_counted_as_a_reproduction(self):
        cand = self.candidate(FLOOD)
        code, out, res = self.run_tool([finding("flood", {"output_regex": "x"})], cand, "--output-cap", "1000")
        self.assertEqual(code, 0, out)
        r = res["results"][0]
        self.assertEqual(r["label"], DNR)
        self.assertIn("output cap", r["reason"].lower())
        self.assertTrue(r["observed"]["output_capped"])
        self.assertLess(len(r["observed"]["stdout"]), 5000)
        self.assertLess(len(json.dumps(res)), 20000)

    def test_a_regex_that_would_run_for_ever_is_an_invalid_finding_not_a_hang_of_the_tool(self):
        res, out = self.one({"output_regex": "^(a+)+$"}, REGEX_TEXT, "--timeout", "2")
        self.assertEqual(res["label"], INV, out)

    def test_a_regex_sees_all_captured_output_not_only_the_part_kept_in_the_result(self):
        text = "print('x' * 5000 + 'TAIL-MARK')" + chr(10)
        self.assertEqual(self.one({"output_regex": "TAIL-MARK"}, text)[0]["label"], NSC)
        self.assertEqual(self.one({"output_not_regex": "TAIL-MARK"}, text)[0]["label"], DNR)

    def test_a_crash_is_recognised_even_when_the_traceback_follows_a_long_stderr(self):
        text = "import sys" + chr(10) + "sys.stderr.write('e' * 5000 + chr(10))" + chr(10) + "raise RuntimeError('late')" + chr(10)
        res, out = self.one({"exit_code": 0}, text)
        self.assertEqual(res["label"], DNR, out)
        self.assertIn("crash", res["reason"].lower())

    def test_a_killed_run_has_no_exit_code(self):
        cand = self.candidate(HANG)
        code, out, res = self.run_tool([finding("slow", {"exit_code": 0})], cand, "--timeout", "1")
        self.assertIsNone(res["results"][0]["observed"]["exit_code"])
        self.assertTrue(res["results"][0]["observed"]["timed_out"])
        code, out, res = self.run_tool([finding("flood", {"exit_code": 0})], self.candidate(FLOOD), "--output-cap", "1000")
        self.assertIsNone(res["results"][0]["observed"]["exit_code"])

    def test_observed_output_is_kept_short(self):
        res, out = self.one({"output_regex": "x"}, "print('x' * 50000)\n")
        self.assertEqual(res["label"], NSC)
        self.assertLessEqual(len(res["observed"]["stdout"]), 2000)
        self.assertEqual(res["observed"]["exit_code"], 0)
        self.assertIsInstance(res["observed"]["seconds"], (int, float))


class ValidationTests(Base):
    def test_malformed_findings_are_invalid_with_a_reason_and_do_not_stop_the_others(self):
        ok = finding("ok", {"output_regex": "hi"})
        bad = [
            {"claim": "c", "spec_quote": "s", "failing_input": {"expect": {"exit_code": 0}}},
            {"id": "no-claim", "spec_quote": "s", "failing_input": {"expect": {"exit_code": 0}}},
            {"id": "no-quote", "claim": "c", "failing_input": {"expect": {"exit_code": 0}}},
            {"id": "blank-quote", "claim": "c", "spec_quote": "  ", "failing_input": {"expect": {"exit_code": 0}}},
            {"id": "no-input", "claim": "c", "spec_quote": "s"},
            {"id": "input-not-object", "claim": "c", "spec_quote": "s", "failing_input": "run it"},
            {"id": "no-expect", "claim": "c", "spec_quote": "s", "failing_input": {"args": ["x"]}},
            finding("empty-expect", {}),
            finding("unknown-expect-key", {"exit_code": 0, "also": 1}),
            finding("unknown-input-key", {"exit_code": 0}, mystery="x"),
            finding("exit-not-int", {"exit_code": "0"}),
            finding("exit-bool", {"exit_code": True}),
            finding("bad-regex", {"output_regex": "("}),
            finding("regex-too-long", {"output_regex": "a" * 5000}),
            finding("args-not-list", {"exit_code": 0}, args="x y"),
            finding("args-not-strings", {"exit_code": 0}, args=[1, 2]),
            finding("files-not-object", {"exit_code": 0}, files=["a"]),
            finding("file-not-text", {"exit_code": 0}, files={"a.txt": 5}),
            finding("stdin-not-text", {"exit_code": 0}, stdin=5),
            finding("hangs-with-others", {"hangs": True, "exit_code": 0}),
            "just a string",
            42,
        ]
        code, out, res = self.run_tool([ok] + bad + [{"id": "ok", "claim": "dup", "spec_quote": "s", "failing_input": {"expect": {"exit_code": 0}}}], self.candidate("print('hi')\n"))
        self.assertEqual(code, 0, out)
        self.assertEqual(len(res["results"]), len(bad) + 2)
        self.assertEqual(res["results"][0]["label"], NSC)
        for r in res["results"][1:]:
            self.assertEqual(r["label"], INV, r)
            self.assertTrue(r["reason"].strip(), r)
        self.assertIn("duplicate", res["results"][-1]["reason"].lower())

    def test_a_very_large_input_is_invalid(self):
        res, out = self.one({"exit_code": 0}, "print(1)\n", stdin="x" * 3_000_000)
        self.assertEqual(res["label"], INV, out)

    def test_usage_errors_exit_2_and_run_nothing(self):
        cand = self.candidate("print('hi')\n")
        ok = self.work / "ok.json"
        ok.write_text(json.dumps({"findings": []}), encoding="utf-8")
        notjson = self.work / "bad.json"
        notjson.write_text("{not json", encoding="utf-8")
        wrongtype = self.work / "wrong.json"
        wrongtype.write_text('"a string"', encoding="utf-8")
        notpy = self.candidate("echo hi", "run.sh")
        cases = [
            [str(self.work / "missing.json"), str(cand)],
            [str(notjson), str(cand)],
            [str(wrongtype), str(cand)],
            [str(ok), str(self.cand_dir / "missing.py")],
            [str(ok), str(notpy)],
            [str(ok), str(self.cand_dir)],
            [str(ok), str(cand), "--timeout", "0"],
            [str(ok), str(cand), "--output-cap", "-5"],
        ]
        for args in cases:
            r = subprocess.run([sys.executable, str(SCRIPT)] + args + ["--out", str(self.work / "never.json")], capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
        self.assertFalse((self.work / "never.json").exists())

    def test_help_is_not_a_usage_error(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("--output-cap", r.stdout)

    def test_an_empty_findings_list_is_a_valid_run_with_no_results(self):
        code, out, res = self.run_tool([], self.candidate("print('hi')\n"))
        self.assertEqual(code, 0, out)
        self.assertEqual(res["results"], [])


def re_json_escape(text):
    import re
    return re.escape(text)


if __name__ == "__main__":
    unittest.main()

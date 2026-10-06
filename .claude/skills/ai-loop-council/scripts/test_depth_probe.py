"""Tests for depth-probe.py: does a local model use a fact placed at depth d of a long prompt? A synthetic fact is hidden in filler text; the model is asked for it; an exact check scores the reply.
A stub server stands in for Ollama, so no model, GPU or network is needed. Standard library only. Set DEPTH_PROBE_PATH to test another file."""
import json
import os
import re
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(os.environ.get("DEPTH_PROBE_PATH") or Path(__file__).resolve().parent / "depth-probe.py")
CODE_RE = re.compile(r"access code for the blue door is ([A-Z]+-\d+)")


class Stub(BaseHTTPRequestHandler):
    blind_after = None          # a depth fraction beyond which the stub "cannot see" the fact
    requests = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][-1]["content"]
        Stub.requests.append(body)
        m = CODE_RE.search(prompt)
        answer = "not stated"
        if m:
            pos = m.start() / max(len(prompt), 1)
            if Stub.blind_after is None or pos <= Stub.blind_after:
                answer = m.group(1)
        out = json.dumps({"message": {"content": answer}, "done": True, "done_reason": "stop", "prompt_eval_count": len(prompt) // 4, "eval_count": 5}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class DepthProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), Stub)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        Stub.blind_after = None
        Stub.requests = []

    def run_script(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), "--url", f"http://127.0.0.1:{self.port}", "--model", "stub-model", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return r.returncode, r.stdout + r.stderr

    def dry(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), "--dry-run", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return r.returncode, r.stdout + r.stderr

    # ---- the prompt
    def test_dry_run_reports_the_size_and_where_the_fact_sits_without_calling_anything(self):
        code, out = self.dry("--lengths", "8000", "--depths", "0.5")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"8000")
        self.assertRegex(out, r"0\.5")
        self.assertEqual(Stub.requests, [])

    def test_the_prompt_is_about_the_requested_token_count(self):
        code, out = self.dry("--lengths", "8000,32000", "--depths", "0.5")
        self.assertEqual(code, 0, out)
        sizes = [int(x) for x in re.findall(r"approx_tokens=(\d+)", out)]
        self.assertEqual(len(sizes), 2 + 2, out)  # two lengths, plus a no-fact control for each
        self.assertTrue(all(abs(s - t) / t < 0.15 for s, t in zip(sizes[::2], (8000, 32000))), sizes)

    def test_chars_per_token_sets_the_sizing_and_the_table_reports_the_counted_tokens(self):
        code, out = self.dry("--lengths", "8000", "--depths", "0.5", "--chars-per-token", "3")
        self.assertEqual(code, 0, out)
        chars = [int(x) for x in re.findall(r"chars=(\d+)", out)]
        self.assertTrue(all(abs(c - 24000) / 24000 < 0.05 for c in chars), chars)  # 8000 * 3
        self.assertTrue(all(abs(int(t) - 8000) / 8000 < 0.05 for t in re.findall(r"approx_tokens=(\d+)", out)), out)
        # a real run: the stub counts len(prompt)//4, and the table shows that count, not the request
        code, out = self.run_script("--lengths", "4000", "--depths", "0.5", "--chars-per-token", "2", "--out", str(Path(os.environ.get("TEMP", ".")) / "depth-probe-cpt.jsonl"))
        self.assertEqual(code, 0, out)
        m = re.search(r"^4000\s+0\.5\s+1/1\s+\S+\s+(\d+)\s*$", out, re.M)
        self.assertIsNotNone(m, out)
        self.assertLess(abs(int(m.group(1)) - 2000) / 2000, 0.05, out)  # 8000 chars / 4
        rows = [json.loads(l) for l in (Path(os.environ.get("TEMP", ".")) / "depth-probe-cpt.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(rows[0]["prompt_tokens"], int(m.group(1)))
        self.assertEqual(rows[0]["chars_per_token"], 2.0)
        (Path(os.environ.get("TEMP", ".")) / "depth-probe-cpt.jsonl").unlink()

    def test_the_fact_sits_near_the_requested_depth(self):
        code, out = self.dry("--lengths", "16000", "--depths", "0.1,0.5,0.9")
        self.assertEqual(code, 0, out)
        got = [float(x) for x in re.findall(r"fact_at=(\d\.\d+)", out)]
        self.assertEqual(len(got), 3, out)
        for want, have in zip((0.1, 0.5, 0.9), got):
            self.assertLess(abs(want - have), 0.03, (want, have))

    def test_the_prompt_is_deterministic_for_a_seed_and_changes_with_it(self):
        a = self.dry("--lengths", "8000", "--depths", "0.5", "--seed", "1", "--show-prompt")[1]
        b = self.dry("--lengths", "8000", "--depths", "0.5", "--seed", "1", "--show-prompt")[1]
        c = self.dry("--lengths", "8000", "--depths", "0.5", "--seed", "2", "--show-prompt")[1]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_a_control_prompt_without_the_fact_is_always_included(self):
        code, out = self.dry("--lengths", "8000", "--depths", "0.5", "--show-prompt")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(CODE_RE.findall(out)), 1, "one prompt carries the fact, the control carries none")
        self.assertIn("control", out.lower())

    # ---- running against the stub
    def test_a_model_that_reads_everything_scores_full_marks_and_the_control_passes(self):
        code, out = self.run_script("--lengths", "4000", "--depths", "0.1,0.9", "--samples", "2")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"4000\s+0\.1\s+2/2")
        self.assertRegex(out, r"4000\s+0\.9\s+2/2")
        self.assertRegex(out, r"control\s+4000\s+2/2", out)

    def test_a_model_blind_to_the_deep_half_shows_zero_there_and_the_exit_code_is_still_0(self):
        Stub.blind_after = 0.5
        code, out = self.run_script("--lengths", "4000", "--depths", "0.1,0.9", "--samples", "2")
        self.assertEqual(code, 0, "a measurement is not a pass or a fail: " + out)
        self.assertRegex(out, r"4000\s+0\.1\s+2/2")
        self.assertRegex(out, r"4000\s+0\.9\s+0/2")

    def test_a_model_that_invents_a_code_for_the_control_fails_the_control(self):
        class Liar(Stub):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                out = json.dumps({"message": {"content": "ZEBRA-9999"}, "done": True, "done_reason": "stop"}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
        httpd = HTTPServer(("127.0.0.1", 0), Liar)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            r = subprocess.run([sys.executable, str(SCRIPT), "--url", f"http://127.0.0.1:{httpd.server_address[1]}", "--model", "m", "--lengths", "4000", "--depths", "0.5"], capture_output=True, text=True, timeout=60)
            self.assertRegex(r.stdout, r"control\s+4000\s+0/1")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_the_request_pins_the_context_and_turns_thinking_off_by_default(self):
        self.run_script("--lengths", "4000", "--depths", "0.5")
        body = Stub.requests[0]
        self.assertEqual(body["options"]["num_ctx"], 65536)
        self.assertIs(body.get("think"), False)
        self.assertIs(body.get("stream"), False)
        self.assertEqual(body["model"], "stub-model")

    def test_results_are_written_as_json_lines_when_asked(self):
        out_file = Path(os.environ.get("TEMP", ".")) / "depth-probe-test.jsonl"
        if out_file.exists():
            out_file.unlink()
        code, out = self.run_script("--lengths", "4000", "--depths", "0.5", "--out", str(out_file))
        self.assertEqual(code, 0, out)
        rows = [json.loads(l) for l in out_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(rows), 2)  # the fact prompt and the control
        self.assertTrue({"length", "depth", "control", "correct", "seconds"} <= set(rows[0]))
        out_file.unlink()

    # ---- safety
    def test_only_a_loopback_address_is_accepted(self):
        for bad in ("http://example.com:11434", "http://198.51.100.5:11434", "https://api.example.org"):
            r = subprocess.run([sys.executable, str(SCRIPT), "--url", bad, "--model", "m", "--lengths", "4000", "--depths", "0.5"], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 2, bad + r.stdout + r.stderr)

    def test_the_script_has_no_dependency_beyond_the_standard_library_and_sends_only_synthetic_text(self):
        import ast
        src = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertFalse(names & {"requests", "numpy", "openai", "ollama", "subprocess"}, names)


if __name__ == "__main__":
    unittest.main()

"""Tests for check-findings-evidence.py: a finding is kept only when its quote is an exact substring of the packet, an
abstention is allowed only without a claim of absence, scope or cause, and a claim verdict loses SUPPORTED when its quote
is not in the packet. Fixtures: ../cases/findings-evidence/ (synthetic). Run: python test_check_findings_evidence.py
(standard library only; no model, network or GPU)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-findings-evidence.py"
CASE = HERE.parent / "cases" / "findings-evidence"

spec = importlib.util.spec_from_file_location("cfe", SCRIPT)
cfe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfe)


def run(packet_text, reply_obj, *extra):
    with tempfile.TemporaryDirectory() as d:
        pk = Path(d) / "packet.md"
        rp = Path(d) / "reply.json"
        out = Path(d) / "checked.json"
        pk.write_text(packet_text, encoding="utf-8")
        rp.write_text(json.dumps(reply_obj), encoding="utf-8")
        p = subprocess.run([sys.executable, "-I", str(SCRIPT), str(pk), str(rp), "--out", str(out), *extra],
                           capture_output=True, text=True, encoding="utf-8")
        checked = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        return p.returncode, p.stdout, checked


class FixtureLabels(unittest.TestCase):
    def test_fixture_labels_match_expected(self):
        packet = (CASE / "packet.md").read_text(encoding="utf-8")
        findings = json.loads((CASE / "findings.json").read_text(encoding="utf-8"))
        expected = json.loads((CASE / "expected.json").read_text(encoding="utf-8"))["labels"]
        self.assertGreater(len(expected), 0)
        self.assertEqual(len(expected), len(findings["findings"]))
        code, stdout, checked = run(packet, findings)
        got = [r["label"] for r in checked["results"]]
        self.assertEqual(got, expected)
        self.assertEqual(code, 1, "something was dropped, so the exit code is 1")
        self.assertEqual(len(checked["findings"]), sum(1 for l in expected if l.startswith("KEPT")))

    def test_positive_control_a_fabricated_quote_is_dropped(self):
        packet = "The sky is blue today.\n"
        code, stdout, checked = run(packet, {"findings": [{"quote": "The sky is green today.", "problem": "x", "fix": "y"}]})
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_NOT_FOUND)
        self.assertEqual(checked["findings"], [])
        self.assertEqual(code, 1)

    def test_clean_list_exits_zero(self):
        packet = "The sky is blue today.\n"
        code, stdout, checked = run(packet, {"findings": [{"quote": "sky is blue", "problem": "fine", "fix": "leave it"}]})
        self.assertEqual(code, 0)
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_KEPT)

    def test_quote_across_a_diff_line_break_matches(self):
        packet = ("diff --git a/x b/x\n@@ -1,2 +1,3 @@\n+    notes: Nothing read forbids automated\n"
                  "+      retrieval for a public repo.\n context line\n")
        reply = {"findings": [{"quote": "Nothing read forbids automated retrieval for a public repo", "problem": "p", "fix": "f"}]}
        code, stdout, checked = run(packet, reply)
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_KEPT)

    def test_no_diff_marker_stripping_outside_a_diff(self):
        packet = "- first bullet\n- second bullet\n"
        self.assertIsNone(cfe.diff_stripped(packet))
        reply = {"findings": [{"quote": "- first bullet", "problem": "p", "fix": "f"}]}
        code, stdout, checked = run(packet, reply)
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_KEPT)

    def test_empty_findings_is_a_valid_answer(self):
        code, stdout, checked = run("anything\n", {"findings": []})
        self.assertEqual(code, 0)
        self.assertEqual(checked["findings"], [])

    def test_curly_quotes_and_whitespace_are_normalised(self):
        packet = "He said “a signed license agreement is not needed” – twice.\n"
        reply = {"findings": [{"quote": "said \"a signed  license agreement is not needed\" - twice", "problem": "p", "fix": "f"}]}
        code, stdout, checked = run(packet, reply)
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_KEPT)

    def test_case_is_kept(self):
        code, stdout, checked = run("Access: API\n", {"findings": [{"quote": "access: api", "problem": "p", "fix": "f"}]})
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_NOT_FOUND)

    def test_widening_word_in_fix_counts_too(self):
        packet = "robots: unknown\n"
        reply = {"findings": [{"quote": "robots: unknown", "problem": "p", "fix": "Nothing to do."}]}
        code, stdout, checked = run(packet, reply)
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_SCOPE)
        self.assertIn("nothing", checked["results"][0]["widening_words"])

    def test_other_quote_field_name(self):
        packet = "line one\n"
        reply = {"findings": [{"evidence": "line one", "problem": "p", "fix": "f"}]}
        code, stdout, checked = run(packet, reply, "--quote-field", "evidence")
        self.assertEqual(checked["results"][0]["label"], cfe.LABEL_KEPT)

    def test_fenced_json_reply_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            pk = Path(d) / "p.md"; rp = Path(d) / "r.json"
            pk.write_text("alpha beta\n", encoding="utf-8")
            rp.write_text("```json\n{\"findings\": [{\"quote\": \"alpha\", \"problem\": \"p\", \"fix\": \"f\"}]}\n```", encoding="utf-8")
            p = subprocess.run([sys.executable, "-I", str(SCRIPT), str(pk), str(rp)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("KEPT", p.stdout)

    def test_bad_input_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            pk = Path(d) / "p.md"; rp = Path(d) / "r.json"
            pk.write_text("x", encoding="utf-8"); rp.write_text("{not json", encoding="utf-8")
            p = subprocess.run([sys.executable, "-I", str(SCRIPT), str(pk), str(rp)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 2)
            p = subprocess.run([sys.executable, "-I", str(SCRIPT), str(pk / "missing"), str(rp)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 2)


class ClaimMode(unittest.TestCase):
    PACKET = ("<sentence>\nIn a study, 33% of teens preferred an AI companion.\n</sentence>\n"
              "<untrusted_page>\n33% of teens reported they would rather discuss something serious with an AI companion than a person.\n</untrusted_page>\n")

    def test_supported_with_found_quote_is_kept(self):
        reply = {"verdict": "SUPPORTED", "overreach_words": [], "quote": "33% of teens reported they would rather discuss", "reason": "r"}
        code, stdout, checked = run(self.PACKET, reply)
        self.assertEqual(code, 0)
        self.assertEqual(checked["verdict"], "SUPPORTED")

    def test_supported_with_fabricated_quote_becomes_unverified(self):
        reply = {"verdict": "SUPPORTED", "overreach_words": [], "quote": "33% of adults reported", "reason": "r"}
        code, stdout, checked = run(self.PACKET, reply)
        self.assertEqual(code, 1)
        self.assertEqual(checked["verdict"], "UNVERIFIED")

    def test_partly_with_fabricated_quote_becomes_unverified(self):
        reply = {"verdict": "PARTLY", "overreach_words": ["teens"], "quote": "nowhere text", "reason": "r"}
        code, stdout, checked = run(self.PACKET, reply)
        self.assertEqual(checked["verdict"], "UNVERIFIED")

    def test_not_stated_may_have_empty_quote(self):
        reply = {"verdict": "NOT STATED", "overreach_words": [], "quote": "", "reason": "r"}
        code, stdout, checked = run(self.PACKET, reply)
        self.assertEqual(code, 0)
        self.assertEqual(checked["verdict"], "NOT STATED")

    def test_overreach_word_not_in_sentence_is_removed(self):
        reply = {"verdict": "PARTLY", "overreach_words": ["teens", "adults"], "quote": "33% of teens reported", "reason": "r"}
        code, stdout, checked = run(self.PACKET, reply)
        self.assertEqual(code, 1)
        self.assertEqual(checked["overreach_words"], ["teens"])
        self.assertEqual(checked["verdict"], "PARTLY")


class Units(unittest.TestCase):
    def test_abstain_forms(self):
        for s in ("not stated", "Not stated in the packet", "not stated in the diff.", " not stated in the document "):
            self.assertTrue(cfe.ABSTAIN.match(s), s)
        for s in ("not stated here", "stated", "the diff does not state it"):
            self.assertFalse(cfe.ABSTAIN.match(s), s)

    def test_widening_words(self):
        self.assertEqual(cfe.widening_words("The entry lacks a base_url, so no tool can reach it"), ["lacks", "no"])
        self.assertEqual(cfe.widening_words("a plain remark about the date"), [])
        self.assertIn("because", cfe.widening_words("It failed because of X"))
        self.assertNotIn("no", cfe.widening_words("notes and nothing"))  # "no" must be a whole word; "nothing" is its own entry


if __name__ == "__main__":
    unittest.main()

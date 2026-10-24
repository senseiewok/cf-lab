#!/usr/bin/env python3
"""Unit tests for tasks/audit_session_errors.py."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

import audit_session_errors as ase  # noqa: E402


class TestAuditSessionErrors(unittest.TestCase):
    def test_redact_sensitive(self):
        text = "Error with API key ghp_1234567890123456789012 and Bearer secret_token_xyz_12345678"
        redacted = ase.redact_sensitive(text)
        self.assertNotIn("ghp_1234567890123456789012", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)
        self.assertIn("[REDACTED_TOKEN]", redacted)

        email_text = "Contact user at research@senseiewok.org for support"
        redacted_email = ase.redact_sensitive(email_text)
        self.assertNotIn("research@senseiewok.org", redacted_email)
        self.assertIn("[REDACTED_EMAIL]", redacted_email)

    def test_scan_transcript_detects_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript = Path(tmpdir) / "transcript.jsonl"
            lines = [
                json.dumps({"step_index": 0, "type": "USER_INPUT", "status": "DONE", "content": "hello"}),
                json.dumps({"step_index": 1, "type": "PLANNER_RESPONSE", "status": "ERROR", "content": "Failed execution"}),
                json.dumps({"step_index": 2, "type": "PLANNER_RESPONSE", "status": "DONE", "content": "Traceback (most recent call last):\n  File \"<string>\", line 1\nSyntaxError: invalid syntax"}),
                json.dumps({"step_index": 3, "type": "TOOL_RESPONSE", "status": "DONE", "content": "The command exited with code 1.\nOutput: grep: The term 'grep' is not recognized"}),
                json.dumps({"step_index": 4, "type": "TOOL_RESPONSE", "status": "DONE", "content": "grep : The term 'grep' is not recognized\nCommand exited with code 0."}),
            ]
            transcript.write_text("\n".join(lines), encoding="utf-8")

            findings = ase.scan_transcript(transcript)
            self.assertEqual(len(findings), 4)
            self.assertEqual(findings[0]["status"], "ERROR")
            self.assertIn("Python SyntaxError", findings[1]["categories"])
            self.assertIn("Python Traceback", findings[1]["categories"])
            self.assertIn("Inline Python -c Error", findings[1]["categories"])
            self.assertIn("Missing Shell Utility (grep/rg)", findings[2]["categories"])
            self.assertIn("Missing Shell Utility (grep/rg)", findings[3]["categories"])

    def test_scan_transcript_ignores_self_audit_and_readonly_views(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript = Path(tmpdir) / "transcript.jsonl"
            lines = [
                json.dumps({
                    "step_index": 1,
                    "type": "TOOL_RESPONSE",
                    "status": "DONE",
                    "content": "Sensei Ewok CF Lab - Session Error & Improvement Audit\nCategory Breakdown:\n  - Python SyntaxError: 18\n  - PowerShell ParserError: 12\nCommand exited with code 0.",
                }),
                json.dumps({
                    "step_index": 2,
                    "type": "TOOL_RESPONSE",
                    "status": "DONE",
                    "content": "Showing lines 1-50 of 100\n45: (re.compile(r'SyntaxError:', re.I), 'Python SyntaxError')",
                }),
                json.dumps({
                    "step_index": 3,
                    "type": "USER_INPUT",
                    "status": "DONE",
                    "content": "Check why SyntaxError: and ParserError: appeared in the digest.",
                }),
                json.dumps({
                    "step_index": 4,
                    "type": "TOOL_RESPONSE",
                    "status": "DONE",
                    "content": "Created At: 2026-10-23T07:24:29-07:00\nCompleted At: 2026-10-23T07:24:30-07:00\nShowing lines 1-50 of 100\n10: Lock actively held by sentinel\n11: Traceback (most recent call last):",
                }),
                json.dumps({
                    "step_index": 5,
                    "type": "TOOL_RESPONSE",
                    "status": "DONE",
                    "content": "Created At: 2026-10-23T07:24:29-07:00\r\nCompleted At: 2026-10-23T07:24:30-07:00\r\nPartial read (lines 1-50 of 100).\r\n10: SyntaxError: invalid syntax",
                }),
            ]
            transcript.write_text("\n".join(lines), encoding="utf-8")
            self.assertEqual(ase.scan_transcript(transcript), [])

    def test_scan_task_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir)
            tasks_dir = session_dir / ".system_generated" / "tasks"
            tasks_dir.mkdir(parents=True)
            log_file = tasks_dir / "task-1.log"
            log_file.write_text("The command exited with code 1.\nError: cannot find path 'missing.txt'\n", encoding="utf-8")
            ok_log = tasks_dir / "task-2.log"
            ok_log.write_text("Command exited with code 0.\nPrinted string Lock actively held during test\n", encoding="utf-8")
            masked_grep_log = tasks_dir / "task-3.log"
            masked_grep_log.write_text("grep : The term 'grep' is not recognized as the name of a cmdlet\nCommand exited with code 0.\n", encoding="utf-8")

            findings = ase.scan_task_logs(session_dir)
            self.assertEqual(len(findings), 2)
            by_file = {f["task_file"]: f["categories"] for f in findings}
            self.assertIn("Non-Zero Exit Code", by_file["task-1.log"])
            self.assertIn("Path Not Found", by_file["task-1.log"])
            self.assertIn("Missing Shell Utility (grep/rg)", by_file["task-3.log"])

    def test_audit_sessions_end_to_end_and_python_step_dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brain_dir = Path(tmpdir)
            session_dir = brain_dir / "test-session-1"
            logs_dir = session_dir / ".system_generated" / "logs"
            logs_dir.mkdir(parents=True)
            transcript = logs_dir / "transcript.jsonl"
            transcript.write_text(
                "\n".join([
                    json.dumps({
                        "step_index": 1,
                        "type": "TOOL_CALL",
                        "status": "ERROR",
                        "content": "ParserError: unexpected token in command",
                    }),
                    json.dumps({
                        "step_index": 2,
                        "type": "TOOL_RESPONSE",
                        "status": "DONE",
                        "content": 'Traceback (most recent call last):\n  File "<string>", line 1\nSyntaxError: invalid syntax',
                    }),
                ]),
                encoding="utf-8",
            )

            digest = ase.audit_sessions(brain_dir, max_age_hours=1.0)
            self.assertEqual(digest["summary"]["sessions_scanned"], 1)
            self.assertEqual(digest["summary"]["sessions_with_errors"], 1)
            self.assertEqual(digest["summary"]["total_error_steps"], 2)
            py_imp = next(i for i in digest["recommended_improvements"] if i["area"] == "python_execution")
            self.assertEqual(
                py_imp["observation"],
                "Detected 1 Python error step(s) (1 from inline python -c).",
            )


if __name__ == "__main__":
    unittest.main()

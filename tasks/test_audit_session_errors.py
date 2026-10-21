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
                json.dumps({"step_index": 2, "type": "PLANNER_RESPONSE", "status": "DONE", "content": "Traceback (most recent call last):\n  File 'x.py', line 1\nSyntaxError: invalid syntax"}),
            ]
            transcript.write_text("\n".join(lines), encoding="utf-8")

            findings = ase.scan_transcript(transcript)
            self.assertEqual(len(findings), 2)
            self.assertEqual(findings[0]["status"], "ERROR")
            self.assertIn("Python SyntaxError", findings[1]["categories"])
            self.assertIn("Python Traceback", findings[1]["categories"])

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

            findings = ase.scan_task_logs(session_dir)
            self.assertEqual(len(findings), 1)
            self.assertIn("Non-Zero Exit Code", findings[0]["categories"])
            self.assertIn("Path Not Found", findings[0]["categories"])

    def test_audit_sessions_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brain_dir = Path(tmpdir)
            session_dir = brain_dir / "test-session-1"
            logs_dir = session_dir / ".system_generated" / "logs"
            logs_dir.mkdir(parents=True)
            transcript = logs_dir / "transcript.jsonl"
            transcript.write_text(json.dumps({
                "step_index": 1,
                "type": "TOOL_CALL",
                "status": "ERROR",
                "content": "ParserError: unexpected token in command"
            }), encoding="utf-8")

            digest = ase.audit_sessions(brain_dir, max_age_hours=1.0)
            self.assertEqual(digest["summary"]["sessions_scanned"], 1)
            self.assertEqual(digest["summary"]["sessions_with_errors"], 1)
            self.assertEqual(digest["summary"]["total_error_steps"], 1)
            self.assertGreaterEqual(len(digest["recommended_improvements"]), 1)
            self.assertEqual(digest["recommended_improvements"][0]["area"], "powershell_tooling")


if __name__ == "__main__":
    unittest.main()

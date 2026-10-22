#!/usr/bin/env python3
"""Unit tests for tasks/check_agent_command_safety.py."""
from __future__ import annotations

import unittest
from pathlib import Path
from tasks.check_agent_command_safety import lint_file_content, scan_workspace


class TestCheckAgentCommandSafety(unittest.TestCase):
    def setUp(self):
        self.dummy_path = Path("tasks/dummy_script.ps1")

    def test_clean_command_passes(self):
        clean_content = (
            "# Safe PowerShell script invocation\n"
            "python tasks/triage_board.py --check\n"
            "$output = & python .claude/skills/workspace-siblings/scripts/check-workspace.py\n"
        )
        findings = lint_file_content(self.dummy_path, clean_content)
        self.assertEqual(len(findings), 0)

    def test_detects_hardcoded_user_dir(self):
        bad_content = (
            "Set-Location C:\\Users\\johndoe\\repo\n"
        )
        findings = lint_file_content(self.dummy_path, bad_content)
        self.assertTrue(any(f["code"] == "HARDCODED_USER_DIR" for f in findings))

    def test_detects_fragile_deep_traversal(self):
        bad_content = (
            "cd ../../../some/other/folder\n"
        )
        findings = lint_file_content(self.dummy_path, bad_content)
        self.assertTrue(any(f["code"] == "FRAGILE_PARENT_CD" for f in findings))

    def test_detects_nested_double_quote_hazard(self):
        bad_content = (
            'python -c "import os; print("hello")"\n'
        )
        findings = lint_file_content(self.dummy_path, bad_content)
        self.assertTrue(any(f["code"] == "NESTED_DOUBLE_QUOTES" for f in findings))

    def test_workspace_scan_runs_without_exception(self):
        findings = scan_workspace()
        self.assertIsInstance(findings, list)


if __name__ == "__main__":
    unittest.main()

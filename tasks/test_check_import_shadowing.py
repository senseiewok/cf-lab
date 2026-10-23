#!/usr/bin/env python3
"""Unit tests for check_import_shadowing.py (T-0344)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_import_shadowing import (
    audit_file_content,
    audit_filename_shadowing,
    audit_workspace,
    is_stdlib_module,
    is_third_party_collision,
)


class TestCheckImportShadowing(unittest.TestCase):
    def test_is_stdlib_module(self) -> None:
        self.assertTrue(is_stdlib_module("math"))
        self.assertTrue(is_stdlib_module("json"))
        self.assertTrue(is_stdlib_module("os"))
        self.assertTrue(is_stdlib_module("sys"))
        self.assertTrue(is_stdlib_module("subprocess"))
        self.assertTrue(is_stdlib_module("argparse"))

        self.assertFalse(is_stdlib_module("custom_model"))
        self.assertFalse(is_stdlib_module("cftr_analyzer"))

    def test_is_third_party_collision(self) -> None:
        self.assertTrue(is_third_party_collision("yaml"))
        self.assertTrue(is_third_party_collision("pytest"))
        self.assertTrue(is_third_party_collision("requests"))
        self.assertTrue(is_third_party_collision("playwright"))

        self.assertFalse(is_third_party_collision("custom_tool"))

    def test_audit_filename_shadowing_stdlib(self) -> None:
        bad_path = Path("tasks/math.py")
        findings = audit_filename_shadowing(bad_path, is_in_package=False)
        errors = [f for f in findings if f.rule == "STDLIB_MODULE_SHADOWING"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "ERROR")

    def test_audit_filename_shadowing_third_party(self) -> None:
        bad_path = Path("tools/yaml.py")
        findings = audit_filename_shadowing(bad_path, is_in_package=False)
        errors = [f for f in findings if f.rule == "THIRD_PARTY_DEPENDENCY_MASQUERADING"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "ERROR")

    def test_audit_filename_clean(self) -> None:
        clean_path = Path("tasks/custom_clean_linter.py")
        findings = audit_filename_shadowing(clean_path, is_in_package=False)
        self.assertEqual(len(findings), 0)

    def test_excessive_relative_import(self) -> None:
        code = """
from .....utils import dangerous_climb
"""
        findings = audit_file_content("my_package/sub/file.py", code)
        errors = [f for f in findings if f.rule == "EXCESSIVE_RELATIVE_IMPORT"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].severity, "ERROR")

    def test_valid_relative_import(self) -> None:
        code = """
from .utils import helper
from ..models import CftrModel
"""
        findings = audit_file_content("my_package/sub/file.py", code)
        errors = [f for f in findings if f.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_audit_workspace_clean(self) -> None:
        lab_root = Path(__file__).resolve().parents[1]
        report = audit_workspace(lab_root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["total_violations"], 0)
        self.assertGreaterEqual(report["total_files_audited"], 10)


if __name__ == "__main__":
    unittest.main()

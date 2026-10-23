#!/usr/bin/env python3
"""Unit tests for tasks/check_dynamic_imports.py."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_dynamic_imports import (
    is_safe_module_name,
    safe_import_module,
    audit_python_dynamic_imports,
    scan_workspace,
)


class TestCheckDynamicImports(unittest.TestCase):
    """Test dynamic import auditing, module validation, and sandboxing."""

    def test_is_safe_module_name(self):
        """Verify strict dotted identifier validation."""
        self.assertTrue(is_safe_module_name("math"))
        self.assertTrue(is_safe_module_name("json.decoder"))
        self.assertTrue(is_safe_module_name("os.path"))
        self.assertTrue(is_safe_module_name("tasks.check_dynamic_imports"))
        self.assertTrue(is_safe_module_name("_private_module.sub_pkg"))

        self.assertFalse(is_safe_module_name(""))
        self.assertFalse(is_safe_module_name("os; rm -rf /"))
        self.assertFalse(is_safe_module_name("../../../etc/passwd"))
        self.assertFalse(is_safe_module_name("foo/bar"))
        self.assertFalse(is_safe_module_name("foo\\bar"))
        self.assertFalse(is_safe_module_name("math\x00"))
        self.assertFalse(is_safe_module_name("123invalid"))
        self.assertFalse(is_safe_module_name("has spaces.mod"))

    def test_safe_import_module_success(self):
        """Verify safe import of permitted standard modules."""
        mod = safe_import_module("math")
        self.assertEqual(mod.__name__, "math")
        self.assertTrue(hasattr(mod, "sqrt"))

        mod_json = safe_import_module("json", allowed_modules={"json", "math"})
        self.assertEqual(mod_json.__name__, "json")

    def test_safe_import_module_containment_violation(self):
        """Verify that unsafe module names raise ValueError."""
        with self.assertRaises(ValueError):
            safe_import_module("os; evil_payload")
        with self.assertRaises(ValueError):
            safe_import_module("../../traversal")

    def test_safe_import_module_whitelist_enforcement(self):
        """Verify that non-whitelisted modules raise ValueError."""
        with self.assertRaises(ValueError):
            safe_import_module("sys", allowed_modules={"math", "json"})

    def test_audit_safe_literal_dynamic_imports(self):
        """Verify that constant string literals in imports do not trigger errors."""
        code = '''
import os
import math

def foo():
    mod = __import__("json")
    return mod
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_dynamic_imports(tmp_path)
            errors = [x for x in findings if x.severity == "ERROR"]
            self.assertEqual(len(errors), 0)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_audit_flag_unconstrained_import_variable(self):
        """Verify that variable or expression arguments to __import__ are flagged."""
        code = '''
def load_plugin(user_name):
    # Unsafe dynamic import
    return __import__(user_name)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_dynamic_imports(tmp_path)
            rules = [x.rule for x in findings]
            self.assertIn("DYNAMIC_IMPORT_UNCONSTRAINED", rules)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_audit_flag_unconstrained_importlib(self):
        """Verify that dynamic importlib.import_module() arguments are flagged."""
        code = '''
import importlib

def load_user_module(name):
    return importlib.import_module(name)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_dynamic_imports(tmp_path)
            rules = [x.rule for x in findings]
            self.assertIn("DYNAMIC_IMPORT_UNCONSTRAINED", rules)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_audit_flag_exec_eval_dynamic_imports(self):
        """Verify that eval() and exec() with embedded imports are flagged."""
        code = '''
def run_bad_stuff():
    exec("import os; os.system('echo hi')")
    eval("__import__('sys').version")
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_dynamic_imports(tmp_path)
            rules = [x.rule for x in findings]
            self.assertEqual(rules.count("EVAL_EXEC_DYNAMIC_IMPORT"), 2)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_test_file_exemption(self):
        """Verify that test files are exempted from production dynamic import flagging."""
        code = '''
import importlib

def test_something():
    m = importlib.import_module("some_test_fixture")
    assert m is not None
'''
        with tempfile.NamedTemporaryFile("w", prefix="test_fixture_", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_dynamic_imports(tmp_path)
            self.assertEqual(len(findings), 0)
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

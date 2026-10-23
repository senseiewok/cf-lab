#!/usr/bin/env python3
"""Unit tests for check_ast_obfuscation_invariants.py."""
from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_ast_obfuscation_invariants import (
    ASTObfuscationVisitor,
    audit_repo_ast_obfuscation,
    get_sibling_repo_roots,
)


class TestASTObfuscationInvariants(unittest.TestCase):
    """Test suite verifying AST dynamic code execution and import obfuscation invariants."""

    def _parse_and_visit(self, code: str, filename: str = "script.py", is_test: bool = False):
        tree = ast.parse(code, filename=filename)
        visitor = ASTObfuscationVisitor(Path(filename), is_test_file=is_test)
        visitor.visit(tree)
        return visitor

    def test_detects_prohibited_eval(self) -> None:
        code = "result = eval('2 + 2')\n"
        visitor = self._parse_and_visit(code)
        self.assertEqual(len(visitor.violations), 1)
        self.assertIn("Prohibited dynamic code execution built-in 'eval()'", visitor.violations[0])

    def test_detects_prohibited_exec(self) -> None:
        code = "exec('import os; os.system(\"ls\")')\n"
        visitor = self._parse_and_visit(code)
        self.assertEqual(len(visitor.violations), 1)
        self.assertIn("Prohibited dynamic code execution built-in 'exec()'", visitor.violations[0])

    def test_detects_prohibited_compile(self) -> None:
        code = "code_obj = compile('x = 1', '<string>', 'exec')\n"
        visitor = self._parse_and_visit(code)
        self.assertEqual(len(visitor.violations), 1)
        self.assertIn("Prohibited dynamic code execution built-in 'compile()'", visitor.violations[0])

    def test_detects_dynamic_import(self) -> None:
        code = "mod = __import__('subprocess')\n"
        visitor = self._parse_and_visit(code)
        self.assertEqual(len(visitor.violations), 1)
        self.assertIn("Dynamic module import '__import__()' detected", visitor.violations[0])

    def test_whitelisted_place_art_inline_import(self) -> None:
        code = "env = {**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'}\n"
        visitor = self._parse_and_visit(code, filename="place-art.py")
        self.assertEqual(len(visitor.violations), 0)

    def test_detects_reflection_subclasses(self) -> None:
        code = "subclasses = object.__subclasses__()\n"
        visitor = self._parse_and_visit(code)
        self.assertTrue(len(visitor.violations) >= 1)
        self.assertTrue(any("__subclasses__" in v for v in visitor.violations))

    def test_detects_reflection_globals(self) -> None:
        code = "g = my_func.__globals__['os']\n"
        visitor = self._parse_and_visit(code)
        self.assertTrue(len(visitor.violations) >= 1)
        self.assertTrue(any("__globals__" in v for v in visitor.violations))

    def test_detects_obfuscated_hex_string(self) -> None:
        # A raw string or bytes dominated by hex escapes / unprintable bytes
        hex_payload = r"\x31\xc0\x50\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69\x6e\x89\xe3\x50\x53\x89\xe1\x31" * 6
        code = f"payload = r'{hex_payload}'\n"
        visitor = self._parse_and_visit(code)
        self.assertEqual(len(visitor.violations), 1)
        self.assertIn("Obfuscated hex-escaped sequence detected", visitor.violations[0])

    def test_detects_obfuscated_binary_bytes(self) -> None:
        raw_bytes = bytes([1, 2, 3, 4, 5, 0, 255, 200, 150, 12, 14, 15] * 10)
        code = f"payload = {repr(raw_bytes)}\n"
        visitor = self._parse_and_visit(code)
        self.assertEqual(len(visitor.violations), 1)
        self.assertIn("Obfuscated binary payload detected", visitor.violations[0])

    def test_clean_python_script_passes(self) -> None:
        code = (
            "import os\n"
            "from pathlib import Path\n"
            "\n"
            "def calculate(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )
        visitor = self._parse_and_visit(code)
        self.assertEqual(len(visitor.violations), 0)
        self.assertEqual(len(visitor.warnings), 0)

    def test_test_file_downgrades_to_warning(self) -> None:
        code = "eval('1 + 1')\n"
        visitor = self._parse_and_visit(code, filename="test_something.py", is_test=True)
        self.assertEqual(len(visitor.violations), 0)
        self.assertEqual(len(visitor.warnings), 1)
        self.assertIn("'eval()'", visitor.warnings[0])


if __name__ == "__main__":
    unittest.main()

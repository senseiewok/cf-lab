#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo Unicode Homoglyph & Invisible Character Injection Linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_unicode_homoglyphs import (  # noqa: E402
    audit_confusable_identifier_homoglyphs,
    audit_invisible_zero_width_characters,
    audit_trojan_source_bidi,
    run_full_unicode_linter,
    REPO_ROOT,
)


class TestCheckUnicodeHomoglyphs(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_repo_root_unicode_linter_pass(self) -> None:
        report = run_full_unicode_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertGreater(report["metadata"]["files_scanned"], 50)

    def test_trojan_source_bidi_clean_pass(self) -> None:
        src = self.root / "clean.py"
        src.write_text("def calculate_score(val):\n    return val * 10\n", encoding="utf-8")
        errors, warnings, meta = audit_trojan_source_bidi(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(meta["bidi_violations"], 0)

    def test_trojan_source_bidi_rlo_detected(self) -> None:
        src = self.root / "trojan.py"
        # Injects U+202E (RLO) in an access control check
        src.write_text("access_level = 'user'\nif access_level == 'admin\u202e':\n    grant()\n", encoding="utf-8")
        errors, _, meta = audit_trojan_source_bidi(self.root)
        self.assertTrue(any("Trojan Source Bidi character U+202E" in e for e in errors))
        self.assertEqual(meta["bidi_violations"], 1)

    def test_trojan_source_bidi_allowlist_comment(self) -> None:
        src = self.root / "exempt.py"
        src.write_text("pattern = '\u202e'  # noqa: unicode\n", encoding="utf-8")
        errors, warnings, meta = audit_trojan_source_bidi(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(meta["bidi_violations"], 0)

    def test_invisible_character_zwsp_detected(self) -> None:
        src = self.root / "hidden.py"
        # Zero-width space U+200B inside identifier or string
        src.write_text("secret_var\u200b = 42\n", encoding="utf-8")
        errors, _, meta = audit_invisible_zero_width_characters(self.root)
        self.assertTrue(any("Invisible character U+200B" in e for e in errors))
        self.assertEqual(meta["invisible_violations"], 1)

    def test_invisible_character_soft_hyphen_detected(self) -> None:
        doc = self.root / "doc.md"
        # Soft hyphen U+00AD
        doc.write_text("# Section\nCon\u00adtent\n", encoding="utf-8")
        errors, _, meta = audit_invisible_zero_width_characters(self.root)
        self.assertTrue(any("Invisible character U+00AD" in e for e in errors))
        self.assertEqual(meta["invisible_violations"], 1)

    def test_confusable_homoglyph_cyrillic_in_identifier(self) -> None:
        src = self.root / "confusable.py"
        # Cyrillic small 'а' (U+0430) instead of ASCII 'a'
        src.write_text("def p\u0430rse_token():\n    pass\n", encoding="utf-8")
        errors, _, meta = audit_confusable_identifier_homoglyphs(self.root)
        self.assertTrue(any("Confusable homoglyph identifier" in e for e in errors))
        self.assertEqual(meta["confusable_violations"], 1)

    def test_confusable_homoglyph_clean_code_and_comment(self) -> None:
        src = self.root / "normal.py"
        src.write_text(
            "# Привет мир (Cyrillic comment is allowed)\n"
            "def parse_token():\n"
            "    return True\n",
            encoding="utf-8",
        )
        errors, warnings, meta = audit_confusable_identifier_homoglyphs(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(meta["confusable_violations"], 0)


if __name__ == "__main__":
    unittest.main()

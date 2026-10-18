#!/usr/bin/env python3
"""Unit tests for tasks/check_i18n_parity.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

import check_i18n_parity as cip  # noqa: E402


class TestCheckI18nParity(unittest.TestCase):
    def test_resolve_key_dotted(self):
        catalog = {
            "chrome": {
                "banner": "Bienvenido",
                "nested": {"deep": "Profundo"},
            }
        }
        self.assertEqual(cip.resolve_key("chrome.banner", catalog), "Bienvenido")
        self.assertEqual(cip.resolve_key("chrome.nested.deep", catalog), "Profundo")
        self.assertIsNone(cip.resolve_key("chrome.missing", catalog))
        self.assertIsNone(cip.resolve_key("nonexistent.key", catalog))

    def test_resolve_key_fallback_sections(self):
        catalog = {
            "ptc": {
                "slider_title": "Control deslizante",
            },
            "cf": {
                "dignity_copy": "Investigación no médica",
            },
        }
        self.assertEqual(cip.resolve_key("slider_title", catalog), "Control deslizante")
        self.assertEqual(cip.resolve_key("dignity_copy", catalog), "Investigación no médica")
        self.assertIsNone(cip.resolve_key("completely_absent", catalog))

    def test_extract_i18n_attributes(self):
        html = """
        <div data-i18n="chrome.banner">Hello</div>
        <span data-i18n-title="tree.title" data-i18n-body="tree.desc">Item</span>
        <button data-i18n-aria-label="btn_close">Close</button>
        <p>No i18n here</p>
        """
        attrs = cip.extract_i18n_attributes(html)
        self.assertEqual(len(attrs), 4)
        attr_dict = dict(attrs)
        self.assertEqual(attr_dict["data-i18n"], "chrome.banner")
        self.assertEqual(attr_dict["data-i18n-title"], "tree.title")
        self.assertEqual(attr_dict["data-i18n-body"], "tree.desc")
        self.assertEqual(attr_dict["data-i18n-aria-label"], "btn_close")

    def test_flatten_catalog(self):
        catalog = {
            "a": {"b": "1", "c": {"d": "2"}},
            "e": "3",
        }
        flat = cip.flatten_catalog(catalog)
        self.assertEqual(len(flat), 3)
        keys = [x[0] for x in flat]
        self.assertIn("a.b", keys)
        self.assertIn("a.c.d", keys)
        self.assertIn("e", keys)

    def test_audit_parity_mock_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            src_dir = tmp_root / "src"
            data_dir = tmp_root / "data" / "i18n"
            scripts_dir = src_dir / "scripts"
            src_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)
            scripts_dir.mkdir(parents=True)

            catalog = {
                "chrome": {"title": "Título", "desc": "Descripción"},
                "tree": {"node1": "Nodo 1"},
            }
            (data_dir / "es-MX.json").write_text(json.dumps(catalog), encoding="utf-8")

            html1 = '<h1 data-i18n="chrome.title">Title</h1><p data-i18n="chrome.desc">Desc</p>'
            (src_dir / "index.html").write_text(html1, encoding="utf-8")

            js1 = 'const x = ES_MX.tree.node1;'
            (scripts_dir / "site.js").write_text(js1, encoding="utf-8")

            digest = cip.audit_parity(tmp_root, routes=["index.html"])
            self.assertEqual(digest["status"], "CLEAN")
            self.assertEqual(digest["missing_keys_count"], 0)
            self.assertEqual(digest["total_attribute_uses"], 2)
            self.assertEqual(digest["orphan_keys_count"], 0)

    def test_audit_parity_mock_missing_and_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            src_dir = tmp_root / "src"
            data_dir = tmp_root / "data" / "i18n"
            src_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)

            catalog = {
                "chrome": {"title": "   "},  # empty/whitespace
            }
            (data_dir / "es-MX.json").write_text(json.dumps(catalog), encoding="utf-8")

            html1 = '<h1 data-i18n="chrome.title">Title</h1><p data-i18n="missing.key">Desc</p>'
            (src_dir / "index.html").write_text(html1, encoding="utf-8")

            digest = cip.audit_parity(tmp_root, routes=["index.html"])
            self.assertEqual(digest["status"], "FAIL")
            self.assertEqual(digest["missing_keys_count"], 2)
            reasons = [m["reason"] for m in digest["missing_keys"]]
            self.assertIn("Empty string", reasons)
            self.assertIn("Missing from catalog", reasons)

    def test_find_ai_root_resolves(self):
        try:
            root = cip.find_ai_root()
            self.assertTrue(root.is_dir())
            self.assertTrue((root / "src").is_dir())
            self.assertTrue((root / "data" / "i18n" / "es-MX.json").is_file())
        except FileNotFoundError:
            self.skipTest(".ai repository sibling not present in this environment")

    def test_live_workspace_i18n_parity(self):
        """Invariant: All data-i18n attributes across all .ai routes must resolve to valid translations."""
        try:
            root = cip.find_ai_root()
        except FileNotFoundError:
            self.skipTest(".ai repository sibling not present in this environment")
        digest = cip.audit_parity(root)
        self.assertEqual(
            digest["missing_keys_count"],
            0,
            f"Expected 0 missing keys, found: {digest['missing_keys']}",
        )
        self.assertEqual(digest["routes_scanned"], len(cip.CANONICAL_ROUTES))
        self.assertGreater(digest["total_attribute_uses"], 80)
        self.assertEqual(digest["status"], "CLEAN")

    def test_cli_execution_check(self):
        script_path = ROOT / "tasks" / "check_i18n_parity.py"
        res = subprocess.run(
            [sys.executable, str(script_path), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, f"CLI exited with non-zero code: {res.stderr}")
        self.assertIn("Status:                 CLEAN", res.stdout)
        self.assertIn("Missing / Unresolved:   0", res.stdout)

    def test_cli_execution_json(self):
        script_path = ROOT / "tasks" / "check_i18n_parity.py"
        res = subprocess.run(
            [sys.executable, str(script_path), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "CLEAN")
        self.assertEqual(data["missing_keys_count"], 0)


if __name__ == "__main__":
    unittest.main()

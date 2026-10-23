#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo Agent Path Traversal & Canonical Path Resolution Linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_path_traversal import (
    audit_python_path_traversal,
    audit_symlink_security,
    audit_workspace,
    is_contained_within,
    safe_resolve_path,
)


class TestCheckPathTraversal(unittest.TestCase):
    def test_safe_resolve_path_within_bounds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "subdir" / "data.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")

            resolved = safe_resolve_path("subdir/data.json", base_dir=base)
            self.assertEqual(resolved, target.resolve())

    def test_safe_resolve_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "workspace"
            base.mkdir()
            with self.assertRaises(ValueError):
                safe_resolve_path("../outside.txt", base_dir=base)

    def test_is_contained_within(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "app"
            base.mkdir()
            self.assertTrue(is_contained_within("config/settings.json", base_dir=base))
            self.assertFalse(is_contained_within("../../etc/passwd", base_dir=base))

    def test_detect_literal_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "vuln.py"
            py_file.write_text(
                "import os\n"
                "p = open('../../confidential/keys.env').read()\n",
                encoding="utf-8",
            )
            findings = audit_python_path_traversal(py_file)
            self.assertTrue(any(f.rule == "LITERAL_PATH_TRAVERSAL" and f.severity == "ERROR" for f in findings))

    def test_detect_unsafe_path_concat(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "concat.py"
            py_file.write_text(
                "def get_user_file(user_id):\n"
                "    return '/data/users/' + user_id\n",
                encoding="utf-8",
            )
            findings = audit_python_path_traversal(py_file)
            self.assertTrue(any(f.rule == "UNSAFE_PATH_CONCATENATION" for f in findings))

    def test_safe_python_file_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "clean.py"
            py_file.write_text(
                "from pathlib import Path\n"
                "base = Path('data').resolve()\n"
                "target = (base / 'file.txt').resolve()\n",
                encoding="utf-8",
            )
            findings = audit_python_path_traversal(py_file)
            errors = [f for f in findings if f.severity == "ERROR"]
            self.assertEqual(len(errors), 0)

    def test_symlink_security_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "data.txt"
            target.write_text("ok", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(target)
                findings = audit_symlink_security(root)
                self.assertEqual(len(findings), 0)
            except OSError:
                # Symlinks might require admin/developer mode on Windows
                pass


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Agent Temporary File Lifecycle & Insecure Mkdir/Mktemp Linter."""
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

from check_tempfile_security import (
    audit_python_tempfile_usage,
    audit_script_tempfile_usage,
    audit_workspace,
    create_secure_temp_dir,
    create_secure_temp_file,
    is_safe_temp_path,
)


class TestCheckTempfileSecurity(unittest.TestCase):
    def test_is_safe_temp_path(self):
        self.assertTrue(is_safe_temp_path("data/raw/catalog.yaml"))
        self.assertTrue(is_safe_temp_path("src/utils/temp_helper.py"))
        self.assertFalse(is_safe_temp_path("/tmp/insecure_script.py"))
        self.assertFalse(is_safe_temp_path("/var/tmp/data.json"))
        self.assertFalse(is_safe_temp_path(r"C:\Temp\output.log"))
        self.assertFalse(is_safe_temp_path(r"C:\Windows\Temp\test.txt"))

    def test_create_secure_temp_dir(self):
        temp_dir = create_secure_temp_dir(prefix="test-temp-dir-")
        try:
            self.assertTrue(temp_dir.exists())
            self.assertTrue(temp_dir.is_dir())
        finally:
            temp_dir.rmdir()

    def test_create_secure_temp_file(self):
        temp_file = create_secure_temp_file(suffix=".test")
        try:
            self.assertTrue(temp_file.exists())
            self.assertTrue(temp_file.is_file())
        finally:
            temp_file.unlink(missing_ok=True)

    def test_detect_insecure_mktemp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "vulnerable_worker.py"
            file_path.write_text(
                "import tempfile\n"
                "p = tempfile.mktemp()\n",
                encoding="utf-8",
            )
            findings = audit_python_tempfile_usage(file_path)
            self.assertTrue(any(f.rule == "INSECURE_MKTEMP" and f.severity == "ERROR" for f in findings))

    def test_detect_hardcoded_tmp_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "worker_output.py"
            file_path.write_text(
                "output_path = '/tmp/scratch_results.txt'\n"
                "with open(output_path, 'w') as f:\n"
                "    f.write('data')\n",
                encoding="utf-8",
            )
            findings = audit_python_tempfile_usage(file_path)
            self.assertTrue(any(f.rule == "HARDCODED_TMP_PATH" and f.severity == "ERROR" for f in findings))

    def test_detect_insecure_mkdir_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "insecure_mkdir.py"
            file_path.write_text(
                "import os\n"
                "os.makedirs('/data/scratch', mode=0o777)\n",
                encoding="utf-8",
            )
            findings = audit_python_tempfile_usage(file_path)
            self.assertTrue(any(f.rule == "INSECURE_DIR_PERMISSIONS" and f.severity == "ERROR" for f in findings))

    def test_clean_tempfile_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "safe_worker.py"
            file_path.write_text(
                "import tempfile\n"
                "with tempfile.TemporaryDirectory() as td:\n"
                "    p = td\n",
                encoding="utf-8",
            )
            findings = audit_python_tempfile_usage(file_path)
            errors = [f for f in findings if f.severity == "ERROR"]
            self.assertEqual(len(errors), 0)

    def test_detect_shell_static_tmp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "run_backup.sh"
            sh_file.write_text(
                "#!/bin/bash\n"
                "echo 'test' > /tmp/static_log.txt\n",
                encoding="utf-8",
            )
            findings = audit_script_tempfile_usage(sh_file)
            self.assertTrue(any(f.rule == "SHELL_STATIC_TMP_FILE" and f.severity == "ERROR" for f in findings))

    def test_audit_workspace_target_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            safe_py = Path(tmpdir) / "worker.py"
            safe_py.write_text(
                "import tempfile\n"
                "with tempfile.NamedTemporaryFile() as tf:\n"
                "    pass\n",
                encoding="utf-8",
            )
            report = audit_workspace(target_path=Path(tmpdir))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["total_violations"], 0)


if __name__ == "__main__":
    unittest.main()

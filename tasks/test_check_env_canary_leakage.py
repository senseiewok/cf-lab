#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Agent Environment Variable Leakage & Canary Isolation Linter."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_env_canary_leakage import (
    audit_canary_leakage,
    audit_python_env_leakage,
    get_isolated_agent_env,
    is_safe_env_dict,
)


class TestCheckEnvCanaryLeakage(unittest.TestCase):
    def test_get_isolated_agent_env_strips_credentials(self):
        # Temporarily inject sensitive environment variable
        old_val = os.environ.get("MOCK_SECRET_API_KEY")
        try:
            os.environ["MOCK_SECRET_API_KEY"] = "super-secret-1234"
            os.environ["MOCK_SAFE_VAR"] = "safe-public-value"
            
            isolated = get_isolated_agent_env()
            self.assertNotIn("MOCK_SECRET_API_KEY", isolated)
            self.assertIn("MOCK_SAFE_VAR", isolated)
        finally:
            if old_val is not None:
                os.environ["MOCK_SECRET_API_KEY"] = old_val
            else:
                os.environ.pop("MOCK_SECRET_API_KEY", None)
            os.environ.pop("MOCK_SAFE_VAR", None)

    def test_get_isolated_agent_env_with_allowed_and_extra(self):
        isolated = get_isolated_agent_env(
            allowed_vars={"SPECIFIC_ALLOWED_KEY"},
            extra_env={"CUSTOM_INJECTED": "test-val"},
        )
        self.assertEqual(isolated.get("CUSTOM_INJECTED"), "test-val")

    def test_is_safe_env_dict(self):
        clean_dict = {"PATH": "/usr/bin", "LANG": "en_US.UTF-8"}
        safe, leaked = is_safe_env_dict(clean_dict)
        self.assertTrue(safe)
        self.assertEqual(leaked, [])

        tainted_dict = {"PATH": "/usr/bin", "GITHUB_TOKEN": "ghp_mock"}
        safe, leaked = is_safe_env_dict(tainted_dict)
        self.assertFalse(safe)
        self.assertEqual(leaked, ["GITHUB_TOKEN"])

    def test_detect_unpurged_os_environ_passed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "worker.py"
            py_file.write_text(
                "import subprocess, os\n"
                "subprocess.run(['tool'], env=os.environ)\n",
                encoding="utf-8",
            )
            findings = audit_python_env_leakage(py_file)
            self.assertTrue(any(f.rule == "UNPURGED_OS_ENVIRON_PASSED" and f.severity == "ERROR" for f in findings))

    def test_detect_os_system_inheritance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "legacy_exec.py"
            py_file.write_text(
                "import os\n"
                "os.system('run_command')\n",
                encoding="utf-8",
            )
            findings = audit_python_env_leakage(py_file)
            self.assertTrue(any(f.rule == "OS_SYSTEM_ENVIRONMENT_INHERITANCE" for f in findings))

    def test_safe_subprocess_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "safe_worker.py"
            py_file.write_text(
                "import subprocess\n"
                "from check_env_canary_leakage import get_isolated_agent_env\n"
                "env = get_isolated_agent_env()\n"
                "subprocess.run(['tool'], env=env)\n",
                encoding="utf-8",
            )
            findings = audit_python_env_leakage(py_file)
            errors = [f for f in findings if f.severity == "ERROR"]
            self.assertEqual(len(errors), 0)

    def test_detect_canary_token_leakage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir) / "repo"
            repo_dir.mkdir()
            # Synthetic canary token inside non-test file
            leaked_file = repo_dir / "config.json"
            leaked_file.write_text('{"token": "sk-canary-1234567890abcdef"}', encoding="utf-8")
            
            findings = audit_canary_leakage(repo_dir)
            self.assertTrue(any(f.rule == "LEAKED_CANARY_TOKEN" and f.severity == "ERROR" for f in findings))


if __name__ == "__main__":
    unittest.main()

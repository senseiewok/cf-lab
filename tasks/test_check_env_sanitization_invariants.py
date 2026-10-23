#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Agent Environment Variable Leak & Process Memory Sanitization Linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_env_sanitization_invariants import (  # noqa: E402
    PRIVACY_PATTERNS_PATH,
    REPO_ROOT,
    audit_repo_subprocess_env,
    get_sanitized_env,
    load_privacy_canaries,
    redact_sensitive_tokens,
    run_full_env_sanitization_linter,
)

# Dynamically construct test tokens so static scanner patterns are not tripped in source files
TEST_GHP = "gh" + "p_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
TEST_SK = "s" + "k-" + "abcdef1234567890abcdef1234567890"
TEST_AKIA = "AK" + "IA" + "1234567890ABCDEF"
TEST_PRIV_KEY = "-----BEG" + "IN RSA PRIVATE " + "KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"


class TestCheckEnvSanitizationInvariants(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_repo_root_env_sanitization_linter_pass(self) -> None:
        report = run_full_env_sanitization_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertGreater(report["metadata"]["total_python_files_audited"], 10)
        self.assertGreaterEqual(report["metadata"]["canary_patterns_loaded"], 10)

    def test_get_sanitized_env_purges_tokens(self) -> None:
        dirty_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/user",
            "GH_TOKEN": "mock-token-sample-12345",
            "GITHUB_TOKEN": "mock-secret-token-sample-xyz",
            "GEMINI_API_KEY": "AIzaSyMockGeminiKey12345",
            "ANTHROPIC_API_KEY": "mock-anthropic-key-value",
            "OPENAI_API_KEY": "mock-openai-key-value",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "DATABASE_URL": "postgres://user:password@localhost:5432/db",
            "CUSTOM_SERVICE_TOKEN": "some-secret-token",
            "SAFE_VAR": "standard_safe_value",
        }
        sanitized = get_sanitized_env(dirty_env)
        self.assertIn("PATH", sanitized)
        self.assertIn("HOME", sanitized)
        self.assertIn("SAFE_VAR", sanitized)

        # Assert all sensitive variables are purged
        self.assertNotIn("GH_TOKEN", sanitized)
        self.assertNotIn("GITHUB_TOKEN", sanitized)
        self.assertNotIn("GEMINI_API_KEY", sanitized)
        self.assertNotIn("ANTHROPIC_API_KEY", sanitized)
        self.assertNotIn("OPENAI_API_KEY", sanitized)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", sanitized)
        self.assertNotIn("DATABASE_URL", sanitized)
        self.assertNotIn("CUSTOM_SERVICE_TOKEN", sanitized)

    def test_get_sanitized_env_allows_explicit_vars(self) -> None:
        dirty_env = {
            "GH_TOKEN": "allowed-token-for-specific-harness",
            "SECRET_KEY": "should_be_stripped",
            "PATH": "/usr/bin",
        }
        sanitized = get_sanitized_env(dirty_env, allow_vars={"GH_TOKEN"})
        self.assertIn("GH_TOKEN", sanitized)
        self.assertEqual(sanitized["GH_TOKEN"], "allowed-token-for-specific-harness")
        self.assertNotIn("SECRET_KEY", sanitized)

    def test_get_sanitized_env_extra_deny(self) -> None:
        env = {
            "MY_CUSTOM_CONFIG": "sensitive_internal_url",
            "PATH": "/usr/bin",
        }
        sanitized = get_sanitized_env(env, extra_deny_vars={"MY_CUSTOM_CONFIG"})
        self.assertNotIn("MY_CUSTOM_CONFIG", sanitized)
        self.assertIn("PATH", sanitized)

    def test_redact_sensitive_tokens(self) -> None:
        sample_log = (
            f"Error authenticating with {TEST_GHP}\n"
            f"Using OpenAI key {TEST_SK}\n"
            f"Using AWS key {TEST_AKIA}\n"
            "Authorization: Bearer my-very-long-oauth-access-token-string-value-here\n"
            "GH_TOKEN=secret_raw_token_value_xyz\n"
            f"{TEST_PRIV_KEY}"
        )
        redacted = redact_sensitive_tokens(sample_log)
        self.assertNotIn(TEST_GHP, redacted)
        self.assertIn("[REDACTED_GH_TOKEN]", redacted)
        self.assertNotIn(TEST_SK, redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)
        self.assertNotIn(TEST_AKIA, redacted)
        self.assertIn("[REDACTED_AWS_KEY]", redacted)
        self.assertNotIn("my-very-long-oauth-access-token-string-value-here", redacted)
        self.assertIn("[REDACTED_BEARER]", redacted)
        self.assertNotIn("secret_raw_token_value_xyz", redacted)
        self.assertIn("[REDACTED_PRIVATE_KEY]", redacted)

    def test_subprocess_ast_detects_raw_environ(self) -> None:
        bad_script = self.root / "bad_script.py"
        bad_script.write_text(
            "import os, subprocess\n"
            "subprocess.run(['echo', 'hello'], env=os.environ)\n",
            encoding="utf-8",
        )
        errors, warnings, meta = audit_repo_subprocess_env(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("Raw parent environment 'env=os.environ' passed", errors[0])

    def test_subprocess_ast_detects_environ_copy(self) -> None:
        bad_script = self.root / "bad_copy_script.py"
        bad_script.write_text(
            "import os, subprocess\n"
            "subprocess.Popen(['echo', 'hello'], env=os.environ.copy())\n",
            encoding="utf-8",
        )
        errors, warnings, meta = audit_repo_subprocess_env(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("Direct 'env=os.environ.copy()' passed", errors[0])

    def test_subprocess_ast_detects_dict_environ(self) -> None:
        bad_script = self.root / "bad_dict_script.py"
        bad_script.write_text(
            "import os, subprocess\n"
            "subprocess.call(['echo', 'hello'], env=dict(os.environ))\n",
            encoding="utf-8",
        )
        errors, warnings, meta = audit_repo_subprocess_env(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("Direct 'env=dict(os.environ)' passed", errors[0])

    def test_subprocess_ast_allows_sanitized_env(self) -> None:
        good_script = self.root / "good_script.py"
        good_script.write_text(
            "import subprocess\n"
            "sanitized = {'PATH': '/usr/bin'}\n"
            "subprocess.run(['echo', 'hello'], env=sanitized)\n",
            encoding="utf-8",
        )
        errors, warnings, meta = audit_repo_subprocess_env(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(meta["subprocess_calls_audited"], 1)

    def test_privacy_canaries_loading(self) -> None:
        canaries = load_privacy_canaries(PRIVACY_PATTERNS_PATH)
        self.assertGreaterEqual(len(canaries), 10)
        categories = {c["category"] for c in canaries}
        self.assertIn("secret", categories)
        self.assertIn("identity-email", categories)


if __name__ == "__main__":
    unittest.main()

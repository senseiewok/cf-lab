#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo Git Commit Email & Author Signature Whitelist Linter."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_author_whitelist import (  # noqa: E402
    audit_repo_commits,
    audit_repo_git_config,
    is_authorized_email,
    is_authorized_persona,
    run_full_git_author_whitelist_linter,
    REPO_ROOT,
)


class TestCheckGitAuthorWhitelist(unittest.TestCase):
    def test_authorized_email_patterns(self) -> None:
        self.assertTrue(is_authorized_email("diego@senseiewok.ai"))
        self.assertTrue(is_authorized_email("senseiewok@senseiewok.ai"))
        self.assertTrue(is_authorized_email("researcher@senseiewok.ai"))
        self.assertTrue(is_authorized_email("senseiewok@users.noreply.github.com"))
        self.assertTrue(is_authorized_email("senseiewok-dev@users.noreply.github.com"))
        self.assertTrue(is_authorized_email("12345+senseiewok@users.noreply.github.com"))
        self.assertTrue(is_authorized_email("noreply@github.com"))
        self.assertTrue(is_authorized_email("actions@github.com"))

        # Unauthorized patterns
        self.assertFalse(is_authorized_email("attacker@evil.com"))
        self.assertFalse(is_authorized_email("user@gmail.com"))
        self.assertFalse(is_authorized_email("admin@spoofed.org"))
        self.assertFalse(is_authorized_email(""))
        self.assertFalse(is_authorized_email("   "))

    def test_authorized_persona_validation(self) -> None:
        self.assertTrue(is_authorized_persona("Sensei Ewok", "diego@senseiewok.ai"))
        self.assertTrue(is_authorized_persona("senseiewok-dev", "senseiewok-dev@users.noreply.github.com"))
        self.assertTrue(is_authorized_persona("GitHub", "noreply@github.com"))
        self.assertTrue(is_authorized_persona("github-actions[bot]", "actions@github.com"))

        # Mismatched name or email
        self.assertFalse(is_authorized_persona("Unknown Attacker", "diego@senseiewok.ai"))
        self.assertFalse(is_authorized_persona("Sensei Ewok", "evil@malicious.com"))
        self.assertFalse(is_authorized_persona("", "diego@senseiewok.ai"))

    def test_repo_root_whitelist_linter_pass(self) -> None:
        report = run_full_git_author_whitelist_linter(REPO_ROOT, commit_limit=25)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertGreaterEqual(report["commits_scanned"], 1)

    @patch("subprocess.run")
    def test_audit_repo_git_config_unauthorized_email(self, mock_run: MagicMock) -> None:
        # Mock git config user.email returning unauthorized email
        def side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            proc = MagicMock()
            proc.returncode = 0
            if "user.email" in cmd:
                proc.stdout = "hacker@badactor.net\n"
            elif "user.name" in cmd:
                proc.stdout = "Sensei Ewok\n"
            return proc

        mock_run.side_effect = side_effect
        findings = audit_repo_git_config("test-repo", Path("/tmp/mock-repo"))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "CONFIG001_UNAUTHORIZED_EMAIL")
        self.assertEqual(findings[0].severity, "ERROR")

    @patch("subprocess.run")
    def test_audit_repo_commits_tampered_signature(self, mock_run: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        # Line format: commit_sha \t author_name \t author_email \t committer_name \t committer_email \t sig_status
        mock_proc.stdout = (
            "abcdef1234567890\tSensei Ewok\tdiego@senseiewok.ai\tSensei Ewok\tdiego@senseiewok.ai\tB\n"
        )
        mock_run.return_value = mock_proc

        findings, count = audit_repo_commits("test-repo", Path("/tmp/mock-repo"), commit_limit=5)
        self.assertEqual(count, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "SIGN001_TAMPERED_SIGNATURE")
        self.assertEqual(findings[0].severity, "ERROR")

    @patch("subprocess.run")
    def test_audit_repo_commits_unauthorized_author_email(self, mock_run: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = (
            "abcdef1234567890\tSensei Ewok\tspoofed@rogue.com\tSensei Ewok\tdiego@senseiewok.ai\tG\n"
        )
        mock_run.return_value = mock_proc

        findings, count = audit_repo_commits("test-repo", Path("/tmp/mock-repo"), commit_limit=5)
        self.assertEqual(count, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "AUTH001_UNAUTHORIZED_AUTHOR_EMAIL")
        self.assertEqual(findings[0].severity, "ERROR")


if __name__ == "__main__":
    unittest.main()

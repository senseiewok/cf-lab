#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Git Commit GPG / SSH Signature Verification & Identity Invariant Linter."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_commit_signatures import (
    audit_repo_commit_signatures,
    audit_workspace,
    check_repo_signing_config,
    verify_author_identity,
)


class TestCheckGitCommitSignatures(unittest.TestCase):
    def test_verify_author_identity_valid_lab_personas(self):
        valid_identities = [
            ("Sensei Ewok", "diego@senseiewok.ai"),
            ("senseiewok", "diego@senseiewok.ai"),
            ("senseiewok-dev", "diego@senseiewok.ai"),
            ("GitHub", "noreply@github.com"),
            ("web-flow", "noreply@github.com"),
            ("Sensei Ewok", "123456+senseiewok@users.noreply.github.com"),
        ]
        for name, email in valid_identities:
            ok, err = verify_author_identity(name, email)
            self.assertTrue(ok, f"Expected {name} <{email}> to be valid, got error: {err}")

    def test_verify_author_identity_spoofed_or_unauthorized(self):
        invalid_identities = [
            ("Attacker", "attacker@evil.com"),
            ("Sensei Ewok", "attacker@fake-domain.com"),
            ("Unknown Dev", "diego@senseiewok.ai"),
            ("Anonymous", "anonymous@tor.onion"),
        ]
        for name, email in invalid_identities:
            ok, err = verify_author_identity(name, email)
            self.assertFalse(ok, f"Expected {name} <{email}> to be rejected")

    def test_check_repo_signing_config(self):
        config = check_repo_signing_config(ROOT)
        self.assertIn("gpg_sign", config)
        self.assertIn("gpg_format", config)
        self.assertIn("signing_key", config)
        self.assertIsInstance(config["gpg_sign"], bool)

    @patch("subprocess.run")
    def test_detect_bad_signature_flag(self, mock_run):
        # Format: %H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%G?%x1f%GS%x1f%GK%x1f%s
        mock_output = (
            "abcd1234ef567890\x1fSensei Ewok\x1fdiego@senseiewok.ai\x1f"
            "Sensei Ewok\x1fdiego@senseiewok.ai\x1fB\x1fFake Key\x1f12345678\x1fTampered commit\n"
        )
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = mock_output
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        findings, stats = audit_repo_commit_signatures("cf-lab", ROOT, max_commits=5)
        self.assertEqual(stats["bad_signatures"], 1)
        self.assertTrue(any(f.rule == "BAD_COMMIT_SIGNATURE" and f.severity == "ERROR" for f in findings))

    @patch("subprocess.run")
    def test_detect_revoked_key_flag(self, mock_run):
        mock_output = (
            "abcd1234ef567890\x1fSensei Ewok\x1fdiego@senseiewok.ai\x1f"
            "Sensei Ewok\x1fdiego@senseiewok.ai\x1fR\x1fRevoked Key\x1f87654321\x1fRevoked commit\n"
        )
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = mock_output
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        findings, stats = audit_repo_commit_signatures("cf-lab", ROOT, max_commits=5)
        self.assertEqual(stats["bad_signatures"], 1)
        self.assertTrue(any(f.rule == "REVOKED_SIGNATURE_KEY" and f.severity == "ERROR" for f in findings))

    def test_live_workspace_commits_pass(self):
        results = audit_workspace(repos=[("cf-lab", ROOT)], max_commits=20)
        self.assertTrue(results["clean"])
        self.assertEqual(results["error_count"], 0)
        self.assertGreater(results["total_commits_audited"], 0)


if __name__ == "__main__":
    unittest.main()

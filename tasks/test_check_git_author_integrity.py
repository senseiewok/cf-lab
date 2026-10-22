#!/usr/bin/env python3
"""Unit tests for check_git_author_integrity.py."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_author_integrity import (
    is_authorized_persona,
    audit_repo_git_authors,
)


class TestGitAuthorIntegrity(unittest.TestCase):
    """Test suite verifying git author identity spoofing guards and signature invariants."""

    def test_authorized_personas_pass(self) -> None:
        valid_cases = [
            ("Sensei Ewok", "diego@senseiewok.ai"),
            ("Sensei Ewok CF Lab", "contact@senseiewok.ai"),
            ("Diego", "19678231+diegogandara@users.noreply.github.com"),
            ("senseiewok", "senseiewok@users.noreply.github.com"),
            ("GitHub", "noreply@github.com"),
            ("web-flow", "noreply@github.com"),
        ]
        for name, email in valid_cases:
            with self.subTest(name=name, email=email):
                self.assertTrue(is_authorized_persona(name, email))

    def test_unauthorized_persona_name_fails(self) -> None:
        self.assertFalse(is_authorized_persona("Mallory Attacker", "diego@senseiewok.ai"))
        self.assertFalse(is_authorized_persona("Evil Bot", "noreply@github.com"))

    def test_unauthorized_persona_email_fails(self) -> None:
        self.assertFalse(is_authorized_persona("Sensei Ewok", "spoofed@evil-phishing.org"))
        self.assertFalse(is_authorized_persona("Diego", "unauthorized@untrusted-domain.org"))

    @patch("subprocess.run")
    def test_audit_detects_spoofed_author(self, mock_run: MagicMock) -> None:
        mock_stdout = (
            "commit1|Sensei Ewok|diego@senseiewok.ai|Sensei Ewok|diego@senseiewok.ai|N|feat: regular task\n"
            "commit2|Attacker|attacker@evil.com|Attacker|attacker@evil.com|N|feat: malicious commit\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout, stderr="")

        errors, warnings, meta = audit_repo_git_authors("mock-repo", Path("."))
        self.assertEqual(meta["commits_audited"], 2)
        self.assertEqual(len(errors), 2)  # 1 author error + 1 committer error for commit2
        self.assertTrue(any("attacker@evil.com" in e for e in errors))

    @patch("subprocess.run")
    def test_audit_detects_bad_signature(self, mock_run: MagicMock) -> None:
        mock_stdout = (
            "commit1|Sensei Ewok|diego@senseiewok.ai|Sensei Ewok|diego@senseiewok.ai|B|feat: tampered signature\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout, stderr="")

        errors, warnings, meta = audit_repo_git_authors("mock-repo", Path("."))
        self.assertEqual(meta["bad_signatures"], 1)
        self.assertTrue(any("TAMPERED commit signature" in e for e in errors))

    @patch("subprocess.run")
    def test_audit_signed_commit_tracking(self, mock_run: MagicMock) -> None:
        mock_stdout = (
            "commit1|Sensei Ewok|diego@senseiewok.ai|Sensei Ewok|diego@senseiewok.ai|G|feat(security): T-0290 release\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout, stderr="")

        errors, warnings, meta = audit_repo_git_authors("mock-repo", Path("."))
        self.assertEqual(len(errors), 0)
        self.assertEqual(meta["signed_commits"], 1)
        self.assertEqual(meta["unsigned_commits"], 0)


if __name__ == "__main__":
    unittest.main()

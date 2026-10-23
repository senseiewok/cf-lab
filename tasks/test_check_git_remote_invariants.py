#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo Git Config & Remote URL Protocol Whitelist Linter."""
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

from check_git_remote_invariants import (
    audit_remote_url,
    audit_script_git_commands,
    audit_workspace,
    is_safe_remote_url,
    parse_git_config_remotes,
)


class TestCheckGitRemoteInvariants(unittest.TestCase):
    def test_is_safe_remote_url(self):
        self.assertTrue(is_safe_remote_url("https://github.com/senseiewok/cf-lab.git"))
        self.assertTrue(is_safe_remote_url("git@github.com:senseiewok/cf-research.git"))
        self.assertFalse(is_safe_remote_url("http://github.com/senseiewok/cf-skills.git"))
        self.assertFalse(is_safe_remote_url("git://github.com/senseiewok/.ai.git"))
        self.assertFalse(is_safe_remote_url("https://token@github.com/senseiewok/cf-lab.git"))
        self.assertFalse(is_safe_remote_url("https://user:pass@github.com/senseiewok/cf-lab.git"))

    def test_detect_plaintext_http(self):
        findings = audit_remote_url("http://github.com/senseiewok/cf-lab.git", remote_name="origin")
        self.assertTrue(any(f.rule == "INSECURE_PLAINTEXT_HTTP" and f.severity == "ERROR" for f in findings))

    def test_detect_insecure_git_protocol(self):
        findings = audit_remote_url("git://github.com/senseiewok/cf-lab.git", remote_name="origin")
        self.assertTrue(any(f.rule == "INSECURE_GIT_PROTOCOL" and f.severity == "ERROR" for f in findings))

    def test_detect_embedded_credentials(self):
        findings = audit_remote_url("https://ghp_1234567890abcdef@github.com/senseiewok/cf-lab.git", remote_name="origin")
        self.assertTrue(any(f.rule == "EMBEDDED_CREDENTIALS" and f.severity == "ERROR" for f in findings))

        findings_userpass = audit_remote_url("https://diego:mysecretpassword@github.com/senseiewok/cf-lab.git", remote_name="origin")
        self.assertTrue(any(f.rule == "EMBEDDED_CREDENTIALS" and f.severity == "ERROR" for f in findings_userpass))

    def test_detect_unauthorized_namespace(self):
        findings = audit_remote_url("https://github.com/unauthorized-fork/cf-lab.git", remote_name="origin")
        self.assertTrue(any(f.rule == "UNAUTHORIZED_NAMESPACE" and f.severity == "WARNING" for f in findings))

    def test_valid_https_and_ssh_pass(self):
        findings_https = audit_remote_url("https://github.com/senseiewok/cf-lab.git", remote_name="origin")
        self.assertEqual(len([f for f in findings_https if f.severity == "ERROR"]), 0)

        findings_ssh = audit_remote_url("git@github.com:senseiewok/cf-lab.git", remote_name="origin")
        self.assertEqual(len([f for f in findings_ssh if f.severity == "ERROR"]), 0)

    def test_parse_git_config_remotes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config"
            config_file.write_text(
                '[core]\n'
                '\trepositoryformatversion = 0\n'
                '[remote "origin"]\n'
                '\turl = https://github.com/senseiewok/cf-lab.git\n'
                '\tfetch = +refs/heads/*:refs/remotes/origin/*\n'
                '[remote "upstream"]\n'
                '\turl = git@github.com:senseiewok/cf-lab.git\n',
                encoding="utf-8",
            )
            remotes = parse_git_config_remotes(config_file)
            self.assertEqual(len(remotes), 2)
            self.assertEqual(remotes["origin"], "https://github.com/senseiewok/cf-lab.git")
            self.assertEqual(remotes["upstream"], "git@github.com:senseiewok/cf-lab.git")

    def test_detect_script_insecure_git_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "setup_clone.sh"
            sh_file.write_text(
                "#!/bin/bash\n"
                "git clone http://github.com/senseiewok/cf-lab.git\n",
                encoding="utf-8",
            )
            findings = audit_script_git_commands(sh_file)
            self.assertTrue(any(f.rule == "SCRIPT_INSECURE_GIT_COMMAND" and f.severity == "ERROR" for f in findings))

    def test_audit_workspace_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            config_file = git_dir / "config"
            config_file.write_text(
                '[remote "origin"]\n'
                '\turl = https://github.com/senseiewok/cf-lab.git\n',
                encoding="utf-8",
            )
            report = audit_workspace(target_path=Path(tmpdir))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["total_violations"], 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for Cross-Repo Agent API Key & Token Entropy Linter (T-0296)."""
import tempfile
import unittest
from pathlib import Path

from tasks.check_secret_entropy_linter import (
    calculate_shannon_entropy,
    is_allowed_token,
    scan_file,
    scan_text,
)


class TestSecretEntropyLinter(unittest.TestCase):
    def test_calculate_shannon_entropy(self):
        # Empty string
        self.assertEqual(calculate_shannon_entropy(""), 0.0)

        # Uniform repetition (H = 0)
        self.assertEqual(calculate_shannon_entropy("AAAAAAAAAA"), 0.0)

        # Two equally probable characters (H = 1.0)
        self.assertAlmostEqual(calculate_shannon_entropy("abababab"), 1.0, places=2)

        # High entropy alphanumeric token
        high_entropy_str = "8vKn2Px9Lq4Wm7Zb1Yt5"
        entropy = calculate_shannon_entropy(high_entropy_str)
        self.assertGreater(entropy, 4.0)

    def test_detect_known_secrets(self):
        # GitHub Token
        text_gh = "export GITHUB_TOKEN=ghp_ABCDefgh1234567890ABCDefgh1234567890"  # privacy-scan: allow
        findings_gh = scan_text(text_gh)
        self.assertEqual(len(findings_gh), 1)
        self.assertEqual(findings_gh[0].rule, "GITHUB_TOKEN")

        # Anthropic API Key
        text_ant = "ANTHROPIC_API_KEY=sk-ant-live01-1234567890ABCDEF1234567890"  # privacy-scan: allow
        findings_ant = scan_text(text_ant)
        self.assertEqual(len(findings_ant), 1)
        self.assertEqual(findings_ant[0].rule, "ANTHROPIC_API_KEY")

        # OpenAI API Key
        text_oai = "OPENAI_API_KEY=sk-proj-ABCDefgh1234567890ABCDefgh1234567890123456"  # privacy-scan: allow
        findings_oai = scan_text(text_oai)
        self.assertEqual(len(findings_oai), 1)
        self.assertEqual(findings_oai[0].rule, "OPENAI_API_KEY")

        # Google API Key
        text_goog = "GOOGLE_KEY=AIzaSyD1234567890ABCDefgh1234567890ABCD"  # privacy-scan: allow
        findings_goog = scan_text(text_goog)
        self.assertEqual(len(findings_goog), 1)
        self.assertEqual(findings_goog[0].rule, "GOOGLE_API_KEY")

        # AWS Access Key (without 'example' canary term)
        text_aws = "AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF"  # privacy-scan: allow
        findings_aws = scan_text(text_aws)
        self.assertEqual(len(findings_aws), 1)
        self.assertEqual(findings_aws[0].rule, "AWS_ACCESS_KEY")

        # Private Key Header
        text_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."  # privacy-scan: allow
        findings_key = scan_text(text_key)
        self.assertGreaterEqual(len(findings_key), 1)
        self.assertEqual(findings_key[0].rule, "PRIVATE_KEY_HEADER")

    def test_allowlist_suppression(self):
        # Commit SHAs should be suppressed
        commit_line = "commit 4021629d779ef98debd3157f6ccb333feaf85446"
        findings_commit = scan_text(commit_line)
        self.assertEqual(len(findings_commit), 0)

        # UUID should be suppressed
        uuid_line = "session_id = 'c37bd2c0-bc41-ff65-e478-788efb0afcbe'"
        findings_uuid = scan_text(uuid_line)
        self.assertEqual(len(findings_uuid), 0)

        # Canary / test token should be suppressed
        canary_line = "API_KEY = 'canary-fake-test-secret-token-1234567890123456'"  # privacy-scan: allow
        findings_canary = scan_text(canary_line)
        self.assertEqual(len(findings_canary), 0)

        # AWS documentation example key with 'EXAMPLE' should be suppressed by canary filter
        aws_doc_example = "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'"  # privacy-scan: allow
        findings_aws_example = scan_text(aws_doc_example)
        self.assertEqual(len(findings_aws_example), 0)

        # SVG path coordinates should be suppressed
        svg_line = '<path d="M10,20 L30,40 C50,60 70,80 90,100 Z" />'
        findings_svg = scan_text(svg_line)
        self.assertEqual(len(findings_svg), 0)

    def test_scan_file_integration(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as f:
            f.write("def foo():\n    return 'clean_code_without_secrets'\n")
            f_path = Path(f.name)

        try:
            findings = scan_file(f_path)
            self.assertEqual(len(findings), 0)
        finally:
            f_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

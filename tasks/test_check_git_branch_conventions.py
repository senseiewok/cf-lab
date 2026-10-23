#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo Git Branch Naming & Semantic Convention Linter."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_branch_conventions import (
    audit_workspace,
    validate_branch_name,
)


class TestCheckGitBranchConventions(unittest.TestCase):
    def test_valid_semantic_branches(self):
        valid_cases = [
            "main",
            "master",
            "feat/hourly-steward-wave31",
            "fix/ci-timeout-fix",
            "work/sentinel-security-t-0361",
            "site/showcase-update",
            "docs/setup-guide",
            "chore/board-replenishment",
            "ci/pin-runner",
            "skills/antigravity-guide",
            "sec/audit-session-errors",
            "perf/ci-matrix",
            "loop/queue-improvements",
            "board/session-follow-ups",
            "feat-t0212-done",
            "board-drop-t0049",
        ]
        for b in valid_cases:
            is_valid, reason = validate_branch_name(b)
            self.assertTrue(is_valid, f"Expected '{b}' to be valid, got: {reason}")

    def test_invalid_refspec_characters(self):
        invalid_cases = [
            "feat/branch with spaces",
            "feat/branch..traversal",
            "feat/branch~1",
            "feat/branch^2",
            "feat/branch:ref",
            "feat/branch?wildcard",
            "feat/branch*glob",
            "feat/branch[bracket]",
            "feat/branch\\backslash",
            "feat/branch@{1}",
            "feat/trailing-slash/",
            "/feat/leading-slash",
            "-feat/leading-hyphen",
            "feat/repo.lock",
            "feat/consecutive//slashes",
        ]
        for b in invalid_cases:
            is_valid, reason = validate_branch_name(b)
            self.assertFalse(is_valid, f"Expected '{b}' to be invalid")

    def test_missing_namespace_prefix(self):
        invalid_cases = [
            "random-branch-name",
            "my_new_feature",
            "unnamespaced-fix",
        ]
        for b in invalid_cases:
            is_valid, reason = validate_branch_name(b)
            self.assertFalse(is_valid, f"Expected '{b}' to be rejected for missing namespace")

    def test_audit_workspace_single_branch(self):
        res = audit_workspace(target_branch="feat/valid-branch")
        self.assertTrue(res["clean"])
        self.assertEqual(res["error_count"], 0)

        res_bad = audit_workspace(target_branch="invalid..branch")
        self.assertFalse(res_bad["clean"])
        self.assertEqual(res_bad["error_count"], 1)


if __name__ == "__main__":
    unittest.main()

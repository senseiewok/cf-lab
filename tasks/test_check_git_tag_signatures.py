#!/usr/bin/env python3
"""Unit tests for tasks/check_git_tag_signatures.py."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_tag_signatures import (
    audit_repository_tags,
    inspect_git_tag,
    is_safe_tag_refname,
    is_valid_semver_tag,
    scan_workspace,
)


class TestCheckGitTagSignatures(unittest.TestCase):
    """Test git tag validation, SemVer parsing, and refname security invariants."""

    def test_is_valid_semver_tag(self):
        """Verify strict SemVer 2.0 validation with mandatory 'v' prefix."""
        self.assertTrue(is_valid_semver_tag("v0.1.0"))
        self.assertTrue(is_valid_semver_tag("v1.0.0"))
        self.assertTrue(is_valid_semver_tag("v2.4.1-rc.1"))
        self.assertTrue(is_valid_semver_tag("v1.2.3+20261022"))
        self.assertTrue(is_valid_semver_tag("v3.0.0-beta.2+exp.sha.5114f85"))

        # Invalid tags
        self.assertFalse(is_valid_semver_tag("1.0.0"))  # missing v
        self.assertFalse(is_valid_semver_tag("v1.0"))  # missing patch
        self.assertFalse(is_valid_semver_tag("v01.0.0"))  # leading zero in major
        self.assertFalse(is_valid_semver_tag("v1.0.0.0"))  # 4 components
        self.assertFalse(is_valid_semver_tag("release-1.0.0"))
        self.assertFalse(is_valid_semver_tag(""))
        self.assertFalse(is_valid_semver_tag("v1..0"))

    def test_is_safe_tag_refname(self):
        """Verify defense against path traversal and command injection in tag names."""
        # Safe refnames
        safe, _ = is_safe_tag_refname("v1.0.0")
        self.assertTrue(safe)
        safe, _ = is_safe_tag_refname("releases/v2.0.0")
        self.assertTrue(safe)
        safe, _ = is_safe_tag_refname("feature_test_tag")
        self.assertTrue(safe)

        # Unsafe refnames
        self.assertFalse(is_safe_tag_refname("-argument_injection")[0])
        self.assertFalse(is_safe_tag_refname("--output=/tmp/evil")[0])
        self.assertFalse(is_safe_tag_refname("path/../traversal")[0])
        self.assertFalse(is_safe_tag_refname("..")[0])
        self.assertFalse(is_safe_tag_refname("has space")[0])
        self.assertFalse(is_safe_tag_refname("has\nnewline")[0])
        self.assertFalse(is_safe_tag_refname("tag~1")[0])
        self.assertFalse(is_safe_tag_refname("tag^2")[0])
        self.assertFalse(is_safe_tag_refname("tag:colon")[0])
        self.assertFalse(is_safe_tag_refname("tag?question")[0])
        self.assertFalse(is_safe_tag_refname("tag*star")[0])
        self.assertFalse(is_safe_tag_refname("tag[bracket]")[0])
        self.assertFalse(is_safe_tag_refname("tag\\backslash")[0])
        self.assertFalse(is_safe_tag_refname("tag@{1}")[0])
        self.assertFalse(is_safe_tag_refname("tag.lock")[0])
        self.assertFalse(is_safe_tag_refname("trailing/")[0])
        self.assertFalse(is_safe_tag_refname("consecutive//slashes")[0])

    def test_annotated_tag_verification_in_temp_repo(self):
        """Verify auditing of annotated vs lightweight tags in a git repository."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)

            # Initialize temp git repository
            subprocess.run(["git", "init"], cwd=str(tmp_repo), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test Committer"], cwd=str(tmp_repo), check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_repo), check=True)

            dummy_file = tmp_repo / "README.md"
            dummy_file.write_text("# Test Repo\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=str(tmp_repo), check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(tmp_repo), check=True)

            # 1. Create a valid annotated release tag
            subprocess.run(["git", "tag", "-a", "v1.0.0", "-m", "Release v1.0.0"], cwd=str(tmp_repo), check=True)

            findings = audit_repository_tags(tmp_repo)
            self.assertEqual(len(findings), 0)

            # 2. Create a lightweight release tag (should trigger TAG-001)
            subprocess.run(["git", "tag", "v2.0.0"], cwd=str(tmp_repo), check=True)

            findings = audit_repository_tags(tmp_repo)
            rules = [f.rule for f in findings]
            self.assertIn("TAG-001", rules)
            err = next(f for f in findings if f.rule == "TAG-001")
            self.assertIn("unannotated lightweight tag", err.message)

            # 3. Create a non-SemVer release tag (should trigger TAG-002)
            subprocess.run(["git", "tag", "-a", "v3.0", "-m", "Bad version"], cwd=str(tmp_repo), check=True)

            findings = audit_repository_tags(tmp_repo)
            rules = [f.rule for f in findings]
            self.assertIn("TAG-002", rules)

    def test_scan_workspace_clean(self):
        """Verify that existing workspace tags are clean and pass."""
        findings, meta = scan_workspace(strict=False)
        self.assertTrue(meta["passed"])
        self.assertEqual(meta["errors"], 0)


if __name__ == "__main__":
    unittest.main()

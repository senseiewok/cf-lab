#!/usr/bin/env python3
"""Unit tests for check_git_release_integrity.py (T-0290)."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tasks.check_git_release_integrity import (
    FORBIDDEN_RELEASE_PATTERNS,
    SEMVER_TAG_REGEX,
    VERSION_FILE_REGEX,
    audit_repository_release,
    is_forbidden_release_path,
    parse_semver_tuple,
    validate_version_file_content,
)


class TestSemverAndVersionParsing(unittest.TestCase):
    def test_version_file_valid(self):
        valid_cases = ["1.0.0", "1.5.0", "0.1.0", "2.10.4"]
        for vc in valid_cases:
            valid, ver = validate_version_file_content(vc)
            self.assertTrue(valid, f"Expected {vc} to be valid VERSION format")
            self.assertEqual(ver, vc)

    def test_version_file_invalid(self):
        invalid_cases = [
            "v1.0.0",  # leading v forbidden in VERSION file
            "01.0.0",  # leading zeroes forbidden
            "1.0",     # incomplete semver
            "1.0.0\n2.0.0",  # multiple lines forbidden
            "1.0.0-beta",    # pre-release in VERSION forbidden by lab-versioning
            "",
        ]
        for ic in invalid_cases:
            valid, _ = validate_version_file_content(ic)
            self.assertFalse(valid, f"Expected {ic!r} to be invalid VERSION format")

    def test_tag_semver_regex(self):
        valid_tags = ["v1.0.0", "v1.5.0", "v0.1.0", "v2.10.4", "v1.0.0-rc1"]
        for vt in valid_tags:
            self.assertTrue(SEMVER_TAG_REGEX.match(vt), f"Expected {vt} to match semver tag")

        invalid_tags = ["1.0.0", "v01.0.0", "latest", "release-1", "v1.0"]
        for it in invalid_tags:
            self.assertFalse(SEMVER_TAG_REGEX.match(it), f"Expected {it} to fail semver tag")

    def test_parse_semver_tuple(self):
        self.assertEqual(parse_semver_tuple("v1.5.0"), (1, 5, 0))
        self.assertEqual(parse_semver_tuple("1.5.0"), (1, 5, 0))
        self.assertEqual(parse_semver_tuple("v2.0.1-rc1"), (2, 0, 1))


class TestForbiddenReleasePatterns(unittest.TestCase):
    def test_forbidden_patterns_matched(self):
        forbidden = [
            ".env",
            ".env.local",
            "config/.env.prod",
            ".loop-logs/audit.json",
            ".worktrees/branch/file.py",
            "cf-lab-files/notes.md",
            "certs/private.key",
            "secrets/cert.pem",
            "id_rsa",
            "temp.tmp",
        ]
        for f in forbidden:
            self.assertTrue(is_forbidden_release_path(f), f"Expected forbidden pattern to match {f}")

    def test_safe_patterns_not_matched(self):
        safe = [
            "VERSION",
            "README.md",
            ".env.example",
            "deploy/.env.example",
            ".env.sample",
            "tasks/board.json",
            "src/scripts/site.js",
            "styles.css",
            "package.json",
        ]
        for s in safe:
            self.assertFalse(is_forbidden_release_path(s), f"Did not expect forbidden pattern to match {s}")


class TestRepositoryReleaseAudit(unittest.TestCase):
    def test_audit_clean_temp_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rdir = Path(tmpdir)
            # init git repo
            subprocess.run(["git", "init", "-b", "main"], cwd=rdir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=rdir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=rdir, capture_output=True, check=True)

            # create valid VERSION file and commit
            vfile = rdir / "VERSION"
            vfile.write_text("1.5.0\n", encoding="utf-8")
            subprocess.run(["git", "add", "VERSION"], cwd=rdir, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=rdir, capture_output=True, check=True)

            # tag matching version
            subprocess.run(["git", "tag", "v1.5.0"], cwd=rdir, capture_output=True, check=True)

            data, violations = audit_repository_release(rdir)
            errors = [v for v in violations if v.severity == "ERROR"]
            self.assertEqual(len(errors), 0, f"Expected 0 errors, got: {errors}")
            self.assertEqual(data["version_file"], "1.5.0")
            self.assertEqual(data["tags"], ["v1.5.0"])

    def test_audit_detects_forbidden_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rdir = Path(tmpdir)
            subprocess.run(["git", "init", "-b", "main"], cwd=rdir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=rdir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=rdir, capture_output=True, check=True)

            # create forbidden file and commit
            env_file = rdir / ".env"
            env_file.write_text("API_KEY=12345\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=rdir, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Accidental secret"], cwd=rdir, capture_output=True, check=True)

            data, violations = audit_repository_release(rdir)
            self.assertTrue(any(v.rule == "FORBIDDEN_RELEASE_ARTIFACT" and v.severity == "ERROR" for v in violations))


if __name__ == "__main__":
    unittest.main()

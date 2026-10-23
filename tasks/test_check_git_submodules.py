#!/usr/bin/env python3
"""Unit tests for tasks/check_git_submodules.py."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_submodules import (
    is_safe_submodule_url,
    is_safe_submodule_path,
    is_safe_submodule_name,
    parse_gitmodules_text,
    audit_gitmodules_file,
    audit_nested_git_directories,
    scan_workspace_submodules,
)


class TestCheckGitSubmodules(unittest.TestCase):
    """Test git submodule architecture invariants and URL/path security."""

    def test_is_safe_submodule_url_valid(self):
        """Verify approved HTTPS and SSH git transport schemes."""
        self.assertTrue(is_safe_submodule_url("https://github.com/senseiewok/cf-skills.git")[0])
        self.assertTrue(is_safe_submodule_url("ssh://git@github.com/senseiewok/cf-research.git")[0])
        self.assertTrue(is_safe_submodule_url("git@github.com:senseiewok/cf-lab.git")[0])

    def test_is_safe_submodule_url_insecure(self):
        """Verify rejection of unencrypted transport and traversal."""
        safe, reason = is_safe_submodule_url("http://github.com/senseiewok/cf-skills.git")
        self.assertFalse(safe)
        self.assertIn("Insecure plaintext", reason)

        safe, reason = is_safe_submodule_url("git://github.com/senseiewok/cf-research.git")
        self.assertFalse(safe)
        self.assertIn("Insecure plaintext", reason)

        safe, reason = is_safe_submodule_url("")
        self.assertFalse(safe)

        safe, reason = is_safe_submodule_url("ftp://example.com/repo.git")
        self.assertFalse(safe)

    def test_is_safe_submodule_path_valid(self):
        """Verify valid relative submodule directory paths."""
        self.assertTrue(is_safe_submodule_path("external/tool")[0])
        self.assertTrue(is_safe_submodule_path("vendor/deps/lib")[0])

    def test_is_safe_submodule_path_traversal(self):
        """Verify rejection of path traversal and hook injection targets."""
        safe, reason = is_safe_submodule_path("../outside")
        self.assertFalse(safe)
        self.assertIn("path traversal", reason)

        safe, reason = is_safe_submodule_path("sub/../../traversal")
        self.assertFalse(safe)
        self.assertIn("path traversal", reason)

        safe, reason = is_safe_submodule_path("/etc/passwd")
        self.assertFalse(safe)
        self.assertIn("cannot be absolute", reason)

        safe, reason = is_safe_submodule_path(".git/hooks/pre-commit")
        self.assertFalse(safe)
        self.assertIn("targets git metadata or hooks", reason)

    def test_is_safe_submodule_name_valid(self):
        """Verify valid submodule section names."""
        self.assertTrue(is_safe_submodule_name("my-submodule")[0])
        self.assertTrue(is_safe_submodule_name("vendor_lib_2")[0])

    def test_is_safe_submodule_name_traversal(self):
        """Verify rejection of directory separators and option injection in names."""
        safe, reason = is_safe_submodule_name("../../evil")
        self.assertFalse(safe)
        self.assertIn("illegal characters", reason)

        safe, reason = is_safe_submodule_name("--upload-pack=evil")
        self.assertFalse(safe)
        self.assertIn("cannot begin with hyphen", reason)

    def test_parse_gitmodules_text(self):
        """Verify parsing of valid .gitmodules INI configuration."""
        text = '''[submodule "vendor/foo"]
\tpath = vendor/foo
\turl = https://github.com/senseiewok/foo.git
\tbranch = main
'''
        entries, findings, lines = parse_gitmodules_text(text)
        self.assertEqual(len(findings), 0)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "vendor/foo")
        self.assertEqual(entries[0].path, "vendor/foo")
        self.assertEqual(entries[0].url, "https://github.com/senseiewok/foo.git")
        self.assertEqual(entries[0].branch, "main")

    def test_audit_gitmodules_flag_insecure_transport(self):
        """Verify that .gitmodules with insecure transport is flagged."""
        text = '''[submodule "insecure-dep"]
\tpath = deps/insecure
\turl = http://insecure.example.com/repo.git
'''
        with tempfile.NamedTemporaryFile("w", suffix=".gitmodules", delete=False, encoding="utf-8") as f:
            f.write(text)
            tmp_path = Path(f.name)

        try:
            findings = audit_gitmodules_file(tmp_path, allow_submodules=True)
            rules = [x.rule for x in findings]
            self.assertIn("SUBMODULE_INSECURE_TRANSPORT", rules)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_audit_gitmodules_flag_path_traversal(self):
        """Verify that .gitmodules with path traversal is flagged (CVE-2018-11235)."""
        text = '''[submodule "evil"]
\tpath = ../../outside_repo
\turl = https://github.com/senseiewok/test.git
'''
        with tempfile.NamedTemporaryFile("w", suffix=".gitmodules", delete=False, encoding="utf-8") as f:
            f.write(text)
            tmp_path = Path(f.name)

        try:
            findings = audit_gitmodules_file(tmp_path, allow_submodules=True)
            rules = [x.rule for x in findings]
            self.assertIn("SUBMODULE_PATH_TRAVERSAL", rules)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_audit_nested_git_directories(self):
        """Verify detection of rogue nested .git directories in working trees."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / ".git").mkdir()  # legitimate root .git
            nested_pkg = repo_root / "tools" / "nested"
            nested_pkg.mkdir(parents=True)
            (nested_pkg / ".git").mkdir()  # rogue nested .git

            findings = audit_nested_git_directories(repo_root)
            rules = [x.rule for x in findings]
            self.assertIn("ROGUE_NESTED_GIT_REPO", rules)


if __name__ == "__main__":
    unittest.main()

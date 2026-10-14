#!/usr/bin/env python3
"""Unit tests for sync-main.py."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to sys.path
scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(scripts_dir))

import importlib
sync_main = importlib.import_module("sync-main")


class TestSyncMain(unittest.TestCase):
    def test_default_root(self):
        root = sync_main.default_root()
        self.assertTrue(root.is_dir())
        self.assertTrue((root / "cf-lab").exists())

    def test_sync_non_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ok, msg = sync_main.sync_repo(tmp_path)
            self.assertFalse(ok)
            self.assertIn("not a git repository", msg)

    def test_check_flag_exits_zero(self):
        ret = sync_main.main(["--check", "--quiet"])
        self.assertEqual(ret, 0)

    def test_temp_git_repo_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a bare remote repo
            remote = root / "remote.git"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)

            # Create origin clone to make an initial commit
            init_clone = root / "init_clone"
            subprocess.run(["git", "clone", str(remote), str(init_clone)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(init_clone), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(init_clone), "config", "user.email", "test@example.com"], check=True)
            (init_clone / "file.txt").write_text("v1", encoding="utf-8")
            subprocess.run(["git", "-C", str(init_clone), "add", "file.txt"], check=True)
            subprocess.run(["git", "-C", str(init_clone), "commit", "-m", "initial commit"], check=True)
            subprocess.run(["git", "-C", str(init_clone), "push", "origin", "main"], check=True)

            # Create test repo clone
            local_repo = root / "test-repo"
            subprocess.run(["git", "clone", str(remote), str(local_repo)], check=True, capture_output=True)

            # Initially should be UP-TO-DATE
            ok, msg = sync_main.sync_repo(local_repo)
            self.assertTrue(ok)
            self.assertIn("UP-TO-DATE", msg)

            # Push a new commit from init_clone
            (init_clone / "file.txt").write_text("v2", encoding="utf-8")
            subprocess.run(["git", "-C", str(init_clone), "add", "file.txt"], check=True)
            subprocess.run(["git", "-C", str(init_clone), "commit", "-m", "second commit"], check=True)
            subprocess.run(["git", "-C", str(init_clone), "push", "origin", "main"], check=True)

            # Now test_repo should pull cleanly
            ok, msg = sync_main.sync_repo(local_repo)
            self.assertTrue(ok)
            self.assertIn("PULLED", msg)
            self.assertIn("second commit", msg)
            self.assertEqual((local_repo / "file.txt").read_text(encoding="utf-8"), "v2")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for tasks/check_worktree_drift.py."""
import json
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TASKS_DIR = Path(__file__).resolve().parent
if str(TASKS_DIR) not in sys.path:
    sys.path.insert(0, str(TASKS_DIR))

try:
    from tasks.check_worktree_drift import (
        detect_lane,
        extract_task_ids,
        find_worktree_root,
        inspect_worktree,
        scan_existing_worktrees,
        main,
    )
except ImportError:
    from check_worktree_drift import (
        detect_lane,
        extract_task_ids,
        find_worktree_root,
        inspect_worktree,
        scan_existing_worktrees,
        main,
    )


class TestCheckWorktreeDrift(unittest.TestCase):
    def test_extract_task_ids(self):
        text = "work/sentinel-research-t-0213 and feat/T-0214-some-desc t-0213"
        ids = extract_task_ids(text)
        self.assertEqual(ids, ["T-0213", "T-0214"])

    def test_detect_lane(self):
        self.assertEqual(detect_lane("sentinel-security-t-0083"), "security")
        self.assertEqual(detect_lane("work/sentinel-research-t-0208"), "research")
        self.assertEqual(detect_lane("site/showcase-cftr"), "showcase")
        self.assertEqual(detect_lane("work/sentinel-showcase-t-0211"), "showcase")
        self.assertIsNone(detect_lane("unrelated-branch-name"))

    def test_find_worktree_root(self):
        # When called from within a worktree path
        dummy_wt = Path("C:/senseiewok/repos/.worktrees/cf-lab/test-topic")
        root = find_worktree_root(dummy_wt)
        self.assertEqual(root.name, ".worktrees")

        # When called from main repo
        dummy_main = Path("C:/senseiewok/repos/cf-lab")
        root2 = find_worktree_root(dummy_main)
        self.assertEqual(root2.name, ".worktrees")

    def test_scan_in_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            wt_root = base / ".worktrees"
            repo_dir = wt_root / "cf-research"
            wt_dir = repo_dir / "sentinel-research-t-0213"
            wt_dir.mkdir(parents=True)

            # Not a git worktree yet
            self.assertIsNone(inspect_worktree(wt_dir, "cf-research"))

            # Initialize a git repo inside wt_dir
            subprocess.run(["git", "init"], cwd=wt_dir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=wt_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=wt_dir, check=True)
            subprocess.run(["git", "checkout", "-b", "work/sentinel-research-t-0213"], cwd=wt_dir, capture_output=True, check=True)

            # Create an initial commit
            (wt_dir / "file.txt").write_text("hello", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt"], cwd=wt_dir, check=True)
            subprocess.run(["git", "commit", "-m", "feat: initial commit for T-0213"], cwd=wt_dir, check=True)

            info = inspect_worktree(wt_dir, "cf-research")
            self.assertIsNotNone(info)
            self.assertEqual(info["repo"], "cf-research")
            self.assertEqual(info["branch"], "work/sentinel-research-t-0213")
            self.assertEqual(info["matching_task_ids"], ["T-0213"])
            self.assertEqual(info["matching_lane"], "research")
            self.assertFalse(info["uncommitted"])

            # Test scanning with filter
            scanned = scan_existing_worktrees(repo_root=base / "dummy", task_ids=["T-0213"])
            self.assertEqual(len(scanned), 1)
            self.assertEqual(scanned[0]["matching_task_ids"], ["T-0213"])

            # Test scanning with non-matching filter
            scanned_empty = scan_existing_worktrees(repo_root=base / "dummy", task_ids=["T-9999"])
            self.assertEqual(len(scanned_empty), 0)

            # Test scanning with lane filter
            scanned_lane = scan_existing_worktrees(repo_root=base / "dummy", lane="research")
            self.assertEqual(len(scanned_lane), 1)

            scanned_other_lane = scan_existing_worktrees(repo_root=base / "dummy", lane="security")
            self.assertEqual(len(scanned_other_lane), 0)

    def test_cli_invocation(self):
        ret = main(["--json", "--task-ids", "T-0213"])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for tasks/harvest_sentinel_worktrees.py (T-0278)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tasks.harvest_sentinel_worktrees import (
    audit_harvestable_worktrees,
    clean_worktrees,
    inspect_worktree_safety,
    is_safe_ignored,
)


class TestHarvestSentinelWorktrees(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))
        self.root = Path(self.tmp_dir)

    def test_is_safe_ignored(self):
        self.assertTrue(is_safe_ignored("__pycache__/foo.pyc"))
        self.assertTrue(is_safe_ignored(".pytest_cache/v/cache"))
        self.assertTrue(is_safe_ignored(".loop-logs/audit.json"))
        self.assertTrue(is_safe_ignored("shots/desktop.png"))
        self.assertTrue(is_safe_ignored("commit-msg-t001.txt"))
        self.assertTrue(is_safe_ignored("pr-body-test.md"))

        self.assertFalse(is_safe_ignored(".env"))
        self.assertFalse(is_safe_ignored("secret.pem"))
        self.assertFalse(is_safe_ignored("src/important.js"))
        self.assertFalse(is_safe_ignored("tasks/script.py"))

    def test_inspect_worktree_safety_nonexistent(self):
        nonexistent = self.root / "does_not_exist"
        res = inspect_worktree_safety(nonexistent, self.root)
        self.assertFalse(res["is_safe"])
        self.assertIn("worktree directory does not exist", res["reasons_to_keep"])

    def test_inspect_worktree_safety_missing_git(self):
        wt = self.root / "wt1"
        wt.mkdir()
        res = inspect_worktree_safety(wt, self.root)
        self.assertFalse(res["is_safe"])
        self.assertIn("missing .git file", res["reasons_to_keep"])

    @patch("subprocess.run")
    def test_inspect_worktree_safety_clean(self, mock_run):
        wt = self.root / "wt_clean"
        wt.mkdir()
        (wt / ".git").write_text("gitdir: /foo/bar", encoding="utf-8")

        def side_effect(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "rev-parse" in cmd:
                m.stdout = "work/sentinel-showcase-t-0275\n"
            elif "status" in cmd and "--ignored" in cmd:
                m.stdout = "!! __pycache__/foo.pyc\n"
            elif "status" in cmd:
                m.stdout = ""
            elif "log" in cmd:
                m.stdout = ""
            return m

        mock_run.side_effect = side_effect
        res = inspect_worktree_safety(wt, self.root)
        self.assertTrue(res["is_safe"])
        self.assertEqual(res["branch"], "work/sentinel-showcase-t-0275")
        self.assertEqual(res["task_ids"], ["T-0275"])
        self.assertEqual(res["reasons_to_keep"], [])

    @patch("subprocess.run")
    def test_inspect_worktree_safety_dirty(self, mock_run):
        wt = self.root / "wt_dirty"
        wt.mkdir()
        (wt / ".git").write_text("gitdir: /foo/bar", encoding="utf-8")

        def side_effect(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "rev-parse" in cmd:
                m.stdout = "work/sentinel-security-t-0278\n"
            elif "status" in cmd and "--ignored" in cmd:
                m.stdout = ""
            elif "status" in cmd:
                m.stdout = " M src/index.html\n?? untracked.txt\n"
            elif "log" in cmd:
                m.stdout = ""
            return m

        mock_run.side_effect = side_effect
        res = inspect_worktree_safety(wt, self.root)
        self.assertFalse(res["is_safe"])
        self.assertEqual(len(res["reasons_to_keep"]), 1)
        self.assertIn("2 uncommitted or untracked file(s)", res["reasons_to_keep"][0])

    @patch("tasks.harvest_sentinel_worktrees.inspect_worktree_safety")
    def test_audit_harvestable_worktrees_classification(self, mock_safety):
        wt_root = self.root / ".worktrees"
        repo_dir = wt_root / "cf-lab"
        repo_dir.mkdir(parents=True)
        (repo_dir / "clean_merged").mkdir()
        (repo_dir / "clean_unmerged").mkdir()
        (repo_dir / "dirty_wt").mkdir()

        def safety_side_effect(wt_path, repo_root):
            name = Path(wt_path).name
            if name == "clean_merged":
                return {
                    "path": str(wt_path),
                    "branch": "feat/clean-merged",
                    "is_safe": True,
                    "reasons_to_keep": [],
                    "task_ids": ["T-0277"],
                    "unmerged_commits": [],
                }
            elif name == "clean_unmerged":
                return {
                    "path": str(wt_path),
                    "branch": "feat/clean-unmerged",
                    "is_safe": True,
                    "reasons_to_keep": [],
                    "task_ids": ["T-0278"],
                    "unmerged_commits": ["abc1234 unpushed commit"],
                }
            else:
                return {
                    "path": str(wt_path),
                    "branch": "feat/dirty",
                    "is_safe": False,
                    "reasons_to_keep": ["1 uncommitted or untracked file(s)"],
                    "task_ids": [],
                    "unmerged_commits": [],
                }

        mock_safety.side_effect = safety_side_effect

        mock_pr_data = {
            "cf-lab": {
                "feat/clean-merged": {
                    "number": 220,
                    "url": "https://github.com/senseiewok/cf-lab/pull/220",
                    "state": "merged",
                }
            }
        }

        audit = audit_harvestable_worktrees(
            worktrees_root=wt_root,
            repos=["cf-lab"],
            pr_data=mock_pr_data,
        )

        self.assertEqual(audit["total_worktrees"], 3)
        self.assertEqual(audit["harvestable_count"], 1)
        self.assertEqual(audit["kept_count"], 2)

        self.assertEqual(audit["harvestable"][0]["topic"], "clean_merged")
        self.assertEqual(audit["harvestable"][0]["pr_number"], 220)

    def test_clean_worktrees_dry_run(self):
        wt_dummy = self.root / "dummy"
        wt_dummy.mkdir()

        harvestable = [{
            "path": str(wt_dummy),
            "repo": "cf-lab",
            "branch": "feat/dummy",
            "topic": "dummy",
        }]

        results = clean_worktrees(harvestable, dry_run=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "dry_run")
        self.assertTrue(wt_dummy.is_dir())


if __name__ == "__main__":
    unittest.main()

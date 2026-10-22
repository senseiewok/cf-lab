#!/usr/bin/env python3
"""Unit tests for tasks/prune_stale_worktrees.py (T-0284)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tasks.prune_stale_worktrees import (
    is_branch_ancestor_of_main,
    prune_single_worktree,
    prune_stale_worktrees,
    sanitize_path,
)


class TestPruneStaleWorktrees(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))
        self.root = Path(self.tmp_dir)

    def test_sanitize_path(self):
        self.assertEqual(sanitize_path(r"worktrees\cf-lab\topic"), "worktrees/cf-lab/topic")
        self.assertEqual(sanitize_path("worktrees/cf-lab/topic"), "worktrees/cf-lab/topic")

    def test_prune_single_worktree_dry_run(self):
        wt_path = self.root / "wt1"
        res = prune_single_worktree(
            wt_path=wt_path,
            repo_name="cf-lab",
            branch="work/sentinel-t-001",
            repo_dir=self.root,
            dry_run=True,
        )
        self.assertEqual(res["status"], "dry_run")
        self.assertFalse(res["branch_deleted"])
        self.assertFalse(res["worktree_pruned"])

    @patch("subprocess.run")
    def test_prune_single_worktree_live(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res

        wt_path = self.root / "wt1"
        res = prune_single_worktree(
            wt_path=wt_path,
            repo_name="cf-lab",
            branch="work/sentinel-t-001",
            repo_dir=self.root,
            dry_run=False,
        )
        self.assertEqual(res["status"], "pruned")
        self.assertTrue(res["branch_deleted"])
        self.assertTrue(res["worktree_pruned"])

    @patch("subprocess.run")
    def test_is_branch_ancestor_of_main(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res
        self.assertTrue(is_branch_ancestor_of_main("feature-branch", self.root))

        mock_res.returncode = 1
        self.assertFalse(is_branch_ancestor_of_main("unmerged-branch", self.root))

        # Special branches should always return False
        self.assertFalse(is_branch_ancestor_of_main("main", self.root))
        self.assertFalse(is_branch_ancestor_of_main("", self.root))

    def test_prune_stale_worktrees_telemetry_output(self):
        telemetry_file = self.root / "telemetry.json"
        mock_pr_data = {
            "cf-lab": {}
        }
        telemetry = prune_stale_worktrees(
            worktrees_root=self.root,
            repos=["cf-lab"],
            dry_run=True,
            pr_data=mock_pr_data,
            telemetry_path=telemetry_file,
        )
        self.assertTrue(telemetry_file.is_file())
        saved_data = json.loads(telemetry_file.read_text(encoding="utf-8"))
        self.assertEqual(saved_data["mode"], "dry_run")
        self.assertEqual(saved_data["total_scanned"], 0)
        self.assertEqual(saved_data["harvestable_count"], 0)

    @patch("tasks.prune_stale_worktrees.audit_harvestable_worktrees")
    def test_prune_stale_worktrees_with_harvestable(self, mock_audit):
        mock_audit.return_value = {
            "total_worktrees": 2,
            "harvestable_count": 1,
            "kept_count": 1,
            "harvestable": [
                {
                    "repo": "cf-lab",
                    "topic": "clean-pruned",
                    "path": str(self.root / "clean-pruned"),
                    "branch": "work/sentinel-t-0100",
                }
            ],
            "kept": [
                {
                    "repo": "cf-lab",
                    "topic": "dirty-kept",
                    "path": str(self.root / "dirty-kept"),
                    "branch": "work/dirty",
                    "reason": "1 uncommitted file",
                }
            ],
            "errors": [],
        }

        telemetry_file = self.root / "telemetry2.json"
        telemetry = prune_stale_worktrees(
            worktrees_root=self.root,
            repos=["cf-lab"],
            dry_run=True,
            telemetry_path=telemetry_file,
        )
        self.assertEqual(telemetry["harvestable_count"], 1)
        self.assertEqual(telemetry["kept_count"], 1)
        self.assertEqual(telemetry["pruned_entries"][0]["status"], "dry_run")
        self.assertEqual(telemetry["kept_entries"][0]["reason"], "1 uncommitted file")


if __name__ == "__main__":
    unittest.main()

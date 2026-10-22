#!/usr/bin/env python3
"""Unit tests for tasks/repair_sentinel_prs.py (T-0279)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tasks.repair_sentinel_prs import (
    close_superseded_pr_gh,
    detect_pr_alerts,
    detect_superseded_pr,
    extract_task_ids_from_text,
    load_board_tasks,
    main as repair_main,
    normalize_pr_task_ids,
    redact_sensitive,
    run_repair_daemon,
    validate_repo_slug,
    verify_branch_deliverables_merged,
)


class TestRepairSentinelPRs(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))
        self.root = Path(self.tmp_dir)

    def test_extract_task_ids_from_text(self):
        text = "Fix T-0279 and T0280 (ref: t-0016, duplicate T-0279)"
        ids = extract_task_ids_from_text(text)
        self.assertEqual(ids, ["T-0279", "T-0280", "T-0016"])

    def test_normalize_pr_task_ids_seeded_tasks(self):
        branch = "work/sentinel-showcase-t-0275-board"
        title = "chore(board): mark T-0274 and T-0275 done (senseiewok/.ai#151) and seed Wave 16 showcase tasks (T-0280, T-0281)"
        board = {
            "T-0274": {"id": "T-0274", "repo": ".ai", "status": "done"},
            "T-0275": {"id": "T-0275", "repo": "cf-lab", "status": "done"},
            "T-0280": {"id": "T-0280", "repo": ".ai", "status": "ready"},
            "T-0281": {"id": "T-0281", "repo": "cf-lab", "status": "ready"},
        }
        res = normalize_pr_task_ids(branch, title, repo_name="cf-lab", board_tasks_by_id=board)
        self.assertEqual(res["branch_task_ids"], ["T-0275"])
        self.assertEqual(res["seeded_task_ids"], ["T-0280", "T-0281"])
        self.assertIn("T-0275", res["deliverable_task_ids"])
        self.assertIn("T-0274", res["deliverable_task_ids"])
        self.assertNotIn("T-0280", res["deliverable_task_ids"])
        self.assertNotIn("T-0281", res["deliverable_task_ids"])
        self.assertTrue(res["has_discrepancy"])

    def test_normalize_pr_task_ids_cross_repo(self):
        branch = "work/sentinel-showcase-t-0275"
        title = "feat(showcase): visualize CFTR assay for T-0260 (T-0275)"
        board = {
            "T-0260": {"id": "T-0260", "repo": "cf-research", "status": "done"},
            "T-0275": {"id": "T-0275", "repo": ".ai", "status": "in_progress"},
        }
        res = normalize_pr_task_ids(branch, title, repo_name=".ai", board_tasks_by_id=board)
        self.assertEqual(res["cross_repo_task_ids"], ["T-0260"])
        self.assertEqual(res["deliverable_task_ids"], ["T-0275"])

    def test_detect_superseded_pr_clean(self):
        pr = {
            "headRefName": "work/sentinel-showcase-t-0275-board",
            "title": "chore(board): mark T-0274 and T-0275 done and seed (T-0280, T-0281)",
            "repo_name": "cf-lab",
        }
        done_ids = {"T-0274", "T-0275"}
        board = {
            "T-0274": {"id": "T-0274", "status": "done"},
            "T-0275": {"id": "T-0275", "status": "done"},
            "T-0280": {"id": "T-0280", "status": "ready"},
            "T-0281": {"id": "T-0281", "status": "ready"},
        }
        is_sup, reason, meta = detect_superseded_pr(pr, done_ids, board_tasks=board)
        self.assertTrue(is_sup)
        self.assertIn("already marked done on origin/main", reason)
        self.assertTrue(meta["deliverables_done"])
        self.assertTrue(meta["seeded_present"])

    def test_detect_superseded_pr_missing_deliverable(self):
        pr = {
            "headRefName": "work/sentinel-security-t-0279",
            "title": "feat(security): automated PR repair daemon (T-0279)",
            "repo_name": "cf-lab",
        }
        done_ids = {"T-0274", "T-0275"}
        board = {
            "T-0279": {"id": "T-0279", "status": "ready"},
        }
        is_sup, reason, meta = detect_superseded_pr(pr, done_ids, board_tasks=board)
        self.assertFalse(is_sup)
        self.assertIn("not yet done on main", reason)

    def test_detect_superseded_pr_missing_seeded_task(self):
        pr = {
            "headRefName": "work/sentinel-showcase-t-0275-board",
            "title": "chore(board): mark T-0275 done and seed (T-0999)",
            "repo_name": "cf-lab",
        }
        done_ids = {"T-0275"}
        board = {
            "T-0275": {"id": "T-0275", "status": "done"},
        }
        is_sup, reason, meta = detect_superseded_pr(pr, done_ids, board_tasks=board)
        self.assertFalse(is_sup)
        self.assertIn("not yet seeded on main board", reason)

    def test_detect_superseded_pr_non_sentinel(self):
        pr = {
            "headRefName": "human/custom-feature",
            "title": "Custom feature for T-0275",
            "repo_name": "cf-lab",
        }
        done_ids = {"T-0275"}
        is_sup, reason, _ = detect_superseded_pr(pr, done_ids)
        self.assertFalse(is_sup)
        self.assertIn("Not a sentinel branch pattern", reason)

    def test_detect_pr_alerts(self):
        pr_conflict = {
            "repo": "senseiewok/cf-lab",
            "number": 222,
            "title": "Conflicting PR",
            "headRefName": "work/sentinel-t-0001",
            "mergeable": "CONFLICTING",
            "mergeStateStatus": "DIRTY",
            "reviewDecision": "",
            "statusCheckRollup": [],
        }
        alerts = detect_pr_alerts(pr_conflict, is_superseded=False, superseded_reason="", norm_info={})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["type"], "merge_conflict")
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(alerts[0]["action_required"], "manual_merge_required")

        # When superseded, severity is medium and action is close_superseded_pr
        alerts_sup = detect_pr_alerts(pr_conflict, is_superseded=True, superseded_reason="All tasks done", norm_info={})
        self.assertEqual(len(alerts_sup), 2)  # superseded + conflict
        types = [a["type"] for a in alerts_sup]
        self.assertIn("superseded_by_main", types)
        self.assertIn("merge_conflict", types)
        self.assertEqual(alerts_sup[0]["severity"], "medium")

    def test_detect_pr_alerts_ci_and_review(self):
        pr_ci_review = {
            "repo": "senseiewok/cf-lab",
            "number": 333,
            "title": "Broken PR",
            "headRefName": "work/sentinel-t-0002",
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "reviewDecision": "CHANGES_REQUESTED",
            "unresolved_threads": [{"author": "reviewer", "snippet": "fix this"}],
            "statusCheckRollup": [
                {"name": "test-suite", "conclusion": "FAILURE"},
            ],
        }
        alerts = detect_pr_alerts(pr_ci_review, is_superseded=False, superseded_reason="", norm_info={})
        types = {a["type"] for a in alerts}
        self.assertIn("ci_failure", types)
        self.assertIn("review_blocker", types)

    def test_close_superseded_pr_gh_dry_run(self):
        res = close_superseded_pr_gh("senseiewok", "cf-lab", 222, "Tasks done", dry_run=True)
        self.assertEqual(res["action"], "WOULD_CLOSE")
        self.assertEqual(res["number"], 222)
        self.assertIn("Closing as superseded by main", res["comment"])

    @patch("subprocess.run")
    def test_close_superseded_pr_gh_execute(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = close_superseded_pr_gh("senseiewok", "cf-lab", 222, "Tasks done", dry_run=False)
        self.assertEqual(res["action"], "CLOSED")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("gh", cmd)
        self.assertIn("close", cmd)
        self.assertIn("222", cmd)

    def test_validate_repo_slug(self):
        self.assertEqual(validate_repo_slug("senseiewok", "cf-lab"), "senseiewok/cf-lab")
        self.assertEqual(validate_repo_slug("owner", ".ai"), "owner/.ai")
        with self.assertRaises(ValueError):
            validate_repo_slug("-bad-owner", "repo")
        with self.assertRaises(ValueError):
            validate_repo_slug("owner", "-bad-flag")
        with self.assertRaises(ValueError):
            validate_repo_slug("owner;rm", "repo")
        with self.assertRaises(ValueError):
            validate_repo_slug(".", "repo")
        with self.assertRaises(ValueError):
            validate_repo_slug("owner", "..")

    def test_redact_sensitive(self):
        raw = "Leak ghp_1234567890123456789012 and Bearer secrettoken12345678 to user@example.com"
        redacted = redact_sensitive(raw)
        self.assertNotIn("ghp_1234567890123456789012", redacted)
        self.assertNotIn("Bearer secrettoken12345678", redacted)
        self.assertNotIn("user@example.com", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)
        self.assertIn("[REDACTED_TOKEN]", redacted)
        self.assertIn("[REDACTED_EMAIL]", redacted)

    def test_replenish_seeded_tasks_normalization(self):
        title = "chore(board): replenish security lane (T-0280, T-0281)"
        branch = "work/sentinel-security-replenish"
        norm = normalize_pr_task_ids(branch, title, repo_name="cf-lab")
        self.assertEqual(norm["seeded_task_ids"], ["T-0280", "T-0281"])
        self.assertEqual(norm["deliverable_task_ids"], [])

    @patch("sys.stderr")
    @patch("sys.argv", ["tasks/repair_sentinel_prs.py", "--pr-data", "nonexistent_file.json"])
    def test_main_missing_pr_data_fails_safely(self, mock_stderr):
        exit_code = repair_main()
        self.assertEqual(exit_code, 2)

    @patch("sys.stderr")
    @patch("sys.argv", ["tasks/repair_sentinel_prs.py", "--repair"])
    def test_main_repair_without_yes_fails_safely(self, mock_stderr):
        exit_code = repair_main()
        self.assertEqual(exit_code, 1)

    @patch("subprocess.run")
    def test_verify_branch_deliverables_merged(self, mock_run):
        repo_dir = self.root / "fake_repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        # Case 1: branch is ancestor
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        is_merged, reason = verify_branch_deliverables_merged(repo_dir, "work/test")
        self.assertTrue(is_merged)
        self.assertIn("ancestor", reason)

        # Case 2: not ancestor, but 0 unmerged code deliverables (only board changes)
        def side_effect(cmd, **kwargs):
            if "merge-base" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="")
            if "diff" in cmd:
                return MagicMock(returncode=0, stdout="tasks/BOARD.md\ntasks/board.json\n", stderr="")
            return MagicMock(returncode=1)

        mock_run.side_effect = side_effect
        is_merged2, reason2 = verify_branch_deliverables_merged(repo_dir, "work/test2")
        self.assertTrue(is_merged2)
        self.assertIn("Zero unmerged code deliverables", reason2)

        # Case 3: unmerged code files exist
        def side_effect_code(cmd, **kwargs):
            if "merge-base" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="")
            if "diff" in cmd:
                return MagicMock(returncode=0, stdout="tasks/BOARD.md\nsrc/script.js\n", stderr="")
            return MagicMock(returncode=1)

        mock_run.side_effect = side_effect_code
        is_merged3, reason3 = verify_branch_deliverables_merged(repo_dir, "work/test3")
        self.assertFalse(is_merged3)
        self.assertIn("unmerged deliverables not present on origin/main", reason3)

    def test_run_repair_daemon_dry_run(self):
        board_file = self.root / "board.json"
        board_file.write_text(json.dumps({
            "tasks": [
                {"id": "T-0274", "status": "done", "repo": ".ai"},
                {"id": "T-0275", "status": "done", "repo": "cf-lab"},
                {"id": "T-0280", "status": "ready", "repo": ".ai"},
                {"id": "T-0281", "status": "ready", "repo": "cf-lab"},
            ]
        }), encoding="utf-8")

        mock_prs = {
            "cf-lab": [
                {
                    "number": 222,
                    "title": "chore(board): mark T-0274 and T-0275 done and seed (T-0280, T-0281)",
                    "headRefName": "work/sentinel-showcase-t-0275-board",
                    "mergeable": "CONFLICTING",
                    "mergeStateStatus": "DIRTY",
                    "reviewDecision": "",
                    "statusCheckRollup": [],
                }
            ]
        }
        out_file = self.root / "alerts.json"
        res = run_repair_daemon(
            owner="senseiewok",
            repos=["cf-lab"],
            pr_data=mock_prs,
            board_path=board_file,
            dry_run=True,
            output_path=out_file,
        )
        self.assertEqual(res["summary"]["total_open_prs"], 1)
        self.assertEqual(res["summary"]["superseded_prs_count"], 1)
        self.assertEqual(res["summary"]["conflicts_count"], 1)
        self.assertEqual(res["summary"]["normalized_discrepancies_count"], 1)
        self.assertEqual(len(res["actions"]), 1)
        self.assertEqual(res["actions"][0]["action"], "WOULD_CLOSE")
        self.assertTrue(out_file.is_file())


if __name__ == "__main__":
    unittest.main()

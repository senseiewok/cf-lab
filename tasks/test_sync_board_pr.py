#!/usr/bin/env python3
"""Unit tests for tasks/sync_board_pr.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sync_board_pr as sbp


class TestSyncBoardPr(unittest.TestCase):
    def test_canonical_branch_name(self):
        self.assertEqual(sbp.BOARD_SYNC_BRANCH, "feat/board-sync")
        self.assertEqual(sbp.BOARD_SYNC_TOPIC, "board-sync")

    def test_is_board_only_path(self):
        self.assertTrue(sbp.is_board_only_path("tasks/board.json"))
        self.assertTrue(sbp.is_board_only_path("tasks/BOARD.md"))
        self.assertTrue(sbp.is_board_only_path("tasks/specs/T-0380.md"))
        self.assertFalse(sbp.is_board_only_path("README.md"))
        self.assertFalse(sbp.is_board_only_path("tasks/pick_bold_task.py"))

    def test_find_open_board_pr_matches_feat_board_sync(self):
        mock_prs = [
            {"number": 250, "headRefName": "work/sentinel-security-t-0300", "title": "security"},
            {"number": 254, "headRefName": "feat/board-sync", "title": "chore(board): sync board"},
        ]
        found = sbp.find_open_board_pr(open_prs=mock_prs)
        self.assertIsNotNone(found)
        self.assertEqual(found["number"], 254)

        none_found = sbp.find_open_board_pr(open_prs=[mock_prs[0]])
        self.assertIsNone(none_found)

    def test_build_updated_pr_body_initializes_and_appends_idempotently(self):
        body1 = sbp.build_updated_pr_body("", "Mark T-0294 done", timestamp="2026-10-23 05:30 UTC")
        self.assertIn("## Cumulative Board Updates (`feat/board-sync`)", body1)
        self.assertIn("- **2026-10-23 05:30 UTC**: Mark T-0294 done", body1)

        # Appending a new summary adds a second bullet
        body2 = sbp.build_updated_pr_body(body1, "Replenish research backlog (T-0383)", timestamp="2026-10-23 06:00 UTC")
        self.assertIn("- **2026-10-23 05:30 UTC**: Mark T-0294 done", body2)
        self.assertIn("- **2026-10-23 06:00 UTC**: Replenish research backlog (T-0383)", body2)

        # Duplicate summary is not repeated
        body3 = sbp.build_updated_pr_body(body2, "Replenish research backlog (T-0383)", timestamp="2026-10-23 06:05 UTC")
        self.assertEqual(body2, body3)


if __name__ == "__main__":
    unittest.main()

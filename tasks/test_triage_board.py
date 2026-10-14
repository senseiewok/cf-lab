#!/usr/bin/env python3
"""Unit tests for tasks/triage_board.py."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

import triage_board as tb  # noqa: E402


class TestTriageBoard(unittest.TestCase):
    def setUp(self):
        self.mock_human_ids = {"T-0001", "T-0006"}
        self.mock_board = {
            "schema_version": 1,
            "tasks": [
                {
                    "id": "T-0001",
                    "title": "Replace LICENSE",
                    "status": "proposed",
                    "source_evidence": "Valid evidence path across repos",
                    "acceptance": "Named OSI license exists",
                    "review_tier": "routine",
                    "roi": {"benefit": 4, "rationale": "High legal clarity"},
                    "effort_hours": {"low": 1.0, "high": 2.0},
                },
                {
                    "id": "T-0002",
                    "title": "Fix YouTube About text",
                    "status": "proposed",
                    "source_evidence": "research/proposals/2026-10-04-youtube-about.md",
                    "acceptance": "About text carries research-not-advice and independence lines",
                    "review_tier": "routine",
                    "roi": {"benefit": 4, "rationale": "Clarifies research boundary"},
                    "effort_hours": {"low": 0.25, "high": 0.5},
                },
                {
                    "id": "T-0005",
                    "title": "Download CFF PDFs by hand",
                    "status": "proposed",
                    "source_evidence": "research/sources/catalog.yaml",
                    "acceptance": "PDFs present in download folder",
                    "review_tier": "routine",
                    "roi": {"benefit": 4, "rationale": "Unblocks US extraction"},
                    "effort_hours": {"low": 0.5, "high": 1.0},
                    "notes": "Human task. Run fetch_sources.py --manual",
                },
                {
                    "id": "T-0158",
                    "title": "Public site health & dignity sentinel",
                    "status": "proposed",
                    "source_evidence": "Scheduled audit spec in SKILL.md",
                    "acceptance": "Daily scheduled check runs tools/check_live.py, check-voice.py, and render-board.ps1 -Check",
                    "review_tier": "routine",
                    "roi": {"benefit": 4, "rationale": "Prevents live site regressions"},
                    "effort_hours": {"low": 2.0, "high": 4.0},
                },
                {
                    "id": "T-0999",
                    "title": "Vague speculative task",
                    "status": "proposed",
                    "source_evidence": "too short",
                    "acceptance": "vague",
                    "review_tier": "routine",
                    "roi": {"benefit": 1, "rationale": "vague"},
                    "effort_hours": {"low": 1.0, "high": 2.0},
                },
            ],
        }

    def test_human_gate_detection(self):
        # T-0001 is in human_ids set
        task_1 = self.mock_board["tasks"][0]
        is_hg_1, reason_1 = tb.is_human_gated(task_1, self.mock_human_ids)
        self.assertTrue(is_hg_1)
        self.assertIn("HUMAN-TASKS.md", reason_1)

        # T-0005 has 'Human task' in notes
        task_5 = self.mock_board["tasks"][2]
        is_hg_5, reason_5 = tb.is_human_gated(task_5, self.mock_human_ids)
        self.assertTrue(is_hg_5)
        self.assertIn("human", reason_5.lower())

        # T-0002 is not human gated
        task_2 = self.mock_board["tasks"][1]
        is_hg_2, _ = tb.is_human_gated(task_2, self.mock_human_ids)
        self.assertFalse(is_hg_2)

    def test_grounded_executable_validation(self):
        # T-0002 has valid fields
        task_2 = self.mock_board["tasks"][1]
        is_val_2, _ = tb.is_grounded_executable(task_2)
        self.assertTrue(is_val_2)

        # T-0999 has short evidence & acceptance
        task_999 = self.mock_board["tasks"][4]
        is_val_999, reason_999 = tb.is_grounded_executable(task_999)
        self.assertFalse(is_val_999)
        self.assertIn("source_evidence", reason_999)

    def test_triage_board_approval_and_completion(self):
        board_copy = copy.deepcopy(self.mock_board)
        updated, stats = tb.triage_board(board_copy, self.mock_human_ids, auto_approve=True)

        # T-0002 should be approved to ready
        self.assertIn("T-0002", stats["approved_to_ready"])
        task_2 = next(t for t in updated["tasks"] if t["id"] == "T-0002")
        self.assertEqual(task_2["status"], "ready")
        self.assertIn("CRO Auto-Triage: Approved to ready", task_2["notes"])

        # T-0158 should be marked done
        self.assertIn("T-0158", stats["completed_to_done"])
        task_158 = next(t for t in updated["tasks"] if t["id"] == "T-0158")
        self.assertEqual(task_158["status"], "done")
        self.assertTrue(task_158["roi"]["measured"])

        # T-0001 and T-0005 remain proposed (human gated)
        task_1 = next(t for t in updated["tasks"] if t["id"] == "T-0001")
        self.assertEqual(task_1["status"], "proposed")
        task_5 = next(t for t in updated["tasks"] if t["id"] == "T-0005")
        self.assertEqual(task_5["status"], "proposed")

        # T-0999 remains proposed (ungrounded)
        task_999 = next(t for t in updated["tasks"] if t["id"] == "T-0999")
        self.assertEqual(task_999["status"], "proposed")

    def test_idempotency(self):
        board_copy = copy.deepcopy(self.mock_board)
        updated_1, stats_1 = tb.triage_board(board_copy, self.mock_human_ids, auto_approve=True)
        self.assertEqual(len(stats_1["approved_to_ready"]), 1)

        # Second pass should make 0 new approvals or completions
        updated_2, stats_2 = tb.triage_board(updated_1, self.mock_human_ids, auto_approve=True)
        self.assertEqual(len(stats_2["approved_to_ready"]), 0)
        self.assertEqual(len(stats_2["completed_to_done"]), 0)


if __name__ == "__main__":
    unittest.main()

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
                    "source_evidence": "Valid evidence path across repos: LICENSE.md",
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
                    "id": "T-0150",
                    "title": "In silico 3D Cryo-EM perturbation modeling and cryptic pocket discovery",
                    "status": "ready",
                    "source_evidence": "PDB coordinates 6MSM, 5UAK, 8EIQ; Horn's quaternion C-alpha alignment",
                    "acceptance": "Cryo-EM theratyping presets for R347 and R1070 render on 3D viewer",
                    "review_tier": "elevated",
                    "roi": {"benefit": 5, "rationale": "Curative theratyping for unclassified variants"},
                    "effort_hours": {"low": 2.0, "high": 4.0},
                },
                {
                    "id": "T-0158",
                    "title": "Public site health & dignity sentinel",
                    "status": "proposed",
                    "source_evidence": "Scheduled audit spec in .claude/skills/scheduled-site-audit/SKILL.md",
                    "acceptance": "Daily scheduled check runs tools/check_live.py, check-voice.py, and render-board.ps1 -Check",
                    "review_tier": "routine",
                    "roi": {"benefit": 4, "rationale": "Prevents live site regressions"},
                    "effort_hours": {"low": 2.0, "high": 4.0},
                },
                {
                    "id": "T-0999",
                    "title": "Vague speculative task claiming only cure",
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
        task_1 = self.mock_board["tasks"][0]
        is_hg_1, reason_1 = tb.is_human_gated(task_1, self.mock_human_ids)
        self.assertTrue(is_hg_1)
        self.assertIn("HUMAN-TASKS.md", reason_1)

        task_5 = self.mock_board["tasks"][2]
        is_hg_5, reason_5 = tb.is_human_gated(task_5, self.mock_human_ids)
        self.assertTrue(is_hg_5)
        self.assertIn("human", reason_5.lower())

        task_2 = self.mock_board["tasks"][1]
        is_hg_2, _ = tb.is_human_gated(task_2, self.mock_human_ids)
        self.assertFalse(is_hg_2)

    def test_grounded_executable_validation(self):
        task_2 = self.mock_board["tasks"][1]
        is_val_2, _ = tb.is_grounded_executable(task_2)
        self.assertTrue(is_val_2)

        task_999 = self.mock_board["tasks"][5]
        is_val_999, reason_999 = tb.is_grounded_executable(task_999)
        self.assertFalse(is_val_999)
        self.assertIn("source_evidence", reason_999)

    def test_anti_hallucination_guardrails(self):
        # Valid anchor (PDB coordinates)
        task_150 = self.mock_board["tasks"][3]
        is_valid_150, _, warnings_150 = tb.verify_anti_hallucination_guardrails(task_150)
        self.assertTrue(is_valid_150)
        self.assertEqual(len(warnings_150), 0)

        # DOI anchor
        doi_task = {
            "title": "Vertex VX-522 trial analysis",
            "source_evidence": "BEACON-CF NCT05668741; DOI 10.1056/NEJMoa2000001",
            "acceptance": "Verify delivery criteria",
            "review_tier": "elevated",
        }
        is_valid_doi, _, _ = tb.verify_anti_hallucination_guardrails(doi_task)
        self.assertTrue(is_valid_doi)

        # Unanchored task
        fake_task = {
            "title": "Random AI conjecture",
            "source_evidence": "Thought of during conversation with no paper or catalog link",
            "acceptance": "Check that thoughts make sense",
            "review_tier": "routine",
        }
        is_valid_fake, reason_fake, _ = tb.verify_anti_hallucination_guardrails(fake_task)
        self.assertFalse(is_valid_fake)
        self.assertIn("Missing verifiable primary literature", reason_fake)

    def test_curative_mission_classification(self):
        task_150 = self.mock_board["tasks"][3]
        cls_150 = tb.classify_curative_mission(task_150)
        self.assertEqual(cls_150["track"], "Track A (Curative Biophysics & Target Discovery)")
        self.assertEqual(cls_150["priority"], "P1")
        self.assertEqual(cls_150["recommended_route"], "frontier")

        atlas_task = {
            "title": "CF trial endpoint atlas from ClinicalTrials.gov",
            "acceptance": "Generate Trial Endpoint Atlas",
            "source_evidence": "ClinicalTrials.gov API v2; sources/catalog.yaml",
            "area": "atlas",
        }
        cls_atlas = tb.classify_curative_mission(atlas_task)
        self.assertEqual(cls_atlas["track"], "Track B (Clinical Translation & Public Platform)")
        self.assertEqual(cls_atlas["priority"], "P1")
        self.assertEqual(cls_atlas["recommended_route"], "cloud")

    def test_triage_board_approval_and_completion(self):
        board_copy = copy.deepcopy(self.mock_board)
        updated, stats = tb.triage_board(board_copy, self.mock_human_ids, auto_approve=True, prioritize=True)

        self.assertIn("T-0002", stats["approved_to_ready"])
        task_2 = next(t for t in updated["tasks"] if t["id"] == "T-0002")
        self.assertEqual(task_2["status"], "ready")
        self.assertIn("CRO Auto-Triage: Approved to ready", task_2["notes"])

        self.assertIn("T-0158", stats["completed_to_done"])
        task_158 = next(t for t in updated["tasks"] if t["id"] == "T-0158")
        self.assertEqual(task_158["status"], "done")
        self.assertTrue(task_158["roi"]["measured"])

        task_1 = next(t for t in updated["tasks"] if t["id"] == "T-0001")
        self.assertEqual(task_1["status"], "proposed")
        task_5 = next(t for t in updated["tasks"] if t["id"] == "T-0005")
        self.assertEqual(task_5["status"], "proposed")

        task_999 = next(t for t in updated["tasks"] if t["id"] == "T-0999")
        self.assertEqual(task_999["status"], "proposed")

    def test_idempotency(self):
        board_copy = copy.deepcopy(self.mock_board)
        updated_1, stats_1 = tb.triage_board(board_copy, self.mock_human_ids, auto_approve=True, prioritize=True)
        self.assertEqual(len(stats_1["approved_to_ready"]), 1)

        updated_2, stats_2 = tb.triage_board(updated_1, self.mock_human_ids, auto_approve=True, prioritize=True)
        self.assertEqual(len(stats_2["approved_to_ready"]), 0)
        self.assertEqual(len(stats_2["completed_to_done"]), 0)


if __name__ == "__main__":
    unittest.main()

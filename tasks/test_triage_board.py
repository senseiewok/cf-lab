#!/usr/bin/env python3
"""Unit tests for tasks/triage_board.py."""
from __future__ import annotations

import copy
import json
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

    def test_all_approved_mode(self):
        board_copy = copy.deepcopy(self.mock_board)
        updated, stats = tb.triage_board(board_copy, self.mock_human_ids, all_approved=True, roi_model=True)
        # All non-done tasks should now be ready
        ready_tasks = [t for t in updated["tasks"] if t["status"] == "ready"]
        self.assertEqual(len(ready_tasks), 5)  # T-0001, T-0002, T-0005, T-0150, T-0999 (T-0158 is done)

        # Human-gated tasks should carry executor: human
        task_1 = next(t for t in updated["tasks"] if t["id"] == "T-0001")
        self.assertEqual(task_1["status"], "ready")
        self.assertEqual(task_1["executor"], "human")
        self.assertTrue(task_1["human_required"])

        # Agent-capable tasks carry executor: agent
        task_2 = next(t for t in updated["tasks"] if t["id"] == "T-0002")
        self.assertEqual(task_2["status"], "ready")
        self.assertEqual(task_2["executor"], "agent")
        self.assertFalse(task_2["human_required"])

    def test_multi_category_roi(self):
        task_150 = self.mock_board["tasks"][3]
        roi_meta = tb.compute_multi_category_roi(task_150)
        self.assertIn("curative_biophysics", roi_meta["categories"])
        self.assertIn("clinical_translation", roi_meta["categories"])
        self.assertGreaterEqual(roi_meta["categories"]["curative_biophysics"], 9.0)
        self.assertGreater(roi_meta["composite_score"], 0)
        self.assertGreater(roi_meta["roi_ratio"], 0)

    def test_high_impact_multi_hour_milestones_prioritized_as_p1(self):
        milestone = {
            "id": "T-0173",
            "title": "Trial Endpoint Atlas: zero-build interactive showcase compilation for /cf/trials/",
            "repo": ".ai",
            "area": "site",
            "status": "ready",
            "priority": "P2",
            "effort_hours": {"low": 4.0, "high": 6.0},
            "roi": {"benefit": 5, "rationale": "Zero-build public atlas"},
            "acceptance": "python -m unittest tests.test_site",
            "review_tier": "full",
        }
        roi_meta = tb.compute_multi_category_roi(milestone)
        # Even though mean_effort_hours is 5.0 (> 4.0), its high mission impact keeps it P1
        self.assertEqual(tb.determine_roi_priority(milestone, roi_meta), "P1")

        tiny_routine = {
            "id": "T-0990",
            "title": "Minor typo cleanup in internal note",
            "repo": "cf-lab",
            "area": "docs",
            "status": "ready",
            "priority": "P2",
            "effort_hours": {"low": 0.25, "high": 0.5},
            "roi": {"benefit": 2, "rationale": "Small cleanup"},
            "acceptance": "check passes",
            "review_tier": "routine",
        }
        tiny_meta = tb.compute_multi_category_roi(tiny_routine)
        self.assertNotEqual(tb.determine_roi_priority(tiny_routine, tiny_meta), "P1")

    def test_council_approved_and_boilerplate_not_human_gated(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            hp = Path(d) / "HUMAN-TASKS.md"
            hp.write_text(
                "# Human tasks\n"
                "- [x] **OpenAlex API key**: done (T-0090)\n"
                "- [ ] **Clinician review (T-0105)**\n\n"
                "## 6. Council-Approved Tasks (Automated & Moved to Ready / Done)\n"
                "| **T-0102** | Variant layer | `ready` | Approved |\n",
                encoding="utf-8",
            )
            ids = tb.load_human_gated_ids(hp)
            self.assertEqual(ids, {"T-0105"})
            approved = tb.load_council_approved_agent_ids(hp)
            self.assertEqual(approved, {"T-0102"})

        boilerplate_task = {
            "id": "T-0060",
            "title": "Refresh website",
            "acceptance": "All tests pass",
            "notes": "Proposed by a model; only a human moves it to ready.",
            "roi": {"rationale": "High value"},
        }
        is_hg, _ = tb.is_human_gated(boilerplate_task, {"T-0105"})
        self.assertFalse(is_hg)


class TestEvidencePackageAndUpdater(unittest.TestCase):
    def test_verify_evidence_package_optional(self):
        task_no_ep = {"id": "T-9999", "title": "Routine task"}
        valid, msg = tb.verify_evidence_package(task_no_ep)
        self.assertTrue(valid)
        self.assertIn("optional", msg.lower())

    def test_verify_evidence_package_validation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            packet = root / "evidence" / "test-packet.md"
            packet.parent.mkdir(parents=True, exist_ok=True)
            claims = root / "claims.json"

            # 1. Missing packet
            task_missing = {"id": "T-9998", "evidence_package": {"packet_path": "evidence/test-packet.md"}}
            valid, _ = tb.verify_evidence_package(task_missing, repo_root=root)
            self.assertFalse(valid)

            # 2. Incomplete sections
            packet.write_text("# Incomplete\n## Some section\n", encoding="utf-8")
            valid, reason = tb.verify_evidence_package(task_missing, repo_root=root)
            self.assertFalse(valid)
            self.assertIn("missing", reason.lower())

            # 3. Complete sections
            packet.write_text(
                "# Title\n"
                "## 1. Primary Sources\n- source\n"
                "## 2. Verbatim Excerpts & Quantitative Metrics\n- Denominators: N=100\n"
                "## 3. Invariants & Guardrails\n- Do not pool\n",
                encoding="utf-8",
            )
            valid, _ = tb.verify_evidence_package(task_missing, repo_root=root)
            self.assertTrue(valid)

            # 4. Invalid claims JSON
            claims.write_text("{bad-json}", encoding="utf-8")
            task_bad_claims = {
                "id": "T-9997",
                "evidence_package": {
                    "packet_path": "evidence/test-packet.md",
                    "claims_file": "claims.json",
                },
            }
            valid, reason = tb.verify_evidence_package(task_bad_claims, repo_root=root)
            self.assertFalse(valid)
            self.assertIn("failed parsing", reason.lower())

            # 5. Valid claims JSON
            claims.write_text('[{"id": "c1", "claim": "Valid claim"}]', encoding="utf-8")
            valid, _ = tb.verify_evidence_package(task_bad_claims, repo_root=root)
            self.assertTrue(valid)

    def test_update_task_helper(self):
        import tempfile
        import update_task as ut
        with tempfile.TemporaryDirectory() as d:
            board_file = Path(d) / "board.json"
            board_file.write_text(
                json.dumps({
                    "schema_version": 1,
                    "tasks": [{
                        "id": "T-9999",
                        "title": "Test task",
                        "repo": "cf-lab",
                        "status": "ready",
                        "priority": "P2",
                        "roi": {"benefit": 3, "rationale": "Test"},
                        "effort_hours": {"low": 1.0, "high": 2.0},
                    }]
                }),
                encoding="utf-8",
            )

            # Update status and evidence package
            success = ut.update_task(
                board_path=board_file,
                task_id="T-9999",
                status="done",
                actual_hours=1.5,
                measured_outcome="Test completed",
                evidence_packet="evidence/test.md",
                answer_tier="T2",
                catalog_sources=["source-1"],
            )
            self.assertTrue(success)

            updated = json.loads(board_file.read_text(encoding="utf-8"))
            t = updated["tasks"][0]
            self.assertEqual(t["status"], "done")
            self.assertEqual(t["roi"]["actual_hours"], 1.5)
            self.assertEqual(t["evidence_package"]["packet_path"], "evidence/test.md")
            self.assertEqual(t["evidence_package"]["answer_tier"], "T2")
            self.assertEqual(t["evidence_package"]["catalog_sources"], ["source-1"])


if __name__ == "__main__":
    unittest.main()


#!/usr/bin/env python3
"""Unit tests for Gemini Deep Research Pilot and Collaborative Planning (T-0049)."""

import tempfile
import unittest
from pathlib import Path

from tasks.pilot_gemini_deep_research import (
    CollaborativePlan,
    HumanReviewGateError,
    PrivateMaterialDetectedError,
    check_no_private_material,
    execute_pilot,
    extract_citations,
    generate_plan,
    verify_citations_offline,
)


class TestPilotGeminiDeepResearch(unittest.TestCase):
    def test_generate_plan_defaults(self):
        plan = generate_plan()
        self.assertEqual(plan.status, "AWAITING_HUMAN_REVIEW")
        self.assertIn("survival methodology", plan.question)
        self.assertGreater(len(plan.objectives), 0)
        self.assertGreater(len(plan.planned_sources), 0)
        self.assertGreater(len(plan.guardrails), 0)
        self.assertIn("Human Review Gate", plan.to_markdown())

    def test_plan_approval_transition(self):
        plan = generate_plan()
        self.assertEqual(plan.status, "AWAITING_HUMAN_REVIEW")
        plan.approve("Sensei Ewok", "Approved for pilot execution.")
        self.assertEqual(plan.status, "APPROVED")
        self.assertEqual(plan.reviewed_by, "Sensei Ewok")
        self.assertIn("Approved for pilot execution", plan.to_markdown())

    def test_human_review_gate_enforcement(self):
        plan = generate_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            report_path = tmp / "report.md"
            ledger_path = tmp / "ledger.jsonl"
            with self.assertRaises(HumanReviewGateError):
                execute_pilot(plan, report_path, ledger_path, force_human_approval=False)
            self.assertFalse(report_path.exists())
            self.assertFalse(ledger_path.exists())

    def test_private_material_detection(self):
        # Clean text
        check_no_private_material("What is the median predicted age of survival in CF?")

        # Google API key pattern
        with self.assertRaises(PrivateMaterialDetectedError):
            check_no_private_material("Query with AIzaSyAbcdef1234567890abcdef123456789")

        # GitHub token pattern
        with self.assertRaises(PrivateMaterialDetectedError):
            check_no_private_material("Query with ghp_123456789012345678901234567890123456")

        # Email pattern
        with self.assertRaises(PrivateMaterialDetectedError):
            check_no_private_material("Contact researcher at patient@example.com for CF data")

    def test_extract_citations(self):
        sample_text = """
        Study published in 10.1016/j.jcf.2023.08.001 and clinical trial NCT03525444.
        Also tracked in NCT05033080 and evaluated TRIKAFTA alongside ALYFTREK and KALYDECO.
        """
        citations = extract_citations(sample_text)
        self.assertIn("10.1016/j.jcf.2023.08.001", citations["dois"])
        self.assertIn("NCT03525444", citations["ncts"])
        self.assertIn("NCT05033080", citations["ncts"])
        self.assertIn("TRIKAFTA", citations["approvals"])
        self.assertIn("ALYFTREK", citations["approvals"])
        self.assertIn("KALYDECO", citations["approvals"])

    def test_verify_citations_offline(self):
        citations = {
            "dois": [
                "10.1016/j.jcf.2023.08.001",
                "10.1016/S0140-6736(97)11096-0",  # Retracted benchmark
            ],
            "ncts": ["NCT03525444"],
            "approvals": ["TRIKAFTA"],
        }
        records, counts = verify_citations_offline(citations)
        self.assertEqual(counts["clean"], 3)
        self.assertEqual(counts["flagged"], 1)
        self.assertEqual(counts["unresolvable"], 0)
        self.assertEqual(counts["total"], 4)

        flagged_record = [r for r in records if r["status"] == "flagged_retraction"]
        self.assertEqual(len(flagged_record), 1)
        self.assertEqual(flagged_record[0]["id"], "10.1016/S0140-6736(97)11096-0")

    def test_approved_execution_end_to_end(self):
        plan = generate_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            report_path = tmp / "report.md"
            ledger_path = tmp / "ledger.jsonl"
            res = execute_pilot(
                plan,
                report_path,
                ledger_path,
                force_human_approval=True,
                human_name="Sensei Ewok",
            )
            self.assertEqual(res["status"], "PASS")
            self.assertTrue(report_path.exists())
            self.assertTrue(ledger_path.exists())
            self.assertGreater(len(res["citations_extracted"]["dois"]), 0)
            self.assertGreater(len(res["citations_extracted"]["ncts"]), 0)
            self.assertGreater(res["citation_counts"]["clean"], 0)


if __name__ == "__main__":
    unittest.main()

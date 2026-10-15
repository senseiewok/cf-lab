#!/usr/bin/env python3
"""Unit tests for tasks/scan_person_generalization.py (Task T-0109)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

import scan_person_generalization as spg  # noqa: E402


class TestScanPersonGeneralization(unittest.TestCase):
    def test_clean_generalized_queries(self):
        """Clean scientific queries without personal attributes must not be flagged."""
        clean = [
            "CFTR gating mutations potentiator response",
            "Trikafta liver enzyme monitoring guidelines",
            "Nonsense mutation readthrough compounds in cystic fibrosis",
            "Pulmonary exacerbation rates with elexacaftor tezacaftor ivacaftor",
            "Pseudomonas aeruginosa bacteriophage therapy co-evolution dynamics",
            "FEV1 ppFEV1 endpoints in cystic fibrosis clinical trials",
            "cf clinic directory and accredited care centers",
            "cystic fibrosis diagnosis guidelines and consensus statements",
            "differential diagnosis of bronchiectasis in adults",
        ]
        for q in clean:
            violation = spg.check_violation(q)
            self.assertIsNone(violation, f"Query falsely flagged: {q}")

    def test_composite_queries_flagged(self):
        """Composite queries combining health terms and personal attributes must be flagged."""
        test_cases = [
            ("14-year-old cystic fibrosis FEV1 decline", ["age"]),
            ("12-yo with cystic fibrosis in Seattle", ["age", "place"]),
            ("10-y/o patient in Cleveland with CF F508del", ["age", "place"]),
            ("Seattle children's hospital Trikafta protocol", ["place"]),
            ("pregnant CF patient Kalydeco safety data", ["status"]),
            ("newly diagnosed CF patient with F508del", ["status"]),
            ("Ashkenazi Jewish W1282X mutation carrier screening", ["origin"]),
            ("diagnosed with cystic fibrosis on 2024-03-15", ["date", "status"]),
        ]
        for query, expected_cats in test_cases:
            violation = spg.check_violation(query)
            self.assertIsNotNone(violation, f"Query not flagged: {query}")
            for cat in expected_cats:
                self.assertIn(cat, violation["categories"], f"Category {cat} not found in {query}")

    def test_transcript_scanning(self):
        """Scanner correctly parses tool_calls in transcript.jsonl."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript = Path(tmpdir) / "transcript.jsonl"
            lines = [
                json.dumps({
                    "step_index": 1,
                    "type": "PLANNER_RESPONSE",
                    "tool_calls": [
                        {"name": "search_web", "args": {"query": "CFTR modulator eligibility"}}
                    ]
                }),
                json.dumps({
                    "step_index": 2,
                    "type": "PLANNER_RESPONSE",
                    "tool_calls": [
                        {"name": "search_web", "args": {"query": "10-year-old child in Chicago with CF F508del"}}
                    ]
                }),
                json.dumps({
                    "step_index": 3,
                    "type": "PLANNER_RESPONSE",
                    "tool_calls": [
                        {"name": "read_browser_page", "args": json.dumps({"url": "https://example.com/patient/14-yo-seattle-trikafta"})}
                    ]
                }),
            ]
            transcript.write_text("\n".join(lines), encoding="utf-8")

            findings = spg.scan_transcript_for_person_queries(transcript)
            self.assertEqual(len(findings), 2)
            self.assertEqual(findings[0]["step_index"], 2)
            self.assertIn("age", findings[0]["categories"])
            self.assertIn("place", findings[0]["categories"])
            self.assertEqual(findings[1]["step_index"], 3)
            self.assertIn("age", findings[1]["categories"])
            self.assertIn("place", findings[1]["categories"])

    def test_self_test_method(self):
        """spg.run_self_test() returns True."""
        self.assertTrue(spg.run_self_test())


if __name__ == "__main__":
    unittest.main()

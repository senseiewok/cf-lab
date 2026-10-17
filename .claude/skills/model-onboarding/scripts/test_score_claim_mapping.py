#!/usr/bin/env python3
"""Unit tests for .claude/skills/model-onboarding/scripts/score_claim_mapping.py (T-0021)."""
from __future__ import annotations

import json
import unittest
from score_claim_mapping import DEFAULT_BASELINE_RESULTS, DEFAULT_FIXTURE, score_predictions, validate_fixture


class TestScoreClaimMapping(unittest.TestCase):
    def test_fixture_exists_and_validates_30_20_10_split(self) -> None:
        ok, msg = validate_fixture(DEFAULT_FIXTURE)
        self.assertTrue(ok, msg)

    def test_baseline_results_report_abstention_separately_from_accuracy(self) -> None:
        self.assertTrue(DEFAULT_BASELINE_RESULTS.is_file(), f"Missing {DEFAULT_BASELINE_RESULTS}")
        data = json.loads(DEFAULT_BASELINE_RESULTS.read_text(encoding="utf-8"))
        self.assertIn("models", data)
        self.assertGreaterEqual(len(data["models"]), 1)
        for m in data["models"]:
            self.assertIn("covered_accuracy", m)
            self.assertIn("abstention_rate_on_uncovered", m)
            self.assertIn("false_confident_on_uncovered", m)
            self.assertNotEqual(m["model_id"], "")

    def test_overconfident_model_on_uncovered_claims_fails_admission(self) -> None:
        fixture = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
        # Perfect on the 50 covered claims, but answers 'supported' on all 10 'abstain' claims
        preds = {}
        for item in fixture["items"]:
            if item["expected_verdict"] == "abstain":
                preds[item["id"]] = "supported"
            else:
                preds[item["id"]] = item["expected_verdict"]

        report = score_predictions(fixture, preds, model_id="overconfident-test-model")
        self.assertEqual(report["covered_accuracy"], 1.0)
        self.assertEqual(report["abstention_rate_on_uncovered"], 0.0)
        self.assertEqual(report["false_confident_on_uncovered"], 10)
        self.assertFalse(report["passed_abstention_gate"])
        self.assertFalse(report["admitted"])


if __name__ == "__main__":
    unittest.main()

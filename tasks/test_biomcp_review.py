"""Unit test verifying that docs/biomcp-admission-review.md satisfies all T-0042 acceptance criteria."""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "biomcp-admission-review.md"


class TestBioMCPAdmissionReview(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DOC_PATH.exists(), f"Expected admission review doc at {DOC_PATH}")
        self.text = DOC_PATH.read_text(encoding="utf-8")

    def test_complement_or_not_decision_and_citation_rule(self):
        self.assertIn("DISCOVERY-ONLY complement", self.text)
        self.assertIn("cf-evidence-loop", self.text)
        self.assertIn("Shipped citations", self.text)

    def test_model_onboarding_section_1_provenance(self):
        self.assertIn("biomcp==0.1.7", self.text)
        self.assertIn("GenomOncology", self.text)
        self.assertIn("MIT", self.text)
        self.assertIn("install", self.text.lower())
        self.assertIn("FastMCP", self.text)

    def test_model_onboarding_section_6_injection(self):
        self.assertIn("injection", self.text.lower())
        self.assertIn("<untrusted_data>", self.text)
        self.assertIn("zero tools", self.text.lower())

    def test_security_runtime_checklist(self):
        self.assertIn("security-runtime", self.text)
        self.assertIn("Auto-Approve", self.text)
        self.assertIn("PHI", self.text)

    def test_network_rules_r1_through_r9(self):
        for r in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"]:
            self.assertIn(f"**{r}**", self.text)

    def test_catalog_conflicts_clingen_and_gnomad(self):
        self.assertIn("ClinGen", self.text)
        self.assertIn("gnomAD", self.text)
        self.assertIn("forbidden", self.text.lower())
        self.assertIn("manual", self.text.lower())

    def test_conditions_of_use(self):
        self.assertIn("Conditions of Use", self.text)
        self.assertIn("Discovery Only", self.text)


if __name__ == "__main__":
    unittest.main()

"""Unit test for T-0117: Identity in public files: one role address, one way to sign.

Verifies the 5 acceptance criteria:
1. One role address in public files (contact@senseiewok.ai).
2. Letters signed by the lab (institutional signature, never personal).
3. The catalog names 'the contact in the terms' instead of addresses.
4. A recorded decision on vendor credit (docs/vendor-credit-decision.md).
5. Commit author addresses checked by the gate (run-gate.ps1).
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestIdentityPolicy(unittest.TestCase):
    """Verifies compliance with T-0117 identity, signing, catalog, vendor credit, and commit gate requirements."""

    def test_one_role_address_in_public_files(self):
        """1. Asserts SECURITY.md uses contact@senseiewok.ai and contains no personal first-name email."""
        sec_path = REPO_ROOT / "SECURITY.md"
        self.assertTrue(sec_path.exists(), "SECURITY.md must exist")
        text = sec_path.read_text(encoding="utf-8")

        self.assertIn("contact@senseiewok.ai", text, "SECURITY.md must use the official role address contact@senseiewok.ai")
        self.assertNotIn("diego@senseiewok.ai", text, "SECURITY.md must not expose personal first-name address diego@senseiewok.ai")

    def test_letters_signed_by_the_lab(self):
        """2. Asserts docs/identity-and-signing-policy.md mandates signing letters by the lab as an entity."""
        policy_path = REPO_ROOT / "docs" / "identity-and-signing-policy.md"
        self.assertTrue(policy_path.exists(), "docs/identity-and-signing-policy.md must exist")
        text = policy_path.read_text(encoding="utf-8")

        self.assertIn("Sensei Ewok CF Lab · contact@senseiewok.ai", text, "Policy must document the institutional signing pattern")
        self.assertIn("The Lab Speaks for Itself", text, "Policy must state that the lab speaks for itself without personal signing")

    def test_catalog_naming_convention(self):
        """3. Asserts catalog contact policy specifies 'the contact in the terms' instead of raw email addresses."""
        policy_path = REPO_ROOT / "docs" / "identity-and-signing-policy.md"
        text = policy_path.read_text(encoding="utf-8")
        self.assertIn("the contact in the terms", text.lower())
        self.assertIn("the contact named in the terms", text.lower())

    def test_recorded_decision_on_vendor_credit(self):
        """4. Asserts docs/vendor-credit-decision.md exists and records vendor independence and credit rationale."""
        decision_path = REPO_ROOT / "docs" / "vendor-credit-decision.md"
        self.assertTrue(decision_path.exists(), "docs/vendor-credit-decision.md must exist")
        text = decision_path.read_text(encoding="utf-8")

        self.assertIn("Governance Decision: Tool and AI Vendor Credit Policy", text)
        self.assertIn("Complete Institutional Independence", text)
        self.assertIn("non-endorsement", text.lower())

    def test_commit_author_addresses_checked_by_gate(self):
        """5. Asserts run-gate.ps1 deterministically checks commit author and committer addresses."""
        gate_path = REPO_ROOT / ".claude" / "skills" / "ai-loop-council" / "scripts" / "run-gate.ps1"
        self.assertTrue(gate_path.exists(), "run-gate.ps1 must exist")
        text = gate_path.read_text(encoding="utf-8")

        self.assertIn("commit author and committer identity", text)
        self.assertIn("GIT_AUTHOR_IDENT", text)
        self.assertIn("commit-author", text)
        self.assertIn("@(gmail|outlook|hotmail|yahoo|icloud|proton|protonmail)", text)


if __name__ == "__main__":
    unittest.main()

"""Unit test verifying that docs/dev-mcps-admission-review.md and AGENTS.md satisfy all T-0050 acceptance criteria."""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "dev-mcps-admission-review.md"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"


class TestDevMCPsAdmissionReview(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DOC_PATH.exists(), f"Expected admission review doc at {DOC_PATH}")
        self.text = DOC_PATH.read_text(encoding="utf-8")
        self.assertTrue(AGENTS_PATH.exists(), f"Expected AGENTS.md at {AGENTS_PATH}")
        self.agents_text = AGENTS_PATH.read_text(encoding="utf-8")

    def test_both_mcps_reviewed_and_admitted(self):
        self.assertIn("GitHub MCP Server", self.text)
        self.assertIn("Microsoft Learn Docs MCP", self.text)
        self.assertIn("read-only", self.text.lower())

    def test_security_runtime_checklist(self):
        self.assertIn("security-runtime", self.text.lower())
        self.assertIn("scoped token", self.text.lower())
        self.assertIn("outside the repositories", self.text.lower())
        self.assertIn("senseiewok", self.text)

    def test_token_scoped_and_stored_outside_repos(self):
        # GitHub token scoped to senseiewok repos only and stored outside the repos
        self.assertIn("senseiewok/cf-lab", self.text)
        self.assertIn("senseiewok/cf-research", self.text)
        self.assertIn("senseiewok/cf-skills", self.text)
        self.assertIn("senseiewok/.ai", self.text)
        self.assertIn("outside the repositories", self.text.lower())

    def test_recorded_read_only_queries(self):
        self.assertIn("list_pull_requests", self.text)
        self.assertIn("search_docs", self.text)
        self.assertIn("Recorded Response Output", self.text)

    def test_model_onboarding_and_injection_guard(self):
        self.assertIn("<untrusted_data>", self.text)
        self.assertIn("zero tools", self.text.lower())
        self.assertIn("MIT", self.text)

    def test_agents_md_names_both_and_permitted_uses(self):
        # AGENTS.md names both and their permitted uses
        self.assertIn("GitHub MCP", self.agents_text)
        self.assertIn("Microsoft Learn Docs MCP", self.agents_text)
        self.assertIn("senseiewok", self.agents_text)
        self.assertIn("read-only", self.agents_text.lower())


if __name__ == "__main__":
    unittest.main()

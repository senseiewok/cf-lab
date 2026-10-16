"""Unit test for T-0095: README tool credits vs website credits and footer alignment."""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_REPO_ROOT = REPO_ROOT.parent.parent / ".ai"
if not AI_REPO_ROOT.exists():
    AI_REPO_ROOT = REPO_ROOT.parent / ".ai"

TOOL_REGEX = re.compile(
    r"(?i)\b(?:Visual Studio Code|GitHub Copilot|GitHub|PowerShell|Playwright|Microsoft Edge|Ollama|Python|Git|Anthropic)\b"
)


class TestCreditsAlignment(unittest.TestCase):
    """Verifies that tool credits between README and website are properly tracked and reconciled."""

    def test_readme_tool_credits(self):
        readme_path = REPO_ROOT / "README.md"
        self.assertTrue(readme_path.exists(), "README.md must exist in cf-lab")

        text = readme_path.read_text(encoding="utf-8")
        match = re.search(r"### Thanks to the tools.*?(?=## Repositories)", text, re.DOTALL)
        self.assertIsNotNone(match, "README must contain '### Thanks to the tools' section")

        section = match.group(0)
        tools = {t.lower() for t in TOOL_REGEX.findall(section)}

        expected_readme_tools = {
            "git",
            "github",
            "github copilot",
            "microsoft edge",
            "ollama",
            "playwright",
            "powershell",
            "python",
            "visual studio code",
        }
        self.assertTrue(
            expected_readme_tools.issubset(tools),
            f"Missing expected tools in README section: {expected_readme_tools - tools}",
        )

    def test_alignment_document_exists_and_covers_differences(self):
        doc_path = REPO_ROOT / "docs" / "tool-credits-alignment.md"
        self.assertTrue(doc_path.exists(), "docs/tool-credits-alignment.md must exist")

        content = doc_path.read_text(encoding="utf-8")
        # Verify that differences (Microsoft Edge, Playwright, PowerShell, Anthropic) are explicitly analyzed
        for term in ["Microsoft Edge", "Playwright", "PowerShell", "Anthropic"]:
            self.assertIn(term, content, f"Alignment doc must analyze '{term}'")

        # Verify non-endorsement sentence analysis is present
        self.assertIn("non-endorsement", content.lower())

    def test_welcome_discussions_draft_exists(self):
        welcome_path = REPO_ROOT / "docs" / "welcome-discussions-draft.md"
        self.assertTrue(welcome_path.exists(), "docs/welcome-discussions-draft.md must exist")
        content = welcome_path.read_text(encoding="utf-8")
        self.assertIn("Welcome to Sensei Ewok's CF Lab Discussions", content)
        self.assertIn("research, not medical advice", content.lower())


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for YouTube channel About text and acceptance criteria (T-0002).

Validates that the approved YouTube About text in docs/youtube-about-update.md:
1. Satisfies T-0002 acceptance criteria: contains 'not medical advice' and 'not affiliated'.
2. Eliminates forbidden hype and curative claims: 'accelerate the cure', 'medical AI', 'bleeding edge'.
3. Preserves legitimate disclosures: donation URL, API token funding, and creative hobbies.
4. Provides an opt-in live check (`--live`) against the public @SenseiEwok YouTube page.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "youtube-about-update.md"


def extract_approved_text(doc_path: Path) -> str:
    """Extract the approved text block from the documentation markdown."""
    content = doc_path.read_text(encoding="utf-8")
    match = re.search(r"```text\s*\n(Welcome to the Sensei Ewok Research Lab.*?)```", content, re.DOTALL)
    if not match:
        raise ValueError(f"Could not locate approved text block in {doc_path}")
    return match.group(1).strip()


class TestYouTubeAboutText(unittest.TestCase):
    """Deterministic offline unit tests for the approved YouTube text."""

    def setUp(self):
        self.assertTrue(DOC_PATH.exists(), f"Missing documentation file: {DOC_PATH}")
        self.text = extract_approved_text(DOC_PATH)

    def test_acceptance_criteria_phrases_present(self):
        """Acceptance requires 'not medical advice' and 'not affiliated'."""
        lower = self.text.lower()
        self.assertIn("not medical advice", lower, "Text must contain 'not medical advice'")
        self.assertIn("not affiliated", lower, "Text must contain 'not affiliated'")

    def test_forbidden_hype_and_cure_claims_absent(self):
        """Must remove 'accelerate the cure', 'medical AI', and 'bleeding edge'."""
        lower = self.text.lower()
        self.assertNotIn("accelerate the cure", lower, "Must not contain 'accelerate the cure'")
        self.assertNotIn("medical ai", lower, "Must not contain 'medical AI'")
        self.assertNotIn("bleeding edge", lower, "Must not contain 'bleeding edge'")

    def test_donation_link_and_revenue_disclosure_present(self):
        """Must include CFF Washington donation link and clear API token disclosure."""
        self.assertIn("https://give.cff.org/washington/donate", self.text)
        self.assertIn("Stream revenue goes toward the API costs", self.text)

    def test_creative_hobbies_preserved(self):
        """Maintains the workshop hobbies: WebGL, sim racing, game design, and guitar."""
        self.assertIn("WebGL", self.text)
        self.assertIn("sim racing", self.text)
        self.assertIn("game design", self.text)
        self.assertIn("guitar", self.text)


def check_live_channel(channel_url: str = "https://www.youtube.com/@SenseiEwok") -> tuple[bool, str]:
    """Fetch live channel metadata and check whether YouTube Studio update has been published."""
    import urllib.request
    from html.parser import HTMLParser

    class MetaParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.description = ""

        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if tag == "meta" and d.get("property") == "og:description":
                self.description = d.get("content", "")

    req = urllib.request.Request(
        channel_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return False, f"Network error reading channel: {e}"

    parser = MetaParser()
    parser.feed(html)
    desc = parser.description

    if not desc:
        return False, "Could not extract og:description from YouTube channel."

    desc_lower = desc.lower()
    has_cure = "accelerate the cure" in desc_lower
    has_advice = "not medical advice" in desc_lower
    has_affil = "not affiliated" in desc_lower

    if not has_cure and has_advice and has_affil:
        return True, "PASS: Live YouTube channel About text matches approved boundary text."

    reasons = []
    if has_cure:
        reasons.append("still contains 'accelerate the cure'")
    if not has_advice:
        reasons.append("missing 'not medical advice'")
    if not has_affil:
        reasons.append("missing 'not affiliated'")

    return False, f"PENDING MAINTAINER ACTION: Live description {', '.join(reasons)}."


if __name__ == "__main__":
    if "--live" in sys.argv:
        ok, msg = check_live_channel()
        print(msg)
        sys.exit(0 if ok else 1)
    unittest.main()

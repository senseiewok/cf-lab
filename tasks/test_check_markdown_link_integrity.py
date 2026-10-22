#!/usr/bin/env python3
"""Unit tests for check_markdown_link_integrity.py (T-0301)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_markdown_link_integrity import (  # noqa: E402
    audit_markdown_file,
    extract_anchors_from_markdown,
    is_ignored_target,
    main,
    scan_markdown_links,
    slugify_heading,
)


class TestMarkdownLinkIntegrity(unittest.TestCase):
    """Test suite verifying markdown link and anchor extraction and validation."""

    def test_slugify_heading_variations(self) -> None:
        """Verify heading slug generation matches GitHub-compatible markdown anchors."""
        self.assertEqual(slugify_heading("Introduction & Overview"), "introduction--overview")
        self.assertEqual(slugify_heading("Quick Start (Setup)"), "quick-start-setup")
        self.assertEqual(slugify_heading("Code `foo.py` and *bold* text"), "code-foopy-and-bold-text")
        self.assertEqual(slugify_heading("  Extra   Spaces  "), "extra-spaces")
        self.assertEqual(slugify_heading("Task T-0295: Automated Multi-Repo Worktree"), "task-t-0295-automated-multi-repo-worktree")
        self.assertEqual(slugify_heading("[Link in Title](http://example.com)"), "link-in-title")

    def test_extract_anchors_duplicate_headings_and_html(self) -> None:
        """Verify extraction of headings with duplicate counts and HTML anchor tags."""
        md = """
# Main Title
## Section
Some content
## Section
Another duplicate section
### Section
Third duplicate section
<a name="custom-anchor"></a>
<div id="div-anchor"></div>
"""
        anchors = extract_anchors_from_markdown(md)
        self.assertIn("main-title", anchors)
        self.assertIn("section", anchors)
        self.assertIn("section-1", anchors)
        self.assertIn("section-2", anchors)
        self.assertIn("custom-anchor", anchors)
        self.assertIn("div-anchor", anchors)

    def test_is_ignored_target(self) -> None:
        """Verify external protocols, placeholders, and dummy links are safely ignored."""
        self.assertTrue(is_ignored_target("https://github.com/senseiewok/cf-lab"))
        self.assertTrue(is_ignored_target("http://localhost:8000"))
        self.assertTrue(is_ignored_target("mailto:steward@senseiewok.ai"))
        self.assertTrue(is_ignored_target("file:///path/to/file"))
        self.assertTrue(is_ignored_target("<conversation-id>"))
        self.assertTrue(is_ignored_target("{task_id}"))
        self.assertTrue(is_ignored_target("$VAR"))
        self.assertTrue(is_ignored_target("#"))
        self.assertFalse(is_ignored_target("docs/SETUP.md"))
        self.assertFalse(is_ignored_target("#section-anchor"))
        self.assertFalse(is_ignored_target("../cf-research/sources/catalog.yaml"))

    def test_audit_valid_links_and_anchors(self) -> None:
        """Verify clean verification on valid relative links and anchors."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            doc_a = root / "doc_a.md"
            doc_b = root / "doc_b.md"

            doc_b.write_text(
                "# Target Document\n\n## Sub Heading\n\nTarget content.",
                encoding="utf-8"
            )

            doc_a.write_text(
                "# Source Document\n\n"
                "- Local link: [to doc b](doc_b.md)\n"
                "- Anchor link: [to doc b sub](doc_b.md#sub-heading)\n"
                "- Same file anchor: [source title](#source-document)\n"
                "- External: [GitHub](https://github.com)\n"
                "- Placeholder: [App Data](<appDataDir>/logs)\n",
                encoding="utf-8"
            )

            findings = audit_markdown_file(doc_a, repo_root=root)
            self.assertEqual(len(findings), 0)

    def test_audit_broken_file_link(self) -> None:
        """Verify broken file link is detected and reported with line number."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            doc_a = root / "doc_a.md"
            doc_a.write_text(
                "# Source\n\nBroken: [missing file](does_not_exist.md)\n",
                encoding="utf-8"
            )

            findings = audit_markdown_file(doc_a, repo_root=root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].error_type, "FILE_NOT_FOUND")
            self.assertEqual(findings[0].line_number, 3)

    def test_audit_broken_same_file_anchor(self) -> None:
        """Verify missing anchor in same file is detected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            doc_a = root / "doc_a.md"
            doc_a.write_text(
                "# Source Document\n\nJump: [to phantom](#phantom-section)\n",
                encoding="utf-8"
            )

            findings = audit_markdown_file(doc_a, repo_root=root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].error_type, "MISSING_ANCHOR")
            self.assertEqual(findings[0].anchor, "phantom-section")

    def test_audit_broken_target_file_anchor(self) -> None:
        """Verify existing target file with missing anchor is detected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            doc_a = root / "doc_a.md"
            doc_b = root / "doc_b.md"

            doc_b.write_text("# Target\n\nOnly target content.\n", encoding="utf-8")
            doc_a.write_text("Link: [target phantom](doc_b.md#missing-heading)\n", encoding="utf-8")

            findings = audit_markdown_file(doc_a, repo_root=root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].error_type, "MISSING_ANCHOR")

    def test_reference_style_links(self) -> None:
        """Verify reference-style links are checked."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            doc_a = root / "doc_a.md"
            doc_a.write_text(
                "Read the [guide][my-guide] for details.\n\n"
                "[my-guide]: missing_guide.md\n",
                encoding="utf-8"
            )

            findings = audit_markdown_file(doc_a, repo_root=root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].error_type, "FILE_NOT_FOUND")

    def test_scan_markdown_links_and_cli(self) -> None:
        """Verify directory walk and CLI main exit codes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            doc = root / "README.md"
            doc.write_text("# Welcome\n\n[Intro](#welcome)\n", encoding="utf-8")

            findings, count = scan_markdown_links(root)
            self.assertEqual(count, 1)
            self.assertEqual(len(findings), 0)

            # Test CLI clean
            code = main(["--root", str(root), "--check", "--quiet"])
            self.assertEqual(code, 0)

            # Add broken link
            bad_doc = root / "bad.md"
            bad_doc.write_text("[bad link](nowhere.md)\n", encoding="utf-8")
            code_fail = main(["--root", str(root), "--check", "--quiet"])
            self.assertEqual(code_fail, 1)


if __name__ == "__main__":
    unittest.main()

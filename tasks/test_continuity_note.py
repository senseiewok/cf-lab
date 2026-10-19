#!/usr/bin/env python3
"""Unit tests for continuity note and governance documentation (T-0129)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_CONTINUITY = REPO_ROOT / "docs" / "continuity-and-governance.md"


def find_private_continuity() -> Path | None:
    candidates = [
        REPO_ROOT.parent / "cf-lab-files" / "continuity-note.md",
        REPO_ROOT.parent.parent.parent / "cf-lab-files" / "continuity-note.md",
        Path("C:/senseiewok/repos/cf-lab-files/continuity-note.md"),
    ]
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            pass
    return None

REQUIRED_TOPICS = {
    "deploy_path": [r"deploy", r"workflow", r"\.github/workflows/deploy\.yml"],
    "stopping_deployment": [r"(?:disable|cancel|halt|stop).*(?:workflow|deploy)", r"gh workflow disable"],
    "emergency_takedown": [r"takedown|maintenance", r"503", r"maintenance\.html"],
    "credential_rotation": [r"rotat", r"credential|secret", r"DEPLOY_PASSWORD"],
    "accounts": [r"account", r"GitHub", r"hosting|domain|DNS"],
    "visitor_communications": [r"visitor|communication", r"medical advice|boundary", r"urgent|emergency"],
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    re.compile(r"(?:https?|ftps?)://[^/\s:@]+:[^/\s:@]+@[^/\s]+"),
    re.compile(r"\b(?:password|passwd|secret)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]", re.IGNORECASE),
]

IPV4_PATTERN = re.compile(r"\b(?!127\.0\.0\.1|0\.0\.0\.0)(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b")


def check_continuity_content(text: str, filename: str) -> list[str]:
    errors: list[str] = []
    
    # 1. Verify coverage of all 6 required domains
    for topic, patterns in REQUIRED_TOPICS.items():
        for pat in patterns:
            if not re.search(pat, text, re.IGNORECASE):
                errors.append(f"{filename}: Missing topic pattern '{pat}' for domain '{topic}'")

    # 2. Verify zero secrets or private credentials
    for sec_pat in SECRET_PATTERNS:
        matches = sec_pat.findall(text)
        if matches:
            errors.append(f"{filename}: Potential leaked secret pattern matched: {sec_pat.pattern}")

    # 3. Verify zero public/private external IP addresses
    ip_matches = IPV4_PATTERN.findall(text)
    if ip_matches:
        errors.append(f"{filename}: Leaked host IP address found: {ip_matches}")

    return errors


class TestContinuityNote(unittest.TestCase):
    def test_repo_continuity_governance_doc(self) -> None:
        self.assertTrue(DOCS_CONTINUITY.is_file(), f"Missing doc: {DOCS_CONTINUITY}")
        text = DOCS_CONTINUITY.read_text(encoding="utf-8")
        self.assertGreater(len(text), 500, "Document too short")
        errors = check_continuity_content(text, "docs/continuity-and-governance.md")
        self.assertEqual(errors, [], "\n".join(errors))

    def test_private_lab_continuity_note_if_present(self) -> None:
        private_note = find_private_continuity()
        if private_note is None or not private_note.is_file():
            self.skipTest("Private continuity note not present in workspace")
        text = private_note.read_text(encoding="utf-8")
        self.assertGreater(len(text), 500, "Private document too short")
        errors = check_continuity_content(text, str(private_note))
        self.assertEqual(errors, [], "\n".join(errors))


if __name__ == "__main__":
    unittest.main()

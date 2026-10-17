#!/usr/bin/env python3
"""Unit tests for tasks/check_third_party_skills.py (T-0116)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from check_third_party_skills import (
    DEFAULT_DOC,
    check_third_party_skills,
    hash_skill_dir,
    parse_pinned_hashes,
)


class TestCheckThirdPartySkills(unittest.TestCase):
    def test_real_third_party_skills_doc_parses_and_passes(self) -> None:
        pins = parse_pinned_hashes(DEFAULT_DOC)
        self.assertEqual(
            set(pins.keys()),
            {"frontend-design", "skill-creator", "algorithmic-art", "theme-factory"},
        )
        code, msgs = check_third_party_skills(doc_path=DEFAULT_DOC)
        self.assertEqual(code, 0, "\n".join(msgs))

    def test_matching_and_mutated_skill_folder_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / "skills"
            s1 = skills_dir / "alpha-skill"
            s1.mkdir(parents=True)
            (s1 / "SKILL.md").write_text("---\nname: alpha-skill\n---\nHello\n", encoding="utf-8")
            (s1 / "LICENSE.txt").write_bytes(b"Apache-2.0\r\n")
            sha1 = hash_skill_dir(s1)

            # Verify CRLF vs LF normalisation produces identical hash
            (s1 / "LICENSE.txt").write_bytes(b"Apache-2.0\n")
            self.assertEqual(hash_skill_dir(s1), sha1)

            doc = root / "THIRD_PARTY_SKILLS.md"
            doc.write_text(
                "| Skill | Source | Folder SHA-256 | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| `alpha-skill` | source | `{sha1}` | note |\n"
                f"| `missing-skill` | source | `{'a' * 64}` | note |\n",
                encoding="utf-8",
            )

            # Passes when alpha-skill matches and missing-skill is optional
            code, msgs = check_third_party_skills(doc_path=doc, skills_dir=skills_dir)
            self.assertEqual(code, 0, "\n".join(msgs))
            self.assertTrue(any("PASS alpha-skill" in m for m in msgs))
            self.assertTrue(any("SKIP missing-skill" in m for m in msgs))

            # Fails when --require-installed is set and missing-skill is absent
            code_req, msgs_req = check_third_party_skills(
                doc_path=doc, skills_dir=skills_dir, require_installed=True
            )
            self.assertEqual(code_req, 1)
            self.assertTrue(any("FAIL missing-skill" in m for m in msgs_req))

            # Positive control: mutating a file inside alpha-skill MUST fail with exit 1
            (s1 / "SKILL.md").write_text("---\nname: alpha-skill\n---\nTampered\n", encoding="utf-8")
            code_bad, msgs_bad = check_third_party_skills(doc_path=doc, skills_dir=skills_dir)
            self.assertEqual(code_bad, 1, "\n".join(msgs_bad))
            self.assertTrue(any("FAIL alpha-skill: hash mismatch" in m for m in msgs_bad))

    def test_malformed_or_missing_doc_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            code, _ = check_third_party_skills(doc_path=root / "nope.md", skills_dir=root)
            self.assertEqual(code, 2)

            empty_doc = root / "THIRD_PARTY_SKILLS.md"
            empty_doc.write_text("# No hashes here\n", encoding="utf-8")
            code2, _ = check_third_party_skills(doc_path=empty_doc, skills_dir=root)
            self.assertEqual(code2, 2)


if __name__ == "__main__":
    unittest.main()

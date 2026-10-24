#!/usr/bin/env python3
"""Unit tests for tasks/check_scite_mcp_admission.py (T-0047, Rule 12, and AH-6)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from check_scite_mcp_admission import (
    DEFAULT_AGENTS,
    DEFAULT_CHALLENGER,
    DEFAULT_CONTEXT_SKILL,
    DEFAULT_COUNCIL_SKILL,
    DEFAULT_DOC,
    check_scite_mcp_admission,
)


class TestCheckSciteMcpAdmission(unittest.TestCase):
    def test_real_repo_passes(self) -> None:
        code, msgs = check_scite_mcp_admission()
        self.assertEqual(code, 0, "\n".join(msgs))

    def test_positive_controls_fail_when_invariants_removed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "scite.md"
            agents = root / "AGENTS.md"
            council = root / "council.md"
            context = root / "context.md"
            challenger = root / "challenger.md"

            doc_text = DEFAULT_DOC.read_text(encoding="utf-8")
            agents_text = DEFAULT_AGENTS.read_text(encoding="utf-8")
            council_text = DEFAULT_COUNCIL_SKILL.read_text(encoding="utf-8")
            context_text = DEFAULT_CONTEXT_SKILL.read_text(encoding="utf-8")
            challenger_text = DEFAULT_CHALLENGER.read_text(encoding="utf-8")

            doc.write_text(doc_text, encoding="utf-8")
            agents.write_text(agents_text, encoding="utf-8")
            council.write_text(council_text, encoding="utf-8")
            context.write_text(context_text, encoding="utf-8")
            challenger.write_text(challenger_text, encoding="utf-8")

            # Baseline passes
            code0, msgs0 = check_scite_mcp_admission(doc, agents, council, context, challenger)
            self.assertEqual(code0, 0, "\n".join(msgs0))

            # Positive control 1: removing manage_subscription from blocked tools fails
            doc.write_text(doc_text.replace("manage_subscription", "other_tool"), encoding="utf-8")
            code1, msgs1 = check_scite_mcp_admission(doc, agents, council, context, challenger)
            self.assertEqual(code1, 1, "\n".join(msgs1))
            doc.write_text(doc_text, encoding="utf-8")

            # Positive control 2: removing Rule 12 native subagent spawning fails
            council.write_text(council_text.replace("Native Subagent Spawning", "Removed"), encoding="utf-8")
            code2, msgs2 = check_scite_mcp_admission(doc, agents, council, context, challenger)
            self.assertEqual(code2, 1, "\n".join(msgs2))
            council.write_text(council_text, encoding="utf-8")

            # Positive control 3: removing Assay Context Conflation Guard fails
            context.write_text(context_text.replace("Assay Context Conflation Guard", "Removed"), encoding="utf-8")
            code3, msgs3 = check_scite_mcp_admission(doc, agents, council, context, challenger)
            self.assertEqual(code3, 1, "\n".join(msgs3))


if __name__ == "__main__":
    unittest.main()

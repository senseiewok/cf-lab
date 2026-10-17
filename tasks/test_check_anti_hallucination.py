#!/usr/bin/env python3
"""Unit tests for tasks/check_anti_hallucination.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_anti_hallucination as cah


class TestCheckAntiHallucination(unittest.TestCase):
    def test_live_repository_passes(self) -> None:
        """The real cf-lab repository must pass all LAB-AH-1..LAB-AH-4 checks."""
        errors = cah.run_all_checks(cah.ROOT_DIR)
        self.assertEqual(errors, [], f"Unexpected anti-hallucination errors: {errors}")

    def test_detects_unknown_task_id_in_human_tasks(self) -> None:
        """LAB-AH-1: A hallucinated T-9999 in HUMAN-TASKS.md is caught."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tasks").mkdir()
            (root / "tasks" / "HUMAN-TASKS.md").write_text(
                "Please review T-0001 and T-9999.\n", encoding="utf-8"
            )
            (root / "tasks" / "sentinels.json").write_text("{}", encoding="utf-8")
            errors = cah.check_task_id_provenance(root, {"T-0001"})
            self.assertEqual(len(errors), 1)
            self.assertIn("LAB-AH-1", errors[0])
            self.assertIn("T-9999", errors[0])

    def test_detects_hallucinated_nct_and_missing_proposal_on_board(self) -> None:
        """LAB-AH-2: A phantom NCT ID or missing cf-research proposal on the board is caught."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cf_res = root / "cf-research"
            (cf_res / "proposals").mkdir(parents=True)
            (cf_res / "proposals" / "real-proposal.md").write_text("# Real\n", encoding="utf-8")

            tasks = [
                {
                    "id": "T-0500",
                    "status": "ready",
                    "title": "Grounded task",
                    "summary": "Uses NCT03525444",
                    "source_evidence": ["proposals/real-proposal.md"],
                },
                {
                    "id": "T-0501",
                    "status": "ready",
                    "title": "Unanchored task",
                    "summary": "Cites NCT99999999 from memory",
                    "source_evidence": ["proposals/ghost-proposal.md"],
                },
            ]
            errors = cah.check_board_identifier_grounding(
                root, tasks, cf_res, {"NCT03525444"}
            )
            self.assertEqual(len(errors), 2)
            self.assertTrue(any("NCT99999999" in e for e in errors))
            self.assertTrue(any("proposals/ghost-proposal.md" in e for e in errors))

    def test_detects_missing_skill_in_agents_md(self) -> None:
        """LAB-AH-3: A phantom skill listed under ## Skills in AGENTS.md is caught."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude" / "skills" / "real-skill").mkdir(parents=True)
            (root / ".claude" / "skills" / "real-skill" / "SKILL.md").write_text(
                "---\nname: real-skill\n---\n", encoding="utf-8"
            )
            (root / "AGENTS.md").write_text(
                "# AGENTS\n\n## Skills\n\n- `real-skill` — exists\n- `phantom-skill` — does not exist\n\n## Task board\n",
                encoding="utf-8",
            )
            errors = cah.check_agents_skill_catalog(root, None, None)
            self.assertEqual(len(errors), 1)
            self.assertIn("LAB-AH-3", errors[0])
            self.assertIn("phantom-skill", errors[0])

    def test_detects_sentinel_prompt_missing_anti_hallucination_rule(self) -> None:
        """LAB-AH-4: A sentinel prompt lacking explicit anti-hallucination rules is caught."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tasks" / "sentinel-prompts").mkdir(parents=True)
            (root / "tasks" / "sentinel-prompts" / "weak.md").write_text(
                "# weak prompt\nJust run things without rules.\n", encoding="utf-8"
            )
            (root / "tasks" / "sentinels.json").write_text(
                json.dumps(
                    {
                        "sentinels": {
                            "weak-sentinel": {
                                "prompt_file": "tasks/sentinel-prompts/weak.md"
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            errors = cah.check_sentinel_prompts(root)
            self.assertTrue(any("LAB-AH-4" in e and "Anti-hallucination" in e for e in errors))


if __name__ == "__main__":
    unittest.main()

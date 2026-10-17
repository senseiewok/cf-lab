#!/usr/bin/env python3
"""Unit tests for tasks/check_biomcp_admission.py (T-0042 & T-0071)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from check_biomcp_admission import DEFAULT_BOARD, DEFAULT_DOC, check_biomcp_admission


class TestCheckBiomcpAdmission(unittest.TestCase):
    def test_real_doc_passes_once_board_updated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            board_copy = Path(td) / "board.json"
            data = json.loads(DEFAULT_BOARD.read_text(encoding="utf-8"))
            for t in data.get("tasks", []):
                if t.get("id") == "T-0042":
                    t["acceptance"] = (
                        t["acceptance"]
                        + " The wrapper's ClinGen and gnomAD tools are blocked until the catalog entries change, and the wrapper's own requests must follow NETWORK-RULES R1-R9."
                    )
            board_copy.write_text(json.dumps(data), encoding="utf-8")
            code, msgs = check_biomcp_admission(doc_path=DEFAULT_DOC, board_path=board_copy)
            self.assertEqual(code, 0, "\n".join(msgs))

    def test_positive_controls_fail_when_rules_or_blocks_removed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "biomcp.md"
            board = root / "board.json"

            # Write valid baseline
            doc_text = DEFAULT_DOC.read_text(encoding="utf-8")
            doc.write_text(doc_text, encoding="utf-8")
            board_data = {
                "tasks": [
                    {
                        "id": "T-0042",
                        "acceptance": "ClinGen and gnomAD tools are blocked until the catalog entries change; wrapper requests follow NETWORK-RULES R1-R9.",
                    }
                ]
            }
            board.write_text(json.dumps(board_data), encoding="utf-8")

            code, msgs = check_biomcp_admission(doc_path=doc, board_path=board)
            self.assertEqual(code, 0, "\n".join(msgs))

            # Positive control 1: removing R7 row from doc fails
            doc.write_text(doc_text.replace("| **R7** |", "| **RX** |"), encoding="utf-8")
            code_r7, msgs_r7 = check_biomcp_admission(doc_path=doc, board_path=board)
            self.assertEqual(code_r7, 1, "\n".join(msgs_r7))

            # Positive control 2: removing ClinGen/gnomAD block from T-0042 acceptance fails
            doc.write_text(doc_text, encoding="utf-8")
            board_data["tasks"][0]["acceptance"] = "No mention of catalog conflicts."
            board.write_text(json.dumps(board_data), encoding="utf-8")
            code_t71, msgs_t71 = check_biomcp_admission(doc_path=doc, board_path=board)
            self.assertEqual(code_t71, 1, "\n".join(msgs_t71))


if __name__ == "__main__":
    unittest.main()

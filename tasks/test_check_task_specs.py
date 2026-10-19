#!/usr/bin/env python3
"""Tests for tasks/check_task_specs.py."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TASKS_DIR = Path(__file__).resolve().parent
if str(TASKS_DIR) not in sys.path:
    sys.path.insert(0, str(TASKS_DIR))

try:
    from tasks.check_task_specs import (
        check_all_specs,
        verify_spec_content,
        main,
    )
except ImportError:
    from check_task_specs import (
        check_all_specs,
        verify_spec_content,
        main,
    )


class TestCheckTaskSpecs(unittest.TestCase):
    def test_verify_spec_content_valid(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(
                "# T-0999 Test Specification\n\n"
                "## Primary Evidence Grounding\n"
                "Grounding citations: DOI 10.1038/s41587-020-0453-z, NCT06237335, and PDB 6MSM.\n\n"
                "## Verification\n"
                "Run `python test_sample.py` to verify acceptance.\n"
            )
            temp_path = Path(f.name)
        try:
            ok, errors = verify_spec_content(temp_path)
            self.assertTrue(ok)
            self.assertEqual(len(errors), 0)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_verify_spec_content_missing_anchor(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(
                "# T-0999 Test Specification\n\n"
                "No primary literature anchor or identifier here.\n\n"
                "Run `pytest` to verify acceptance criteria.\n"
            )
            temp_path = Path(f.name)
        try:
            ok, errors = verify_spec_content(temp_path)
            self.assertFalse(ok)
            self.assertTrue(any("missing verifiable primary-source anchor" in e for e in errors))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_verify_spec_content_missing_command(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(
                "# T-0999 Test Specification\n\n"
                "DOI 10.1038/s41587-020-0453-z is cited here.\n\n"
                "However, no verification command is included in this document at all.\n"
            )
            temp_path = Path(f.name)
        try:
            ok, errors = verify_spec_content(temp_path)
            self.assertFalse(ok)
            self.assertTrue(any("missing deterministic verification command" in e for e in errors))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_check_all_specs_integration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            specs_dir = base / "tasks" / "specs"
            specs_dir.mkdir(parents=True)
            spec_file = specs_dir / "T-0999.md"
            spec_file.write_text(
                "# T-0999 Specification\n\n"
                "Grounding: DOI 10.1038/s41587-020-0453-z, NCT06237335.\n\n"
                "Verification: `python tasks/test_sample.py`\n",
                encoding="utf-8",
            )

            board_file = base / "tasks" / "board.json"
            board_data = {
                "tasks": [
                    {
                        "id": "T-0999",
                        "title": "Sample Spec Task",
                        "spec_path": "tasks/specs/T-0999.md",
                    }
                ]
            }
            board_file.write_text(json.dumps(board_data), encoding="utf-8")

            passed, results = check_all_specs(board_path=board_file, specs_dir=specs_dir, repo_root=base)
            self.assertTrue(passed)
            self.assertEqual(results["board_tasks_with_spec"], 1)
            self.assertEqual(results["disk_specs_count"], 1)

    def test_cli_invocation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            specs_dir = base / "tasks" / "specs"
            specs_dir.mkdir(parents=True)
            board_file = base / "tasks" / "board.json"
            board_file.write_text(json.dumps({"tasks": []}), encoding="utf-8")

            ret = main(["--board", str(board_file), "--specs-dir", str(specs_dir), "--json"])
            self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()

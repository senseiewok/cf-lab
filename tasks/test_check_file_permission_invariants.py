#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo File Permission & Executable Bit Invariant Linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_file_permission_invariants import (  # noqa: E402
    REPO_ROOT,
    audit_git_index_modes,
    parse_git_ls_files,
    run_full_file_permission_linter,
)


class TestCheckFilePermissionInvariants(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_repo_root_file_permission_linter_pass(self) -> None:
        report = run_full_file_permission_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertGreater(report["metadata"]["total_files_audited"], 100)
        self.assertGreater(report["metadata"]["total_non_executable_data_files"], 50)

    def test_parse_git_ls_files(self) -> None:
        raw_output = (
            "100644 d28ca8a27a4a6ca2126bc06f9dcbc115f787587a 0\tREADME.md\n"
            "100755 5b85a3c3d84e4c340c657d782958334c378ea5f0 0\tsetup.sh\n"
            "120000 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 0\tlink_to_file\n"
        )
        entries = parse_git_ls_files(raw_output)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["mode"], "100644")
        self.assertEqual(entries[0]["path"], "README.md")
        self.assertEqual(entries[1]["mode"], "100755")
        self.assertEqual(entries[1]["path"], "setup.sh")
        self.assertEqual(entries[2]["mode"], "120000")
        self.assertEqual(entries[2]["path"], "link_to_file")

    def test_detect_invalid_git_mode(self) -> None:
        raw = "100777 abcdef1234567890abcdef1234567890abcdef12 0\tbad_mode.py\n"
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = raw
            mock_run.return_value = mock_proc

            errors, warnings, meta = audit_git_index_modes("test_repo", self.root)
            self.assertEqual(len(errors), 1)
            self.assertIn("Invalid git file mode '100777'", errors[0])

    def test_detect_executable_data_file(self) -> None:
        raw = (
            "100755 abcdef1234567890abcdef1234567890abcdef12 0\tdata/catalog.json\n"
            "100755 abcdef1234567890abcdef1234567890abcdef12 0\tdocs/guide.md\n"
            "100755 abcdef1234567890abcdef1234567890abcdef12 0\tassets/logo.svg\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = raw
            mock_run.return_value = mock_proc

            errors, warnings, meta = audit_git_index_modes("test_repo", self.root)
            self.assertEqual(len(errors), 3)
            self.assertTrue(all("Strict non-executable invariant violation" in e for e in errors))

    def test_allow_executable_script_with_shebang(self) -> None:
        script = self.root / "run_worker.py"
        script.write_text("#!/usr/bin/env python3\nprint('hello')\n", encoding="utf-8")
        raw = f"100755 abcdef1234567890abcdef1234567890abcdef12 0\trun_worker.py\n"

        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = raw
            mock_run.return_value = mock_proc

            errors, warnings, meta = audit_git_index_modes("test_repo", self.root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertIn("run_worker.py", meta["executable_files"])

    def test_warn_executable_script_without_shebang(self) -> None:
        script = self.root / "no_shebang.py"
        script.write_text("print('no shebang')\n", encoding="utf-8")
        raw = f"100755 abcdef1234567890abcdef1234567890abcdef12 0\tno_shebang.py\n"

        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = raw
            mock_run.return_value = mock_proc

            errors, warnings, meta = audit_git_index_modes("test_repo", self.root)
            self.assertEqual(errors, [])
            self.assertEqual(len(warnings), 1)
            self.assertIn("lacks a shebang line", warnings[0])


if __name__ == "__main__":
    unittest.main()

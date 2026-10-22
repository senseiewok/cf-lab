#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo Playwright Test Artifact & Server Port Hygiene Linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_playwright_test_hygiene import (  # noqa: E402
    audit_browser_cache_provenance,
    audit_artifact_gitignore_quarantine,
    audit_local_server_binding_hygiene,
    run_full_playwright_hygiene_linter,
    REPO_ROOT,
)


class TestCheckPlaywrightTestHygiene(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_browser_cache_provenance_pass(self) -> None:
        errors, warnings, meta = audit_browser_cache_provenance(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertTrue(meta["setup_script_present"])
        self.assertIsNotNone(meta["pinned_version"])

    def test_browser_cache_provenance_missing_version(self) -> None:
        script_dir = (
            self.root
            / ".claude"
            / "skills"
            / "playwright-browser-testing"
            / "scripts"
        )
        script_dir.mkdir(parents=True)
        setup_script = script_dir / "setup-browser-testing.py"
        setup_script.write_text("# missing PLAYWRIGHT_VERSION\nLOCALAPPDATA = 'foo'\n", encoding="utf-8")

        errors, _, meta = audit_browser_cache_provenance(self.root)
        self.assertTrue(meta["setup_script_present"])
        self.assertTrue(any("missing pinned PLAYWRIGHT_VERSION" in e for e in errors))

    def test_browser_cache_provenance_in_repo_install(self) -> None:
        script_dir = (
            self.root
            / ".claude"
            / "skills"
            / "playwright-browser-testing"
            / "scripts"
        )
        script_dir.mkdir(parents=True)
        setup_script = script_dir / "setup-browser-testing.py"
        setup_script.write_text(
            'PLAYWRIGHT_VERSION = "1.63.0"\ndefault_venv = REPO_ROOT / "venv"\nLOCALAPPDATA = "foo"\n',
            encoding="utf-8",
        )

        errors, _, _ = audit_browser_cache_provenance(self.root)
        self.assertTrue(any("installs venv inside workspace repo" in e for e in errors))

    def test_artifact_quarantine_clean(self) -> None:
        errors, warnings, meta = audit_artifact_gitignore_quarantine(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(meta["tracked_artifact_leaks"], 0)

    def test_server_binding_hygiene_clean(self) -> None:
        errors, warnings, meta = audit_local_server_binding_hygiene(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_server_binding_insecure_0000(self) -> None:
        tools_dir = self.root / "tools"
        tools_dir.mkdir(parents=True)
        server_script = tools_dir / "preview_server.py"
        server_script.write_text("import http.server\nhost = '0.0.0.0'\n", encoding="utf-8")

        errors, _, _ = audit_local_server_binding_hygiene(self.root)
        self.assertTrue(any("Insecure 0.0.0.0 public interface binding" in e for e in errors))

    def test_run_full_playwright_hygiene_linter(self) -> None:
        report = run_full_playwright_hygiene_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertIn("timestamp", report)


if __name__ == "__main__":
    unittest.main()

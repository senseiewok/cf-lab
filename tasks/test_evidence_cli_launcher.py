#!/usr/bin/env python3
"""Unit tests for scripts/evidence_cli.py launcher (T-0051)."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPO_ROOT / "scripts" / "evidence_cli.py"


class TestEvidenceCliLauncher(unittest.TestCase):
    def test_launcher_exists(self) -> None:
        self.assertTrue(LAUNCHER.is_file(), f"Missing {LAUNCHER}")

    def test_sources_subcommand_runs_offline(self) -> None:
        env = dict(os.environ)
        env["EVIDENCE_DRY_RUN"] = "1"
        proc = subprocess.run(
            [sys.executable, str(LAUNCHER), "sources"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ncbi-eutils", proc.stdout)
        self.assertIn("crossref", proc.stdout)

    def test_retractions_dry_run_plans_crossref_lookup(self) -> None:
        env = dict(os.environ)
        env["EVIDENCE_DRY_RUN"] = "1"
        proc = subprocess.run(
            [sys.executable, str(LAUNCHER), "retractions", "10.1016/S0140-6736(97)11096-0"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("S0140-6736", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()

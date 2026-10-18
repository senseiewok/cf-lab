#!/usr/bin/env python3
"""Unit tests for scripts/evidence_cli.py launcher (T-0051)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPO_ROOT / "scripts" / "evidence_cli.py"


def _find_real_cf_skills() -> Path | None:
    for base in (REPO_ROOT.parent, REPO_ROOT.parent.parent, REPO_ROOT.parent.parent.parent):
        cand = base / "cf-skills"
        if (cand / ".claude" / "skills" / "cf-evidence-loop" / "scripts" / "evidence" / "cli.py").is_file():
            return cand
    return None


class TestEvidenceCliLauncher(unittest.TestCase):
    _stub_root: Path | None = None

    @classmethod
    def setUpClass(cls) -> None:
        if _find_real_cf_skills() is None:
            tmp = Path(tempfile.mkdtemp(prefix="cf-skills-stub-"))
            cls._stub_root = tmp
            ev_dir = tmp / ".claude" / "skills" / "cf-evidence-loop" / "scripts" / "evidence"
            ev_dir.mkdir(parents=True, exist_ok=True)
            (ev_dir / "__init__.py").write_text("", encoding="utf-8")
            (ev_dir / "cli.py").write_text(
                "import os, sys\n"
                "from pathlib import Path\n"
                "def main(argv=None):\n"
                "    args = list(sys.argv[1:] if argv is None else argv)\n"
                "    cat = Path(os.environ['EVIDENCE_CATALOG']).read_text(encoding='utf-8')\n"
                "    if args and args[0] == 'sources':\n"
                "        print(cat)\n"
                "        return 0\n"
                "    if args and args[0] == 'retractions':\n"
                "        print('dry-run crossref retractions lookup:', ' '.join(args[1:]))\n"
                "        return 0\n"
                "    return 1\n",
                encoding="utf-8",
            )

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._stub_root and cls._stub_root.exists():
            shutil.rmtree(cls._stub_root, ignore_errors=True)

    def _base_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["EVIDENCE_DRY_RUN"] = "1"
        if self._stub_root is not None:
            env["CF_SKILLS_ROOT"] = str(self._stub_root)
        return env

    def test_launcher_exists(self) -> None:
        self.assertTrue(LAUNCHER.is_file(), f"Missing {LAUNCHER}")

    def test_missing_cf_skills_fails_closed(self) -> None:
        env = dict(os.environ)
        env["CF_SKILLS_ROOT"] = str(REPO_ROOT / "nonexistent-cf-skills-dir")
        proc = subprocess.run(
            [sys.executable, str(LAUNCHER), "sources"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cf-skills not found", proc.stderr)

    def test_sources_subcommand_runs_offline(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(LAUNCHER), "sources"],
            cwd=str(REPO_ROOT),
            env=self._base_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ncbi-eutils", proc.stdout)
        self.assertIn("crossref", proc.stdout)

    def test_retractions_dry_run_plans_crossref_lookup(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(LAUNCHER), "retractions", "10.1016/S0140-6736(97)11096-0"],
            cwd=str(REPO_ROOT),
            env=self._base_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("S0140-6736", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()

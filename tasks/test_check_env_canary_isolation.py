#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Agent Environment Variable (.env) & Canary Isolation Linter."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_env_canary_isolation import (  # noqa: E402
    calculate_shannon_entropy,
    load_privacy_canaries,
    parse_env_file,
    audit_gitignore_invariants,
    audit_template_parity,
    audit_canary_and_entropy_isolation,
    run_full_env_canary_linter,
    REPO_ROOT,
    PRIVACY_PATTERNS_PATH,
)


class TestCheckEnvCanaryIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_shannon_entropy_calculation(self) -> None:
        self.assertEqual(calculate_shannon_entropy(""), 0.0)
        self.assertEqual(calculate_shannon_entropy("aaaaaa"), 0.0)
        # Random key should have entropy > 3.0
        rand_key = "d8f9a2c4e1b7f0e3a5c8d2e1b4f7a0"
        self.assertGreater(calculate_shannon_entropy(rand_key), 3.0)

    def test_load_privacy_canaries(self) -> None:
        canaries = load_privacy_canaries(PRIVACY_PATTERNS_PATH)
        self.assertGreater(len(canaries), 5)
        # Verify canaries are parsed into structured dicts with non-empty string values
        for c in canaries:
            self.assertIn("category", c)
            self.assertIn("pattern", c)
            self.assertIn("canary", c)
            self.assertGreater(len(c["canary"]), 0)

    def test_parse_env_file(self) -> None:
        env_file = self.root / ".env"
        env_file.write_text(
            "# Comment line\n"
            "FOO=bar\n"
            'QUOTED="quoted_val"\n'
            "SPACED = spaced_val \n"
            "\n"
            "EMPTY=\n",
            encoding="utf-8",
        )
        parsed = parse_env_file(env_file)
        self.assertEqual(parsed.get("FOO"), "bar")
        self.assertEqual(parsed.get("QUOTED"), "quoted_val")
        self.assertEqual(parsed.get("SPACED"), "spaced_val")
        self.assertEqual(parsed.get("EMPTY"), "")

    def test_gitignore_invariants_pass(self) -> None:
        errors, _ = audit_gitignore_invariants(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_gitignore_invariants_missing_rule(self) -> None:
        repo_dir = self.root / "fake-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / ".gitignore").write_text("node_modules/\n*.log\n", encoding="utf-8")
        content = (repo_dir / ".gitignore").read_text()
        has_env = ".env" in content.splitlines()
        self.assertFalse(has_env)

    def test_template_parity_clean(self) -> None:
        errors, warnings, meta = audit_template_parity(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertIn("example_var_count", meta)
        self.assertGreaterEqual(meta["example_var_count"], 1)

    def test_template_parity_undocumented_key(self) -> None:
        (self.root / ".env.example").write_text(
            "UNDOCUMENTED_SECRET_VAR_XYZ=your_key_here\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("# Project\nNo secrets here.\n", encoding="utf-8")
        errors, warnings, _ = audit_template_parity(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("UNDOCUMENTED_SECRET_VAR_XYZ" in w for w in warnings))

    def test_template_parity_high_entropy_secret(self) -> None:
        (self.root / ".env.example").write_text(
            "LEAKED_KEY=" + "high_entropy_secret_token_1234567890abcdef\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("LEAKED_KEY docs\n", encoding="utf-8")
        errors, _, _ = audit_template_parity(self.root)
        self.assertTrue(any("Possible real credential" in e for e in errors))

    def test_canary_collision_detected(self) -> None:
        # Load a canary from patterns and inject it into mock .env
        canaries = load_privacy_canaries(PRIVACY_PATTERNS_PATH)
        target_canary = canaries[0]["canary"]
        env_file = self.root / ".env"
        env_file.write_text(f"TEST_API_KEY={target_canary}\n", encoding="utf-8")
        errors, _, meta = audit_canary_and_entropy_isolation(self.root, custom_env_path=env_file)
        self.assertTrue(any("matches test canary" in e for e in errors))

    def test_entropy_auditing_low_entropy(self) -> None:
        env_file = self.root / ".env"
        env_file.write_text("MY_SECRET_KEY=11111111111111111111\n", encoding="utf-8")
        _, warnings, _ = audit_canary_and_entropy_isolation(self.root, custom_env_path=env_file)
        self.assertTrue(any("Low Shannon entropy" in w for w in warnings))

    def test_entropy_auditing_short_key(self) -> None:
        env_file = self.root / ".env"
        env_file.write_text("MY_SECRET_KEY=short\n", encoding="utf-8")
        errors, _, _ = audit_canary_and_entropy_isolation(self.root, custom_env_path=env_file)
        self.assertTrue(any("Suspiciously short" in e for e in errors))

    def test_missing_env_handled_gracefully(self) -> None:
        non_existent = self.root / ".env"
        errors, warnings, meta = audit_canary_and_entropy_isolation(
            self.root, custom_env_path=non_existent
        )
        self.assertEqual(errors, [])
        self.assertFalse(meta["env_file_present"])

    def test_run_full_env_canary_linter(self) -> None:
        report = run_full_env_canary_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertIn("timestamp", report)


if __name__ == "__main__":
    unittest.main()

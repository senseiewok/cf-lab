#!/usr/bin/env python3
"""Unit tests for Automated Cross-Repo Agent Tool Permission & Denial Rule Invariant Linter."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_tool_permission_invariants import (  # noqa: E402
    audit_control_settings_denials,
    audit_denial_rule_symmetry,
    audit_workspace_path_containment,
    audit_reviewer_scope_enforcement,
    run_full_tool_permission_linter,
    REPO_ROOT,
    REQUIRED_CORE_SECRET_DENIES,
    REQUIRED_FORCE_PUSH_DENIES,
)


class TestCheckToolPermissionInvariants(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_control_settings_denials_pass(self) -> None:
        errors, warnings, meta = audit_control_settings_denials(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertTrue(meta["bypass_disabled"])
        self.assertGreater(meta["deny_rule_count"], 50)

    def test_missing_control_settings(self) -> None:
        errors, _, _ = audit_control_settings_denials(self.root)
        self.assertTrue(any("Missing control settings file" in e for e in errors))

    def test_bypass_not_disabled(self) -> None:
        claude_dir = self.root / ".claude"
        claude_dir.mkdir(parents=True)
        settings_path = claude_dir / "settings.json"
        settings_path.write_text(
            json.dumps({"permissions": {"disableBypassPermissionsMode": "allow", "deny": []}}),
            encoding="utf-8",
        )
        errors, _, _ = audit_control_settings_denials(self.root)
        self.assertTrue(any("disableBypassPermissionsMode must be explicitly set" in e for e in errors))

    def test_missing_secret_deny_rule(self) -> None:
        claude_dir = self.root / ".claude"
        claude_dir.mkdir(parents=True)
        settings_path = claude_dir / "settings.json"
        settings_path.write_text(
            json.dumps({
                "permissions": {
                    "disableBypassPermissionsMode": "disable",
                    "deny": ["Bash(git push --force*)", "PowerShell(git push --force*)"],
                }
            }),
            encoding="utf-8",
        )
        errors, _, _ = audit_control_settings_denials(self.root)
        self.assertTrue(any("Missing required core secret deny rule: 'Read(.env)'" in e for e in errors))

    def test_missing_force_push_deny_rule(self) -> None:
        claude_dir = self.root / ".claude"
        claude_dir.mkdir(parents=True)
        settings_path = claude_dir / "settings.json"
        settings_path.write_text(
            json.dumps({
                "permissions": {
                    "disableBypassPermissionsMode": "disable",
                    "deny": list(REQUIRED_CORE_SECRET_DENIES),
                }
            }),
            encoding="utf-8",
        )
        errors, _, _ = audit_control_settings_denials(self.root)
        self.assertTrue(any("Missing required force-push deny rule" in e for e in errors))

    def test_denial_rule_symmetry_pass(self) -> None:
        errors, _ = audit_denial_rule_symmetry(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_workspace_path_containment_clean(self) -> None:
        errors, warnings = audit_workspace_path_containment(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_workspace_path_containment_escape(self) -> None:
        claude_dir = self.root / ".claude"
        claude_dir.mkdir(parents=True)
        example_path = claude_dir / "settings.local.json.example"
        example_path.write_text(
            json.dumps({
                "permissions": {
                    "additionalDirectories": [
                        "../../etc/passwd",
                        "C:\\Users\\admin",
                    ]
                }
            }),
            encoding="utf-8",
        )
        errors, warnings = audit_workspace_path_containment(self.root)
        self.assertTrue(any("additionalDirectories entry" in w for w in warnings))

    def test_reviewer_scope_enforcement_clean(self) -> None:
        errors, warnings = audit_reviewer_scope_enforcement(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_reviewer_scope_enforcement_mutation_detected(self) -> None:
        tasks_dir = self.root / "tasks"
        tasks_dir.mkdir(parents=True)
        reviewer_doc = tasks_dir / "agent-reviewer.md"
        reviewer_doc.write_text("Reviewer agent may use write_file to update test notes.", encoding="utf-8")
        errors, _ = audit_reviewer_scope_enforcement(self.root)
        self.assertTrue(any("grants write tools" in e for e in errors))

    def test_run_full_tool_permission_linter(self) -> None:
        report = run_full_tool_permission_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertIn("timestamp", report)


if __name__ == "__main__":
    unittest.main()

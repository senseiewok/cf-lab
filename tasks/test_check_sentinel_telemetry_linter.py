#!/usr/bin/env python3
"""Unit tests for check_sentinel_telemetry_linter.py (T-0302)."""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_sentinel_telemetry_linter import (  # noqa: E402
    ALLOWED_DECISIONS,
    SentinelTelemetryLinter,
    parse_iso_datetime,
    validate_cron_expression,
)


class TestSentinelTelemetryLinter(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.logs_dir = self.root / ".loop-logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir = self.root / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

        self.manifest_path = self.tasks_dir / "sentinels.json"
        self.runs_log = self.logs_dir / "sentinel-runs.jsonl"

        # Create dummy prompt files
        (self.tasks_dir / "prompt-sec.md").write_text("# Security Prompt", encoding="utf-8")

        # Create valid manifest
        self.valid_manifest = {
            "version": 1,
            "sentinels": {
                "daily-security-sentinel": {
                    "cron": "0,30 * * * *",
                    "max_idle_hours": 3,
                    "lock_timeout_minutes": 25,
                    "prompt_file": "tasks/prompt-sec.md",
                    "watermark": ".loop-logs/last-security-audit.json",
                    "watch_paths": ["tasks"],
                }
            },
        }
        self.manifest_path.write_text(json.dumps(self.valid_manifest), encoding="utf-8")

        # Create valid watermark
        self.valid_wm = {
            "timestamp": "2026-10-22T10:00:00Z",
            "sentinel_id": "daily-security-sentinel",
            "tree_hashes": {
                "tasks": "a" * 40,
            },
        }
        (self.logs_dir / "last-security-audit.json").write_text(json.dumps(self.valid_wm), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_iso_datetime(self) -> None:
        d1 = parse_iso_datetime("2026-10-22T10:00:00Z")
        self.assertIsNotNone(d1)
        self.assertEqual(d1.year, 2026)
        self.assertIsNone(parse_iso_datetime("invalid-date"))
        self.assertIsNone(parse_iso_datetime(""))

    def test_validate_cron_expression(self) -> None:
        self.assertTrue(validate_cron_expression("0,30 * * * *"))
        self.assertTrue(validate_cron_expression("*/5 * * * *"))
        self.assertTrue(validate_cron_expression("10 4 * * 1-5"))
        self.assertFalse(validate_cron_expression("every hour"))
        self.assertFalse(validate_cron_expression("0 30 * *"))  # only 4 fields
        self.assertFalse(validate_cron_expression(""))

    def test_audit_manifest_valid(self) -> None:
        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        self.assertEqual(linter.errors, [])
        self.assertIn("daily-security-sentinel", linter.declared_sentinels)

    def test_audit_manifest_invalid_cron(self) -> None:
        self.valid_manifest["sentinels"]["daily-security-sentinel"]["cron"] = "bad cron"
        self.manifest_path.write_text(json.dumps(self.valid_manifest), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        self.assertTrue(any("invalid cron" in e for e in linter.errors))

    def test_audit_manifest_invalid_bounds(self) -> None:
        self.valid_manifest["sentinels"]["daily-security-sentinel"]["max_idle_hours"] = 100
        self.manifest_path.write_text(json.dumps(self.valid_manifest), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        self.assertTrue(any("max_idle_hours" in e for e in linter.errors))

    def test_audit_watermarks_valid(self) -> None:
        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        linter.audit_watermarks()
        self.assertEqual(linter.errors, [])

    def test_audit_watermarks_invalid_hash(self) -> None:
        self.valid_wm["tree_hashes"]["tasks"] = "not-a-40-char-hex"
        (self.logs_dir / "last-security-audit.json").write_text(json.dumps(self.valid_wm), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        linter.audit_watermarks()
        self.assertTrue(any("invalid hex40" in e for e in linter.errors))

    def test_audit_runs_log_valid(self) -> None:
        entries = [
            {"ts": "2026-10-22T10:00:00Z", "sentinel": "daily-security-sentinel", "decision": "idle", "detail": ""},
            {"ts": "2026-10-22T10:30:00Z", "sentinel": "daily-security-sentinel", "decision": "launched", "detail": "run 1"},
            {"ts": "2026-10-22T10:35:00Z", "sentinel": "daily-security-sentinel", "decision": "completed", "detail": "done"},
        ]
        self.runs_log.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        linter.audit_runs_log()
        self.assertEqual(linter.errors, [])

    def test_audit_runs_log_invalid_decision(self) -> None:
        entry = {"ts": "2026-10-22T10:00:00Z", "sentinel": "daily-security-sentinel", "decision": "exploded", "detail": ""}
        self.runs_log.write_text(json.dumps(entry), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        linter.audit_runs_log()
        self.assertTrue(any("Invalid sentinel decision 'exploded'" in e for e in linter.errors))

    def test_audit_runs_log_idle_fatal(self) -> None:
        entry = {"ts": "2026-10-22T10:00:00Z", "sentinel": "daily-security-sentinel", "decision": "idle", "detail": "fatal failure"}
        self.runs_log.write_text(json.dumps(entry), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_manifest()
        linter.audit_runs_log()
        self.assertTrue(any("Idle decision with fatal error detail" in e for e in linter.errors))

    def test_audit_locks_stale(self) -> None:
        old_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).isoformat()
        lock_content = {"held_by": "daily-security-sentinel", "acquired_at": old_time, "pid": 12345}
        (self.logs_dir / "sentinel-daily-security-sentinel.lock").write_text(json.dumps(lock_content), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        linter.audit_locks()
        self.assertTrue(any("Abandoned stale lock file" in w for w in linter.warnings))

    def test_run_all_end_to_end(self) -> None:
        entry = {"ts": "2026-10-22T10:00:00Z", "sentinel": "daily-security-sentinel", "decision": "idle", "detail": ""}
        self.runs_log.write_text(json.dumps(entry), encoding="utf-8")

        linter = SentinelTelemetryLinter(
            repo_root=self.root,
            manifest_path=self.manifest_path,
            logs_dir=self.logs_dir,
            runs_log=self.runs_log,
            verify_git=False,
        )
        report = linter.run_all()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["errors_count"], 0)


if __name__ == "__main__":
    unittest.main()

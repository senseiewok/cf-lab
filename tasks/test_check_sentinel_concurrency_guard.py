#!/usr/bin/env python3
"""Unit tests for Sentinel Concurrency Collision Guard (T-0295)."""
import datetime
import json
import os
import tempfile
import unittest
from pathlib import Path

from tasks.check_sentinel_concurrency_guard import (
    DEFAULT_LOCK_TIMEOUT_MINUTES,
    check_schedule_collisions,
    inspect_lock_file,
    is_pid_alive,
    parse_cron_minutes,
    parse_iso_timestamp,
    prune_stale_sentinel_locks,
    scan_active_sentinel_locks,
)


class TestSentinelConcurrencyGuard(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.loop_logs = self.test_root / ".loop-logs"
        self.loop_logs.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_cron_minutes(self):
        self.assertEqual(parse_cron_minutes("0,30 * * * *"), {0, 30})
        self.assertEqual(parse_cron_minutes("10,40 * * * *"), {10, 40})
        self.assertEqual(parse_cron_minutes("*/20 * * * *"), {0, 20, 40})
        self.assertEqual(parse_cron_minutes("1-3 * * * *"), {1, 2, 3})
        self.assertEqual(len(parse_cron_minutes("* * * * *")), 60)

    def test_check_schedule_collisions(self):
        # Staggered schedules (no collision)
        cfg_staggered = {
            "sentinel-a": {"cron": "0,30 * * * *"},
            "sentinel-b": {"cron": "10,40 * * * *"},
            "sentinel-c": {"cron": "20,50 * * * *"},
        }
        alerts = check_schedule_collisions(cfg_staggered)
        self.assertEqual(len(alerts), 0)

        # Overlapping schedules
        cfg_colliding = {
            "sentinel-a": {"cron": "0,30 * * * *"},
            "sentinel-b": {"cron": "30 * * * *"},
        }
        alerts = check_schedule_collisions(cfg_colliding)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, "SCHEDULE_COLLISION")

    def test_is_pid_alive(self):
        # Current process is alive
        my_pid = os.getpid()
        self.assertTrue(is_pid_alive(my_pid))

        # Negative and zero PID
        self.assertFalse(is_pid_alive(-1))
        self.assertFalse(is_pid_alive(0))

        # Non-existent PID (large number unlikely to exist)
        self.assertFalse(is_pid_alive(99999999))

    def test_inspect_valid_lock(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        lock_file = self.loop_logs / "sentinel-daily-security-sentinel.lock"
        payload = {
            "held_by": "daily-security-sentinel",
            "pid": os.getpid(),
            "ts": now.isoformat(),
        }
        lock_file.write_text(json.dumps(payload), encoding="utf-8")

        sentinels_cfg = {"daily-security-sentinel": {"lock_timeout_minutes": 25}}
        alerts = inspect_lock_file(lock_file, sentinels_cfg, now=now)
        self.assertEqual(len(alerts), 0)

    def test_inspect_stale_lock(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_time = now - datetime.timedelta(minutes=30)
        lock_file = self.loop_logs / "sentinel-daily-research-sentinel.lock"
        payload = {
            "held_by": "daily-research-sentinel",
            "pid": os.getpid(),
            "ts": stale_time.isoformat(),
        }
        lock_file.write_text(json.dumps(payload), encoding="utf-8")

        sentinels_cfg = {"daily-research-sentinel": {"lock_timeout_minutes": 25}}
        alerts = inspect_lock_file(lock_file, sentinels_cfg, now=now)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, "STALE_LOCK")
        self.assertEqual(alerts[0].severity, "ERROR")

    def test_inspect_orphan_lock(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        lock_file = self.loop_logs / "sentinel-daily-site-showcase-sentinel.lock"
        payload = {
            "held_by": "daily-site-showcase-sentinel",
            "pid": 99999999,  # dead PID
            "ts": now.isoformat(),
        }
        lock_file.write_text(json.dumps(payload), encoding="utf-8")

        sentinels_cfg = {"daily-site-showcase-sentinel": {"lock_timeout_minutes": 25}}
        alerts = inspect_lock_file(lock_file, sentinels_cfg, now=now)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, "ORPHAN_LOCK")
        self.assertEqual(alerts[0].severity, "ERROR")

    def test_inspect_corrupt_lock(self):
        lock_file = self.loop_logs / "sentinel-corrupt.lock"
        lock_file.write_text("NOT_VALID_JSON{", encoding="utf-8")

        alerts = inspect_lock_file(lock_file, {})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, "CORRUPT_LOCK")

    def test_concurrent_collision_detection(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        lock_a = self.loop_logs / "sentinel-daily-security-sentinel.lock"
        lock_b = self.loop_logs / "sentinel-daily-research-sentinel.lock"

        payload_a = {"held_by": "daily-security-sentinel", "pid": os.getpid(), "ts": now.isoformat()}
        payload_b = {"held_by": "daily-research-sentinel", "pid": os.getpid(), "ts": now.isoformat()}

        lock_a.write_text(json.dumps(payload_a), encoding="utf-8")
        lock_b.write_text(json.dumps(payload_b), encoding="utf-8")

        sentinels_cfg = {
            "daily-security-sentinel": {"lock_timeout_minutes": 25},
            "daily-research-sentinel": {"lock_timeout_minutes": 25},
        }

        files, alerts = scan_active_sentinel_locks(self.loop_logs, sentinels_cfg, now=now)
        self.assertEqual(len(files), 2)
        collision_alerts = [a for a in alerts if a.alert_type == "CONCURRENT_COLLISION"]
        self.assertEqual(len(collision_alerts), 1)

    def test_prune_stale_locks(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_time = now - datetime.timedelta(minutes=45)
        lock_file = self.loop_logs / "sentinel-stale.lock"
        payload = {"held_by": "stale-sentinel", "pid": os.getpid(), "ts": stale_time.isoformat()}
        lock_file.write_text(json.dumps(payload), encoding="utf-8")

        sentinels_cfg = {"stale-sentinel": {"lock_timeout_minutes": 25}}
        _, alerts = scan_active_sentinel_locks(self.loop_logs, sentinels_cfg, now=now)

        # Dry run does not delete
        pruned_dry = prune_stale_sentinel_locks(alerts, dry_run=True)
        self.assertEqual(len(pruned_dry), 1)
        self.assertTrue(lock_file.exists())

        # Live prune deletes file
        pruned_live = prune_stale_sentinel_locks(alerts, dry_run=False)
        self.assertEqual(len(pruned_live), 1)
        self.assertFalse(lock_file.exists())


if __name__ == "__main__":
    unittest.main()

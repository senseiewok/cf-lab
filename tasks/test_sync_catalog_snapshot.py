#!/usr/bin/env python3
"""Unit tests for tasks/sync_catalog_snapshot.py (T-0140)."""
from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

from sync_catalog_snapshot import check_snapshot, write_snapshot


class TestSyncCatalogSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "catalog.yaml"
        self.src.write_text("sources:\n  - id: pubmed\n    access: api\n", encoding="utf-8")
        self.snap = self.root / "catalog.snapshot.yaml"
        self.sha = "a" * 40
        self.date = "2026-10-17"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_write_and_check_passes(self) -> None:
        rc = write_snapshot(self.snap, source_catalog=self.src, generated_date=self.date, commit_sha=self.sha)
        self.assertEqual(rc, 0)
        text = self.snap.read_text(encoding="utf-8")
        self.assertIn("generated, do not edit", text)
        self.assertIn("senseiewok/cf-research", text)
        self.assertIn(self.sha, text)

        ok, msg = check_snapshot(
            self.snap,
            source_catalog=self.src,
            today=dt.date(2026, 10, 20),
        )
        self.assertTrue(ok, msg)

    def test_one_byte_tamper_fails(self) -> None:
        write_snapshot(self.snap, source_catalog=self.src, generated_date=self.date, commit_sha=self.sha)
        raw = bytearray(self.snap.read_bytes())
        raw[-2] = ord("X") if raw[-2] != ord("X") else ord("Y")
        self.snap.write_bytes(bytes(raw))

        ok, msg = check_snapshot(self.snap, source_catalog=self.src, today=dt.date(2026, 10, 17))
        self.assertFalse(ok)
        self.assertIn("refresh the catalog", msg)

    def test_drift_from_sibling_source_fails(self) -> None:
        write_snapshot(self.snap, source_catalog=self.src, generated_date=self.date, commit_sha=self.sha)
        self.src.write_text("sources:\n  - id: pubmed\n    access: fetch\n", encoding="utf-8")

        ok, msg = check_snapshot(self.snap, source_catalog=self.src, today=dt.date(2026, 10, 17))
        self.assertFalse(ok)
        self.assertIn("differs from", msg)

    def test_stale_snapshot_fails_closed(self) -> None:
        write_snapshot(self.snap, source_catalog=self.src, generated_date="2026-08-01", commit_sha=self.sha)
        ok, msg = check_snapshot(
            self.snap,
            source_catalog=self.src,
            max_age_days=30,
            today=dt.date(2026, 10, 17),
        )
        self.assertFalse(ok)
        self.assertIn("refresh the catalog", msg)


if __name__ == "__main__":
    unittest.main()

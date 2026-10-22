#!/usr/bin/env python3
"""Unit tests for tasks/check_catalog_schema_lock.py (T-0286)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tasks.check_catalog_schema_lock import (
    audit_catalog_schema_lock,
    compute_sha256,
    validate_catalog_schema,
    verify_cryptographic_locks,
)


class TestCheckCatalogSchemaLock(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))
        self.root = Path(self.tmp_dir)

    def test_validate_catalog_schema_valid(self):
        cat_file = self.root / "valid_catalog.yaml"
        cat_content = """schema_version: 1
updated: 2026-10-22
defaults:
  redistribute: false
sources:
  - id: test-source-1
    title: Test Source Title
    publisher: Test Publisher
    kind: registry_annual_report
    access: fetch
    url: https://example.org/report.pdf
    robots: allow
  - id: test-api-source
    title: Test API
    publisher: Test Publisher
    kind: api_endpoint
    access: api
    base_url: https://api.example.org/v1/
    terms_url: https://api.example.org/terms
    robots: allow
"""
        cat_file.write_text(cat_content, encoding="utf-8")
        violations, warnings, data = validate_catalog_schema(cat_file, label="test")
        self.assertEqual(violations, [])
        self.assertEqual(len(data.get("sources", [])), 2)

    def test_validate_catalog_schema_invalid_version(self):
        cat_file = self.root / "bad_ver.yaml"
        cat_file.write_text("schema_version: 2\nupdated: 2026-10-22\nsources:\n  - id: s1\n    title: T\n    publisher: P\n    kind: K\n    access: fetch\n    url: https://example.org/x.pdf\n", encoding="utf-8")
        violations, _, _ = validate_catalog_schema(cat_file, label="test")
        self.assertTrue(any("schema_version must be 1" in v for v in violations))

    def test_validate_catalog_schema_duplicate_ids(self):
        cat_file = self.root / "dupe_ids.yaml"
        cat_content = """schema_version: 1
updated: 2026-10-22
sources:
  - id: dupe-id
    title: First
    publisher: Pub
    kind: K
    access: fetch
    url: https://example.org/1.pdf
  - id: dupe-id
    title: Second
    publisher: Pub
    kind: K
    access: fetch
    url: https://example.org/2.pdf
"""
        cat_file.write_text(cat_content, encoding="utf-8")
        violations, _, _ = validate_catalog_schema(cat_file, label="test")
        self.assertTrue(any("Duplicate source id: 'dupe-id'" in v for v in violations))

    def test_validate_catalog_schema_invalid_access(self):
        cat_file = self.root / "bad_access.yaml"
        cat_file.write_text("""schema_version: 1
updated: 2026-10-22
sources:
  - id: bad-acc
    title: Title
    publisher: Pub
    kind: K
    access: unauthorized_scraping
""", encoding="utf-8")
        violations, _, _ = validate_catalog_schema(cat_file, label="test")
        self.assertTrue(any("invalid access mode" in v for v in violations))

    def test_validate_catalog_schema_api_and_fetch_invariants(self):
        cat_file = self.root / "bad_api_fetch.yaml"
        cat_content = """schema_version: 1
updated: 2026-10-22
sources:
  - id: missing-terms-api
    title: Title
    publisher: Pub
    kind: api_endpoint
    access: api
    base_url: https://api.example.com/
  - id: disallowed-fetch
    title: Title 2
    publisher: Pub
    kind: registry_report
    access: fetch
    url: https://example.com/data.pdf
    robots: disallow
"""
        cat_file.write_text(cat_content, encoding="utf-8")
        violations, _, _ = validate_catalog_schema(cat_file, label="test")
        self.assertTrue(any("must declare 'terms_url'" in v for v in violations))
        self.assertTrue(any("declares robots: disallow" in v for v in violations))

    def test_verify_cryptographic_locks_mismatch(self):
        cat_file = self.root / "catalog.yaml"
        cat_file.write_text("dummy canonical catalog content", encoding="utf-8")

        lock_file = self.root / "catalog.lock.json"
        lock_file.write_text(json.dumps({
            "inputs": {
                "sources/catalog.yaml": "0000000000000000000000000000000000000000000000000000000000000000"
            },
            "copy_sha256": "1111111111111111111111111111111111111111111111111111111111111111"
        }), encoding="utf-8")

        violations, _, _ = verify_cryptographic_locks(cat_file, None, lock_file, None)
        self.assertTrue(any("Lock file input hash mismatch" in v for v in violations))

    def test_verify_cryptographic_locks_valid(self):
        cat_file = self.root / "catalog.yaml"
        raw_canonical = b"schema_version: 1\nupdated: 2026-10-22\nsources: []\n"
        cat_file.write_bytes(raw_canonical)
        c_hash = compute_sha256(raw_canonical)

        skills_file = self.root / "skills_catalog.yaml"
        raw_skills = b"schema_version: 1\nupdated: 2026-10-22\nsources: []\n# copy\n"
        skills_file.write_bytes(raw_skills)
        s_hash = compute_sha256(raw_skills)

        lock_file = self.root / "catalog.lock.json"
        lock_file.write_text(json.dumps({
            "inputs": {
                "sources/catalog.yaml": c_hash
            },
            "copy_sha256": s_hash
        }), encoding="utf-8")

        violations, _, info = verify_cryptographic_locks(cat_file, skills_file, lock_file, None)
        self.assertEqual(violations, [])
        self.assertEqual(info["canonical_hash"], c_hash)
        self.assertEqual(info["skills_hash"], s_hash)

    def test_audit_catalog_schema_lock_live_check(self):
        # Runs against actual repository files
        report = audit_catalog_schema_lock(report_path=self.root / "audit_report.json")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["violations"]), 0)
        self.assertGreater(report["sources_scanned"], 0)


if __name__ == "__main__":
    unittest.main()

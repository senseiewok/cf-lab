#!/usr/bin/env python3
"""Unit tests for tasks/check_restricted_hosts.py."""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

import check_restricted_hosts as crh  # noqa: E402


class TestCheckRestrictedHosts(unittest.TestCase):
    def test_extract_restricted_hosts(self):
        catalog = {
            "sources": [
                {
                    "id": "open-api",
                    "access": "api",
                    "base_url": "https://api.permitted.org/v1",
                    "landing_page": "https://www.permitted.org/about",
                },
                {
                    "id": "manual-report",
                    "access": "manual",
                    "url": "https://manual.restricted.org/download.pdf",
                    "landing_page": "https://manual.restricted.org/reports",
                },
                {
                    "id": "forbidden-db",
                    "access": "forbidden",
                    "landing_page": "https://blocked.source.com/cftr",
                },
                {
                    "id": "request-registry",
                    "access": "request",
                    "url": "https://ictrp.who.int/trials",
                },
                {
                    "id": "shared-domain-permitted",
                    "access": "fetch",
                    "url": "https://shared.domain.com/public.pdf",
                },
                {
                    "id": "shared-domain-restricted",
                    "access": "manual",
                    "url": "https://shared.domain.com/private.pdf",
                },
            ]
        }
        hosts = crh.extract_restricted_hosts(catalog)
        self.assertIn("manual.restricted.org", hosts)
        self.assertIn("blocked.source.com", hosts)
        self.assertIn("ictrp.who.int", hosts)
        # Shared domain with a permitted access source is not blocked
        self.assertNotIn("shared.domain.com", hosts)
        self.assertNotIn("api.permitted.org", hosts)
        self.assertNotIn("www.permitted.org", hosts)

    def test_get_denied_web_hosts(self):
        settings = {
            "permissions": {
                "deny": [
                    "Read(.env)",
                    "WebFetch(domain:apps.cff.org)",
                    "WebFetch(domain:CFTR2.ORG)",
                    "Bash(git push*)",
                    "WebFetch(invalid-syntax)",
                ]
            }
        }
        denied = crh.get_denied_web_hosts(settings)
        self.assertIn("apps.cff.org", denied)
        self.assertIn("cftr2.org", denied)
        self.assertNotIn("invalid-syntax", denied)
        self.assertEqual(len(denied), 2)

    def test_self_test_runs_cleanly(self):
        ret = crh.run_self_test()
        self.assertEqual(ret, 0)

    def test_skips_when_catalog_absent(self):
        """A standalone cf-lab clone (GitHub Actions) has no ../cf-research: skip, exit 0."""
        out = io.StringIO()
        with mock.patch.object(crh, "find_catalog", return_value=None), \
                contextlib.redirect_stdout(out):
            ret = crh.main([])
        self.assertEqual(ret, 0)
        self.assertIn("SKIP: catalog.yaml not found", out.getvalue())

    def test_standalone_copy_exits_zero(self):
        """Run the script from a copy with no sibling repositories, as CI sees it."""
        env = {k: v for k, v in os.environ.items() if k != "EVIDENCE_CATALOG"}
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "cf-lab"
            (clone / "tasks").mkdir(parents=True)
            (clone / ".claude").mkdir()
            shutil.copy2(ROOT / "tasks" / "check_restricted_hosts.py", clone / "tasks")
            shutil.copy2(ROOT / ".claude" / "settings.json", clone / ".claude")
            proc = subprocess.run(
                [sys.executable, str(clone / "tasks" / "check_restricted_hosts.py")],
                capture_output=True, text=True, env=env, timeout=60,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("SKIP", proc.stdout)


if __name__ == "__main__":
    unittest.main()

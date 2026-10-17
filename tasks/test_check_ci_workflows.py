#!/usr/bin/env python3
"""Unit tests for tasks/check_ci_workflows.py (T-0114)."""
from __future__ import annotations

import unittest
from check_ci_workflows import REPO_ROOT, check_workflow_text, find_public_repo_workflows


class TestCheckCiWorkflows(unittest.TestCase):
    def test_shipped_workflows_pass(self) -> None:
        wfs = find_public_repo_workflows(REPO_ROOT)
        self.assertGreaterEqual(len(wfs), 1)
        for wf in wfs:
            errs = check_workflow_text(wf.read_text(encoding="utf-8"), str(wf))
            self.assertEqual(errs, [], f"{wf} failed: {errs}")

    def test_unpinned_tag_action_is_rejected(self) -> None:
        bad = """
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        errs = check_workflow_text(bad, "bad.yml")
        self.assertTrue(any("not pinned by a 40-char commit SHA" in e for e in errs))

    def test_write_permission_is_rejected(self) -> None:
        bad = """
on:
  pull_request:
permissions:
  contents: write
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
"""
        errs = check_workflow_text(bad, "bad.yml")
        self.assertTrue(any("write permission" in e or "contents: read" in e for e in errs))

    def test_write_all_and_commented_permissions_are_rejected(self) -> None:
        bad = """
on:
  pull_request:
# permissions:
#   contents: read
permissions: write-all
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      # - uses: actions/checkout@v4
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
"""
        errs = check_workflow_text(bad, "bad2.yml")
        self.assertTrue(any("missing top-level 'permissions: contents: read'" in e for e in errs))
        self.assertTrue(any("write permission is forbidden" in e for e in errs))


if __name__ == "__main__":
    unittest.main()

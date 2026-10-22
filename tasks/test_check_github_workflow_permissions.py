#!/usr/bin/env python3
"""Unit tests for tasks/check_github_workflow_permissions.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_github_workflow_permissions import (
    audit_repository_workflows,
    audit_workflow_content,
    audit_workspace,
    get_sibling_repo_roots,
)


class TestCheckGitHubWorkflowPermissions(unittest.TestCase):
    """Test suite for GitHub Actions workflow permissions and action pinning."""

    def test_valid_workflow_passes(self) -> None:
        valid_yml = """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: echo "All clean"
"""
        violations, warnings = audit_workflow_content("valid.yml", valid_yml)
        self.assertEqual(len(violations), 0)
        self.assertEqual(len(warnings), 0)

    def test_missing_permissions_block_fails(self) -> None:
        no_perms_yml = """
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
"""
        violations, _ = audit_workflow_content("no_perms.yml", no_perms_yml)
        self.assertTrue(any("Missing explicit top-level 'permissions:' block" in v for v in violations))

    def test_write_all_permissions_fails(self) -> None:
        write_all_yml = """
name: ci
on: [push]
permissions: write-all
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
"""
        violations, _ = audit_workflow_content("write_all.yml", write_all_yml)
        self.assertTrue(any("write-all" in v for v in violations))

    def test_mutable_tag_action_fails(self) -> None:
        tag_yml = """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        violations, _ = audit_workflow_content("tag.yml", tag_yml)
        self.assertTrue(any("pinned to mutable ref '@v4'" in v for v in violations))

    def test_unpinned_action_fails(self) -> None:
        unpinned_yml = """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout
"""
        violations, _ = audit_workflow_content("unpinned.yml", unpinned_yml)
        self.assertTrue(any("missing a version specifier or commit SHA" in v for v in violations))

    def test_local_action_exempted(self) -> None:
        local_yml = """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/custom-step
"""
        violations, _ = audit_workflow_content("local.yml", local_yml)
        self.assertEqual(len(violations), 0)

    def test_docker_action_exempted(self) -> None:
        docker_yml = """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: docker://alpine:3.18
"""
        violations, _ = audit_workflow_content("docker.yml", docker_yml)
        self.assertEqual(len(violations), 0)

    def test_unsafe_script_injection_detected(self) -> None:
        script_inject_yml = """
name: ci
on: [pull_request]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: |
          echo "Processing PR: ${{ github.event.pull_request.title }}"
"""
        violations, _ = audit_workflow_content("inject.yml", script_inject_yml)
        self.assertTrue(any("Unsafe inline expansion" in v for v in violations))

    def test_safe_env_var_step_passes(self) -> None:
        safe_env_yml = """
name: ci
on: [pull_request]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Print Title
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: |
          echo "Processing PR: $PR_TITLE"
"""
        violations, _ = audit_workflow_content("safe_env.yml", safe_env_yml)
        self.assertEqual(len(violations), 0)

    def test_audit_workspace_clean(self) -> None:
        lab_root = Path(__file__).resolve().parents[1]
        report = audit_workspace(lab_root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["total_violations"], 0)
        self.assertGreaterEqual(report["files_audited"], 4)


if __name__ == "__main__":
    unittest.main()

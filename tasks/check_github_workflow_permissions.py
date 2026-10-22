#!/usr/bin/env python3
"""Automated Cross-Repo GitHub Actions Workflow Token Permission & Least Privilege Linter.

Audits GitHub Actions workflow definitions (.github/workflows/*.yml, *.yaml) across
all workspace repositories (cf-lab, cf-research, cf-skills, .ai) to enforce
strict security invariants against CI supply chain compromise and token privilege escalation:
1. Explicit Top-Level Permissions Block:
   - Verifies that every workflow file declares an explicit top-level `permissions:` block,
     prohibiting reliance on default permissive repository tokens.
2. Least Privilege Enforcement:
   - Ensures workflows request only minimal required scopes (e.g. `contents: read`),
     strictly prohibiting unconstrained `write-all` permissions.
3. Third-Party Action Pinning by Full Commit SHA:
   - Audits all `uses:` directives to ensure external actions are pinned to an immutable
     40-character hexadecimal commit SHA, preventing tag mutation / supply chain hijacking.
4. Script Injection Guard:
   - Detects unsafe inline expansions of untrusted GitHub event contexts (e.g. PR titles,
     issue bodies) inside `run:` shell commands, requiring environment variable assignment.

Usage:
    python tasks/check_github_workflow_permissions.py --check
    python tasks/check_github_workflow_permissions.py --json
    python tasks/check_github_workflow_permissions.py --strict
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "github-workflow-permissions-audit.json"

SHA1_RX = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)

# Dangerous GitHub event expressions that must never be directly interpolated in `run:` steps
DANGEROUS_INLINE_EVENT_EXPRS = (
    "github.event.issue.title",
    "github.event.issue.body",
    "github.event.pull_request.title",
    "github.event.pull_request.body",
    "github.event.comment.body",
    "github.event.review.body",
    "github.head_ref",
)


def get_sibling_repo_roots(lab_root: Path) -> List[Tuple[str, Path]]:
    """Resolve sibling workspace repositories (cf-lab, cf-research, cf-skills, .ai)."""
    parts = lab_root.parts
    if ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        repos_root = Path(*parts[:wt_idx])
    else:
        repos_root = lab_root.parent

    candidates = [
        ("cf-lab", repos_root / "cf-lab" if (repos_root / "cf-lab").exists() else lab_root),
        ("cf-research", repos_root / "cf-research"),
        ("cf-skills", repos_root / "cf-skills"),
        (".ai", repos_root / ".ai"),
    ]
    return [(name, p) for name, p in candidates if p.exists() and p.is_dir()]


def parse_workflow_yaml(content: str) -> Dict[str, Any]:
    """Parse YAML content using PyYAML if available, or lightweight line-based fallback."""
    try:
        import yaml
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception:
        # Fallback dictionary for basic structure if syntax error
        return {}


def audit_workflow_content(filename: str, content: str) -> Tuple[List[str], List[str]]:
    """Audit workflow content for security invariants, returning (violations, warnings)."""
    violations: List[str] = []
    warnings: List[str] = []

    parsed = parse_workflow_yaml(content)

    # 1. Top-Level Permissions Block Verification
    has_top_permissions = False
    if parsed and "permissions" in parsed:
        has_top_permissions = True
        perms = parsed["permissions"]
        if perms == "write-all":
            violations.append(
                f"{filename}: Top-level permissions set to 'write-all'. Least privilege requires minimal scopes."
            )
        elif perms == "read-all":
            warnings.append(
                f"{filename}: Top-level permissions set to 'read-all'. Prefer explicit minimal scopes like 'contents: read'."
            )
    else:
        # Fallback regex scan for top-level permissions
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r"^permissions\s*:", line):
                has_top_permissions = True
                if "write-all" in stripped:
                    violations.append(
                        f"{filename}:{idx + 1}: Top-level permissions set to 'write-all'."
                    )
                break

    if not has_top_permissions:
        violations.append(
            f"{filename}: Missing explicit top-level 'permissions:' block. Prohibited from using default permissive token."
        )

    # 2. Third-Party Action Pinning by Full Commit SHA
    uses_pattern = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)(?:#.*)?$", re.MULTILINE)
    for match in uses_pattern.finditer(content):
        action_ref = match.group(1).strip()
        # Exempt local actions
        if action_ref.startswith("./") or action_ref.startswith("docker://"):
            continue

        if "@" not in action_ref:
            violations.append(
                f"{filename}: Action '{action_ref}' is missing a version specifier or commit SHA."
            )
            continue

        action_name, ref = action_ref.split("@", 1)
        # Check if ref is a full 40-character hex SHA
        if not SHA1_RX.match(ref):
            violations.append(
                f"{filename}: Action '{action_name}' is pinned to mutable ref '@{ref}'. "
                "Must be pinned to an immutable 40-character commit SHA."
            )

    # 3. Script Injection Guard in `run:` steps
    if parsed and "jobs" in parsed and isinstance(parsed["jobs"], dict):
        for job_id, job in parsed["jobs"].items():
            if isinstance(job, dict) and "steps" in job and isinstance(job["steps"], list):
                for step_idx, step in enumerate(job["steps"]):
                    if isinstance(step, dict) and "run" in step:
                        run_cmd = str(step["run"])
                        for dangerous_expr in DANGEROUS_INLINE_EVENT_EXPRS:
                            pattern = re.compile(rf"\${{\{{\s*{re.escape(dangerous_expr)}\s*\}}\}}")
                            if pattern.search(run_cmd):
                                step_name = step.get("name", f"step {step_idx + 1}")
                                violations.append(
                                    f"{filename}: Job '{job_id}' {step_name} has Unsafe inline expansion of "
                                    f"'${{{{{dangerous_expr}}}}}' in 'run:' script. "
                                    "Pass via an intermediate environment variable ('env:') to prevent script injection."
                                )
    else:
        # Fallback line-by-line scanner with state machine for `run:` blocks
        in_run_block = False
        run_indent = 0
        for idx, line in enumerate(content.splitlines()):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if re.match(r"^\s*(?:-\s*)?run:\s*", line):
                in_run_block = True
                run_indent = indent
            elif in_run_block and (indent <= run_indent and stripped and not stripped.startswith("#")):
                in_run_block = False

            if in_run_block:
                for dangerous_expr in DANGEROUS_INLINE_EVENT_EXPRS:
                    pattern = re.compile(rf"\${{\{{\s*{re.escape(dangerous_expr)}\s*\}}\}}")
                    if pattern.search(line):
                        violations.append(
                            f"{filename}:{idx + 1}: Unsafe inline expansion of '${{{{{dangerous_expr}}}}}' in shell step. "
                            "Pass via an intermediate environment variable to prevent script injection."
                        )

    return violations, warnings


def audit_repository_workflows(repo_name: str, repo_path: Path) -> Dict[str, Any]:
    """Audit all GitHub Actions workflows in a repository."""
    workflows_dir = repo_path / ".github" / "workflows"
    violations: List[str] = []
    warnings: List[str] = []
    files_audited = 0

    if workflows_dir.exists() and workflows_dir.is_dir():
        for f in workflows_dir.glob("*.y*ml"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                v_list, w_list = audit_workflow_content(f"{repo_name}/.github/workflows/{f.name}", content)
                violations.extend(v_list)
                warnings.extend(w_list)
                files_audited += 1
            except Exception as exc:
                violations.append(f"{repo_name}/.github/workflows/{f.name}: Read error: {exc}")

    return {
        "repo": repo_name,
        "path": str(repo_path),
        "files_audited": files_audited,
        "violations": violations,
        "warnings": warnings,
        "clean": len(violations) == 0,
    }


def audit_workspace(lab_root: Path) -> Dict[str, Any]:
    """Audit workflows across all workspace repositories."""
    repos = get_sibling_repo_roots(lab_root)
    results = []
    total_violations = 0
    total_warnings = 0
    total_files = 0

    for name, path in repos:
        res = audit_repository_workflows(name, path)
        results.append(res)
        total_violations += len(res["violations"])
        total_warnings += len(res["warnings"])
        total_files += res["files_audited"]

    return {
        "status": "PASS" if total_violations == 0 else "FAIL",
        "repositories_audited": len(repos),
        "files_audited": total_files,
        "total_violations": total_violations,
        "total_warnings": total_warnings,
        "repositories": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Cross-Repo GitHub Actions Workflow Token Permission & Least Privilege Linter"
    )
    parser.add_argument("--check", action="store_true", help="Run audit and exit 0 if clean, 1 if violations found")
    parser.add_argument("--json", action="store_true", help="Print report as formatted JSON")
    parser.add_argument("--report-file", type=Path, default=DEFAULT_REPORT_PATH, help="Path to write JSON report")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as violations")
    args = parser.parse_args()

    report = audit_workspace(REPO_ROOT)

    if args.report_file:
        try:
            args.report_file.parent.mkdir(parents=True, exist_ok=True)
            args.report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"Warning: Could not write report to {args.report_file}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 1

    print("GitHub Actions Workflow Permissions & Action Pinning Linter:")
    print(f"  Status: {report['status']}")
    print(f"  Repositories audited: {report['repositories_audited']}")
    print(f"  Workflow files audited: {report['files_audited']}")

    if report["total_violations"] > 0:
        print("\nViolations detected:")
        for repo_res in report["repositories"]:
            for v in repo_res["violations"]:
                print(f"  [ERROR] [{repo_res['repo']}] {v}")

    if report["total_warnings"] > 0:
        print("\nWarnings:")
        for repo_res in report["repositories"]:
            for w in repo_res["warnings"]:
                print(f"  [WARN] [{repo_res['repo']}] {w}")

    if report["status"] == "PASS":
        if args.strict and report["total_warnings"] > 0:
            print("\nFAIL: Strict mode enabled and warnings are present.")
            return 1
        print("All workflow permission blocks and action SHA pinning verified clean! (PASS)")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

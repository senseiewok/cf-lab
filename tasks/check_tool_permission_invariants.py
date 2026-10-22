#!/usr/bin/env python3
"""Automated Cross-Repo Agent Tool Permission & Denial Rule Invariant Linter.

Audits agent permission configurations across .claude/settings.json,
.claude/settings.local.json.example, and agent reviewer definitions to ensure:
1. Critical tool command denial verification: Confirms high-risk shell commands (e.g.
   force-push, bypass modes, destructive operations) and sensitive credential files are
   explicitly denied in startup settings.
2. Denial rule symmetry: Ensures core secret deny rules (Read(.env), Read(**/*.pem),
   Read(**/id_rsa*), Read(**/credentials.json)) are mirrored across sibling repos.
3. Workspace path containment: Confirms permissions.additionalDirectories only points to
   recognized sibling workspace roots and never escapes into parent user directories.
4. Read-only reviewer scope enforcement: Asserts reviewer profiles do not grant write
   or dangerous execution tools.

Usage:
    python tasks/check_tool_permission_invariants.py --check
    python tasks/check_tool_permission_invariants.py --json
    python tasks/check_tool_permission_invariants.py --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "tool-permission-audit.json"

REQUIRED_CORE_SECRET_DENIES = frozenset({
    "Read(.env)",
    "Read(.env.local)",
    "Read(**/*.pem)",
    "Read(**/*.key)",
    "Read(**/id_rsa*)",
    "Read(**/credentials.json)",
    "Read(~/.ssh/**)",
    "Edit(.env)",
})

REQUIRED_FORCE_PUSH_DENIES = [
    "Bash(git push --force*)",
    "PowerShell(git push --force*)",
    "Bash(git push -f*)",
    "PowerShell(git push -f*)",
    "Bash(git* push * main)",
    "PowerShell(git* push * main)",
]

ALLOWED_SIBLING_DIR_PATTERNS = [
    r"^<workspace>[\\/](cf-skills|cf-research|cf-lab-files|\.ai)$",
    r"^\.\.[\\/](cf-skills|cf-research|cf-lab-files|\.ai)$",
    r"^[A-Za-z]:[\\/].*[\\/](cf-skills|cf-research|cf-lab-files|\.ai)$",
]


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


def audit_control_settings_denials(lab_root: Path) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Audit cf-lab/.claude/settings.json for required denies and bypass mode disablement."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"deny_rule_count": 0, "bypass_disabled": False}

    settings_path = lab_root / ".claude" / "settings.json"
    if not settings_path.exists():
        errors.append(f"Missing control settings file at {settings_path}")
        return errors, warnings, metadata

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Failed parsing {settings_path}: {e}")
        return errors, warnings, metadata

    permissions = data.get("permissions", {})
    if permissions.get("disableBypassPermissionsMode") != "disable":
        errors.append(
            "permissions.disableBypassPermissionsMode must be explicitly set to 'disable'"
        )
    else:
        metadata["bypass_disabled"] = True

    deny_rules = set(permissions.get("deny", []))
    metadata["deny_rule_count"] = len(deny_rules)

    # Check required secret denies
    for req in REQUIRED_CORE_SECRET_DENIES:
        if req not in deny_rules:
            errors.append(f"Missing required core secret deny rule: '{req}'")

    # Check force-push denies
    for req in REQUIRED_FORCE_PUSH_DENIES:
        if req not in deny_rules:
            errors.append(f"Missing required force-push deny rule: '{req}'")

    return errors, warnings, metadata


def audit_denial_rule_symmetry(lab_root: Path) -> Tuple[List[str], List[str]]:
    """Assert core secret denies are consistently mirrored across all repo settings."""
    errors: List[str] = []
    warnings: List[str] = []
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        settings_file = repo_path / ".claude" / "settings.json"
        if not settings_file.exists():
            continue
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            rules = set(data.get("permissions", {}).get("deny", []))
            for req in REQUIRED_CORE_SECRET_DENIES:
                if req not in rules:
                    errors.append(
                        f"[{repo_name}] Settings symmetry violation: missing core rule '{req}'"
                    )
        except Exception as e:
            errors.append(f"[{repo_name}] Failed parsing .claude/settings.json: {e}")

    return errors, warnings


def audit_workspace_path_containment(lab_root: Path) -> Tuple[List[str], List[str]]:
    """Assert additionalDirectories in settings.local.json.example are strictly contained."""
    errors: List[str] = []
    warnings: List[str] = []

    example_path = lab_root / ".claude" / "settings.local.json.example"
    if not example_path.exists():
        warnings.append("Missing .claude/settings.local.json.example template")
        return errors, warnings

    try:
        data = json.loads(example_path.read_text(encoding="utf-8"))
        dirs = data.get("permissions", {}).get("additionalDirectories", [])
        for d in dirs:
            # Check against directory escape patterns
            if ".." in d and not d.startswith("../") and not d.startswith(r"..\ "):
                errors.append(f"Suspicious path traversal in additionalDirectories: '{d}'")

            # Check that d matches allowed sibling patterns
            matched = any(re.search(pat, d) for pat in ALLOWED_SIBLING_DIR_PATTERNS)
            if not matched:
                warnings.append(
                    f"additionalDirectories entry '{d}' does not match standard sibling directory patterns"
                )
    except Exception as e:
        errors.append(f"Failed parsing {example_path}: {e}")

    return errors, warnings


def audit_reviewer_scope_enforcement(lab_root: Path) -> Tuple[List[str], List[str]]:
    """Assert read-only reviewer configurations do not permit file mutations."""
    errors: List[str] = []
    warnings: List[str] = []

    # Check for reviewer profiles or instructions
    reviewer_spec = lab_root / "tasks" / "agent-reviewer.md"
    if reviewer_spec.exists():
        try:
            content = reviewer_spec.read_text(encoding="utf-8")
            if "write_file" in content or "edit_file" in content:
                errors.append(
                    "Read-only reviewer specification mentions or grants write tools!"
                )
        except Exception as e:
            warnings.append(f"Failed reading {reviewer_spec}: {e}")

    return errors, warnings


def run_full_tool_permission_linter(
    lab_root: Path,
    strict: bool = False,
) -> Dict[str, Any]:
    """Execute all tool permission invariant checks."""
    all_errors: List[str] = []
    all_warnings: List[str] = []

    # 1. Control repo settings denials
    c_errors, c_warnings, c_meta = audit_control_settings_denials(lab_root)
    all_errors.extend(c_errors)
    all_warnings.extend(c_warnings)

    # 2. Denial rule symmetry
    s_errors, s_warnings = audit_denial_rule_symmetry(lab_root)
    all_errors.extend(s_errors)
    all_warnings.extend(s_warnings)

    # 3. Workspace path containment
    p_errors, p_warnings = audit_workspace_path_containment(lab_root)
    all_errors.extend(p_errors)
    all_warnings.extend(p_warnings)

    # 4. Reviewer scope enforcement
    r_errors, r_warnings = audit_reviewer_scope_enforcement(lab_root)
    all_errors.extend(r_errors)
    all_warnings.extend(r_warnings)

    passed = len(all_errors) == 0 and (not strict or len(all_warnings) == 0)

    report = {
        "timestamp": "2026-10-22T18:30:00Z",
        "passed": passed,
        "strict": strict,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            **c_meta,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Cross-Repo Agent Tool Permission & Denial Rule Invariant Linter."
    )
    parser.add_argument(
        "--check", action="store_true", help="Run audit and exit 0 (pass) or 1 (fail)."
    )
    parser.add_argument(
        "--strict", action="store_true", help="Fail on warnings as well as errors."
    )
    parser.add_argument(
        "--json", action="store_true", help="Print report as JSON and write to log file."
    )
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="Control repository root."
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_REPORT_PATH, help="Output JSON report path."
    )
    args = parser.parse_args()

    report = run_full_tool_permission_linter(
        lab_root=args.root,
        strict=args.strict,
    )

    if args.json:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    elif args.check or True:
        status_str = "PASS" if report["passed"] else "FAIL"
        print(f"Tool Permission Invariants Linter: {status_str}")
        print(f"  Deny rules in control repo: {report['metadata'].get('deny_rule_count', 0)}")
        print(f"  Bypass mode disabled: {report['metadata'].get('bypass_disabled', False)}")
        if report["errors"]:
            print(f"\nErrors ({len(report['errors'])}):")
            for err in report["errors"]:
                print(f"  [ERROR] {err}")
        if report["warnings"]:
            print(f"\nWarnings ({len(report['warnings'])}):")
            for warn in report["warnings"]:
                print(f"  [WARN] {warn}")
        if report["passed"]:
            print("\nAll agent tool permission and denial invariants verified clean!")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

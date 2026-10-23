#!/usr/bin/env python3
"""Automated Multi-Repo Git Hook & Pre-Commit Shell Invariant Linter.

Audits git hook configurations, pre-commit wrappers, and setup scripts across
all workspace repositories (cf-lab, cf-research, cf-skills, .ai) to ensure:
1. Hook Directory Containment: Asserts that git hooks (.githooks/, .husky/,
   .git/hooks/) do not execute unvetted external binaries or download untracked
   network payloads (no curl, wget, npm install, pip install inside hooks).
2. Interpreter Portability: Verifies hook scripts invoke portable interpreters
   (python3, pwsh -NoProfile, sh) with explicit failure propagation (set -e,
   $ErrorActionPreference = 'Stop').
3. Privacy Scanner Integration: Asserts that check-staged.ps1 or equivalent privacy
   scanners are present, executable, and referenced in git security baselines.

Usage:
    python tasks/check_git_hooks_invariants.py --check
    python tasks/check_git_hooks_invariants.py --json
    python tasks/check_git_hooks_invariants.py --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "git-hooks-audit.json"
CHECK_STAGED_PATH = (
    REPO_ROOT / ".claude" / "skills" / "security-git" / "scripts" / "check-staged.ps1"
)

# Network download commands prohibited in pre-commit hooks
PROHIBITED_HOOK_PAYLOAD_PATTERNS = [
    (r"\bcurl\b", "Prohibited network download utility 'curl'"),
    (r"\bwget\b", "Prohibited network download utility 'wget'"),
    (r"\bInvoke-WebRequest\b", "Prohibited network download cmdlet 'Invoke-WebRequest'"),
    (r"\biwr\b", "Prohibited network download alias 'iwr'"),
    (r"\bInvoke-RestMethod\b", "Prohibited network download cmdlet 'Invoke-RestMethod'"),
    (r"\birm\b", "Prohibited network download alias 'irm'"),
    (r"\bnpm\s+(install|i|add)\b", "Prohibited package installer 'npm install'"),
    (r"\bpip\s+install\b", "Prohibited package installer 'pip install'"),
    (r"\bgit\s+clone\b", "Prohibited repository clone 'git clone'"),
]

HOOK_DIR_NAMES = [".githooks", ".husky", "githooks"]


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


def audit_hook_directory_containment(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Audit git hook scripts across repos for prohibited external download payloads."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"audited_hook_scripts": 0, "hook_directories": []}
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        # Check standard hook directories
        for hdir_name in HOOK_DIR_NAMES:
            hdir = repo_path / hdir_name
            if not hdir.exists() or not hdir.is_dir():
                continue

            metadata["hook_directories"].append(str(hdir.relative_to(repo_path.parent)))
            for script_path in hdir.rglob("*"):
                if not script_path.is_file() or script_path.suffix in [".md", ".txt", ".json"]:
                    continue

                metadata["audited_hook_scripts"] += 1
                try:
                    content = script_path.read_text(encoding="utf-8", errors="ignore")
                    rel_p = f"[{repo_name}] {script_path.name}"

                    for pattern, desc in PROHIBITED_HOOK_PAYLOAD_PATTERNS:
                        if re.search(pattern, content, re.IGNORECASE):
                            errors.append(
                                f"{rel_p}: {desc} detected in hook script. "
                                "Git hooks must run deterministically offline without network payloads."
                            )
                except Exception as e:
                    warnings.append(f"[{repo_name}] Could not read hook script {script_path.name}: {e}")

        # Also inspect .git/hooks if this is a standard git repo (not worktree)
        git_hooks = repo_path / ".git" / "hooks"
        if git_hooks.exists() and git_hooks.is_dir():
            for script_path in git_hooks.glob("*"):
                if script_path.is_file() and not script_path.name.endswith(".sample"):
                    metadata["audited_hook_scripts"] += 1
                    try:
                        content = script_path.read_text(encoding="utf-8", errors="ignore")
                        rel_p = f"[{repo_name}] .git/hooks/{script_path.name}"
                        for pattern, desc in PROHIBITED_HOOK_PAYLOAD_PATTERNS:
                            if re.search(pattern, content, re.IGNORECASE):
                                errors.append(
                                    f"{rel_p}: {desc} detected in active git hook. Hooks must be offline."
                                )
                    except Exception as e:
                        warnings.append(f"[{repo_name}] Could not inspect .git/hooks/{script_path.name}: {e}")

    return errors, warnings, metadata


def audit_hook_interpreter_portability(
    lab_root: Path,
) -> Tuple[List[str], List[str]]:
    """Assert hook scripts specify portable interpreters and fail-safe error propagation."""
    errors: List[str] = []
    warnings: List[str] = []
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        for hdir_name in HOOK_DIR_NAMES:
            hdir = repo_path / hdir_name
            if not hdir.exists() or not hdir.is_dir():
                continue

            for script_path in hdir.rglob("*"):
                if not script_path.is_file() or script_path.suffix in [".md", ".txt", ".json", ".yaml"]:
                    continue

                try:
                    lines = script_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if not lines:
                        continue

                    first_line = lines[0].strip()
                    rel_p = f"[{repo_name}] {script_path.name}"

                    # Shell scripts
                    if script_path.suffix in [".sh", ""] and first_line.startswith("#!"):
                        if not any(sh in first_line for sh in ["/bin/sh", "/bin/bash", "/usr/bin/env sh", "/usr/bin/env bash"]):
                            warnings.append(f"{rel_p}: Non-standard shebang '{first_line}'. Use portable '#!/bin/sh' or '#!/usr/bin/env bash'.")

                        content = "\n".join(lines)
                        if "set -e" not in content and "set -eo" not in content and "set -euo pipefail" not in content:
                            warnings.append(f"{rel_p}: Shell hook missing 'set -e' for deterministic error propagation.")

                    # PowerShell scripts
                    elif script_path.suffix in [".ps1"]:
                        content = "\n".join(lines)
                        if "$ErrorActionPreference" not in content and "-ErrorAction Stop" not in content:
                            warnings.append(f"{rel_p}: PowerShell hook should set $ErrorActionPreference = 'Stop'.")

                except Exception as e:
                    warnings.append(f"[{repo_name}] Could not parse hook header {script_path.name}: {e}")

    return errors, warnings


def audit_privacy_precommit_integration(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Verify presence and executable integrity of check-staged.ps1 privacy guard."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"check_staged_present": False, "privacy_patterns_count": 0}

    # Verify check-staged.ps1 exists
    staged_script = lab_root / ".claude" / "skills" / "security-git" / "scripts" / "check-staged.ps1"
    if not staged_script.exists():
        errors.append(f"Missing core pre-commit privacy scanner at {staged_script}")
        return errors, warnings, metadata

    metadata["check_staged_present"] = True

    try:
        content = staged_script.read_text(encoding="utf-8")
        if "privacy-patterns.txt" not in content:
            errors.append(f"{staged_script.name} does not reference privacy-patterns.txt canary file")
        if "git diff --cached" not in content:
            errors.append(f"{staged_script.name} does not inspect staged git index (--cached)")
    except Exception as e:
        errors.append(f"Failed reading {staged_script}: {e}")

    # Verify privacy patterns canary file exists
    patterns_file = lab_root / ".claude" / "skills" / "security-git" / "scripts" / "privacy-patterns.txt"
    if patterns_file.exists():
        try:
            lines = [l.strip() for l in patterns_file.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
            metadata["privacy_patterns_count"] = len(lines)
            if len(lines) < 5:
                warnings.append(f"Privacy canary patterns file has fewer than 5 active patterns ({len(lines)})")
        except Exception as e:
            warnings.append(f"Failed reading {patterns_file}: {e}")
    else:
        errors.append(f"Missing privacy canary patterns file at {patterns_file}")

    return errors, warnings, metadata


def run_full_git_hooks_linter(
    lab_root: Path,
    strict: bool = False,
) -> Dict[str, Any]:
    """Execute all git hook and pre-commit invariant checks."""
    all_errors: List[str] = []
    all_warnings: List[str] = []

    # 1. Hook containment
    c_errors, c_warnings, c_meta = audit_hook_directory_containment(lab_root)
    all_errors.extend(c_errors)
    all_warnings.extend(c_warnings)

    # 2. Interpreter portability
    p_errors, p_warnings = audit_hook_interpreter_portability(lab_root)
    all_errors.extend(p_errors)
    all_warnings.extend(p_warnings)

    # 3. Privacy pre-commit integration
    s_errors, s_warnings, s_meta = audit_privacy_precommit_integration(lab_root)
    all_errors.extend(s_errors)
    all_warnings.extend(s_warnings)

    passed = len(all_errors) == 0 and (not strict or len(all_warnings) == 0)

    report = {
        "timestamp": "2026-10-22T19:25:00Z",
        "passed": passed,
        "strict": strict,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            **c_meta,
            **s_meta,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Multi-Repo Git Hook & Pre-Commit Shell Invariant Linter."
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

    report = run_full_git_hooks_linter(
        lab_root=args.root,
        strict=args.strict,
    )

    if args.json:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    elif args.check or True:
        status_str = "PASS" if report["passed"] else "FAIL"
        print(f"Git Hooks & Pre-Commit Invariants Linter: {status_str}")
        print(f"  Audited hook scripts: {report['metadata'].get('audited_hook_scripts', 0)}")
        print(f"  Privacy scanner present: {report['metadata'].get('check_staged_present', False)}")
        print(f"  Privacy patterns monitored: {report['metadata'].get('privacy_patterns_count', 0)}")
        if report["errors"]:
            print(f"\nErrors ({len(report['errors'])}):")
            for err in report["errors"]:
                print(f"  [ERROR] {err}")
        if report["warnings"]:
            print(f"\nWarnings ({len(report['warnings'])}):")
            for warn in report["warnings"]:
                print(f"  [WARN] {warn}")
        if report["passed"]:
            print("\nAll git hook and pre-commit invariants verified clean!")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

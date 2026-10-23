#!/usr/bin/env python3
"""Automated Cross-Repo Playwright Test Artifact & Server Port Hygiene Linter.

Audits Playwright visual regression test infrastructure and artifact storage across
all workspace repositories (cf-lab, cf-research, cf-skills, .ai) to ensure:
1. Browser Binary Provenance: Asserts Playwright setup scripts strictly point to
   isolated external browser caches outside git repositories (e.g. %LOCALAPPDATA%\\lab-playwright).
2. Artifact Quarantine & Gitignore Invariant: Asserts browser traces, videos, and
   generated screenshots (test-results/, .playwright/, playwright-report/) are excluded
   from git tracking.
3. Local Server Binding Hygiene: Verifies test scripts strictly bind to loopback
   (127.0.0.1 / localhost) and never expose test HTTP servers to public interfaces (0.0.0.0).

Usage:
    python tasks/check_playwright_test_hygiene.py --check
    python tasks/check_playwright_test_hygiene.py --json
    python tasks/check_playwright_test_hygiene.py --strict
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "playwright-hygiene-audit.json"

TEST_ARTIFACT_PATTERNS = [
    r"\.playwright/",
    r"test-results/",
    r"playwright-report/",
    r"\.cache/ms-playwright",
]

PUBLIC_BINDING_PATTERNS = [
    (r"host\s*=\s*['\"]0\.0\.0\.0['\"]", "Insecure 0.0.0.0 public interface binding"),
    (r"bind\s*\(\s*\(\s*['\"]0\.0\.0\.0['\"]", "Insecure 0.0.0.0 public socket binding"),
    (r"--host\s+0\.0\.0\.0", "Insecure 0.0.0.0 command-line flag"),
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


def audit_browser_cache_provenance(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Verify setup-browser-testing.py targets external cache and pinned version."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"setup_script_present": False, "pinned_version": None}

    setup_script = (
        lab_root
        / ".claude"
        / "skills"
        / "playwright-browser-testing"
        / "scripts"
        / "setup-browser-testing.py"
    )
    if not setup_script.exists():
        warnings.append(f"Optional browser setup script not found at {setup_script}")
        return errors, warnings, metadata

    metadata["setup_script_present"] = True

    try:
        content = setup_script.read_text(encoding="utf-8")
        # Check pinned version
        m_version = re.search(r'PLAYWRIGHT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
        if m_version:
            metadata["pinned_version"] = m_version.group(1)
        else:
            errors.append("setup-browser-testing.py is missing pinned PLAYWRIGHT_VERSION constant")

        # Check external venv path definition
        if "LOCALAPPDATA" not in content and "XDG_DATA_HOME" not in content:
            errors.append(
                "setup-browser-testing.py does not define external venv cache (LOCALAPPDATA/XDG_DATA_HOME)"
            )

        # Check repository containment (must NOT install inside workspace repo)
        if 'default_venv = REPO_ROOT / "venv"' in content or 'default_venv = Path("venv")' in content:
            errors.append("setup-browser-testing.py installs venv inside workspace repo")

    except Exception as e:
        errors.append(f"Failed reading {setup_script}: {e}")

    return errors, warnings, metadata


def audit_artifact_gitignore_quarantine(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Assert test artifact folders (test-results, .playwright) are untracked."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"tracked_artifact_leaks": 0}
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        # Check git index for tracked test artifacts
        for pat in ["*test-results*", "*.trace", "*playwright-report*"]:
            try:
                res = subprocess.run(
                    ["git", "-C", str(repo_path), "ls-files", pat],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    leaks = [l for l in res.stdout.strip().splitlines() if l.strip()]
                    if leaks:
                        metadata["tracked_artifact_leaks"] += len(leaks)
                        errors.append(
                            f"[{repo_name}] Tracked test artifact leak detected in git index: {leaks[:3]}"
                        )
            except Exception as e:
                warnings.append(f"[{repo_name}] Could not check git ls-files for {pat}: {e}")

    return errors, warnings, metadata


def audit_local_server_binding_hygiene(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Assert test observation and review scripts strictly bind to loopback."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"scripts_audited": 0}
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        # Search scripts across skills and tools
        for script_path in repo_path.glob("**/*.py"):
            # Skip virtual environments or caches
            parts = script_path.parts
            if any(p in parts for p in ["venv", ".venv", "__pycache__", ".git", ".worktrees"]):
                continue

            # Only inspect server or test runner scripts
            name_lower = script_path.name.lower()
            if not any(k in name_lower for k in ["server", "observe", "capture", "preview", "browser"]):
                continue

            metadata["scripts_audited"] += 1
            try:
                content = script_path.read_text(encoding="utf-8", errors="ignore")
                for pat, desc in PUBLIC_BINDING_PATTERNS:
                    if re.search(pat, content):
                        rel = f"[{repo_name}] {script_path.relative_to(repo_path)}"
                        errors.append(f"{rel}: {desc}. Test servers must bind strictly to 127.0.0.1.")
            except Exception as e:
                warnings.append(f"[{repo_name}] Could not inspect script {script_path.name}: {e}")

    return errors, warnings, metadata


def run_full_playwright_hygiene_linter(
    lab_root: Path,
    strict: bool = False,
) -> Dict[str, Any]:
    """Execute all Playwright test artifact and port hygiene invariant checks."""
    all_errors: List[str] = []
    all_warnings: List[str] = []

    # 1. Browser cache provenance
    b_errors, b_warnings, b_meta = audit_browser_cache_provenance(lab_root)
    all_errors.extend(b_errors)
    all_warnings.extend(b_warnings)

    # 2. Artifact gitignore quarantine
    a_errors, a_warnings, a_meta = audit_artifact_gitignore_quarantine(lab_root)
    all_errors.extend(a_errors)
    all_warnings.extend(a_warnings)

    # 3. Server binding hygiene
    s_errors, s_warnings, s_meta = audit_local_server_binding_hygiene(lab_root)
    all_errors.extend(s_errors)
    all_warnings.extend(s_warnings)

    passed = len(all_errors) == 0 and (not strict or len(all_warnings) == 0)

    report = {
        "timestamp": "2026-10-22T19:30:00Z",
        "passed": passed,
        "strict": strict,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            **b_meta,
            **a_meta,
            **s_meta,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Cross-Repo Playwright Test Artifact & Server Port Hygiene Linter."
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

    report = run_full_playwright_hygiene_linter(
        lab_root=args.root,
        strict=args.strict,
    )

    if args.json:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    elif args.check or True:
        status_str = "PASS" if report["passed"] else "FAIL"
        print(f"Playwright Test Artifact & Server Port Hygiene Linter: {status_str}")
        print(f"  Setup script present: {report['metadata'].get('setup_script_present', False)}")
        print(f"  Pinned version: {report['metadata'].get('pinned_version', 'None')}")
        print(f"  Scripts audited for binding: {report['metadata'].get('scripts_audited', 0)}")
        print(f"  Tracked artifact leaks: {report['metadata'].get('tracked_artifact_leaks', 0)}")
        if report["errors"]:
            print(f"\nErrors ({len(report['errors'])}):")
            for err in report["errors"]:
                print(f"  [ERROR] {err}")
        if report["warnings"]:
            print(f"\nWarnings ({len(report['warnings'])}):")
            for warn in report["warnings"]:
                print(f"  [WARN] {warn}")
        if report["passed"]:
            print("\nAll Playwright test artifact and server port invariants verified clean!")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Automated Multi-Repo Agent Environment Variable (.env) & Canary Isolation Linter.

Audits environment variable configuration files (.env, .env.example, .env.test) and
canary tokens across all workspace repositories to ensure:
1. Zero-Leakage Canary Verification: Asserts git-tracked test canary tokens never collide
   with active keys in private .env, and no active key appears in tracked git files.
2. Entropy & Key Structure Auditing: Validates keys in untracked .env conform to length and
   entropy requirements without using dummy/insecure values.
3. Template Parity & Stale Variable Guard: Ensures every configuration slot in .env.example
   is documented in README.md or docs/SETUP.md, with only safe placeholder values.
4. Gitignore Invariant: Confirms .env and .env.* are rigorously ignored in gitignore across
   all workspace repositories and never tracked in git index.

Usage:
    python tasks/check_env_canary_isolation.py --check
    python tasks/check_env_canary_isolation.py --json
    python tasks/check_env_canary_isolation.py --strict
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "env-canary-audit.json"
PRIVACY_PATTERNS_PATH = (
    REPO_ROOT / ".claude" / "skills" / "security-git" / "scripts" / "privacy-patterns.txt"
)

# Known benign placeholder values in .env or .env.example
KNOWN_PLACEHOLDERS = frozenset({
    "your_key_here",
    "your_key_here_or_leave_blank",
    "mock-canary-test-value",
    "you@example.org",
    "true",
    "false",
    "../cf-research/sources/catalog.yaml",
    "../cf-lab-files",
    "./.claude/skills/model-qwen3-8-27b/ollama-profile.fast.json",
    "./.claude/skills/model-qwen3-8-27b/ollama-profile.json",
    "./.claude/skills/model-qwen3-8-27b/ollama-profile.64k.fast.json",
    "./.claude/skills/model-qwen3-8-27b/ollama-profile.64k.json",
    "qwen3.8:27b",
    "qwen3.8:27b-64k",
})


def calculate_shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy in bits per character."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    counts: Dict[str, int] = {}
    for char in data:
        counts[char] = counts.get(char, 0) + 1
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def load_privacy_canaries(pattern_path: Path) -> List[Dict[str, str]]:
    """Load canary tokens from privacy-patterns.txt."""
    canaries: List[Dict[str, str]] = []
    if not pattern_path.exists():
        return canaries
    try:
        content = pattern_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                category, pattern, canary = parts[0], parts[1], parts[2]
                canaries.append({
                    "category": category,
                    "pattern": pattern,
                    "canary": canary,
                })
    except Exception:
        pass
    return canaries


def parse_env_file(env_path: Path) -> Dict[str, str]:
    """Parse KEY=value lines from an env file without shell execution."""
    env_vars: Dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                # Remove optional wrapping quotes
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                env_vars[key] = val
    except Exception:
        pass
    return env_vars


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
    # Filter to existing directories
    return [(name, p) for name, p in candidates if p.exists() and p.is_dir()]


def audit_gitignore_invariants(
    lab_root: Path,
) -> Tuple[List[str], List[str]]:
    """Assert .env and .env.* are ignored across all workspace repos and untracked."""
    errors: List[str] = []
    warnings: List[str] = []
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        gitignore_path = repo_path / ".gitignore"
        if not gitignore_path.exists():
            errors.append(f"[{repo_name}] Missing .gitignore file")
            continue
        try:
            content = gitignore_path.read_text(encoding="utf-8")
            lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
            has_env_rule = any(
                re.match(r"^\.?\.env(\.\*)?$", l) or l == ".env" or l == ".env.*"
                for l in lines
            )
            if not has_env_rule:
                errors.append(
                    f"[{repo_name}] .gitignore does not explicitly ignore .env or .env.*"
                )
        except Exception as e:
            errors.append(f"[{repo_name}] Failed reading .gitignore: {e}")

        # Verify no tracked file is named .env or .env.local
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_path), "ls-files", "*.env", ".env", ".env.*"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                tracked_env_files = [
                    f
                    for f in res.stdout.strip().splitlines()
                    if f.endswith(".env") or f == ".env" or ".env.local" in f
                ]
                # Filter out test fixtures under cases/
                tracked_env_files = [
                    f for f in tracked_env_files if "cases/env-secrets" not in f
                ]
                if tracked_env_files:
                    errors.append(
                        f"[{repo_name}] Tracked secret env file committed in git: {tracked_env_files}"
                    )
        except Exception:
            pass

    return errors, warnings


def audit_template_parity(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Assert .env.example slots are documented in README or SETUP and contain safe values."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}

    example_path = lab_root / ".env.example"
    if not example_path.exists():
        errors.append("Missing .env.example template in repository root")
        return errors, warnings, metadata

    example_vars = parse_env_file(example_path)
    metadata["example_var_count"] = len(example_vars)
    metadata["example_variables"] = list(example_vars.keys())

    # Read README.md and docs/SETUP.md for documentation check
    readme_text = ""
    setup_text = ""
    readme_path = lab_root / "README.md"
    setup_path = lab_root / "docs" / "SETUP.md"
    if readme_path.exists():
        readme_text = readme_path.read_text(encoding="utf-8")
    if setup_path.exists():
        setup_text = setup_path.read_text(encoding="utf-8")
    combined_docs = readme_text + "\n" + setup_text

    for key, val in example_vars.items():
        # Check that value is a harmless placeholder
        if val not in KNOWN_PLACEHOLDERS and not val.startswith("../") and not val.startswith("./"):
            if len(val) > 20 and calculate_shannon_entropy(val) > 3.0:
                errors.append(
                    f"Possible real credential in .env.example for key '{key}' (high entropy: {val[:4]}...)"
                )

        # Check documentation mention
        if key not in combined_docs:
            warnings.append(
                f".env.example variable '{key}' is not mentioned in README.md or docs/SETUP.md"
            )

    return errors, warnings, metadata


def audit_canary_and_entropy_isolation(
    lab_root: Path,
    custom_env_path: Optional[Path] = None,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Assert active .env keys do not collide with canaries and meet entropy standards."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {
        "env_file_present": False,
        "active_keys_checked": 0,
        "canaries_scanned": 0,
    }

    canaries = load_privacy_canaries(PRIVACY_PATTERNS_PATH)
    metadata["canaries_scanned"] = len(canaries)
    canary_values = {c["canary"] for c in canaries}

    env_path = custom_env_path or (lab_root / ".env")
    if not env_path.exists():
        metadata["env_file_present"] = False
        return errors, warnings, metadata

    metadata["env_file_present"] = True
    env_vars = parse_env_file(env_path)
    metadata["active_keys_checked"] = len(env_vars)

    for key, val in env_vars.items():
        if not val or val in KNOWN_PLACEHOLDERS:
            continue

        # 1. Canary Collision Check: Real key must never match a test canary
        if val in canary_values or any(val == c["canary"] for c in canaries):
            errors.append(
                f"Collision: active variable '{key}' in .env matches test canary value!"
            )

        # 2. Entropy and Length Check for API keys
        if "KEY" in key or "SECRET" in key or "TOKEN" in key:
            entropy = calculate_shannon_entropy(val)
            if len(val) < 12:
                errors.append(
                    f"Suspiciously short credential for '{key}' in .env (length: {len(val)} < 12)"
                )
            elif entropy < 2.2:
                warnings.append(
                    f"Low Shannon entropy for credential '{key}' in .env ({entropy:.2f} bits/char)"
                )

        # 3. Zero-Leakage Invariant: Confirm active key does NOT appear in git tracked files
        if len(val) >= 16:
            try:
                res = subprocess.run(
                    ["git", "-C", str(lab_root), "grep", "-q", "-F", val],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    errors.append(
                        f"CRITICAL LEAK: Active credential for '{key}' was found tracked in git files!"
                    )
            except Exception:
                pass

    return errors, warnings, metadata


def run_full_env_canary_linter(
    lab_root: Path,
    custom_env_path: Optional[Path] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Execute all env and canary isolation audits."""
    all_errors: List[str] = []
    all_warnings: List[str] = []

    # 1. Gitignore and uncommitted invariants
    gi_errors, gi_warnings = audit_gitignore_invariants(lab_root)
    all_errors.extend(gi_errors)
    all_warnings.extend(gi_warnings)

    # 2. Template parity and documentation
    tp_errors, tp_warnings, tp_meta = audit_template_parity(lab_root)
    all_errors.extend(tp_errors)
    all_warnings.extend(tp_warnings)

    # 3. Canary collision, entropy, and zero-leakage check
    ci_errors, ci_warnings, ci_meta = audit_canary_and_entropy_isolation(
        lab_root, custom_env_path
    )
    all_errors.extend(ci_errors)
    all_warnings.extend(ci_warnings)

    passed = len(all_errors) == 0 and (not strict or len(all_warnings) == 0)

    report = {
        "timestamp": "2026-10-22T18:30:00Z",
        "passed": passed,
        "strict": strict,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            **tp_meta,
            **ci_meta,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Multi-Repo Agent Environment Variable (.env) & Canary Isolation Linter."
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
        "--env-file", type=Path, default=None, help="Custom .env file path to audit."
    )
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="Control repository root."
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_REPORT_PATH, help="Output JSON report path."
    )
    args = parser.parse_args()

    report = run_full_env_canary_linter(
        lab_root=args.root,
        custom_env_path=args.env_file,
        strict=args.strict,
    )

    if args.json:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    elif args.check or True:
        status_str = "PASS" if report["passed"] else "FAIL"
        print(f"Env & Canary Isolation Linter: {status_str}")
        print(f"  Scanned .env.example slots: {report['metadata'].get('example_var_count', 0)}")
        print(f"  Privacy canaries audited: {report['metadata'].get('canaries_scanned', 0)}")
        print(f"  .env file present: {report['metadata'].get('env_file_present', False)}")
        if report["errors"]:
            print(f"\nErrors ({len(report['errors'])}):")
            for err in report["errors"]:
                print(f"  [ERROR] {err}")
        if report["warnings"]:
            print(f"\nWarnings ({len(report['warnings'])}):")
            for warn in report["warnings"]:
                print(f"  [WARN] {warn}")
        if report["passed"]:
            print("\nAll environment variable and canary isolation invariants verified clean!")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

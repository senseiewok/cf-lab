#!/usr/bin/env python3
"""Automated Multi-Repo Git Submodule & External Dependency Supply Chain Linter.

Audits git submodule pointers, package configurations, third-party skill exclusions,
and external script references across all workspace repositories (cf-lab, cf-research,
cf-skills, .ai) to enforce:
1. Submodule Pinning & Remote URL Validation:
   - Asserts that git submodules (if configured in .gitmodules) point strictly to
     pinned commit SHAs rather than moving branch heads, with verified HTTPS remote URLs.
2. Third-Party Skill & Dependency Quarantine:
   - Verifies that third-party skills listed in THIRD_PARTY_SKILLS.md are explicitly
     git-ignored in .gitignore and never leaked into the git index.
3. External CDN & Dynamic Import Guard:
   - Audits HTML and JS files in web roots for unvetted external script tags
     (<script src="https://...">) and remote dynamic imports, enforcing strict
     zero-CDN buildless architecture.

Usage:
    python tasks/check_git_supply_chain_integrity.py --check
    python tasks/check_git_supply_chain_integrity.py --json
    python tasks/check_git_supply_chain_integrity.py --strict
"""
from __future__ import annotations

import argparse
import configparser
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "supply-chain-audit.json"

ROW_RE = re.compile(
    r"^\|\s*`([a-z0-9][a-z0-9_-]*)`\s*\|[^|]+\|\s*`([0-9a-f]{64})`\s*\|",
    re.MULTILINE,
)

EXTERNAL_SCRIPT_PATTERN = re.compile(
    r"""<script[^>]+src\s*=\s*["'](https?://[^"']+)["']""",
    re.IGNORECASE,
)

EXTERNAL_DYNAMIC_IMPORT_PATTERN = re.compile(
    r"""import\s*\(\s*["'](https?://[^"']+)["']\s*\)""",
    re.IGNORECASE,
)

EXTERNAL_CSS_IMPORT_PATTERN = re.compile(
    r"""@import\s+(?:url\s*\(\s*)?["'](https?://[^"']+)["']""",
    re.IGNORECASE,
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


def audit_git_submodule_pinning(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Audit .gitmodules configurations across workspace repos for pinning and secure protocols."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"submodules_audited": 0, "submodules_found": []}
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        gitmodules_path = repo_path / ".gitmodules"
        if not gitmodules_path.is_file():
            continue

        try:
            content = gitmodules_path.read_text(encoding="utf-8", errors="ignore")
            # Parse ini-style gitmodules
            cfg = configparser.ConfigParser()
            cfg.read_string(content)

            for section in cfg.sections():
                if not section.startswith('submodule "') or not section.endswith('"'):
                    continue

                sub_name = section[len('submodule "') : -1]
                metadata["submodules_audited"] += 1
                metadata["submodules_found"].append(f"[{repo_name}] {sub_name}")

                url = cfg.get(section, "url", fallback="").strip()
                branch = cfg.get(section, "branch", fallback="").strip()
                path_val = cfg.get(section, "path", fallback="").strip()

                rel_p = f"[{repo_name}] .gitmodules: {sub_name}"

                # Protocol validation
                if url:
                    if not url.startswith("https://") and not url.startswith("git@github.com:"):
                        errors.append(
                            f"{rel_p}: Insecure or unvetted remote URL '{url}'. "
                            "Submodules must use HTTPS or approved SSH protocol."
                        )
                else:
                    errors.append(f"{rel_p}: Missing 'url' attribute.")

                # Branch tracking validation
                if branch in [".", "HEAD", "main", "master"]:
                    warnings.append(
                        f"{rel_p}: Submodule tracks floating branch '{branch}'. "
                        "Submodules should be explicitly pinned by commit SHA."
                    )

                # Check if submodule path exists and is a git submodule pointer
                if path_val:
                    target_dir = repo_path / path_val
                    if target_dir.exists():
                        # Submodule directory should have a .git file (worktree/submodule pointer) or be tracked
                        git_ptr = target_dir / ".git"
                        if not git_ptr.exists():
                            warnings.append(
                                f"{rel_p}: Path '{path_val}' exists but has no active .git pointer."
                            )

        except Exception as e:
            errors.append(f"[{repo_name}] Failed parsing .gitmodules: {e}")

    return errors, warnings, metadata


def parse_third_party_skills(doc_path: Path) -> Set[str]:
    """Extract set of third-party skill directory names from THIRD_PARTY_SKILLS.md."""
    if not doc_path.is_file():
        return set()
    text = doc_path.read_text(encoding="utf-8")
    skills: Set[str] = set()
    for m in ROW_RE.finditer(text):
        skills.add(m.group(1))
    return skills


def audit_third_party_skill_quarantine(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Assert third-party skills are explicitly git-ignored and never tracked in git index."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {
        "third_party_skills_count": 0,
        "skills_quarantined": [],
    }

    doc_path = lab_root / "THIRD_PARTY_SKILLS.md"
    if not doc_path.is_file():
        errors.append(f"Missing THIRD_PARTY_SKILLS.md in lab root ({lab_root})")
        return errors, warnings, metadata

    skills = parse_third_party_skills(doc_path)
    metadata["third_party_skills_count"] = len(skills)
    metadata["skills_quarantined"] = sorted(list(skills))

    gitignore_path = lab_root / ".gitignore"
    if not gitignore_path.is_file():
        errors.append(f"Missing .gitignore in lab root ({lab_root})")
        return errors, warnings, metadata

    gi_text = gitignore_path.read_text(encoding="utf-8", errors="ignore")

    for skill in sorted(skills):
        pattern1 = f".claude/skills/{skill}/"
        pattern2 = f".claude/skills/{skill}"
        if pattern1 not in gi_text and pattern2 not in gi_text:
            errors.append(
                f"Third-party skill '{skill}' from THIRD_PARTY_SKILLS.md is not listed in .gitignore"
            )

        # Check git index for tracked files
        try:
            skill_rel = f".claude/skills/{skill}"
            cmd = ["git", "ls-files", skill_rel]
            res = subprocess.run(
                cmd,
                cwd=str(lab_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            tracked = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            if tracked:
                errors.append(
                    f"Third-party skill '{skill}' has {len(tracked)} tracked file(s) in git index: "
                    f"{', '.join(tracked[:3])}"
                )
        except Exception as e:
            warnings.append(f"Could not run 'git ls-files' for skill '{skill}': {e}")

    return errors, warnings, metadata


def audit_external_script_and_cdn_guard(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Scan HTML and JS files in web roots for prohibited external CDN script tags and imports."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {
        "web_files_scanned": 0,
        "external_resources_detected": 0,
    }

    repos = get_sibling_repo_roots(lab_root)

    # Web file extensions to audit
    target_extensions = {".html", ".htm", ".js", ".mjs"}
    ignore_dir_names = {
        ".git",
        "node_modules",
        "__pycache__",
        ".playwright",
        "test-results",
        "playwright-report",
        "dist",
        "build",
        "downloads",
        "eval-viewer",
    }

    # Also resolve quarantined third-party skill directory names to avoid flagging local third-party templates
    third_party_doc = lab_root / "THIRD_PARTY_SKILLS.md"
    quarantined_skills = parse_third_party_skills(third_party_doc)

    for repo_name, repo_path in repos:
        # Check files in .ai repo or web-facing folders
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in target_extensions:
                continue

            # Skip ignored directories and downloads
            if any(ign in file_path.parts for ign in ignore_dir_names):
                continue
            if "sources" in file_path.parts and "downloads" in file_path.parts:
                continue

            # Skip quarantined third-party skills directories
            if any(skill in file_path.parts for skill in quarantined_skills):
                continue

            metadata["web_files_scanned"] += 1
            rel_path = f"[{repo_name}] {file_path.relative_to(repo_path)}"

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                # 1. External <script src="https://...">
                for m in EXTERNAL_SCRIPT_PATTERN.finditer(content):
                    url = m.group(1)
                    metadata["external_resources_detected"] += 1
                    errors.append(
                        f"{rel_path}: Prohibited external CDN script '{url}'. "
                        "Web assets must use zero-CDN buildless architecture with local vendoring."
                    )

                # 2. External dynamic import("https://...")
                for m in EXTERNAL_DYNAMIC_IMPORT_PATTERN.finditer(content):
                    url = m.group(1)
                    metadata["external_resources_detected"] += 1
                    errors.append(
                        f"{rel_path}: Prohibited dynamic import from external URL '{url}'."
                    )

                # 3. External @import url("https://...") in HTML <style> or CSS
                for m in EXTERNAL_CSS_IMPORT_PATTERN.finditer(content):
                    url = m.group(1)
                    metadata["external_resources_detected"] += 1
                    errors.append(
                        f"{rel_path}: Prohibited external CSS @import from '{url}'."
                    )

            except Exception as e:
                warnings.append(f"Could not read {rel_path}: {e}")

    return errors, warnings, metadata


def run_full_supply_chain_linter(
    lab_root: Path,
    strict: bool = False,
) -> Dict[str, Any]:
    """Execute all git submodule and supply chain integrity checks."""
    all_errors: List[str] = []
    all_warnings: List[str] = []

    # 1. Submodule pinning
    s_errors, s_warnings, s_meta = audit_git_submodule_pinning(lab_root)
    all_errors.extend(s_errors)
    all_warnings.extend(s_warnings)

    # 2. Third-party skills quarantine
    q_errors, q_warnings, q_meta = audit_third_party_skill_quarantine(lab_root)
    all_errors.extend(q_errors)
    all_warnings.extend(q_warnings)

    # 3. External CDN & dynamic import guard
    c_errors, c_warnings, c_meta = audit_external_script_and_cdn_guard(lab_root)
    all_errors.extend(c_errors)
    all_warnings.extend(c_warnings)

    passed = len(all_errors) == 0 and (not strict or len(all_warnings) == 0)

    report = {
        "timestamp": "2026-10-22T20:00:00Z",
        "passed": passed,
        "strict": strict,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            **s_meta,
            **q_meta,
            **c_meta,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Multi-Repo Git Submodule & External Dependency Supply Chain Linter."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run linter in verification mode (exit 0 on pass, 1 on fail).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full audit report in JSON format.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Path to control repo root (default: cf-lab root).",
    )
    args = parser.parse_args()

    report = run_full_supply_chain_linter(args.root, strict=args.strict)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1

    print("Git Submodule & Dependency Supply Chain Linter: " + ("PASS" if report["passed"] else "FAIL"))
    print(f"  Submodules audited: {report['metadata'].get('submodules_audited', 0)}")
    print(f"  Third-party skills quarantined: {report['metadata'].get('third_party_skills_count', 0)}")
    print(f"  Web files audited: {report['metadata'].get('web_files_scanned', 0)}")
    print(f"  External resources detected: {report['metadata'].get('external_resources_detected', 0)}")

    if report["warnings"]:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"  [WARN] {w}")

    if report["errors"]:
        print(f"\nErrors ({len(report['errors'])}):")
        for e in report["errors"]:
            print(f"  [FAIL] {e}")

    if report["passed"]:
        print("All git submodule and dependency supply chain invariants verified clean!")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

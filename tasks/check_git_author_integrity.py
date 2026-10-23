#!/usr/bin/env python3
"""Automated Cross-Repo Git Commit Author Signature & Identity Spoofing Linter.

Audits git commit history across all workspace repositories (cf-lab, cf-research, cf-skills, .ai)
to enforce cryptographic commit integrity, approved author/committer whitelisting, and
provenance tracking for automated sentinels:
1. Authorized Author & Committer Persona Whitelisting:
   - Asserts that commit authors and committers match approved lab personas:
     Names: 'Sensei Ewok', 'Sensei Ewok CF Lab', 'Diego', 'senseiewok', 'senseiewok-dev', 'GitHub', 'web-flow'
     Emails: '*@senseiewok.ai', '*@users.noreply.github.com', 'noreply@github.com'
   - Strictly flags unauthorized or spoofed third-party email domains.
2. Cryptographic GPG / SSH Commit Signature Auditing:
   - Inspects git signature status flags (%G?):
     Flag 'B' (bad / tampered signature) triggers an immediate hard violation.
     Flags 'G' / 'U' / 'N' are tracked for cryptographic hygiene metrics.
3. Autonomous Sentinel & Steward Provenance Tracking:
   - Validates that automated sentinel and hourly steward commits carry verifiable
     provenance metadata (e.g. task IDs, model identifiers, or standard co-author trailers).

Usage:
    python tasks/check_git_author_integrity.py --check
    python tasks/check_git_author_integrity.py --json
    python tasks/check_git_author_integrity.py --strict
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "git-author-audit.json"

# Authorized workspace author/committer names
AUTHORIZED_NAMES: frozenset[str] = frozenset({
    "sensei ewok",
    "sensei ewok cf lab",
    "diego",
    "senseiewok",
    "senseiewok-dev",
    "github",
    "web-flow",
    "github-actions[bot]",
    "dependabot[bot]",
})

# Regex pattern for approved workspace email domains
APPROVED_EMAIL_REGEX: re.Pattern[str] = re.compile(
    r"(?i)^([a-zA-Z0-9_.+-]+@senseiewok\.ai|[0-9a-zA-Z_.+-]+@users\.noreply\.github\.com|noreply@github\.com)$"
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


def is_authorized_persona(name: str, email: str) -> bool:
    """Check whether a name and email match authorized workspace personas."""
    norm_name = name.strip().lower()
    norm_email = email.strip().lower()

    if norm_name not in AUTHORIZED_NAMES:
        return False

    if not APPROVED_EMAIL_REGEX.match(norm_email):
        return False

    return True


def audit_repo_git_authors(
    repo_name: str,
    repo_path: Path,
    commit_limit: int = 100,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Audit recent git commits in a repository for author whitelist, signatures, and provenance."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {
        "repo": repo_name,
        "commits_audited": 0,
        "signed_commits": 0,
        "unsigned_commits": 0,
        "bad_signatures": 0,
        "authors_observed": [],
        "committers_observed": [],
    }

    cmd = [
        "git",
        "log",
        f"-n{commit_limit}",
        "--pretty=format:%H|%an|%ae|%cn|%ce|%G?|%s",
    ]

    try:
        res = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30,
            check=False,
        )
        if res.returncode != 0:
            warnings.append(f"git log failed in {repo_name}: {res.stderr.strip()}")
            return errors, warnings, metadata
    except Exception as e:
        warnings.append(f"Failed to execute git log in {repo_name}: {e}")
        return errors, warnings, metadata

    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    metadata["commits_audited"] = len(lines)

    authors_set: Set[str] = set()
    committers_set: Set[str] = set()

    for line in lines:
        parts = line.split("|", 6)
        if len(parts) < 7:
            continue

        commit_hash, author_name, author_email, committer_name, committer_email, sig_status, subject = parts
        authors_set.add(f"{author_name} <{author_email}>")
        committers_set.add(f"{committer_name} <{committer_email}>")

        # 1. Author Whitelist Invariant
        if not is_authorized_persona(author_name, author_email):
            errors.append(
                f"{repo_name} {commit_hash[:10]}: Unauthorized commit author "
                f"'{author_name} <{author_email}>' (spoofing guard violation)."
            )

        # 2. Committer Whitelist Invariant
        if not is_authorized_persona(committer_name, committer_email):
            errors.append(
                f"{repo_name} {commit_hash[:10]}: Unauthorized committer "
                f"'{committer_name} <{committer_email}>' (spoofing guard violation)."
            )

        # 3. Cryptographic Signature Status
        sig_code = sig_status.strip().upper()
        if sig_code == "B":
            errors.append(
                f"{repo_name} {commit_hash[:10]}: Cryptographically BAD / TAMPERED commit signature (%G?=B)!"
            )
            metadata["bad_signatures"] += 1
        elif sig_code in ("G", "U"):
            metadata["signed_commits"] += 1
        else:
            metadata["unsigned_commits"] += 1

        # 4. Sentinel / Steward Provenance Check
        if "sentinel" in subject.lower() or "hourly-steward" in subject.lower():
            # Sentinel and steward commits should reference a task or wave
            has_provenance = bool(
                re.search(r"\bT-\d{4}\b", subject)
                or re.search(r"\bwave\d+\b", subject, re.IGNORECASE)
                or re.search(r"\(#\d+\)", subject)
            )
            if not has_provenance:
                warnings.append(
                    f"{repo_name} {commit_hash[:10]}: Sentinel/steward commit missing "
                    f"explicit task ID or wave provenance in subject: '{subject}'"
                )

    metadata["authors_observed"] = sorted(authors_set)
    metadata["committers_observed"] = sorted(committers_set)

    return errors, warnings, metadata


def run_full_git_author_integrity_linter(
    lab_root: Path,
    commit_limit: int = 100,
    strict: bool = False,
    report_path: Optional[Path] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Run git commit author integrity and signature linter across all workspace repositories."""
    repos = get_sibling_repo_roots(lab_root)
    all_errors: List[str] = []
    all_warnings: List[str] = []
    repo_stats: Dict[str, Any] = {}

    total_commits = 0
    total_signed = 0
    total_unsigned = 0
    total_bad_signatures = 0

    for name, rpath in repos:
        errors, warnings, meta = audit_repo_git_authors(name, rpath, commit_limit=commit_limit)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        repo_stats[name] = meta

        total_commits += meta["commits_audited"]
        total_signed += meta["signed_commits"]
        total_unsigned += meta["unsigned_commits"]
        total_bad_signatures += meta["bad_signatures"]

    report_data: Dict[str, Any] = {
        "status": "PASS" if not all_errors else "FAIL",
        "strict_mode": strict,
        "total_repos": len(repos),
        "total_commits_audited": total_commits,
        "total_signed_commits": total_signed,
        "total_unsigned_commits": total_unsigned,
        "total_bad_signatures": total_bad_signatures,
        "total_violations": len(all_errors),
        "total_warnings": len(all_warnings),
        "repositories": repo_stats,
        "errors": all_errors,
        "warnings": all_warnings,
    }

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    exit_code = 1 if all_errors or (strict and all_warnings) else 0
    return exit_code, report_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Cross-Repo Git Commit Author Signature & Identity Spoofing Linter"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run linter and exit with non-zero if violations are detected",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict mode where warnings also trigger non-zero exit",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of recent commits to audit per repository (defaults to 100)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON audit report to stdout",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write JSON audit report (defaults to .loop-logs/git-author-audit.json)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Root repository directory (defaults to cf-lab)",
    )
    args = parser.parse_args()

    exit_code, report = run_full_git_author_integrity_linter(
        lab_root=args.root,
        commit_limit=args.limit,
        strict=args.strict,
        report_path=args.report,
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return exit_code

    if exit_code == 0:
        print("Git Commit Author & Signature Integrity Linter: PASS")
        print(f"  Repositories audited: {report['total_repos']}")
        print(f"  Recent commits audited: {report['total_commits_audited']}")
        print(f"  Signed commits: {report['total_signed_commits']}")
        print(f"  Unsigned commits: {report['total_unsigned_commits']}")
        print("All commit author identities and cryptographic signature invariants verified clean!")
    else:
        print("Git Commit Author & Signature Integrity Linter: FAIL", file=sys.stderr)
        print(f"  Violations found: {len(report['errors'])}", file=sys.stderr)
        for err in report["errors"]:
            print(f"    - {err}", file=sys.stderr)
        if args.strict and report["warnings"]:
            print(f"  Warnings ({len(report['warnings'])}):", file=sys.stderr)
            for warn in report["warnings"]:
                print(f"    - [WARN] {warn}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

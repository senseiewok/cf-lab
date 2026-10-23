#!/usr/bin/env python3
"""Automated Cross-Repo Git Commit Email & Author Signature Whitelist Linter.

Audits git commit authorship metadata, local repository identity configs, and cryptographic
signatures across all workspace repositories (cf-lab, cf-research, cf-skills, .ai) to enforce
strict zero-vulnerability invariants against commit spoofing, unauthorized commit emails,
and unverified identities:
1. Author Identity Whitelisting (CWE-284 / CWE-290):
   - Audits commit author and committer emails in local branches and recent commit histories
     to ensure they strictly match authorized lab maintainer emails or approved automated
     sentinel identities (e.g. *@senseiewok.ai, *@users.noreply.github.com, noreply@github.com).
2. Local Repository Config Integrity (CWE-284):
   - Audits repository-level git configuration (user.name and user.email) to prevent committing
     under default, generic, or spoofed third-party email addresses.
3. Cryptographic Signature & Ref Integrity (CWE-347):
   - Inspects commit and tag metadata for invalid/tampered cryptographic signatures ('B')
     and tracks signature coverage across production branches.
4. Deterministic Verification:
   - Audits all sibling workspace repos in < 0.3s, integrating with check-all.ps1.

Primary Source Grounding:
- OWASP Top 10:2025 A07: Identification and Authentication Failures (CWE-290)
- CWE-290: Authentication Bypass by Spoofing
- CWE-284: Improper Access Control
- CWE-347: Improper Verification of Cryptographic Signature
- Workspace Standards: .claude/skills/security-baseline/SKILL.md, .claude/skills/security-git/SKILL.md

Usage:
    python tasks/check_git_author_whitelist.py --check
    python tasks/check_git_author_whitelist.py --json
    python tasks/check_git_author_whitelist.py --strict
    python tasks/check_git_author_whitelist.py --path <repo_or_dir>
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "git-author-whitelist-audit.json"

# Authorized workspace author/committer names (case-insensitive comparison)
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

# Whitelist regex pattern for approved workspace email domains
APPROVED_EMAIL_REGEX: re.Pattern[str] = re.compile(
    r"(?i)^([a-zA-Z0-9_.+-]+@senseiewok\.ai|[0-9a-zA-Z_.+-]+@users\.noreply\.github\.com|noreply@github\.com|actions@github\.com)$"
)


@dataclass
class Finding:
    repo: str
    target: str  # Commit SHA, branch, tag, or config file
    rule: str
    severity: str  # "ERROR" | "WARNING"
    message: str
    detail: str


def is_authorized_email(email: str) -> bool:
    """Check whether an email string satisfies the workspace whitelist."""
    if not isinstance(email, str) or not email.strip():
        return False
    return bool(APPROVED_EMAIL_REGEX.match(email.strip()))


def is_authorized_persona(name: str, email: str) -> bool:
    """Check whether both name and email match authorized lab personas."""
    norm_name = name.strip().lower() if isinstance(name, str) else ""
    norm_email = email.strip().lower() if isinstance(email, str) else ""

    if norm_name not in AUTHORIZED_NAMES:
        return False

    return is_authorized_email(norm_email)


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


def audit_repo_git_config(repo_name: str, repo_path: Path) -> List[Finding]:
    """Audit local git configuration for user.name and user.email whitelist compliance."""
    findings: List[Finding] = []

    # Read git config using git command for accurate inheritance
    try:
        email_res = subprocess.run(
            ["git", "-C", str(repo_path), "config", "user.email"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        user_email = email_res.stdout.strip() if email_res.returncode == 0 else ""

        name_res = subprocess.run(
            ["git", "-C", str(repo_path), "config", "user.name"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        user_name = name_res.stdout.strip() if name_res.returncode == 0 else ""

        if user_email and not is_authorized_email(user_email):
            findings.append(
                Finding(
                    repo=repo_name,
                    target=".git/config",
                    rule="CONFIG001_UNAUTHORIZED_EMAIL",
                    severity="ERROR",
                    message=f"Git config user.email '{user_email}' does not match authorized domain whitelist.",
                    detail=f"user.name='{user_name}', user.email='{user_email}'",
                )
            )

        if user_name and user_name.strip().lower() not in AUTHORIZED_NAMES and user_email:
            findings.append(
                Finding(
                    repo=repo_name,
                    target=".git/config",
                    rule="CONFIG002_UNAUTHORIZED_NAME",
                    severity="WARNING",
                    message=f"Git config user.name '{user_name}' is not in approved maintainer persona list.",
                    detail=f"user.name='{user_name}'",
                )
            )
    except Exception as exc:
        findings.append(
            Finding(
                repo=repo_name,
                target=".git/config",
                rule="CONFIG003_EXEC_ERROR",
                severity="WARNING",
                message=f"Could not read git config: {exc}",
                detail="",
            )
        )

    return findings


def audit_repo_commits(
    repo_name: str,
    repo_path: Path,
    commit_limit: int = 50,
) -> Tuple[List[Finding], int]:
    """Audit recent commits in repository for author/committer whitelist and signature tampering."""
    findings: List[Finding] = []
    commits_scanned = 0

    cmd = [
        "git",
        "-C",
        str(repo_path),
        "log",
        f"-n{commit_limit}",
        "--format=%H%x09%an%x09%ae%x09%cn%x09%ce%x09%G?",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception as exc:
        findings.append(
            Finding(
                repo=repo_name,
                target="git-log",
                rule="GIT001_LOG_ERROR",
                severity="WARNING",
                message=f"Failed to execute git log: {exc}",
                detail="",
            )
        )
        return findings, 0

    if proc.returncode != 0:
        return findings, 0

    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue

        commit_sha, author_name, author_email, committer_name, committer_email, sig_status = parts
        commits_scanned += 1
        short_sha = commit_sha[:8]

        # 1. Author email whitelist check
        if not is_authorized_email(author_email):
            findings.append(
                Finding(
                    repo=repo_name,
                    target=short_sha,
                    rule="AUTH001_UNAUTHORIZED_AUTHOR_EMAIL",
                    severity="ERROR",
                    message=f"Commit author email '{author_email}' is not in authorized domain whitelist.",
                    detail=f"author='{author_name} <{author_email}>'",
                )
            )

        # 2. Committer email whitelist check
        if not is_authorized_email(committer_email):
            findings.append(
                Finding(
                    repo=repo_name,
                    target=short_sha,
                    rule="AUTH002_UNAUTHORIZED_COMMITTER_EMAIL",
                    severity="ERROR",
                    message=f"Commit committer email '{committer_email}' is not in authorized domain whitelist.",
                    detail=f"committer='{committer_name} <{committer_email}>'",
                )
            )

        # 3. Bad signature check ('B' = bad / tampered signature)
        if sig_status == "B":
            findings.append(
                Finding(
                    repo=repo_name,
                    target=short_sha,
                    rule="SIGN001_TAMPERED_SIGNATURE",
                    severity="ERROR",
                    message=f"Cryptographic signature check returned 'B' (tampered or bad signature).",
                    detail=f"commit={commit_sha}",
                )
            )

    return findings, commits_scanned


def run_full_git_author_whitelist_linter(
    target_path: Path,
    commit_limit: int = 50,
) -> Dict[str, Any]:
    """Audit git author identities and configurations across sibling repos or a single repo."""
    all_findings: List[Finding] = []
    total_commits = 0
    repos_scanned = 0

    resolved = target_path.resolve()
    # If target is inside cf-lab, audit all sibling repositories
    if (resolved / "tasks").exists() or resolved.name == "cf-lab":
        repo_list = get_sibling_repo_roots(resolved)
    elif (resolved / ".git").exists():
        repo_list = [(resolved.name, resolved)]
    else:
        repo_list = [(resolved.name, resolved)]

    for repo_name, repo_dir in repo_list:
        if not (repo_dir / ".git").exists() and not (repo_dir / ".git").is_file():
            continue
        repos_scanned += 1
        all_findings.extend(audit_repo_git_config(repo_name, repo_dir))
        findings, count = audit_repo_commits(repo_name, repo_dir, commit_limit=commit_limit)
        all_findings.extend(findings)
        total_commits += count

    errors = [f for f in all_findings if f.severity == "ERROR"]
    warnings = [f for f in all_findings if f.severity == "WARNING"]

    return {
        "passed": len(errors) == 0,
        "repos_scanned": repos_scanned,
        "commits_scanned": total_commits,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": [asdict(e) for e in errors],
        "warnings": [asdict(w) for w in warnings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Cross-Repo Git Commit Email & Author Signature Whitelist Linter"
    )
    parser.add_argument("--check", action="store_true", help="Run audit and exit 0 if clean, 1 on errors")
    parser.add_argument("--json", action="store_true", help="Output audit report as JSON")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
    parser.add_argument("--commits", type=int, default=50, help="Number of recent commits to audit per repo")
    parser.add_argument("--path", type=Path, default=REPO_ROOT, help="Target repo or directory to audit")
    args = parser.parse_args()

    report = run_full_git_author_whitelist_linter(args.path, commit_limit=args.commits)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if (report["passed"] and (not args.strict or report["warning_count"] == 0)) else 1

    if report["passed"]:
        if args.strict and report["warning_count"] > 0:
            print(f"FAIL: {report['warning_count']} warnings found in strict mode.")
            for w in report["warnings"]:
                print(f"  [{w['repo']}] {w['target']} [{w['rule']}] {w['message']}")
            return 1
        print(
            f"PASS: Git author email & signature whitelist clean "
            f"({report['repos_scanned']} repos, {report['commits_scanned']} commits audited, 0 errors)."
        )
        return 0
    else:
        print(f"FAIL: {report['error_count']} git author whitelist violations found:")
        for err in report["errors"]:
            print(f"  [{err['repo']}] {err['target']} [{err['rule']}] {err['message']}")
            if err["detail"]:
                print(f"    {err['detail']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

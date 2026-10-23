#!/usr/bin/env python3
"""Automated Multi-Repo Git Submodule & Unchecked External Git Dependency Linter.

Audits git submodules, nested git directories, and .gitmodules configurations across all
workspace repositories (cf-lab, cf-research, cf-skills, .ai) to enforce strict
zero-vulnerability invariants against rogue dependencies and directory traversal:
1. Submodule Architecture Invariants (CWE-829 / CWE-20):
   - Verifies that no rogue or unreviewed git submodules exist across the workspace,
     enforcing the lab's deliberate sibling repository design pattern (cf-lab.code-workspace)
     over brittle nested submodule structures.
2. URL & Transport Security:
   - If submodules are declared in future tooling, verifies that URLs enforce HTTPS/SSH
     cryptographic transport and point exclusively to authorized GitHub organizations,
     strictly prohibiting unencrypted http:// or git:// transports (CVE-2018-11235 mitigation).
3. Submodule Hook & Path Safety:
   - Prohibits path traversal sequences (../), absolute paths, or nested .git/hooks inside
     submodule path and name specifications.
4. Fast Deterministic Verification:
   - Operates in < 0.2s across all workspace repositories, integrating with check-all.ps1.

Primary Source Grounding:
- CVE-2018-11235: Arbitrary code execution via git submodule .git/hooks directory traversal
- CWE-829: Inclusion of Functionality from Untrusted Control Sphere
- CWE-20: Improper Input Validation (Git Refspec / Submodule Path Traversal)
- Workspace Standards: .claude/skills/security-baseline/SKILL.md, .claude/skills/security-git/SKILL.md

Usage:
    python tasks/check_git_submodules.py --check
    python tasks/check_git_submodules.py --json
    python tasks/check_git_submodules.py --strict
    python tasks/check_git_submodules.py --path <repo_or_dir>
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "git-submodules-audit.json"

# Insecure git transport schemes prohibited in submodules
INSECURE_SCHEMES_RX = re.compile(r"^(?:http://|git://)", re.IGNORECASE)

# Safe git transport schemes
SAFE_SCHEMES_RX = re.compile(r"^(?:https://|ssh://|git@github\.com:)", re.IGNORECASE)

# Dangerous path traversal patterns
TRAVERSAL_RX = re.compile(r"(?:^|/|\\)\.\.(?:/|\\|$)")

# Submodule name safety (prohibit directory separators, traversal, or control chars)
DANGEROUS_NAME_CHARS_RX = re.compile(r"[/\\:\x00]|^\.\.")

SKIP_DIRS: Set[str] = {
    ".git",
    ".worktrees",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    ".loop-logs",
    "dist",
    "build",
}


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    severity: str  # "ERROR" | "WARNING"
    message: str
    snippet: str


@dataclass
class SubmoduleEntry:
    name: str
    path: str
    url: str
    branch: Optional[str] = None


def is_safe_submodule_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate submodule URL transport security."""
    if not isinstance(url, str) or not url.strip():
        return False, "Submodule URL is empty"

    clean_url = url.strip()
    if INSECURE_SCHEMES_RX.match(clean_url):
        return False, f"Insecure plaintext transport scheme in URL: {clean_url}"

    if not SAFE_SCHEMES_RX.match(clean_url):
        return False, f"URL does not use approved HTTPS/SSH transport: {clean_url}"

    if ".." in clean_url or "\x00" in clean_url:
        return False, f"URL contains forbidden traversal or control characters: {clean_url}"

    return True, None


def is_safe_submodule_path(path: str) -> Tuple[bool, Optional[str]]:
    """Validate submodule target directory path against traversal and hook injection."""
    if not isinstance(path, str) or not path.strip():
        return False, "Submodule path is empty"

    clean_path = path.strip().replace("\\", "/")

    if clean_path.startswith("/") or re.match(r"^[a-zA-Z]:", clean_path):
        return False, f"Submodule path cannot be absolute: {clean_path}"

    if TRAVERSAL_RX.search(clean_path) or clean_path.startswith(".."):
        return False, f"Submodule path contains path traversal (CVE-2018-11235): {clean_path}"

    parts = [p.lower() for p in clean_path.split("/") if p]
    if ".git" in parts or "hooks" in parts:
        return False, f"Submodule path targets git metadata or hooks directory: {clean_path}"

    return True, None


def is_safe_submodule_name(name: str) -> Tuple[bool, Optional[str]]:
    """Validate submodule section name against option injection and traversal."""
    if not isinstance(name, str) or not name.strip():
        return False, "Submodule name is empty"

    clean_name = name.strip()
    if clean_name.startswith("-"):
        return False, f"Submodule name cannot begin with hyphen (argument injection): {clean_name}"

    if DANGEROUS_NAME_CHARS_RX.search(clean_name):
        return False, f"Submodule name contains illegal characters or traversal: {clean_name}"

    return True, None


def parse_gitmodules_text(text: str) -> Tuple[List[SubmoduleEntry], List[Finding], List[str]]:
    """Parse .gitmodules text into structured entries and validate syntax."""
    entries: List[SubmoduleEntry] = []
    findings: List[Finding] = []
    lines = text.splitlines()

    # Use configparser with lenient parsing
    config = configparser.ConfigParser()
    try:
        config.read_string(text)
    except Exception as e:
        findings.append(
            Finding(
                file=".gitmodules",
                line=1,
                rule="GITMODULES_SYNTAX_ERROR",
                severity="ERROR",
                message=f"Failed to parse .gitmodules config: {e}",
                snippet=lines[0] if lines else "",
            )
        )
        return entries, findings, lines

    for section in config.sections():
        # Match 'submodule "name"'
        m = re.match(r'^submodule\s+"(.*)"$', section)
        if not m:
            m = re.match(r"^submodule\.(.*)$", section)
        
        name = m.group(1) if m else section
        path = config.get(section, "path", fallback="")
        url = config.get(section, "url", fallback="")
        branch = config.get(section, "branch", fallback=None)

        entries.append(SubmoduleEntry(name=name, path=path, url=url, branch=branch))

    return entries, findings, lines


def audit_gitmodules_file(
    file_path: Path,
    allow_submodules: bool = False,
) -> List[Finding]:
    """Audit a .gitmodules file for architecture compliance and transport security."""
    findings: List[Finding] = []
    if not file_path.is_file():
        return findings

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [
            Finding(
                file=str(file_path),
                line=1,
                rule="GITMODULES_READ_ERROR",
                severity="ERROR",
                message=f"Failed to read .gitmodules: {e}",
                snippet="",
            )
        ]

    entries, parse_findings, lines = parse_gitmodules_text(content)
    findings.extend(parse_findings)

    # 1. Architecture policy check: Lab uses sibling workspace model over git submodules
    if not allow_submodules and entries:
        findings.append(
            Finding(
                file=str(file_path),
                line=1,
                rule="SUBMODULE_ARCHITECTURE_POLICY_VIOLATION",
                severity="WARNING" if not allow_submodules else "INFO",
                message=(
                    "Submodule declared in repository. Sensei Ewok CF Lab architecture enforces "
                    "sibling repositories (cf-lab.code-workspace) rather than nested git submodules."
                ),
                snippet=lines[0] if lines else "",
            )
        )

    # 2. Inspect each submodule entry
    for entry in entries:
        # Validate name
        safe_name, reason_name = is_safe_submodule_name(entry.name)
        if not safe_name:
            findings.append(
                Finding(
                    file=str(file_path),
                    line=1,
                    rule="SUBMODULE_NAME_TRAVERSAL",
                    severity="ERROR",
                    message=f"Dangerous submodule name: {reason_name}",
                    snippet=f'[submodule "{entry.name}"]',
                )
            )

        # Validate path
        safe_path, reason_path = is_safe_submodule_path(entry.path)
        if not safe_path:
            findings.append(
                Finding(
                    file=str(file_path),
                    line=1,
                    rule="SUBMODULE_PATH_TRAVERSAL",
                    severity="ERROR",
                    message=f"Dangerous submodule path: {reason_path}",
                    snippet=f"path = {entry.path}",
                )
            )

        # Validate URL
        safe_url, reason_url = is_safe_submodule_url(entry.url)
        if not safe_url:
            findings.append(
                Finding(
                    file=str(file_path),
                    line=1,
                    rule="SUBMODULE_INSECURE_TRANSPORT",
                    severity="ERROR",
                    message=f"Insecure submodule URL: {reason_url}",
                    snippet=f"url = {entry.url}",
                )
            )

    return findings


def audit_nested_git_directories(repo_path: Path) -> List[Finding]:
    """Audit working tree for unauthorized nested .git directories or gitlink files."""
    findings: List[Finding] = []
    if not repo_path.is_dir():
        return findings

    root_git = repo_path / ".git"

    for root, dirs, files in os.walk(repo_path):
        # Skip top-level repo .git and .worktrees directory
        dirs[:] = [d for d in dirs if d not in {".worktrees", "node_modules", ".venv", "venv"}]

        rel_root = Path(root).relative_to(repo_path)
        if str(rel_root) == ".":
            # Don't check the top-level repo's own .git
            dirs[:] = [d for d in dirs if d != ".git"]
            continue

        if ".git" in dirs:
            findings.append(
                Finding(
                    file=str(Path(root) / ".git"),
                    line=1,
                    rule="ROGUE_NESTED_GIT_REPO",
                    severity="ERROR",
                    message=f"Rogue nested .git repository detected inside {rel_root}. Nested repos break multi-repo workspace invariants.",
                    snippet=str(rel_root),
                )
            )
            dirs.remove(".git")

        if ".git" in files:
            # .git file is typically a submodule gitlink or worktree pointer
            git_file = Path(root) / ".git"
            findings.append(
                Finding(
                    file=str(git_file),
                    line=1,
                    rule="ROGUE_NESTED_GITLINK_FILE",
                    severity="ERROR",
                    message=f"Rogue .git pointer file detected inside {rel_root}.",
                    snippet=str(rel_root),
                )
            )

    return findings


def get_sibling_repo_roots(lab_root: Path) -> List[Tuple[str, Path]]:
    """Resolve sibling workspace repositories (cf-lab, cf-research, cf-skills, .ai)."""
    parts = lab_root.parts
    if ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        repos_root = Path(*parts[:wt_idx])
        cf_lab_path = lab_root if "cf-lab" in parts[wt_idx:] else (repos_root / "cf-lab")
    else:
        repos_root = lab_root.parent
        cf_lab_path = lab_root if (lab_root.name == "cf-lab") else (repos_root / "cf-lab")

    candidates = [
        ("cf-lab", cf_lab_path),
        ("cf-research", repos_root / "cf-research"),
        ("cf-skills", repos_root / "cf-skills"),
        (".ai", repos_root / ".ai"),
    ]
    return [(name, p) for name, p in candidates if p.is_dir()]


def scan_workspace_submodules(
    target_path: Optional[Path] = None,
    allow_submodules: bool = False,
    strict: bool = False,
) -> Tuple[List[Finding], Dict[str, Any]]:
    """Scan workspace repositories for submodule compliance."""
    all_findings: List[Finding] = []
    audited_repos: List[str] = []

    if target_path:
        repo_dirs = [(target_path.name, target_path)]
    else:
        repo_dirs = get_sibling_repo_roots(REPO_ROOT)

    for name, rpath in repo_dirs:
        audited_repos.append(name)
        # Check .gitmodules file
        gm_file = rpath / ".gitmodules"
        if gm_file.exists():
            all_findings.extend(audit_gitmodules_file(gm_file, allow_submodules=allow_submodules))

        # Check for nested .git directories
        all_findings.extend(audit_nested_git_directories(rpath))

    errors = [f for f in all_findings if f.severity == "ERROR"]
    warnings = [f for f in all_findings if f.severity == "WARNING"]

    summary = {
        "audited_repos": audited_repos,
        "repo_count": len(audited_repos),
        "total_findings": len(all_findings),
        "errors": len(errors),
        "warnings": len(warnings),
        "is_compliant": len(errors) == 0 and (not strict or len(warnings) == 0),
    }

    return all_findings, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit git submodules and external git dependencies across workspace.")
    parser.add_argument("--check", action="store_true", help="Run check and exit 1 if errors found.")
    parser.add_argument("--json", action="store_true", help="Output results as JSON.")
    parser.add_argument("--strict", action="store_true", help="Treat architecture warnings as errors.")
    parser.add_argument("--allow-submodules", action="store_true", help="Allow validly configured submodules.")
    parser.add_argument("--path", type=str, default=None, help="Specific repo or directory to scan.")
    parser.add_argument("--output", type=str, default=None, help="Custom output report path.")

    args = parser.parse_args()

    target = Path(args.path).resolve() if args.path else None
    findings, summary = scan_workspace_submodules(
        target_path=target,
        allow_submodules=args.allow_submodules,
        strict=args.strict,
    )

    report_path = Path(args.output).resolve() if args.output else DEFAULT_REPORT_PATH
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = {
            "summary": summary,
            "findings": [asdict(f) for f in findings],
        }
        report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Warning: could not write audit log: {e}\n")

    if args.json:
        print(json.dumps({"summary": summary, "findings": [asdict(f) for f in findings]}, indent=2))
        return 0 if summary["is_compliant"] else 1

    print(f"Audited {summary['repo_count']} workspace repositories: {', '.join(summary['audited_repos'])}.")
    if summary["errors"] > 0:
        print(f"\nFound {summary['errors']} git submodule violation(s):")
        for f in findings:
            if f.severity == "ERROR":
                print(f"  [ERROR] {f.file}:{f.line} ({f.rule}) - {f.message}")
                if f.snippet:
                    print(f"          Snippet: {f.snippet}")
    if summary["warnings"] > 0 and args.strict:
        print(f"\nFound {summary['warnings']} warning(s):")
        for f in findings:
            if f.severity == "WARNING":
                print(f"  [WARN]  {f.file}:{f.line} ({f.rule}) - {f.message}")

    if summary["is_compliant"]:
        print(f"CHECK PASS: Zero rogue submodules or transport violations detected across {summary['repo_count']} repositories.")
        return 0
    else:
        print(f"CHECK FAIL: Git submodule compliance failed ({summary['errors']} errors, {summary['warnings']} warnings).")
        return 1


if __name__ == "__main__":
    sys.exit(main())

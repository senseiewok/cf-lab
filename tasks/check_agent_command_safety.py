#!/usr/bin/env python3
"""Automated Multi-Repo Agent Command Quoting Safety & Path Linter.

Detects command quoting hazards, PowerShell parser traps, hardcoded user paths,
and fragile sibling directory references across sentinel prompts, task scripts,
and agent skills.

Mined from 43 session forensic audits in .loop-logs/session-error-digest.json
(tasks/audit_session_errors.py).

Usage:
    python tasks/check_agent_command_safety.py [--check] [--json] [--path PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Unescaped nested quote hazard in inline python or pwsh strings:
# e.g. python -c "import foo; bar = "baz"" or pwsh -Command "..."
NESTED_DOUBLE_QUOTE_RX = re.compile(
    r'(?:python(?:\.exe)?\s+-c|pwsh(?:\.exe)?\s+-(?:Command|c))\s+"([^"\n]*"[^"\n]*)"',
    re.I,
)

# Hardcoded user/home directory paths that should never be in tracked files:
HARDCODED_USER_DIR_RX = re.compile(
    r'(?:[cC]:\\Users\\[a-zA-Z0-9_\.]+|/(?:home|Users)/[a-zA-Z0-9_\.]+)',
    re.I,
)

# Check for raw cd / Set-Location without checking error or using standard workspace anchors:
FRAGILE_PARENT_PATH_RX = re.compile(
    r'\b(?:cd|Set-Location)\s+["\']?\.\./\.\./\.\./',
    re.I,
)

WATCH_DIRS = [
    REPO_ROOT / "tasks",
    REPO_ROOT / ".claude" / "skills",
]

RELEVANT_EXTENSIONS = {".ps1", ".py", ".md", ".sh", ".cmd"}


def _format_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def lint_file_content(path: Path, content: str) -> list[dict[str, any]]:
    """Scan file content for command quoting and path safety violations."""
    findings = []
    lines = content.splitlines()
    rel_path = _format_rel(path)

    for idx, line in enumerate(lines, start=1):
        # 1. Hardcoded user profile paths
        # Skip this file itself and historical logs/specs/canaries that explicitly test or document it
        if "check_agent_command_safety" not in path.name and "canary" not in path.name:
            match_user = HARDCODED_USER_DIR_RX.search(line)
            if match_user and not line.strip().startswith("#"):
                findings.append({
                    "file": rel_path,
                    "line": idx,
                    "code": "HARDCODED_USER_DIR",
                    "message": f"Hardcoded machine/user home path detected: {match_user.group(0)}",
                    "snippet": line.strip()[:100],
                })

        # 2. Fragile deep relative cd navigation
        if path.suffix in {".ps1", ".sh", ".cmd", ".md"}:
            match_nav = FRAGILE_PARENT_PATH_RX.search(line)
            if match_nav:
                findings.append({
                    "file": rel_path,
                    "line": idx,
                    "code": "FRAGILE_PARENT_CD",
                    "message": "Fragile deep relative directory traversal (../../../) without root anchor",
                    "snippet": line.strip()[:100],
                })

        # 3. Unescaped nested double quote hazard in command string
        if path.suffix in {".ps1", ".md", ".sh"}:
            match_quotes = NESTED_DOUBLE_QUOTE_RX.search(line)
            if match_quotes:
                findings.append({
                    "file": rel_path,
                    "line": idx,
                    "code": "NESTED_DOUBLE_QUOTES",
                    "message": "Potential unescaped nested double quotes in inline command",
                    "snippet": line.strip()[:100],
                })

    return findings


def scan_workspace(root_dir: Path | None = None) -> list[dict[str, any]]:
    """Scan relevant workspace directories for agent command safety hazards."""
    root = root_dir or REPO_ROOT
    all_findings = []

    for watch_dir in WATCH_DIRS:
        if not watch_dir.is_dir():
            continue
        for file_path in watch_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix not in RELEVANT_EXTENSIONS:
                continue
            # Skip git, venv, and binary artifacts
            if any(part.startswith(".") and part not in {".claude"} for part in file_path.parts):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            findings = lint_file_content(file_path, content)
            all_findings.extend(findings)

    return all_findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit non-zero if safety hazards are detected")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    parser.add_argument("--path", type=Path, help="Scan a specific file or directory instead of workspace")
    args = parser.parse_args()

    if args.path:
        target = args.path.resolve()
        if target.is_file():
            findings = lint_file_content(target, target.read_text(encoding="utf-8", errors="replace"))
        else:
            findings = scan_workspace(target)
    else:
        findings = scan_workspace()

    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings}, indent=2))
    else:
        print(f"Agent Command Safety Scan: {len(findings)} issue(s) detected across scanned assets.")
        for f in findings:
            print(f"  [{f['code']}] {f['file']}:{f['line']}: {f['message']}")
            print(f"    --> {f['snippet']}")

    if args.check and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

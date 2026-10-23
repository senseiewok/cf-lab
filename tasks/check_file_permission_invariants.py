#!/usr/bin/env python3
"""Automated Cross-Repo File Permission & Executable Bit Invariant Linter.

Audits git index file mode bits (100644 vs 100755) and file permissions across all
workspace repositories (cf-lab, cf-research, cf-skills, .ai) to enforce:
1. Strict Non-Executable Data File Invariant:
   - Asserts that static assets, documentation, configuration files, and datasets
     (.json, .md, .yaml, .yml, .txt, .html, .css, .png, .svg, .toml, .csv, etc.)
     are strictly non-executable (100644) in the git index.
2. Script Shebang & Executable Bit Parity:
   - Verifies that any file with executable bit (100755) is an intended script
     with a valid shebang line (e.g. #!/usr/bin/env ... or #!/bin/sh).
3. Automated Git Index Mode Verification:
   - Uses `git ls-files -s` directly to inspect git object tree modes, catching
     accidental chmod permission flips across Windows/macOS/Linux checkouts.

Usage:
    python tasks/check_file_permission_invariants.py --check
    python tasks/check_file_permission_invariants.py --json
    python tasks/check_file_permission_invariants.py --strict
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
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "file-permission-audit.json"

VALID_GIT_MODES: frozenset[str] = frozenset({
    "100644",  # Regular non-executable file
    "100755",  # Executable file
    "120000",  # Symbolic link
    "160000",  # Gitlink / submodule
})

# Extensions that must NEVER have the executable bit (100755) set in git index
STRICT_NON_EXECUTABLE_EXTENSIONS: frozenset[str] = frozenset({
    ".json",
    ".md",
    ".markdown",
    ".yaml",
    ".yml",
    ".txt",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".png",
    ".svg",
    ".ico",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".toml",
    ".ini",
    ".cfg",
    ".xml",
    ".csv",
    ".tsv",
    ".diff",
    ".patch",
    ".pdf",
    ".lock",
    ".example",
})

SHEBANG_PATTERN = re.compile(r"^#!\s*([^\r\n]+)")


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


def parse_git_ls_files(output: str) -> List[Dict[str, str]]:
    """Parse output lines from `git ls-files -s`.

    Format per line: <mode> <sha> <stage>\\t<path>
    """
    entries: List[Dict[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        metadata_str, filepath = parts[0], parts[1]
        meta_tokens = metadata_str.split()
        if len(meta_tokens) >= 3:
            entries.append({
                "mode": meta_tokens[0],
                "sha": meta_tokens[1],
                "stage": meta_tokens[2],
                "path": filepath,
            })
    return entries


def audit_git_index_modes(
    repo_name: str,
    repo_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Audit git index modes in a repository for non-executable and executable invariants."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {
        "repo": repo_name,
        "total_files": 0,
        "mode_counts": {},
        "executable_files": [],
        "non_executable_verified": 0,
    }

    try:
        proc = subprocess.run(
            ["git", "ls-files", "-s"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        warnings.append(f"Could not run git ls-files in {repo_root}: {e}")
        return errors, warnings, metadata

    entries = parse_git_ls_files(proc.stdout)
    metadata["total_files"] = len(entries)

    mode_counts: Dict[str, int] = {}
    for entry in entries:
        mode = entry["mode"]
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        rel_path = entry["path"]
        ext = Path(rel_path).suffix.lower()

        # Invariant 1: Valid Git mode
        if mode not in VALID_GIT_MODES:
            errors.append(
                f"[{repo_name}] Invalid git file mode '{mode}' for {rel_path}."
            )
            continue

        # Invariant 2: Non-executable data files MUST NOT have 100755 mode
        if ext in STRICT_NON_EXECUTABLE_EXTENSIONS:
            metadata["non_executable_verified"] += 1
            if mode == "100755":
                errors.append(
                    f"[{repo_name}] Strict non-executable invariant violation: data file "
                    f"'{rel_path}' has executable mode 100755 (must be 100644)."
                )

        # Invariant 3: Executable scripts (100755) should have valid shebangs
        if mode == "100755":
            metadata["executable_files"].append(rel_path)
            full_path = repo_root / rel_path
            if full_path.is_file():
                try:
                    first_line = full_path.read_bytes().split(b"\n", 1)[0].decode("utf-8", errors="ignore").strip()
                    if not SHEBANG_PATTERN.match(first_line):
                        warnings.append(
                            f"[{repo_name}] Executable file '{rel_path}' (mode 100755) lacks a shebang line."
                        )
                except Exception:
                    pass

    metadata["mode_counts"] = mode_counts
    return errors, warnings, metadata


def run_full_file_permission_linter(lab_root: Path) -> Dict[str, Any]:
    """Run cross-repo file permission audit across all sibling repos."""
    all_errors: List[str] = []
    all_warnings: List[str] = []
    repos = get_sibling_repo_roots(lab_root)

    total_files = 0
    total_non_exec = 0
    repo_summaries: Dict[str, Any] = {}

    for repo_name, repo_path in repos:
        errs, warns, meta = audit_git_index_modes(repo_name, repo_path)
        all_errors.extend(errs)
        all_warnings.extend(warns)
        total_files += meta["total_files"]
        total_non_exec += meta["non_executable_verified"]
        repo_summaries[repo_name] = meta

    passed = len(all_errors) == 0

    return {
        "passed": passed,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            "repositories_audited": len(repos),
            "total_files_audited": total_files,
            "total_non_executable_data_files": total_non_exec,
            "repo_summaries": repo_summaries,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit git index file modes (100644 vs 100755) and executable invariants."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run audit and return non-zero exit code on errors.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON summary report to stdout.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write JSON report output (default: .loop-logs/file-permission-audit.json).",
    )

    args = parser.parse_args()
    report = run_full_file_permission_linter(REPO_ROOT)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status_label = "PASS" if report["passed"] else "FAIL"
        print(f"File Permission & Executable Bit Linter: {status_label}")
        print(f"  Repositories audited: {report['metadata']['repositories_audited']}")
        print(f"  Total files audited: {report['metadata']['total_files_audited']}")
        print(f"  Non-executable data files verified: {report['metadata']['total_non_executable_data_files']}")

        if report["warnings"]:
            print(f"\nWarnings ({len(report['warnings'])}):")
            for w in report["warnings"]:
                print(f"  - {w}")

        if report["errors"]:
            print(f"\nErrors ({len(report['errors'])}):")
            for e in report["errors"]:
                print(f"  - {e}")
        else:
            print("All git index file permission and executable bit invariants verified clean!")

    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        pass

    if args.strict and (report["errors"] or report["warnings"]):
        return 1
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

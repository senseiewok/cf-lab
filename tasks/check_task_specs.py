#!/usr/bin/env python3
"""Spec dossier integrity checker for tasks/specs/<TASK-ID>.md.

Verifies that:
1. Every task in `tasks/board.json` with a `spec_path` resolves to an existing markdown file.
2. Every spec markdown file contains:
   - A markdown title (# ...)
   - Verifiable primary-source citations (DOI, NCT ID, PDB structure, or PMID)
   - Deterministic acceptance/verification commands (e.g. python, pytest, pwsh, check_claims)
3. Every specification file in `tasks/specs/` corresponds to a known task ID in `tasks/board.json`.

Usage:
    python tasks/check_task_specs.py [--board tasks/board.json] [--specs-dir tasks/specs]
    python tasks/check_task_specs.py --check
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOARD = REPO_ROOT / "tasks" / "board.json"
DEFAULT_SPECS_DIR = REPO_ROOT / "tasks" / "specs"

DOI_RX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)
NCT_RX = re.compile(r"\bNCT\d{8}\b", re.I)
PDB_RX = re.compile(r"\b(6MSM|5UAK|8EIQ|8EJ1|7SVD|7SV7|8EX1|6O1V|6O2P)\b|\bPDB\s*#?:?\s*([1-9][A-Za-z0-9]{3})\b", re.I)
PMID_RX = re.compile(r"\bPMID:?\s*\d+\b", re.I)
CATALOG_RX = re.compile(r"\b(catalog\.yaml|sources/|cf-research/sources|cffpr|ecfspr)\b", re.I)
REGULATORY_RX = re.compile(r"\b(FDA|EMA|openFDA|ClinicalTrials\.gov)\b", re.I)
CODE_RX = re.compile(r"(tests/|tools/|tasks/|src/|\.ps1|\.py|\.html|\.js|\.md)", re.I)

VERIFICATION_CMD_RX = re.compile(
    r"\b(python|pytest|pwsh|unittest|check_claims|check-all|check_task_specs|check_worktree_drift|test_[a-zA-Z0-9_]+\.py)\b",
    re.I,
)


def verify_spec_content(spec_path: Path) -> tuple[bool, list[str]]:
    """Verify content of a spec dossier file."""
    errors: list[str] = []
    if not spec_path.is_file():
        return False, [f"Spec file does not exist: {spec_path}"]

    try:
        content = spec_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"Failed to read {spec_path}: {e}"]

    if len(content.strip()) < 100:
        errors.append(f"Spec file {spec_path.name} is too brief (< 100 characters)")

    # Title check
    if not re.search(r"^#\s+.+", content, re.M):
        errors.append(f"Spec file {spec_path.name} missing top-level markdown heading (# Title)")

    # Primary source citations
    has_primary_anchor = bool(
        DOI_RX.search(content)
        or NCT_RX.search(content)
        or PDB_RX.search(content)
        or PMID_RX.search(content)
        or CATALOG_RX.search(content)
        or REGULATORY_RX.search(content)
        or CODE_RX.search(content)
    )
    if not has_primary_anchor:
        errors.append(f"Spec file {spec_path.name} missing verifiable primary-source anchor (DOI, NCT, PDB, PMID, catalog, or codebase reference)")

    # Verification / acceptance commands
    has_verification_cmd = bool(VERIFICATION_CMD_RX.search(content))
    if not has_verification_cmd:
        errors.append(f"Spec file {spec_path.name} missing deterministic verification command (python, pytest, pwsh, etc.)")

    return len(errors) == 0, errors


def check_all_specs(
    board_path: Path = DEFAULT_BOARD,
    specs_dir: Path = DEFAULT_SPECS_DIR,
    repo_root: Path = REPO_ROOT,
) -> tuple[bool, dict[str, Any]]:
    """Check integrity of all specs referenced on board and on disk."""
    results: dict[str, Any] = {
        "board_tasks_with_spec": 0,
        "disk_specs_count": 0,
        "verified_specs": [],
        "errors": [],
    }

    if not board_path.is_file():
        results["errors"].append(f"Board file not found: {board_path}")
        return False, results

    try:
        board_data = json.loads(board_path.read_text(encoding="utf-8"))
        tasks = board_data.get("tasks", []) if isinstance(board_data, dict) else board_data
    except Exception as e:
        results["errors"].append(f"Failed to parse board JSON: {e}")
        return False, results

    tasks_by_id = {t["id"]: t for t in tasks if isinstance(t, dict) and "id" in t}

    # 1. Verify tasks declaring spec_path
    for tid, t in tasks_by_id.items():
        spec_path_str = t.get("spec_path")
        if not spec_path_str:
            continue
        results["board_tasks_with_spec"] += 1

        resolved = (repo_root / spec_path_str).resolve()
        ok, errs = verify_spec_content(resolved)
        if not ok:
            results["errors"].extend([f"Task {tid} ({spec_path_str}): {e}" for e in errs])
        else:
            results["verified_specs"].append({
                "id": tid,
                "spec_path": spec_path_str,
                "file": str(resolved),
            })

    # 2. Check all markdown files in specs_dir
    if specs_dir.is_dir():
        spec_files = sorted(specs_dir.glob("*.md"))
        results["disk_specs_count"] = len(spec_files)
        for sf in spec_files:
            match = re.match(r"^(T-\d{4})\.md$", sf.name, re.I)
            if not match:
                results["errors"].append(f"File in specs dir does not follow T-XXXX.md naming: {sf.name}")
                continue

            spec_tid = match.group(1).upper()
            if spec_tid not in tasks_by_id:
                results["errors"].append(f"Orphan spec dossier {sf.name} has no corresponding task in board.json")
            else:
                task = tasks_by_id[spec_tid]
                if not task.get("spec_path"):
                    results["errors"].append(f"Task {spec_tid} exists in board.json but is missing 'spec_path: tasks/specs/{sf.name}'")

            ok, errs = verify_spec_content(sf)
            if not ok:
                results["errors"].extend([f"{sf.name}: {e}" for e in errs])

    passed = len(results["errors"]) == 0
    return passed, results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify task specification dossiers for primary evidence grounding and verification commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--board", default=str(DEFAULT_BOARD), help="Path to board.json")
    parser.add_argument("--specs-dir", default=str(DEFAULT_SPECS_DIR), help="Path to tasks/specs/")
    parser.add_argument("--check", action="store_true", help="Run check and exit 1 if errors found, 0 otherwise")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args(argv)

    board_path = Path(args.board)
    specs_dir = Path(args.specs_dir)
    passed, results = check_all_specs(board_path=board_path, specs_dir=specs_dir, repo_root=board_path.parent.parent)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0 if passed else 1

    if not passed:
        print(f"CHECK FAIL: {len(results['errors'])} spec integrity error(s) found:")
        for err in results["errors"]:
            print(f"  - {err}")
        return 1

    print(f"CHECK PASS: {results['board_tasks_with_spec']} board task spec(s) verified; {results['disk_specs_count']} disk spec dossier(s) healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

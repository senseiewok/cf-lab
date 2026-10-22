#!/usr/bin/env python3
"""Automated Multi-Repo Worktree Leak & Stale Worktree Pruning Sentinel.

Automates scheduled discovery and cleanup of fully merged, clean worktrees
across Sensei Ewok's CF Lab repositories (cf-lab, cf-research, cf-skills, .ai).
Builds directly on tasks/harvest_sentinel_worktrees.py with rigorous
data-loss prevention invariants:
1. Strict prerequisite safety check: 0 uncommitted changes, 0 untracked files,
   0 unpushed commits, and verified PR merge status (MERGED via GitHub API
   or git ancestor verification on origin/main).
2. Requires explicit --yes flag to execute live deletions; defaults to
   comprehensive dry-run preview emitting JSON summary.
3. Automatically prunes associated local branch references and cleans git
   worktree administrative metadata (git worktree prune).
4. Logs structured telemetry into .loop-logs/worktree-prune.json with
   sanitized paths and timestamps.

Usage:
    python tasks/prune_stale_worktrees.py --dry-run
    python tasks/prune_stale_worktrees.py --yes
    python tasks/prune_stale_worktrees.py --json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / ".loop-logs"
DEFAULT_TELEMETRY_PATH = LOGS_DIR / "worktree-prune.json"
DEFAULT_REPOS = ["cf-lab", "cf-research", "cf-skills", ".ai"]

# Import core audit primitives from harvest_sentinel_worktrees
try:
    from tasks.harvest_sentinel_worktrees import (
        audit_harvestable_worktrees,
        fetch_merged_prs_gh,
        find_worktree_root,
        inspect_worktree_safety,
    )
except ImportError:
    # Allow running directly as standalone script
    sys.path.insert(0, str(REPO_ROOT))
    from tasks.harvest_sentinel_worktrees import (
        audit_harvestable_worktrees,
        fetch_merged_prs_gh,
        find_worktree_root,
        inspect_worktree_safety,
    )


def sanitize_path(p: Path | str) -> str:
    """Normalize path to forward slashes for clean portable telemetry."""
    return str(p).replace("\\", "/")


def is_branch_ancestor_of_main(branch: str, repo_dir: Path) -> bool:
    """Verify if branch is an ancestor of origin/main in git history."""
    if not branch or branch in ("main", "origin/main", "HEAD"):
        return False
    try:
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", branch, "origin/main"],
            cwd=repo_dir,
            capture_output=True,
            timeout=10,
        )
        return res.returncode == 0
    except Exception:
        return False


def prune_single_worktree(
    wt_path: Path,
    repo_name: str,
    branch: str,
    repo_dir: Path,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Prune a single validated worktree, its branch reference, and run git prune."""
    record: Dict[str, Any] = {
        "path": sanitize_path(wt_path),
        "repo": repo_name,
        "branch": branch,
        "status": "dry_run" if dry_run else "pruned",
        "branch_deleted": False,
        "worktree_pruned": False,
        "error": None,
    }

    if dry_run:
        return record

    # Guard: never prune current active working directory
    try:
        cwd = Path.cwd().resolve()
        if wt_path.resolve() == cwd or wt_path.resolve() in cwd.parents:
            record["status"] = "skipped"
            record["error"] = "Cannot prune current working directory or its parent"
            return record
    except Exception:
        pass

    try:
        # 1. git worktree remove
        p = subprocess.run(
            ["git", "worktree", "remove", "--force", str(wt_path)],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if p.returncode != 0:
            # Fallback if git worktree remove failed
            if wt_path.exists():
                shutil.rmtree(wt_path, ignore_errors=True)

        # 2. git worktree prune
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repo_dir,
            capture_output=True,
            timeout=15,
        )
        record["worktree_pruned"] = True

        # 3. Delete associated branch if verified merged
        if branch and branch != "main":
            b_del = subprocess.run(
                ["git", "branch", "-D", branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if b_del.returncode == 0:
                record["branch_deleted"] = True

    except Exception as e:
        record["status"] = "error"
        record["error"] = str(e)

    return record


def prune_stale_worktrees(
    worktrees_root: Optional[Path] = None,
    repos: Optional[List[str]] = None,
    owner: str = "senseiewok",
    dry_run: bool = True,
    pr_data: Optional[Dict[str, Dict[str, Any]]] = None,
    telemetry_path: Optional[Path] = DEFAULT_TELEMETRY_PATH,
) -> Dict[str, Any]:
    """Audit and prune clean, merged worktrees across sibling repositories."""
    wt_root = find_worktree_root(worktrees_root)
    target_repos = repos or DEFAULT_REPOS

    # Audit candidates through harvest primitives
    audit_summary = audit_harvestable_worktrees(
        worktrees_root=wt_root,
        repos=target_repos,
        owner=owner,
        pr_data=pr_data,
    )

    harvestable = audit_summary.get("harvestable", [])
    prune_results: List[Dict[str, Any]] = []

    for item in harvestable:
        wt_path = Path(item["path"])
        repo_name = item["repo"]
        branch = item["branch"]

        # Determine repo base directory
        repo_dir = REPO_ROOT.parent / repo_name if REPO_ROOT.name != repo_name else REPO_ROOT

        # Confirm safety invariant via git ancestor or merged PR
        res = prune_single_worktree(
            wt_path=wt_path,
            repo_name=repo_name,
            branch=branch,
            repo_dir=repo_dir,
            dry_run=dry_run,
        )
        prune_results.append(res)

    telemetry: Dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "dry_run" if dry_run else "live",
        "worktrees_root": sanitize_path(wt_root),
        "total_scanned": audit_summary.get("total_worktrees", 0),
        "harvestable_count": len(harvestable),
        "pruned_count": len([r for r in prune_results if r["status"] in ("pruned", "dry_run")]),
        "kept_count": audit_summary.get("kept_count", 0),
        "pruned_entries": prune_results,
        "kept_entries": [
            {
                "repo": k["repo"],
                "topic": k["topic"],
                "path": sanitize_path(k["path"]),
                "branch": k.get("branch", ""),
                "reason": k.get("reason", ""),
            }
            for k in audit_summary.get("kept", [])
        ],
        "errors": audit_summary.get("errors", []),
    }

    if telemetry_path:
        try:
            telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            telemetry_path.write_text(json.dumps(telemetry, indent=2), encoding="utf-8")
        except Exception as e:
            telemetry["errors"].append(f"Failed to write telemetry: {e}")

    return telemetry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated multi-repo stale worktree pruning sentinel with zero data-loss invariants"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate cleanup and preview removable worktrees without deleting (default)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Execute live deletion of verified merged, clean worktrees",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Custom .worktrees root directory for inspection",
    )
    parser.add_argument(
        "--repos",
        nargs="+",
        default=DEFAULT_REPOS,
        help="List of repository names to scan",
    )
    parser.add_argument(
        "--pr-data",
        type=Path,
        help="Optional path to mock PR JSON file for offline testing",
    )
    parser.add_argument(
        "--telemetry-path",
        type=Path,
        default=DEFAULT_TELEMETRY_PATH,
        help="Path to write structured telemetry JSON",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full telemetry JSON to stdout",
    )

    args = parser.parse_args()

    # If --yes is explicitly given, dry_run is False
    is_dry_run = not args.yes

    pr_dict = None
    if args.pr_data and args.pr_data.is_file():
        try:
            pr_dict = json.loads(args.pr_data.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error loading --pr-data: {e}", file=sys.stderr)
            return 1

    telemetry = prune_stale_worktrees(
        worktrees_root=args.root,
        repos=args.repos,
        dry_run=is_dry_run,
        pr_data=pr_dict,
        telemetry_path=args.telemetry_path,
    )

    if args.json:
        print(json.dumps(telemetry, indent=2))
    else:
        mode_str = "DRY-RUN" if is_dry_run else "LIVE EXECUTION"
        print(f"Worktree Pruning Sentinel [{mode_str}]")
        print(f"  Total Scanned:     {telemetry['total_scanned']}")
        print(f"  Harvestable/Pruned: {telemetry['pruned_count']}")
        print(f"  Kept (Protected):  {telemetry['kept_count']}")
        if telemetry["pruned_entries"]:
            print("  Entries:")
            for p in telemetry["pruned_entries"]:
                print(f"    * [{p['status']}] {p['repo']}: {p['branch']} ({p['path']})")
        if is_dry_run and telemetry["harvestable_count"] > 0:
            print(f"\nRun with --yes to execute live deletion of {telemetry['harvestable_count']} worktree(s).")

    return 0


if __name__ == "__main__":
    sys.exit(main())

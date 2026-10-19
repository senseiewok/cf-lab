#!/usr/bin/env python3
"""Automated worktree harvest & duplicate-PR preflight guard.

Scans `../.worktrees/*/*` across sibling repositories (cf-lab, cf-research, cf-skills, .ai)
to identify unmerged commits, active branches, and worktrees matching specific tasks or lanes.
Integrates into `tasks/pick_bold_task.py` and `scheduled-security-sentinel` so agents resume/harvest
existing worktree commits instead of starting from scratch or opening duplicate PRs.

Usage:
    python tasks/check_worktree_drift.py [--json] [--lane {security,research,showcase}] [--task-ids T-XXXX,...]
    python tasks/check_worktree_drift.py --check
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

TASK_ID_RX = re.compile(r"\bT-(\d{4})\b", re.I)
LANE_RX = re.compile(r"\b(security|research|showcase)\b", re.I)


def find_worktree_root(repo_root: Path | None = None) -> Path:
    """Find the root .worktrees directory holding sibling repo worktrees."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    parts = repo_root.resolve().parts
    if ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        return Path(*parts[:wt_idx]) / ".worktrees"
    return repo_root.resolve().parent / ".worktrees"


def detect_lane(text: str) -> str | None:
    """Detect lane from branch name, path, or topic name."""
    low = text.lower()
    if "sentinel-security" in low or "sec-fix" in low:
        return "security"
    if "sentinel-research" in low:
        return "research"
    if "sentinel-showcase" in low or "site/showcase" in low or "showcase" in low:
        return "showcase"
    m = LANE_RX.search(text)
    if m:
        return m.group(1).lower()
    return None


def extract_task_ids(text: str) -> list[str]:
    """Extract ordered unique T-XXXX task IDs from a string."""
    out: list[str] = []
    for digits in TASK_ID_RX.findall(text):
        tid = f"T-{digits}"
        if tid not in out:
            out.append(tid)
    return out


def inspect_worktree(wt_dir: Path, repo_name: str) -> dict[str, Any] | None:
    """Inspect a single worktree directory and extract git status and commits."""
    git_ref = wt_dir / ".git"
    if not git_ref.exists():
        return None

    # Get branch name
    branch = "unknown"
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=wt_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if p.returncode == 0 and p.stdout.strip():
            branch = p.stdout.strip()
    except Exception:
        pass

    # Check uncommitted status
    uncommitted = False
    try:
        p = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=wt_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if p.returncode == 0:
            lines = [l for l in p.stdout.strip().splitlines() if l.strip()]
            uncommitted = len(lines) > 0
    except Exception:
        pass

    # Check unmerged commits relative to origin/main or main
    unmerged_commits: list[str] = []
    for base in ("origin/main", "main"):
        try:
            p = subprocess.run(
                ["git", "log", f"{base}..HEAD", "--oneline"],
                cwd=wt_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if p.returncode == 0:
                unmerged_commits = [l.strip() for l in p.stdout.strip().splitlines() if l.strip()]
                break
        except Exception:
            pass

    # Combine text for matching task IDs and lane
    combined_text = f"{repo_name} {wt_dir.name} {branch} {' '.join(unmerged_commits)}"
    matched_task_ids = extract_task_ids(combined_text)
    detected_lane = detect_lane(f"{wt_dir.name} {branch}")

    return {
        "repo": repo_name,
        "path": str(wt_dir.resolve()).replace("\\", "/"),
        "topic": wt_dir.name,
        "branch": branch,
        "uncommitted": uncommitted,
        "unmerged_commits": unmerged_commits,
        "matching_task_ids": matched_task_ids,
        "matching_lane": detected_lane,
    }


def scan_existing_worktrees(
    repo_root: Path | None = None,
    task_ids: list[str] | set[str] | None = None,
    lane: str | None = None,
) -> list[dict[str, Any]]:
    """Scan all existing worktrees under the workspace .worktrees root.

    Filters by task_ids or lane if specified.
    """
    wt_root = find_worktree_root(repo_root)
    if not wt_root.is_dir():
        return []

    target_task_ids = {t.upper() for t in task_ids} if task_ids else set()
    target_lane = lane.lower() if lane else None

    results: list[dict[str, Any]] = []

    try:
        repo_dirs = sorted([d for d in wt_root.iterdir() if d.is_dir()])
    except Exception:
        return []

    for repo_dir in repo_dirs:
        repo_name = repo_dir.name
        try:
            wt_dirs = sorted([d for d in repo_dir.iterdir() if d.is_dir()])
        except Exception:
            continue

        for wt_dir in wt_dirs:
            info = inspect_worktree(wt_dir, repo_name)
            if info is None:
                continue

            matches_task = False
            if target_task_ids:
                matches_task = any(tid.upper() in target_task_ids for tid in info["matching_task_ids"])

            matches_lane = False
            if target_lane:
                matches_lane = bool(info["matching_lane"] and info["matching_lane"].lower() == target_lane)

            # Filter logic: if task_ids or lane requested, must match either
            if target_task_ids or target_lane:
                if (target_task_ids and matches_task) or (target_lane and matches_lane):
                    results.append(info)
            else:
                results.append(info)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Automated worktree harvest & duplicate-PR preflight guard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", help="Custom path to .worktrees root directory")
    parser.add_argument("--lane", choices=["security", "research", "showcase"], help="Filter by lane")
    parser.add_argument("--task-ids", help="Comma-separated list of task IDs to filter by (e.g. T-0213,T-0214)")
    parser.add_argument("--check", action="store_true", help="Exit 1 if unharvested unmerged worktrees exist, 0 otherwise")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args(argv)

    repo_root = Path(args.root) if args.root else None
    task_id_list = [t.strip() for t in args.task_ids.split(",") if t.strip()] if args.task_ids else None

    wts = scan_existing_worktrees(repo_root=repo_root, task_ids=task_id_list, lane=args.lane)

    unmerged = [w for w in wts if w["unmerged_commits"] or w["uncommitted"]]

    if args.json or not args.check:
        print(json.dumps({
            "total_scanned": len(wts),
            "unmerged_count": len(unmerged),
            "worktrees": wts,
        }, indent=2))

    if args.check:
        if unmerged:
            print(f"CHECK FAIL: {len(unmerged)} unmerged/dirty worktrees found needing harvest or cleanup:")
            for u in unmerged:
                print(f"  [{u['repo']}] {u['topic']} ({u['branch']}): {len(u['unmerged_commits'])} commits ahead, dirty={u['uncommitted']}")
            return 1
        print(f"CHECK PASS: {len(wts)} worktrees scanned, 0 unmerged/dirty worktrees.")
        return 0

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

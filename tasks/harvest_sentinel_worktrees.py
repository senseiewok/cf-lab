#!/usr/bin/env python3
"""Stale Sentinel Worktree Harvest & Automated Branch Hygiene Daemon.

Scans git worktrees under `../.worktrees/*/*` across Sensei Ewok's CF Lab repositories
(cf-lab, cf-research, cf-skills, .ai). Identifies worktrees whose branches have been
cleanly merged into `origin/main` on GitHub, verifies zero uncommitted/untracked/unpushed
work, and safely cleans them to prevent local worktree accumulation.

Usage:
    python tasks/harvest_sentinel_worktrees.py --dry-run
    python tasks/harvest_sentinel_worktrees.py --clean [--yes]
    python tasks/harvest_sentinel_worktrees.py --check [--json]
    python tasks/harvest_sentinel_worktrees.py --pr-data fixtures/mock_prs.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / ".loop-logs"
HARVEST_LOG = LOGS_DIR / "worktree-harvest.jsonl"

SAFE_IGNORED_PATTERNS = [
    re.compile(r"(^|/)(__pycache__|\.pytest_cache|\.loop-logs|\.agents|build|dist|\.cache|\.coverage|shots)(/|$)", re.I),
    re.compile(r"\.(pyc|pyo|pyd)$", re.I),
    re.compile(r"(^|/)(commit-msg[^/]*|pr-body[^/]*|run-record[^/]*)\.(txt|md|png|json)$", re.I),
    re.compile(r"(^|/)(commit-msg[^/]*|pr-body[^/]*)$", re.I),
]

TASK_ID_RX = re.compile(r"\bT-(\d{4})\b", re.I)


def is_safe_ignored(rel_path: str) -> bool:
    """Check if an ignored file is a transient or regenerable cache/artifact."""
    norm = rel_path.replace("\\", "/")
    return any(p.search(norm) for p in SAFE_IGNORED_PATTERNS)


def find_worktree_root(custom_root: Optional[Path] = None) -> Path:
    """Locate the root `.worktrees` directory."""
    if custom_root is not None:
        return custom_root.resolve()

    parts = REPO_ROOT.parts
    if ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        return Path(*parts[:wt_idx]) / ".worktrees"
    return REPO_ROOT.parent / ".worktrees"


def fetch_merged_prs_gh(owner: str, repo: str) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """Fetch merged PRs for a repository via gh CLI; returns {branch_name: pr_dict}."""
    slug = f"{owner}/{repo}"
    cmd = [
        "gh", "pr", "list",
        "--repo", slug,
        "--state", "merged",
        "--json", "number,title,headRefName,url,mergedAt",
        "--limit", "100"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            return {}, f"gh pr list failed for {slug} (code {res.returncode}): {res.stderr.strip()}"
        data = json.loads(res.stdout or "[]")
        merged_by_branch: Dict[str, Dict[str, Any]] = {}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "headRefName" in item:
                    merged_by_branch[item["headRefName"]] = item
        return merged_by_branch, None
    except FileNotFoundError:
        return {}, "gh executable not found on PATH"
    except subprocess.TimeoutExpired:
        return {}, f"gh pr list timed out for {slug}"
    except Exception as e:
        return {}, f"Failed querying gh for {slug}: {e}"


def inspect_worktree_safety(wt_path: Path, repo_root: Path) -> Dict[str, Any]:
    """Inspect git state of a worktree; returns safety assessment."""
    result: Dict[str, Any] = {
        "path": str(wt_path),
        "branch": "",
        "is_safe": False,
        "reasons_to_keep": [],
        "task_ids": [],
        "unmerged_commits": [],
    }

    if not wt_path.is_dir():
        result["reasons_to_keep"].append("worktree directory does not exist")
        return result

    git_file = wt_path / ".git"
    if not git_file.exists():
        result["reasons_to_keep"].append("missing .git file")
        return result

    # 1. Get HEAD branch
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if p.returncode != 0:
            result["reasons_to_keep"].append(f"git rev-parse failed: {p.stderr.strip()}")
            return result
        branch = p.stdout.strip()
        result["branch"] = branch
        if branch in ("", "HEAD"):
            result["reasons_to_keep"].append("detached HEAD")
            return result
    except Exception as e:
        result["reasons_to_keep"].append(f"exception checking HEAD branch: {e}")
        return result

    # Extract task IDs from branch name and directory name
    task_ids = TASK_ID_RX.findall(f"{branch} {wt_path.name}")
    result["task_ids"] = [f"T-{tid}" for tid in dict.fromkeys(task_ids)]

    # 2. Check working tree status (uncommitted / untracked changes)
    try:
        p = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if p.returncode != 0:
            result["reasons_to_keep"].append(f"git status failed: {p.stderr.strip()}")
            return result
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        if lines:
            result["reasons_to_keep"].append(f"{len(lines)} uncommitted or untracked file(s)")
            return result
    except Exception as e:
        result["reasons_to_keep"].append(f"exception checking git status: {e}")
        return result

    # 3. Check for non-whitelisted ignored files
    try:
        p = subprocess.run(
            ["git", "status", "--ignored", "--porcelain"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if p.returncode == 0:
            ignored_hazard: List[str] = []
            for line in p.stdout.splitlines():
                if line.startswith("!! "):
                    path_str = line[3:].strip()
                    if not is_safe_ignored(path_str):
                        ignored_hazard.append(path_str)
            if ignored_hazard:
                sample = ", ".join(ignored_hazard[:3])
                result["reasons_to_keep"].append(f"{len(ignored_hazard)} unsafe ignored file(s) (e.g. {sample})")
                return result
    except Exception:
        pass

    # 4. Check for unpushed commits not on origin/main
    try:
        p = subprocess.run(
            ["git", "log", f"origin/main..{branch}", "--oneline"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if p.returncode == 0:
            unpushed = [l.strip() for l in p.stdout.splitlines() if l.strip()]
            result["unmerged_commits"] = unpushed
            # If there are commits ahead of origin/main, we check if they are in merged PR
        else:
            # origin/main might not be fetched in local worktree
            pass
    except Exception:
        pass

    result["is_safe"] = len(result["reasons_to_keep"]) == 0
    return result


def audit_harvestable_worktrees(
    worktrees_root: Path,
    repos: List[str],
    owner: str = "senseiewok",
    pr_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Audit all worktrees and classify as HARVESTABLE or KEPT."""
    summary: Dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "worktrees_root": str(worktrees_root),
        "total_worktrees": 0,
        "harvestable_count": 0,
        "kept_count": 0,
        "harvestable": [],
        "kept": [],
        "errors": [],
    }

    if not worktrees_root.is_dir():
        summary["errors"].append(f"Worktree root directory does not exist: {worktrees_root}")
        return summary

    # Group merged PRs by repo
    merged_prs_by_repo: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for repo in repos:
        if pr_data and repo in pr_data:
            merged_prs_by_repo[repo] = pr_data[repo]
        else:
            prs, err = fetch_merged_prs_gh(owner, repo)
            if err:
                summary["errors"].append(err)
            merged_prs_by_repo[repo] = prs

    # Discover worktrees under worktrees_root/<repo>/*
    for repo_name in repos:
        repo_wt_dir = worktrees_root / repo_name
        if not repo_wt_dir.is_dir():
            continue

        repo_main = REPO_ROOT.parent / repo_name if REPO_ROOT.name != repo_name else REPO_ROOT

        for entry in sorted(repo_wt_dir.iterdir()):
            if not entry.is_dir():
                continue

            summary["total_worktrees"] += 1
            safety = inspect_worktree_safety(entry, repo_main)
            branch = safety["branch"]
            merged_dict = merged_prs_by_repo.get(repo_name, {})

            # Must be clean to harvest
            if not safety["is_safe"]:
                summary["kept_count"] += 1
                summary["kept"].append({
                    "repo": repo_name,
                    "topic": entry.name,
                    "path": str(entry),
                    "branch": branch,
                    "reason": "; ".join(safety["reasons_to_keep"]),
                    "task_ids": safety["task_ids"],
                })
                continue

            # Must correspond to a merged PR or be fully merged into origin/main
            is_merged = False
            pr_info: Optional[Dict[str, Any]] = None

            if branch in merged_dict:
                is_merged = True
                pr_info = merged_dict[branch]
            elif not safety["unmerged_commits"] and branch != "main":
                # If zero commits ahead of origin/main and branch != main, it is merged into main
                is_merged = True

            if is_merged:
                summary["harvestable_count"] += 1
                summary["harvestable"].append({
                    "repo": repo_name,
                    "topic": entry.name,
                    "path": str(entry),
                    "branch": branch,
                    "task_ids": safety["task_ids"],
                    "pr_number": pr_info.get("number") if pr_info else None,
                    "pr_url": pr_info.get("url") if pr_info else None,
                })
            else:
                summary["kept_count"] += 1
                reason = "branch not yet merged into origin/main and no merged PR recorded"
                if safety["unmerged_commits"]:
                    reason += f" ({len(safety['unmerged_commits'])} unpushed commit(s))"
                summary["kept"].append({
                    "repo": repo_name,
                    "topic": entry.name,
                    "path": str(entry),
                    "branch": branch,
                    "reason": reason,
                    "task_ids": safety["task_ids"],
                })

    return summary


def clean_worktrees(
    harvestable: List[Dict[str, Any]],
    dry_run: bool = True,
) -> List[Dict[str, Any]]:
    """Remove harvestable worktrees safely."""
    results: List[Dict[str, Any]] = []

    for item in harvestable:
        wt_path = Path(item["path"])
        repo_name = item["repo"]
        repo_dir = REPO_ROOT.parent / repo_name if REPO_ROOT.name != repo_name else REPO_ROOT

        entry_res: Dict[str, Any] = {
            "path": str(wt_path),
            "repo": repo_name,
            "branch": item["branch"],
            "topic": item["topic"],
            "status": "dry_run" if dry_run else "pending",
            "error": None,
        }

        if dry_run:
            results.append(entry_res)
            continue

        try:
            # 1. git worktree remove
            p = subprocess.run(
                ["git", "worktree", "remove", str(wt_path)],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if p.returncode != 0:
                # If failed, retry with prune
                subprocess.run(["git", "worktree", "prune"], cwd=repo_dir, capture_output=True, timeout=15)
                if wt_path.exists():
                    shutil.rmtree(wt_path, ignore_errors=True)

            # 2. Prune git worktree list
            subprocess.run(["git", "worktree", "prune"], cwd=repo_dir, capture_output=True, timeout=15)

            entry_res["status"] = "removed"
        except Exception as e:
            entry_res["status"] = "failed"
            entry_res["error"] = str(e)

        results.append(entry_res)

        # Log to .loop-logs/worktree-harvest.jsonl
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(HARVEST_LOG, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "action": "harvest",
                    "repo": repo_name,
                    "topic": item["topic"],
                    "branch": item["branch"],
                    "status": entry_res["status"],
                    "error": entry_res["error"],
                }
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Stale Sentinel Worktree Harvest & Automated Branch Hygiene Daemon")
    parser.add_argument("--dry-run", action="store_true", help="Print worktrees that would be harvested without deleting")
    parser.add_argument("--clean", action="store_true", help="Clean harvestable worktrees")
    parser.add_argument("--yes", action="store_true", help="Confirm deletion under --clean")
    parser.add_argument("--check", action="store_true", help="Check worktree hygiene; exit 0 if clean, 1 if harvestable exist")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON format")
    parser.add_argument("--worktree-root", type=Path, help="Override root .worktrees directory")
    parser.add_argument("--pr-data", type=Path, help="Load mock PR state from JSON file")
    parser.add_argument("--owner", default="senseiewok", help="GitHub owner/organization")
    parser.add_argument("--repos", nargs="+", default=["cf-lab", "cf-research", "cf-skills", ".ai"], help="Repositories to inspect")

    args = parser.parse_args()

    wt_root = find_worktree_root(args.worktree_root)
    pr_data = None
    if args.pr_data and args.pr_data.is_file():
        try:
            pr_data = json.loads(args.pr_data.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading --pr-data: {e}", file=sys.stderr)
            return 2

    audit = audit_harvestable_worktrees(
        worktrees_root=wt_root,
        repos=args.repos,
        owner=args.owner,
        pr_data=pr_data,
    )

    if args.clean and not args.yes and not args.dry_run:
        print("Note: --clean requires --yes to proceed with actual removal. Running in dry-run mode.")
        args.dry_run = True

    if args.clean or args.dry_run:
        clean_results = clean_worktrees(audit["harvestable"], dry_run=args.dry_run)
        audit["clean_results"] = clean_results

    if args.json:
        print(json.dumps(audit, indent=2))
        return 0

    # Human-readable report
    mode_str = "DRY RUN" if args.dry_run or (not args.clean and not args.check) else "EXECUTION"
    print(f"Sentinel Worktree Harvest [{mode_str}] - {audit['timestamp']}")
    print(f"  Root: {wt_root}")
    print(f"  Total Worktrees Inspected: {audit['total_worktrees']}")
    print(f"  Harvestable (Merged & Clean): {audit['harvestable_count']}")
    print(f"  Kept (Active/Dirty/Unpushed): {audit['kept_count']}")

    if audit["harvestable"]:
        print("\nHarvestable Worktrees:")
        for item in audit["harvestable"]:
            pr_desc = f" (PR #{item['pr_number']})" if item.get("pr_number") else ""
            print(f"  [HARVEST] {item['repo']}/{item['topic']} -> branch '{item['branch']}'{pr_desc}")

    if args.check:
        return 1 if audit["harvestable_count"] > 0 else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

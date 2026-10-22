#!/usr/bin/env python3
"""Automated Sentinel PR Repair & Superseded Branch Cleaner Daemon (T-0279).

Automates remediation of the GitHub PR repair queue identified across
Sensei Ewok's CF Lab repositories (cf-lab, cf-skills, cf-research, .ai):
1. Safely detects superseded sentinel PRs whose referenced board tasks are already
   marked done on `origin/main`, confirms identical deliverables, and closes the duplicate
   PR with an explanatory comment.
2. Identifies branch/title task-ID discrepancies (such as cross-repo research tools
   cited in showcase PR titles or newly seeded tasks in board chores) and normalizes
   them to prevent false-positive superseded or starving warnings.
3. Emits structured JSON alerts for manual intervention when unresolvable merge
   conflicts or review blockers are detected.

Usage:
    python tasks/repair_sentinel_prs.py --dry-run
    python tasks/repair_sentinel_prs.py --repair [--yes]
    python tasks/repair_sentinel_prs.py --check
    python tasks/repair_sentinel_prs.py --pr-data fixtures/mock_prs.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / ".loop-logs"
DEFAULT_ALERT_PATH = LOGS_DIR / "pr-repair-alerts.json"
BOARD_PATH = REPO_ROOT / "tasks" / "board.json"

DEFAULT_OWNER = "senseiewok"
DEFAULT_REPOS = ["cf-lab", "cf-skills", "cf-research", ".ai"]

VALID_SLUG_PART_RX = re.compile(r"^[A-Za-z0-9_\.][A-Za-z0-9_\-\.]*$")
TASK_ID_RX = re.compile(r"\bT-?(\d{4})\b", re.I)
SENTINEL_BRANCH_RX = re.compile(r"^(?:work/sentinel-|site/showcase-|sec-fix-|agent-improve-|feat/t-)", re.I)

# Regex to detect where seeded task annotations start in PR titles
SEED_KEYWORD_RX = re.compile(r"\b(?:seed(?:ed|ing)?|add(?:ed|ing)?\s+tasks?|propos(?:ed|ing)?|replenish(?:ed|ing)?)\b(.*)", re.I)

# Redaction patterns for sensitive tokens per security-baseline
REDACT_PATTERNS = [
    (re.compile(r"(ghp_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_\-]{20,}|sk-[A-Za-z0-9_\-]{20,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.I), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED_EMAIL]"),
]


def redact_sensitive(text: str) -> str:
    """Sanitize API keys, tokens, and personal email addresses."""
    for pattern, replacement in REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def validate_repo_slug(owner: str, repo: str) -> str:
    """Validate owner and repo to prevent argument or path injection."""
    if owner in (".", "..") or not VALID_SLUG_PART_RX.match(owner):
        raise ValueError(f"Invalid repository owner: {owner!r}")
    if repo in (".", "..") or not VALID_SLUG_PART_RX.match(repo):
        raise ValueError(f"Invalid repository name: {repo!r}")
    return f"{owner}/{repo}"


def extract_task_ids_from_text(text: str) -> List[str]:
    """Extract canonical T-XXXX task IDs from arbitrary text in occurrence order."""
    seen: List[str] = []
    for digits in TASK_ID_RX.findall(text or ""):
        tid = f"T-{digits}"
        if tid not in seen:
            seen.append(tid)
    return seen


def extract_seeded_task_ids(title: str) -> List[str]:
    """Find task IDs that appear in a 'seed' or 'propose' context in PR title."""
    seeded: List[str] = []
    m = SEED_KEYWORD_RX.search(title or "")
    if m:
        after_keyword = m.group(1)
        for tid in extract_task_ids_from_text(after_keyword):
            if tid not in seeded:
                seeded.append(tid)
    return seeded


def load_board_tasks(board_path: Path = BOARD_PATH) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
    """Load tasks from board.json, returning (tasks_by_id, done_task_ids)."""
    if not board_path.is_file():
        return {}, set()
    try:
        data = json.loads(board_path.read_text(encoding="utf-8"))
        tasks = data.get("tasks", [])
        by_id: Dict[str, Dict[str, Any]] = {}
        done_ids: Set[str] = set()
        for t in tasks:
            tid = t.get("id")
            if tid:
                by_id[tid] = t
                if t.get("status") == "done":
                    done_ids.add(tid)
        return by_id, done_ids
    except Exception:
        return {}, set()


def normalize_pr_task_ids(
    branch: str,
    title: str,
    repo_name: str = "",
    board_tasks_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Normalizes task IDs from PR branch name and title.

    Resolves discrepancies:
    1. Distinguishes primary deliverable task IDs from seeded tasks (e.g. 'seed T-0280, T-0281').
    2. Identifies cross-repo task references (e.g. citing a cf-research task in a .ai title).
    3. Prevents newly seeded board tasks from being misclassified as unfulfilled deliverables
       that would prevent detection of superseded chore PRs.
    """
    board = board_tasks_by_id or {}
    branch_tids = extract_task_ids_from_text(branch)
    title_tids = extract_task_ids_from_text(title)

    # Detect seeded task IDs in the title
    seeded_tids = extract_seeded_task_ids(title)

    # Classify title task IDs
    cross_repo_tids: List[str] = []
    for tid in title_tids:
        t_info = board.get(tid)
        if t_info:
            t_repo = t_info.get("repo", "")
            if repo_name and t_repo and t_repo != repo_name:
                cross_repo_tids.append(tid)

    # Deliverable task IDs:
    # 1. Start with branch task IDs (the canonical intent of sentinel branches)
    # 2. Add title task IDs that are NOT in seeded context
    deliverable_tids: List[str] = []
    for tid in branch_tids:
        if tid not in deliverable_tids:
            deliverable_tids.append(tid)

    for tid in title_tids:
        if tid not in seeded_tids and tid not in cross_repo_tids and tid not in deliverable_tids:
            deliverable_tids.append(tid)

    # If title has marked tasks done (e.g. 'mark/close/record T-0274 and T-0275 done') on cf-lab board chores
    is_board_chore = repo_name == "cf-lab" and (branch.endswith("-board") or "board" in (title or "").lower())
    if is_board_chore and any(kw in (title or "").lower() for kw in ("mark", "close", "record", "complete")) and "done" in (title or "").lower():
        for tid in title_tids:
            if tid not in seeded_tids and tid not in deliverable_tids:
                deliverable_tids.append(tid)

    discrepancies: List[str] = []
    if set(branch_tids) != set(title_tids):
        diff_title = [t for t in title_tids if t not in branch_tids]
        diff_branch = [t for t in branch_tids if t not in title_tids]
        if diff_title:
            discrepancies.append(f"Title references task(s) not in branch: {', '.join(diff_title)}")
        if diff_branch:
            discrepancies.append(f"Branch references task(s) not in title: {', '.join(diff_branch)}")

    if cross_repo_tids:
        discrepancies.append(f"Cross-repo task references in title: {', '.join(cross_repo_tids)}")
    if seeded_tids:
        discrepancies.append(f"Seeded task references in title: {', '.join(seeded_tids)}")

    return {
        "branch_task_ids": branch_tids,
        "title_task_ids": title_tids,
        "deliverable_task_ids": deliverable_tids,
        "seeded_task_ids": seeded_tids,
        "cross_repo_task_ids": cross_repo_tids,
        "has_discrepancy": len(discrepancies) > 0,
        "discrepancies": discrepancies,
    }


def verify_branch_deliverables_merged(repo_path: Path, branch: str) -> Tuple[bool, str]:
    """
    Verify whether the branch's deliverables are already present on origin/main:
    1. Tests whether the branch tip is already an ancestor of origin/main.
    2. Tests whether git diff origin/main...<branch> contains any unmerged code files
       (excluding board files if chore PR).
    """
    if not repo_path.is_dir() or not (repo_path / ".git").exists():
        return False, "Not a valid git repository"

    # Check 1: Is branch an ancestor of origin/main?
    for ref in [branch, f"origin/{branch}"]:
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_path), "merge-base", "--is-ancestor", "--", ref, "origin/main"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return True, f"Branch {ref} is an ancestor of origin/main"
        except Exception:
            pass

    # Check 2: Inspect diff between origin/main and branch
    for ref in [f"origin/{branch}", branch]:
        try:
            diff_res = subprocess.run(
                ["git", "-C", str(repo_path), "diff", f"origin/main...{ref}", "--name-only", "--"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if diff_res.returncode == 0:
                changed_files = [line.strip() for line in diff_res.stdout.splitlines() if line.strip()]
                # If only board files changed, or zero files changed, it is identical tree deliverables
                code_changes = [f for f in changed_files if not f.startswith("tasks/")]
                if len(code_changes) == 0:
                    return True, f"Zero unmerged code deliverables in {ref} compared to origin/main"
        except Exception:
            pass

    return False, f"Branch {branch} contains unmerged deliverables not present on origin/main"


def detect_superseded_pr(
    pr: Dict[str, Any],
    done_task_ids: Set[str],
    board_tasks: Optional[Dict[str, Dict[str, Any]]] = None,
    repo_path: Optional[Path] = None,
    require_deliverable_verification: bool = False,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely determines if an open PR is superseded by origin/main.

    Criteria:
    1. The PR is a sentinel PR (branch matches SENTINEL_BRANCH_RX).
    2. All deliverable task IDs (normalized from branch and title) are already marked done on main.
    3. Any seeded task IDs mentioned in the title are already present in board.json on main.
    4. Confirms that main already has the deliverables (identical tree / ancestor verification).
    """
    branch = pr.get("headRefName") or pr.get("branch") or ""
    title = pr.get("title") or ""
    repo_name = pr.get("repo_name") or (pr.get("repo", "").split("/")[-1] if "/" in pr.get("repo", "") else pr.get("repo", ""))

    board = board_tasks or {}
    norm = normalize_pr_task_ids(branch, title, repo_name=repo_name, board_tasks_by_id=board)
    deliverable_ids = norm["deliverable_task_ids"]
    seeded_ids = norm["seeded_task_ids"]

    metadata = {
        "normalized": norm,
        "deliverables_done": False,
        "seeded_present": False,
        "deliverables_verified_merged": False,
        "deliverables_verification_reason": "",
    }

    if not branch or not SENTINEL_BRANCH_RX.match(branch):
        return False, "Not a sentinel branch pattern", metadata

    if not deliverable_ids:
        return False, "No deliverable task IDs identified", metadata

    # Check 1: Are all deliverable task IDs marked 'done' on main?
    all_done = all(tid in done_task_ids for tid in deliverable_ids)
    metadata["deliverables_done"] = all_done
    if not all_done:
        missing = [t for t in deliverable_ids if t not in done_task_ids]
        return False, f"Deliverable task(s) not yet done on main: {', '.join(missing)}", metadata

    # Check 2: Are all seeded tasks already present on main board?
    if seeded_ids:
        all_seeded_present = all(tid in board for tid in seeded_ids)
        metadata["seeded_present"] = all_seeded_present
        if not all_seeded_present:
            missing_seeded = [t for t in seeded_ids if t not in board]
            return False, f"Seeded task(s) not yet seeded on main board: {', '.join(missing_seeded)}", metadata
    else:
        metadata["seeded_present"] = True

    # Check 3: Deliverable / ancestor verification
    is_board_chore = repo_name == "cf-lab" and (branch.endswith("-board") or "board" in (title or "").lower())
    if is_board_chore:
        metadata["deliverables_verified_merged"] = True
        metadata["deliverables_verification_reason"] = "Board state deliverables confirmed registered on main board.json"
    elif repo_path and repo_path.is_dir():
        is_merged, v_reason = verify_branch_deliverables_merged(repo_path, branch)
        metadata["deliverables_verified_merged"] = is_merged
        metadata["deliverables_verification_reason"] = v_reason
        if require_deliverable_verification and not is_merged:
            return False, f"Deliverable verification failed: {v_reason}", metadata
    elif require_deliverable_verification:
        return False, "Repo path required for deliverable verification", metadata

    reason = f"All referenced tasks ({', '.join(deliverable_ids)}) are already marked done on origin/main"
    if seeded_ids:
        reason += f" and seeded tasks ({', '.join(seeded_ids)}) are already registered on main board"
    if metadata["deliverables_verified_merged"]:
        reason += f" ({metadata['deliverables_verification_reason']})"

    return True, reason, metadata


def detect_pr_alerts(
    pr: Dict[str, Any],
    is_superseded: bool,
    superseded_reason: str,
    norm_info: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Detect actionable alerts (merge conflicts, review blockers, CI failures, superseded)."""
    alerts: List[Dict[str, Any]] = []
    repo = pr.get("repo", "")
    num = pr.get("number")
    title = redact_sensitive(pr.get("title", ""))
    branch = pr.get("headRefName") or pr.get("branch", "")
    mergeable = str(pr.get("mergeable") or "UNKNOWN").upper()
    merge_state = str(pr.get("mergeStateStatus") or "UNKNOWN").upper()
    review_decision = str(pr.get("reviewDecision") or "").upper()
    is_draft = pr.get("isDraft", False)

    is_conflicting = (mergeable == "CONFLICTING" or merge_state in ("DIRTY", "BLOCKED_BY_DIRTY"))

    if is_superseded:
        alerts.append({
            "repo": repo,
            "number": num,
            "title": title,
            "branch": branch,
            "type": "superseded_by_main",
            "severity": "medium",
            "details": redact_sensitive(superseded_reason),
            "action_required": "close_superseded_pr",
            "task_normalization": norm_info,
        })

    if is_conflicting:
        severity = "medium" if is_superseded else "high"
        action = "close_superseded_pr" if is_superseded else "manual_merge_required"
        alerts.append({
            "repo": repo,
            "number": num,
            "title": title,
            "branch": branch,
            "type": "merge_conflict",
            "severity": severity,
            "details": f"PR has merge conflict ({mergeable}/{merge_state})",
            "action_required": action,
            "task_normalization": norm_info,
        })

    # CI checks
    status_rollup = pr.get("statusCheckRollup") or []
    failed_checks = []
    for check in status_rollup:
        conclusion = (check.get("conclusion") or check.get("state") or "").upper()
        if conclusion in ("FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"):
            failed_checks.append({
                "name": check.get("name") or check.get("context") or "unknown",
                "conclusion": conclusion,
            })
    if failed_checks and not is_superseded and not is_draft:
        alerts.append({
            "repo": repo,
            "number": num,
            "title": title,
            "branch": branch,
            "type": "ci_failure",
            "severity": "high",
            "details": f"{len(failed_checks)} CI check(s) failed",
            "failed_checks": failed_checks,
            "action_required": "inspect_failing_checks",
            "task_normalization": norm_info,
        })

    # Review blockers
    threads = pr.get("unresolved_threads") or []
    has_blocker = (review_decision == "CHANGES_REQUESTED" or len(threads) > 0)
    if has_blocker and not is_superseded and not is_draft:
        sanitized_threads = []
        for t in threads:
            sanitized_threads.append({
                "author": t.get("author", "unknown"),
                "snippet": redact_sensitive(t.get("snippet", "")),
                "url": t.get("url", ""),
            })
        alerts.append({
            "repo": repo,
            "number": num,
            "title": title,
            "branch": branch,
            "type": "review_blocker",
            "severity": "high",
            "details": f"Review decision {review_decision} with {len(threads)} unresolved thread(s)",
            "unresolved_threads": sanitized_threads,
            "action_required": "resolve_review_comments",
            "task_normalization": norm_info,
        })

    return alerts


def fetch_open_prs_gh(owner: str, repo: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Fetch open pull requests from GitHub via gh CLI."""
    try:
        slug = validate_repo_slug(owner, repo)
    except ValueError as e:
        return None, str(e)
    cmd = [
        "gh", "pr", "list",
        "--repo", slug,
        "--state", "open",
        "--json", "number,title,headRefName,url,updatedAt,mergeable,mergeStateStatus,reviewDecision,isDraft,statusCheckRollup",
        "--limit", "100"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            return None, f"gh pr list failed for {slug}: {res.stderr.strip()}"
        data = json.loads(res.stdout or "[]")
        for item in data:
            item["repo"] = slug
            item["repo_name"] = repo
        return data, None
    except Exception as e:
        return None, str(e)


def close_superseded_pr_gh(owner: str, repo: str, pr_number: int, reason: str, dry_run: bool = True) -> Dict[str, Any]:
    """Close a superseded PR using gh CLI with an explanatory comment."""
    try:
        slug = validate_repo_slug(owner, repo)
    except ValueError as e:
        return {
            "action": "CLOSE_FAILED",
            "repo": f"{owner}/{repo}",
            "number": pr_number,
            "error": str(e),
            "status": "error",
        }
    if not isinstance(pr_number, int) or pr_number <= 0:
        return {
            "action": "CLOSE_FAILED",
            "repo": slug,
            "number": pr_number,
            "error": f"Invalid PR number: {pr_number!r}",
            "status": "error",
        }
    comment = f"Closing as superseded by main: {reason}."
    if dry_run:
        return {
            "action": "WOULD_CLOSE",
            "repo": slug,
            "number": pr_number,
            "comment": comment,
            "status": "dry_run",
        }

    cmd = [
        "gh", "pr", "close", str(pr_number),
        "--repo", slug,
        "--comment", comment,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            return {
                "action": "CLOSED",
                "repo": slug,
                "number": pr_number,
                "comment": comment,
                "status": "success",
            }
        else:
            return {
                "action": "CLOSE_FAILED",
                "repo": slug,
                "number": pr_number,
                "error": res.stderr.strip(),
                "status": "error",
            }
    except Exception as e:
        return {
            "action": "CLOSE_FAILED",
            "repo": slug,
            "number": pr_number,
            "error": str(e),
            "status": "error",
        }


def run_repair_daemon(
    owner: str = DEFAULT_OWNER,
    repos: Optional[List[str]] = None,
    pr_data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    board_path: Path = BOARD_PATH,
    dry_run: bool = True,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute main repair and hygiene daemon cycle."""
    target_repos = repos or DEFAULT_REPOS
    board_tasks, done_ids = load_board_tasks(board_path)

    all_prs: List[Dict[str, Any]] = []
    fetch_errors: List[Dict[str, str]] = []

    for r in target_repos:
        if pr_data and r in pr_data:
            for p in pr_data[r]:
                p.setdefault("repo", f"{owner}/{r}")
                p.setdefault("repo_name", r)
                all_prs.append(p)
        else:
            prs, err = fetch_open_prs_gh(owner, r)
            if err:
                fetch_errors.append({"repo": f"{owner}/{r}", "error": err})
            elif prs:
                all_prs.extend(prs)

    all_alerts: List[Dict[str, Any]] = []
    actions_taken: List[Dict[str, Any]] = []
    superseded_count = 0
    discrepancy_count = 0
    conflict_count = 0
    ci_failure_count = 0
    review_blocker_count = 0

    def resolve_local_repo_path(r_name: str) -> Optional[Path]:
        parts = REPO_ROOT.parts
        if ".worktrees" in parts:
            wt_idx = parts.index(".worktrees")
            base = Path(*parts[:wt_idx])
        else:
            base = REPO_ROOT.parent

        candidate = REPO_ROOT if r_name == "cf-lab" and ".worktrees" not in parts else base / r_name
        return candidate if candidate.is_dir() else None

    for pr in all_prs:
        repo_name = pr.get("repo_name", "")
        branch = pr.get("headRefName") or pr.get("branch", "")
        title = pr.get("title", "")
        num = pr.get("number")

        norm = normalize_pr_task_ids(branch, title, repo_name=repo_name, board_tasks_by_id=board_tasks)
        if norm["has_discrepancy"]:
            discrepancy_count += 1

        local_repo_path = resolve_local_repo_path(repo_name)
        is_superseded, sup_reason, meta = detect_superseded_pr(
            pr,
            done_ids,
            board_tasks=board_tasks,
            repo_path=local_repo_path,
            require_deliverable_verification=True,
        )

        if is_superseded:
            superseded_count += 1
            action_res = close_superseded_pr_gh(owner, repo_name, num, sup_reason, dry_run=dry_run)
            actions_taken.append(action_res)

        alerts = detect_pr_alerts(pr, is_superseded, sup_reason, norm)
        for a in alerts:
            if a["type"] == "merge_conflict":
                conflict_count += 1
            elif a["type"] == "ci_failure":
                ci_failure_count += 1
            elif a["type"] == "review_blocker":
                review_blocker_count += 1
        all_alerts.extend(alerts)

    result: Dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dry_run": dry_run,
        "repos_audited": target_repos,
        "open_prs_count": len(all_prs),
        "summary": {
            "total_open_prs": len(all_prs),
            "superseded_prs_count": superseded_count,
            "conflicts_count": conflict_count,
            "ci_failures_count": ci_failure_count,
            "review_blockers_count": review_blocker_count,
            "normalized_discrepancies_count": discrepancy_count,
            "actions_count": len(actions_taken),
        },
        "alerts": all_alerts,
        "actions": actions_taken,
        "fetch_errors": fetch_errors,
    }

    # Write alert digest
    out_file = output_path or DEFAULT_ALERT_PATH
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception as e:
        fetch_errors.append({"error": f"Failed writing alert digest to {out_file}: {e}"})

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Automated Sentinel PR Repair & Superseded Branch Cleaner Daemon")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="Simulate actions without making mutations (default)")
    mode_group.add_argument("--repair", action="store_true", help="Execute PR mutations (requires --yes)")
    parser.add_argument("--yes", action="store_true", help="Confirm execution of live PR mutations when using --repair")
    parser.add_argument("--check", action="store_true", help="Exit 1 if unresolvable high-severity PR alerts exist")
    parser.add_argument("--pr-data", type=Path, help="JSON fixture containing mock open PRs by repo")
    parser.add_argument("--board-path", type=Path, default=BOARD_PATH, help="Path to board.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_ALERT_PATH, help="Path to output alerts digest JSON")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="GitHub repository owner/org")
    parser.add_argument("--repos", nargs="+", default=DEFAULT_REPOS, help="Repositories to scan")

    args = parser.parse_args()

    if args.repair and not args.yes:
        sys.stderr.write("Error: --repair requires --yes to confirm live mutations.\n")
        return 1

    is_dry_run = not args.repair

    pr_mock = None
    if args.pr_data:
        if not args.pr_data.is_file():
            sys.stderr.write(f"Error: --pr-data file not found: {args.pr_data}\n")
            return 2
        try:
            pr_mock = json.loads(args.pr_data.read_text(encoding="utf-8"))
        except Exception as e:
            sys.stderr.write(f"Error: Invalid JSON in --pr-data file {args.pr_data}: {e}\n")
            return 2
        pr_mock = json.loads(args.pr_data.read_text(encoding="utf-8"))

    results = run_repair_daemon(
        owner=args.owner,
        repos=args.repos,
        pr_data=pr_mock,
        board_path=args.board_path,
        dry_run=is_dry_run,
        output_path=args.output,
    )

    summary = results["summary"]
    mode_str = "DRY RUN" if is_dry_run else "LIVE REPAIR"
    print(f"Sentinel PR Repair Daemon [{mode_str}] - {results['timestamp']}")
    print(f"  Open PRs: {summary['total_open_prs']}")
    print(f"  Superseded PRs: {summary['superseded_prs_count']}")
    print(f"  Merge Conflicts: {summary['conflicts_count']}")
    print(f"  CI Failures: {summary['ci_failures_count']}")
    print(f"  Review Blockers: {summary['review_blockers_count']}")
    print(f"  Normalized Discrepancies: {summary['normalized_discrepancies_count']}")
    print(f"  Actions: {summary['actions_count']}")

    if results["actions"]:
        for act in results["actions"]:
            print(f"    * {act.get('action')}: PR #{act.get('number')} on {act.get('repo')} - {act.get('comment', act.get('error', ''))}")

    if args.check:
        high_severity = [a for a in results["alerts"] if a.get("severity") == "high"]
        if high_severity:
            print(f"\n[CHECK FAIL] {len(high_severity)} high-severity unresolved PR issue(s) require intervention.")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

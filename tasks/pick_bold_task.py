#!/usr/bin/env python3
"""Pick the next bigger, bolder bundle of `ready` board tasks for a scheduled sentinel lane.

Why this exists: the board's ROI triage divides impact by effort, which quietly favors the
smallest task, and the sentinels only audited. This picker ranks the other way (impact x scope),
bundles up to a few related tasks of one repo into one pull request, and still refuses anything
a person has to do, anything with an unfinished dependency, and any lane that already has a
sentinel pull request waiting for review.

  --check   exit 0 when a bundle is available and the lane has capacity (prints a one-line reason
            otherwise: 20 nothing eligible, 21 lane already has an open sentinel PR,
            22 open pull requests could not be read, so build nothing)
  --json    print the bundle as JSON (same selection, no state change)
  --claim   like --json, and record an attempt so a task that keeps failing is not retried forever

Lanes: security (cf-lab, cf-skills, .ai reliability work and everything not claimed below), research
(cf-research, science, sources, evidence), showcase (site and content work, which is what the showcase
sentinel's own rules allow it to open pull requests for).
Branch convention for the pull request: work/sentinel-<lane>-<first-task-id> (`work/` is one of the prefixes
worktrees.py accepts; the lane prefix is what the capacity check looks for).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import triage_board  # noqa: E402  (reuses the human-gate rules and the ROI scoring)
from check_worktree_drift import scan_existing_worktrees  # noqa: E402

REPO_ROOT = HERE.parent
DEFAULT_BOARD = REPO_ROOT / "tasks" / "board.json"
DEFAULT_ATTEMPTS = REPO_ROOT / ".loop-logs" / "bold-attempts.json"
GITHUB_OWNER = "senseiewok"
GITHUB_REPOS = ["cf-lab", "cf-research", "cf-skills", ".ai"]

LANES = ("security", "research", "showcase")
SHOWCASE_AREAS = {"content", "web", "website", "site", "ai-in-care", "ui", "viewer", "frontend"}
RESEARCH_AREAS = {"research", "science", "sources", "evidence", "grounding", "atlas"}

# Wording that means a person must read, test on hardware/external UI, or decide something, which triage_board's approval patterns miss.
PERSON_REVIEW_RX = re.compile(
    r"\b("
    r"registry scientist|scientist review|human review|human reviewer|person review|clinician review|"
    r"the human reads|a human reads|a person reads|a human confirms|a person confirms|"
    r"a human approves|a person approves|awaiting_human|awaiting human|"
    r"on a real mac|in a real client|paste-ready boxes on gemini"
    r")\b",
    re.I,
)

COMPLEXITY_WEIGHT = {"low": 1.0, "medium": 1.5, "high": 2.0}
PRIORITY_WEIGHT = {"P0": 2.0, "P1": 1.5, "P2": 1.0, "P3": 0.7}

SENTINEL_BRANCH_PREFIX_RX = re.compile(r"^work/sentinel-[a-z]+-", re.I)
TASK_ID_TOKEN_RX = re.compile(r"\bt-?(\d{4})\b", re.I)


def lane_of(task: dict) -> str:
    repo = task.get("repo")
    area = task.get("area")
    if area in SHOWCASE_AREAS:
        return "showcase"
    if repo == "cf-research":
        return "research"
    if area in RESEARCH_AREAS:
        return "research"
    return "security"


def needs_a_person(task: dict, human_ids: set[str]) -> bool:
    """True when the task, or a task its text points at, is human-only work or needs a person's review."""
    if task.get("executor") == "human" or task.get("human_required") is True:
        return True
    if triage_board.is_human_gated(task, human_ids)[0]:
        return True
    if re.match(r"\s*decide\b", task.get("title") or "", re.I):
        return True  # "Decide ..." tasks are the maintainer's call
    text = " ".join([task.get("title") or "", task.get("acceptance") or "", task.get("notes") or ""])
    if PERSON_REVIEW_RX.search(text):
        return True
    return any(hid in text for hid in human_ids if hid != task["id"])


def mean_effort(task: dict) -> float:
    eff = task.get("effort_hours")
    if isinstance(eff, dict) and "low" in eff and "high" in eff:
        return (float(eff["low"]) + float(eff["high"])) / 2.0
    if isinstance(eff, (int, float)):
        return float(eff)
    return 2.0


def impact(task: dict) -> float:
    roi = task.get("roi") or {}
    score = roi.get("composite_score")
    if isinstance(score, (int, float)):
        return float(score)
    return float(triage_board.compute_multi_category_roi(task)["composite_score"])


def boldness(task: dict) -> float:
    """Impact x priority x scope. Scope grows with complexity and (square root of) effort, capped at 8 h."""
    scope = COMPLEXITY_WEIGHT.get(task.get("complexity"), 1.0) * math.sqrt(min(max(mean_effort(task), 0.5), 8.0))
    return impact(task) * PRIORITY_WEIGHT.get(task.get("priority"), 1.0) * scope


def recent_attempts(attempts: dict, task_id: str, now: datetime, window_hours: float) -> int:
    n = 0
    for ts in attempts.get(task_id, []):
        try:
            when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if now - when <= timedelta(hours=window_hours):
            n += 1
    return n


def open_pr_task_ids(prs: list[dict]) -> set[str]:
    """Task IDs (e.g. 'T-0083') that already have an open sentinel PR (including draft PRs and bundled secondary tasks)."""
    ids: set[str] = set()
    for p in prs:
        branch = str(p.get("headRefName", ""))
        if not SENTINEL_BRANCH_PREFIX_RX.match(branch):
            continue
        combined = f"{branch} {p.get('title', '')}"
        for digits in TASK_ID_TOKEN_RX.findall(combined):
            ids.add(f"T-{digits}")
    return ids


def eligible(tasks: list[dict], lane: str, human_ids: set[str], attempts: dict, now: datetime,
             attempt_limit: int, window_hours: float, max_task_hours: float,
             oversize: list[str] | None = None,
             skip_ids: set[str] | None = None) -> list[dict]:
    done = {t["id"] for t in tasks if t.get("status") == "done"}
    skipped = skip_ids or set()
    out = []
    for t in tasks:
        if t["id"] in skipped:
            continue
        if t.get("status") != "ready" or lane_of(t) != lane:
            continue
        if t.get("repo") not in GITHUB_REPOS:
            continue
        if needs_a_person(t, human_ids):
            continue
        if any(dep not in done for dep in (t.get("depends_on") or [])):
            continue
        if recent_attempts(attempts, t["id"], now, window_hours) >= attempt_limit:
            continue
        if mean_effort(t) > max_task_hours:
            # too big for one run: report it so the board can split it, never hand it to an agent whole
            if oversize is not None:
                oversize.append(t["id"])
            continue
        out.append(t)
    return out


def build_bundle(candidates: list[dict], max_tasks: int, max_hours: float,
                 all_tasks: list[dict] | None = None, lane: str | None = None,
                 human_ids: set[str] | None = None, attempts: dict | None = None,
                 now: datetime | None = None, attempt_limit: int = 2,
                 window_hours: float = 48.0, max_task_hours: float = 12.0,
                 skip_ids: set[str] | None = None) -> list[dict]:
    """Best task first, then related ready tasks of the same repo and area (including direct dependency chains) within budget."""
    ranked = sorted(candidates, key=boldness, reverse=True)
    if not ranked:
        return []
    top = ranked[0]
    bundle = [top]
    bundled_ids = {top["id"]}
    total = mean_effort(top)
    max_hours = max(max_hours, total)

    for t in ranked[1:]:
        if len(bundle) >= max_tasks:
            break
        if t.get("repo") != top.get("repo") or t.get("area") != top.get("area"):
            continue
        if total + mean_effort(t) > max_hours:
            continue
        bundle.append(t)
        bundled_ids.add(t["id"])
        total += mean_effort(t)

    # Also allow chaining direct dependents in the same repo and area whose dependencies are now satisfied by (done U bundle).
    if all_tasks and len(bundle) < max_tasks:
        done = {t["id"] for t in all_tasks if t.get("status") == "done"}
        skipped = skip_ids or set()
        h_ids = human_ids or set()
        att = attempts or {}
        cur_now = now or datetime.now(timezone.utc)
        changed = True
        while changed and len(bundle) < max_tasks:
            changed = False
            satisfied = done | bundled_ids
            chain_candidates = []
            for t in all_tasks:
                if t["id"] in bundled_ids or t["id"] in skipped:
                    continue
                if t.get("status") != "ready":
                    continue
                if lane and lane_of(t) != lane:
                    continue
                if t.get("repo") != top.get("repo") or t.get("area") != top.get("area"):
                    continue
                if needs_a_person(t, h_ids):
                    continue
                deps = t.get("depends_on") or []
                if not deps or any(dep not in satisfied for dep in deps):
                    continue
                if recent_attempts(att, t["id"], cur_now, window_hours) >= attempt_limit:
                    continue
                if mean_effort(t) > max_task_hours or total + mean_effort(t) > max_hours:
                    continue
                chain_candidates.append(t)
            if chain_candidates:
                best_dep = sorted(chain_candidates, key=boldness, reverse=True)[0]
                bundle.append(best_dep)
                bundled_ids.add(best_dep["id"])
                total += mean_effort(best_dep)
                changed = True

    return bundle


def read_open_prs(path: str | None) -> list[dict] | None:
    """Open pull requests with merge and check status, or None when they cannot be read."""
    if path:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return None
            return [
                {
                    "repo": p["repo"],
                    "number": p.get("number"),
                    "headRefName": p["headRefName"],
                    "isDraft": bool(p.get("isDraft", False)),
                    "title": str(p.get("title", "")),
                    "url": str(p.get("url", "")),
                    "mergeable": str(p.get("mergeable", "MERGEABLE")),
                    "mergeStateStatus": str(p.get("mergeStateStatus", "CLEAN")),
                    "reviewDecision": str(p.get("reviewDecision", "")),
                    "statusCheckRollup": list(p.get("statusCheckRollup") or []),
                    "unresolved_threads": list(p.get("unresolved_threads") or []),
                }
                for p in raw
            ]
        except (OSError, ValueError, KeyError, TypeError):
            return None
    prs: list[dict] = []
    for repo in GITHUB_REPOS:
        try:
            res = subprocess.run(
                ["gh", "pr", "list", "--repo", f"{GITHUB_OWNER}/{repo}", "--state", "open",
                 "--json", "number,headRefName,isDraft,title,url,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup",
                 "--limit", "100"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if res.returncode != 0:
            return None
        try:
            prs.extend(
                {
                    "repo": repo,
                    "number": p.get("number"),
                    "headRefName": p["headRefName"],
                    "isDraft": bool(p.get("isDraft", False)),
                    "title": str(p.get("title", "")),
                    "url": str(p.get("url", "")),
                    "mergeable": str(p.get("mergeable", "UNKNOWN")),
                    "mergeStateStatus": str(p.get("mergeStateStatus", "UNKNOWN")),
                    "reviewDecision": str(p.get("reviewDecision", "")),
                    "statusCheckRollup": list(p.get("statusCheckRollup") or []),
                    "unresolved_threads": list(p.get("unresolved_threads") or []),
                }
                for p in json.loads(res.stdout)
            )
        except (ValueError, KeyError, TypeError):
            return None
    return prs


def pr_task_ids(pr: dict) -> list[str]:
    """Ordered unique T-XXXX task IDs mentioned in a PR's branch or title."""
    combined = f"{pr.get('headRefName', '')} {pr.get('title', '')}"
    out: list[str] = []
    for digits in TASK_ID_TOKEN_RX.findall(combined):
        tid = f"T-{digits}"
        if tid not in out:
            out.append(tid)
    return out


def is_sentinel_branch(branch: str) -> bool:
    """True when a branch follows one of the lab's autonomous sentinel naming conventions."""
    low = branch.lower()
    return low.startswith(("work/sentinel-", "site/showcase-", "sec-fix-", "agent-improve-"))


def pr_lane_of(pr: dict, tasks_by_id: dict[str, dict]) -> str | None:
    """Assign an open sentinel PR to the lane responsible for checking and repairing it.

    Non-sentinel branches (e.g. human feature branches or external bots without a sentinel prefix
    or known board task ID) return None so sentinels never hijack unrelated branches.
    """
    branch = str(pr.get("headRefName", ""))
    low = branch.lower()
    m = re.match(r"^work/sentinel-(security|research|showcase)-", low)
    if m:
        return m.group(1)
    if low.startswith("site/showcase-"):
        return "showcase"
    if low.startswith(("sec-fix-", "agent-improve-")):
        return "security"
    for tid in pr_task_ids(pr):
        if tid in tasks_by_id:
            return lane_of(tasks_by_id[tid])
    return None


def pr_failed_checks(pr: dict) -> list[dict]:
    """Return failing CheckRun or StatusContext entries from statusCheckRollup."""
    failed: list[dict] = []
    for check in (pr.get("statusCheckRollup") or []):
        if not isinstance(check, dict):
            continue
        conclusion = str(check.get("conclusion") or check.get("state") or "").upper()
        if conclusion in ("FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"):
            failed.append({
                "name": str(check.get("name") or check.get("context") or "unknown"),
                "workflow": str(check.get("workflowName") or ""),
                "conclusion": conclusion,
                "details_url": str(check.get("detailsUrl") or check.get("targetUrl") or ""),
            })
    return failed


def pr_issues(pr: dict, done_ids: set[str]) -> list[str]:
    """Return actionable PR issues (merge_conflict, ci_failure, review_blocker, superseded_by_main)."""
    issues: list[str] = []
    mergeable = str(pr.get("mergeable") or "").upper()
    merge_state = str(pr.get("mergeStateStatus") or "").upper()
    if mergeable == "CONFLICTING" or merge_state in ("DIRTY", "BLOCKED_BY_DIRTY"):
        issues.append("merge_conflict")

    failed = pr_failed_checks(pr)
    for fc in failed:
        issues.append(f"ci_failure:{fc['name']}({fc['conclusion']})")

    review_decision = str(pr.get("reviewDecision") or "").upper()
    threads = pr.get("unresolved_threads") or []
    if review_decision == "CHANGES_REQUESTED" or len(threads) > 0:
        issues.append("review_blocker")

    tids = pr_task_ids(pr)
    branch = str(pr.get("headRefName", ""))
    if tids and done_ids and is_sentinel_branch(branch) and all(tid in done_ids for tid in tids):
        issues.append("superseded_by_main")

    return issues


def pr_attempt_key(pr: dict) -> str:
    ident = pr.get("number") if pr.get("number") is not None else pr.get("headRefName", "unknown")
    return f"PR:{pr.get('repo', 'unknown')}#{ident}"


def summarize_pr_repair(pr: dict, issues: list[str]) -> dict:
    repo = str(pr.get("repo") or "")
    return {
        "repo": repo,
        "repo_slug": f"{GITHUB_OWNER}/{repo}" if repo else GITHUB_OWNER,
        "number": pr.get("number"),
        "branch": pr.get("headRefName"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "is_draft": bool(pr.get("isDraft", False)),
        "mergeable": pr.get("mergeable"),
        "merge_state": pr.get("mergeStateStatus"),
        "review_decision": pr.get("reviewDecision"),
        "failed_checks": pr_failed_checks(pr),
        "unresolved_threads": pr.get("unresolved_threads") or [],
        "task_ids": pr_task_ids(pr),
        "issues": issues,
        "repair_steps": [
            "If superseded_by_main: verify deliverables and task status on origin/main, then close the duplicate PR with 'gh pr close <number> --repo <repo_slug>'.",
            "If merge_conflict: in the PR worktree, run 'git fetch origin main' and 'git merge origin/main' (never force-push), resolve conflicts, regenerate derived files (e.g. render-board.ps1), run checks + run-gate.ps1, and push.",
            "If ci_failure or review_blocker: inspect failed check logs ('gh pr checks <number> --repo <repo_slug>' / 'gh run view --log-failed') and unresolved review comments ('gh api repos/<repo_slug>/pulls/<number>/comments'), apply minimal deterministic fix in the worktree, verify via run-gate.ps1, and push.",
        ],
    }


def summarize(t: dict, repo_root: Path = REPO_ROOT) -> dict:
    entry = {
        "id": t["id"], "title": t.get("title"), "repo": t.get("repo"), "area": t.get("area"),
        "priority": t.get("priority"), "complexity": t.get("complexity"),
        "review_tier": t.get("review_tier"), "recommended_route": t.get("recommended_route"),
        "effort_hours": t.get("effort_hours"), "acceptance": t.get("acceptance"),
    }
    spec_path_str = t.get("spec_path")
    candidate_path = None
    if spec_path_str:
        p = triage_board.resolve_repo_file(repo_root, spec_path_str)
        if p and p.is_file():
            candidate_path = p
        elif (repo_root / spec_path_str).is_file():
            candidate_path = (repo_root / spec_path_str).resolve()
    else:
        default_spec = f"tasks/specs/{t['id']}.md"
        p = triage_board.resolve_repo_file(repo_root, default_spec)
        if p and p.is_file():
            candidate_path = p
            spec_path_str = default_spec
        elif (repo_root / default_spec).is_file():
            candidate_path = (repo_root / default_spec).resolve()
            spec_path_str = default_spec

    if candidate_path and candidate_path.is_file():
        entry["spec_path"] = spec_path_str.replace("\\", "/")
        try:
            entry["spec_markdown"] = candidate_path.read_text(encoding="utf-8")
        except Exception:
            entry["spec_markdown"] = None
    elif spec_path_str:
        entry["spec_path"] = spec_path_str.replace("\\", "/")
        entry["spec_markdown"] = None

    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", required=True, choices=LANES)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--json", action="store_true")
    mode.add_argument("--claim", action="store_true")
    ap.add_argument("--board", default=str(DEFAULT_BOARD))
    ap.add_argument("--human-file", default=str(triage_board.HUMAN_TASKS_PATH))
    ap.add_argument("--attempts-file", default=str(DEFAULT_ATTEMPTS))
    ap.add_argument("--open-prs-file", default=None, help="test hook: JSON list instead of asking gh")
    ap.add_argument("--now", default=None, help="test hook: ISO time")
    ap.add_argument("--max-bundle-tasks", type=int, default=3)
    ap.add_argument("--max-bundle-hours", type=float, default=8.0)
    ap.add_argument("--max-task-hours", type=float, default=12.0,
                    help="a single task estimated above this many mean hours is never handed out (split it on the board)")
    ap.add_argument("--attempt-limit", type=int, default=2)
    ap.add_argument("--attempt-window-hours", type=float, default=48.0)
    args = ap.parse_args(argv)

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    board_path = Path(args.board)
    board_repo_root = board_path.resolve().parent.parent if board_path.resolve().parent.name == "tasks" else board_path.resolve().parent
    board = json.loads(board_path.read_text(encoding="utf-8"))
    tasks = board["tasks"] if isinstance(board, dict) else board
    tasks_by_id = {t["id"]: t for t in tasks if isinstance(t, dict) and "id" in t}
    done_ids = {t["id"] for t in tasks if isinstance(t, dict) and t.get("status") == "done" and "id" in t}
    human_ids = triage_board.load_human_gated_ids(Path(args.human_file))
    attempts_path = Path(args.attempts_file)
    try:
        attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        attempts = {}

    prs = read_open_prs(args.open_prs_file)
    if prs is None:
        print("capacity unknown: open pull requests could not be read, building nothing")
        return 22

    # 1. PR Check & Merge Conflict Repair First:
    # Before blocking a lane on an open PR, check whether any open sentinel PR in this lane has failing CI checks,
    # merge conflicts (CONFLICTING / DIRTY), review blockers, or is superseded by tasks already done on main.
    # If so, wake the sentinel in pr_repair mode (up to attempt_limit retries per window) instead of exiting 21.
    repairs: list[dict] = []
    repair_keys: list[str] = []
    for p in prs:
        if pr_lane_of(p, tasks_by_id) != args.lane:
            continue
        issues = pr_issues(p, done_ids)
        if not issues:
            continue
        rkey = pr_attempt_key(p)
        if recent_attempts(attempts, rkey, now, args.attempt_window_hours) >= args.attempt_limit:
            continue
        repairs.append(summarize_pr_repair(p, issues))
        repair_keys.append(rkey)

    if repairs:
        top_repair = repairs[0]
        top_key = repair_keys[0]
        existing_wts = scan_existing_worktrees(repo_root=board_repo_root, task_ids=top_repair.get("task_ids", []), lane=args.lane)
        repair_result = {
            "mode": "pr_repair",
            "lane": args.lane,
            "branch": top_repair["branch"],
            "repo": top_repair["repo"],
            "repo_slug": top_repair["repo_slug"],
            "total_mean_effort_hours": 1.5,
            "pr_repairs": [top_repair],
            "queued_pr_repairs_count": len(repairs),
            "existing_worktrees": existing_wts,
            "bundle": [],
            "why": "open pull request in this lane has failing checks, merge conflicts, review blockers, or is superseded by main",
            "too_big_to_hand_out": [],
        }
        if args.check:
            summary_str = ", ".join(
                f"{r['repo_slug']}#{r['number'] if r.get('number') is not None else r['branch']} ({'+'.join(r['issues'])})"
                for r in repairs
            )
            print(f"pr repair needed: {summary_str}")
            return 0
        if args.claim:
            stamp = now.isoformat()
            attempts.setdefault(top_key, []).append(stamp)
            attempts_path.parent.mkdir(parents=True, exist_ok=True)
            attempts_path.write_text(json.dumps(attempts, indent=2), encoding="utf-8")
        print(json.dumps(repair_result, indent=2))
        return 0

    # 2. Capacity check for healthy open sentinel PRs:
    # A lane with a healthy non-draft sentinel pull request still waiting for review builds nothing more.
    # Draft sentinel PRs (e.g. parked awaiting human sign-off on a licence or API key) do not freeze the lane,
    # and their task IDs are skipped in eligible() so they are not re-claimed.
    prefix = f"work/sentinel-{args.lane}-"
    lane_prs = [
        p for p in prs
        if str(p.get("headRefName", "")).startswith(prefix)
        or (args.lane == "showcase" and str(p.get("headRefName", "")).lower().startswith("site/showcase-"))
    ]
    waiting = [p for p in lane_prs if not p.get("isDraft", False)]
    if waiting:
        print(f"lane {args.lane} already has an open sentinel pull request ({waiting[0]['repo']}: {waiting[0]['headRefName']})")
        return 21
    drafts = [p for p in lane_prs if p.get("isDraft", False)]
    if len(drafts) >= 2:
        print(f"lane {args.lane} already has {len(drafts)} open draft sentinel pull requests (cap 2)")
        return 21

    skip_ids = open_pr_task_ids(prs)
    oversize: list[str] = []
    candidates = eligible(tasks, args.lane, human_ids, attempts, now, args.attempt_limit,
                          args.attempt_window_hours, args.max_task_hours, oversize, skip_ids=skip_ids)
    bundle = build_bundle(
        candidates, args.max_bundle_tasks, args.max_bundle_hours,
        all_tasks=tasks, lane=args.lane, human_ids=human_ids,
        attempts=attempts, now=now, attempt_limit=args.attempt_limit,
        window_hours=args.attempt_window_hours, max_task_hours=args.max_task_hours,
        skip_ids=skip_ids,
    )
    if not bundle:
        extra = f" ({len(oversize)} too big for one run, split on the board: {', '.join(oversize)})" if oversize else ""
        print(f"no eligible ready task in lane {args.lane}{extra}")
        return 20

    picked_task_ids = [t["id"] for t in bundle]
    existing_wts = scan_existing_worktrees(repo_root=board_repo_root, task_ids=picked_task_ids, lane=args.lane)
    result = {
        "mode": "build",
        "lane": args.lane,
        "branch": f"{prefix}{bundle[0]['id'].lower()}",
        "repo": bundle[0].get("repo"),
        "total_mean_effort_hours": round(sum(mean_effort(t) for t in bundle), 2),
        "pr_repairs": [],
        "existing_worktrees": existing_wts,
        "bundle": [summarize(t, board_repo_root) for t in bundle],
        "why": "ranked by impact x priority x scope (complexity, effort), not by impact per hour",
        "too_big_to_hand_out": oversize,
    }
    if args.check:
        print(f"work available: {', '.join(t['id'] for t in bundle)} (~{result['total_mean_effort_hours']} h, repo {result['repo']})")
        return 0
    if args.claim:
        stamp = now.isoformat()
        for t in bundle:
            attempts.setdefault(t["id"], []).append(stamp)
        attempts_path.parent.mkdir(parents=True, exist_ok=True)
        attempts_path.write_text(json.dumps(attempts, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0



if __name__ == "__main__":
    raise SystemExit(main())

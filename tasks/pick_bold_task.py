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

Lanes: security (cf-lab, cf-skills and everything not claimed below), research (cf-research, science,
sources, evidence), showcase (.ai, site and content work).
Branch convention for the pull request: sentinel/<lane>/<first-task-id>.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import triage_board  # noqa: E402  (reuses the human-gate rules and the ROI scoring)

REPO_ROOT = HERE.parent
DEFAULT_BOARD = REPO_ROOT / "tasks" / "board.json"
DEFAULT_ATTEMPTS = REPO_ROOT / ".loop-logs" / "bold-attempts.json"
GITHUB_OWNER = "senseiewok"
GITHUB_REPOS = ["cf-lab", "cf-research", "cf-skills", ".ai"]

LANES = ("security", "research", "showcase")
SHOWCASE_AREAS = {"content", "web", "website", "site"}
RESEARCH_AREAS = {"research", "science", "sources", "evidence", "grounding", "atlas"}

COMPLEXITY_WEIGHT = {"low": 1.0, "medium": 1.5, "high": 2.0}
PRIORITY_WEIGHT = {"P0": 2.0, "P1": 1.5, "P2": 1.0, "P3": 0.7}


def lane_of(task: dict) -> str:
    repo = task.get("repo")
    area = task.get("area")
    if repo == ".ai":
        return "showcase"
    if repo == "cf-research":
        return "research"
    if area in SHOWCASE_AREAS:
        return "showcase"
    if area in RESEARCH_AREAS:
        return "research"
    return "security"


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


def eligible(tasks: list[dict], lane: str, human_ids: set[str], attempts: dict, now: datetime,
             attempt_limit: int, window_hours: float) -> list[dict]:
    done = {t["id"] for t in tasks if t.get("status") == "done"}
    out = []
    for t in tasks:
        if t.get("status") != "ready" or lane_of(t) != lane:
            continue
        if t.get("executor") == "human" or t.get("human_required") is True:
            continue
        if triage_board.is_human_gated(t, human_ids)[0]:
            continue
        if any(dep not in done for dep in (t.get("depends_on") or [])):
            continue
        if recent_attempts(attempts, t["id"], now, window_hours) >= attempt_limit:
            continue
        out.append(t)
    return out


def build_bundle(candidates: list[dict], max_tasks: int, max_hours: float) -> list[dict]:
    """Best task first, then related ready tasks of the same repo and area while the total stays within budget."""
    ranked = sorted(candidates, key=boldness, reverse=True)
    if not ranked:
        return []
    top = ranked[0]
    bundle = [top]
    total = mean_effort(top)
    for t in ranked[1:]:
        if len(bundle) >= max_tasks:
            break
        if t.get("repo") != top.get("repo") or t.get("area") != top.get("area"):
            continue
        if total + mean_effort(t) > max_hours:
            continue
        bundle.append(t)
        total += mean_effort(t)
    return bundle


def read_open_prs(path: str | None) -> list[dict] | None:
    """Open pull requests as [{repo, headRefName}], or None when they cannot be read."""
    if path:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    prs: list[dict] = []
    for repo in GITHUB_REPOS:
        try:
            res = subprocess.run(
                ["gh", "pr", "list", "--repo", f"{GITHUB_OWNER}/{repo}", "--state", "open",
                 "--json", "headRefName", "--limit", "100"],
                capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if res.returncode != 0:
            return None
        try:
            prs.extend({"repo": repo, "headRefName": p["headRefName"]} for p in json.loads(res.stdout))
        except (ValueError, KeyError):
            return None
    return prs


def summarize(t: dict) -> dict:
    return {
        "id": t["id"], "title": t.get("title"), "repo": t.get("repo"), "area": t.get("area"),
        "priority": t.get("priority"), "complexity": t.get("complexity"),
        "review_tier": t.get("review_tier"), "recommended_route": t.get("recommended_route"),
        "effort_hours": t.get("effort_hours"), "acceptance": t.get("acceptance"),
    }


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
    ap.add_argument("--attempt-limit", type=int, default=2)
    ap.add_argument("--attempt-window-hours", type=float, default=48.0)
    args = ap.parse_args(argv)

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    board = json.loads(Path(args.board).read_text(encoding="utf-8"))
    tasks = board["tasks"] if isinstance(board, dict) else board
    human_ids = triage_board.load_human_gated_ids(Path(args.human_file))
    attempts_path = Path(args.attempts_file)
    try:
        attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        attempts = {}

    # Capacity first: a lane with a sentinel pull request still waiting for review builds nothing more.
    prs = read_open_prs(args.open_prs_file)
    if prs is None:
        print("capacity unknown: open pull requests could not be read, building nothing")
        return 22
    prefix = f"sentinel/{args.lane}/"
    waiting = [p for p in prs if str(p.get("headRefName", "")).startswith(prefix)]
    if waiting:
        print(f"lane {args.lane} already has an open sentinel pull request ({waiting[0]['repo']}: {waiting[0]['headRefName']})")
        return 21

    candidates = eligible(tasks, args.lane, human_ids, attempts, now, args.attempt_limit, args.attempt_window_hours)
    bundle = build_bundle(candidates, args.max_bundle_tasks, args.max_bundle_hours)
    if not bundle:
        print(f"no eligible ready task in lane {args.lane}")
        return 20

    result = {
        "lane": args.lane,
        "branch": f"{prefix}{bundle[0]['id'].lower()}",
        "repo": bundle[0].get("repo"),
        "total_mean_effort_hours": round(sum(mean_effort(t) for t in bundle), 2),
        "bundle": [summarize(t) for t in bundle],
        "why": "ranked by impact x priority x scope (complexity, effort), not by impact per hour",
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

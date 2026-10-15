#!/usr/bin/env python3
"""Deterministic Task Board Update Helper.

Applies atomic, targeted updates to tasks in tasks/board.json to mitigate
concurrent board merge conflicts across branches and sentinels.

Usage:
    python tasks/update_task.py --id T-0146 --status done --notes "Verified via .ai PR #82" --render
    python tasks/update_task.py --id T-0168 --evidence-packet cf-research/landscape/multi-registry-eligibility-2026.md --answer-tier T2 --render
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = REPO_ROOT / "tasks" / "board.json"
RENDER_SCRIPT = REPO_ROOT / "tasks" / "render-board.ps1"


def update_task(
    board_path: Path,
    task_id: str,
    status: str | None = None,
    branch: str | None = None,
    notes: str | None = None,
    append_notes: bool = True,
    actual_hours: float | None = None,
    measured_outcome: str | None = None,
    evidence_packet: str | None = None,
    claims_file: str | None = None,
    catalog_sources: list[str] | None = None,
    answer_tier: str | None = None,
    verified_at: str | None = None,
    completed_by_name: str | None = None,
    completed_by_kind: str | None = None,
    completed_by_model: str | None = None,
    render: bool = False,
) -> bool:
    """Apply targeted updates to a single task in board.json."""
    if not board_path.is_file():
        print(f"ERROR: Board file not found at {board_path}", file=sys.stderr)
        return False

    with open(board_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    task = None
    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            task = t
            break

    if not task:
        print(f"ERROR: Task {task_id} not found in {board_path}", file=sys.stderr)
        return False

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    # Update status
    if status:
        valid_statuses = ("proposed", "ready", "in_progress", "done", "blocked", "dropped")
        if status not in valid_statuses:
            print(f"ERROR: Invalid status '{status}'. Must be one of {valid_statuses}", file=sys.stderr)
            return False
        task["status"] = status
        task["updated_at"] = now_iso

        if status == "done":
            if not task.get("completed_at"):
                task["completed_at"] = now_iso
            if completed_by_kind or completed_by_name or not task.get("completed_by"):
                c_kind = completed_by_kind or ("model" if completed_by_model else "human")
                c_obj: dict[str, str] = {"kind": c_kind}
                if completed_by_name:
                    c_obj["name"] = completed_by_name
                elif c_kind == "model":
                    c_obj["name"] = "Sensei Ewok Agent"
                else:
                    c_obj["name"] = "Maintainer"
                if completed_by_model:
                    c_obj["model_id"] = completed_by_model
                task["completed_by"] = c_obj

    # Update branch
    if branch is not None:
        if branch == "clear" or branch == "":
            task.pop("branch", None)
        else:
            task["branch"] = branch

    # Update notes
    if notes is not None:
        existing_notes = task.get("notes") or ""
        if append_notes and existing_notes:
            task["notes"] = f"{existing_notes} | {notes}"
        else:
            task["notes"] = notes

    # Update measured outcome & actual hours
    if actual_hours is not None or measured_outcome is not None:
        if not isinstance(task.get("roi"), dict):
            task["roi"] = {}
        if actual_hours is not None:
            task["roi"]["actual_hours"] = actual_hours
            task["roi"]["measured"] = True
        if measured_outcome is not None:
            task["roi"]["measured_outcome"] = measured_outcome
            task["roi"]["measured"] = True

    # Update evidence package
    if evidence_packet is not None or claims_file is not None or catalog_sources is not None or answer_tier is not None:
        ep = task.get("evidence_package") or {}
        if evidence_packet is not None:
            ep["packet_path"] = evidence_packet
        if claims_file is not None:
            ep["claims_file"] = None if claims_file == "none" else claims_file
        if catalog_sources is not None:
            ep["catalog_sources"] = catalog_sources
        if answer_tier is not None:
            if answer_tier not in ("T0", "T1", "T2", "T3"):
                print(f"ERROR: Invalid answer_tier '{answer_tier}'", file=sys.stderr)
                return False
            ep["answer_tier"] = answer_tier
        if verified_at is not None:
            ep["verified_at"] = verified_at
        elif "verified_at" not in ep:
            ep["verified_at"] = today_str
        task["evidence_package"] = ep

    # Write formatted JSON back to board.json
    with open(board_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"SUCCESS: Updated {task_id} in {board_path}")

    # Render board if requested
    if render:
        if RENDER_SCRIPT.is_file():
            print("Rendering board markdown via render-board.ps1...")
            res = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(RENDER_SCRIPT)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                print(f"ERROR: render-board.ps1 failed (exit {res.returncode}):\n{res.stderr}", file=sys.stderr)
                return False
            print(res.stdout.strip())
        else:
            print("WARNING: render-board.ps1 not found; skipping render.", file=sys.stderr)

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Task Board Update Helper")
    parser.add_argument("--id", required=True, help="Task ID (e.g. T-0146)")
    parser.add_argument("--status", choices=["proposed", "ready", "in_progress", "done", "blocked", "dropped"])
    parser.add_argument("--branch", help="Git branch name, or 'clear' to unset")
    parser.add_argument("--notes", help="Notes text to set or append")
    parser.add_argument("--replace-notes", action="store_true", help="Replace notes entirely instead of appending")
    parser.add_argument("--actual-hours", type=float, help="Actual effort hours")
    parser.add_argument("--measured-outcome", help="Measured outcome text")
    parser.add_argument("--evidence-packet", help="Path to evidence packet markdown")
    parser.add_argument("--claims-file", help="Path to companion claims JSON, or 'none'")
    parser.add_argument("--catalog-sources", help="Comma-separated catalog source IDs")
    parser.add_argument("--answer-tier", choices=["T0", "T1", "T2", "T3"])
    parser.add_argument("--verified-at", help="Verification date (YYYY-MM-DD)")
    parser.add_argument("--completed-by-name", help="Completed by person/agent name")
    parser.add_argument("--completed-by-kind", choices=["human", "model"])
    parser.add_argument("--completed-by-model", help="Completed by model ID")
    parser.add_argument("--render", action="store_true", help="Run render-board.ps1 after updating")
    parser.add_argument("--board", type=Path, default=BOARD_PATH, help="Path to board.json")

    args = parser.parse_args()

    cat_sources = [s.strip() for s in args.catalog_sources.split(",")] if args.catalog_sources else None

    success = update_task(
        board_path=args.board,
        task_id=args.id,
        status=args.status,
        branch=args.branch,
        notes=args.notes,
        append_notes=not args.replace_notes,
        actual_hours=args.actual_hours,
        measured_outcome=args.measured_outcome,
        evidence_packet=args.evidence_packet,
        claims_file=args.claims_file,
        catalog_sources=cat_sources,
        answer_tier=args.answer_tier,
        verified_at=args.verified_at,
        completed_by_name=args.completed_by_name,
        completed_by_kind=args.completed_by_kind,
        completed_by_model=args.completed_by_model,
        render=args.render,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Single-Branch, Single-PR Board Synchronization Manager (feat/board-sync).

Enforces the lab-wide invariant that all task board changes (`tasks/board.json`,
`tasks/BOARD.md`, and `tasks/specs/T-*.md`) across all sentinels, stewards, and
interactive sessions use the single canonical branch `feat/board-sync` (in worktree
`../.worktrees/cf-lab/board-sync`) and reuse a single open GitHub pull request on
`senseiewok/cf-lab`.

Modes:
  --prepare   Ensure `../.worktrees/cf-lab/board-sync` is checked out on `feat/board-sync`,
              synced with `origin/main` (and `origin/feat/board-sync` if an open PR exists,
              or reset cleanly to `origin/main` if the previous PR was merged/closed).
  --publish   Re-render `tasks/BOARD.md`, verify `tasks/check_task_specs.py --check`,
              commit staged/modified board files, push `origin feat/board-sync`, and
              create or update the single open `feat/board-sync` PR on `senseiewok/cf-lab`.
  --check     Deterministic policy check verifying that sentinel prompts and skills
              enforce the single `feat/board-sync` branch/PR strategy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
BOARD_SYNC_BRANCH = "feat/board-sync"
BOARD_SYNC_TOPIC = "board-sync"
DEFAULT_REPO_SLUG = "senseiewok/cf-lab"
ALLOWED_BOARD_PATHS = ("tasks/board.json", "tasks/BOARD.md", "tasks/specs/")


def resolve_worktree_path(repo_root: Path = REPO_ROOT) -> Path:
    """Resolve the canonical `../.worktrees/cf-lab/board-sync` worktree directory."""
    parts = repo_root.resolve().parts
    if ".worktrees" in parts:
        idx = parts.index(".worktrees")
        workspace_parent = Path(*parts[:idx])
    else:
        workspace_parent = repo_root.resolve().parent
    return workspace_parent / ".worktrees" / "cf-lab" / BOARD_SYNC_TOPIC


def is_board_only_path(rel_path: str) -> bool:
    """Return True if rel_path belongs to the allowed board/spec file set."""
    norm = rel_path.replace("\\", "/").lstrip("./")
    return norm in ("tasks/board.json", "tasks/BOARD.md") or norm.startswith("tasks/specs/")


def find_open_board_pr(
    repo_slug: str = DEFAULT_REPO_SLUG,
    head_branch: str = BOARD_SYNC_BRANCH,
    open_prs: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Return the open PR dict for `feat/board-sync` if one is currently open, else None."""
    if open_prs is not None:
        for pr in open_prs:
            if str(pr.get("headRefName", "")).strip().lower() == head_branch.lower():
                return pr
        return None

    cmd = [
        "gh", "pr", "list",
        "--repo", repo_slug,
        "--head", head_branch,
        "--state", "open",
        "--json", "number,title,body,headRefName,url",
        "--limit", "5",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if res.returncode != 0:
        raise RuntimeError(f"gh pr list failed: {res.stderr.strip()}")
    items = json.loads(res.stdout or "[]")
    return items[0] if items else None


def build_updated_pr_body(existing_body: str, summary_line: str, timestamp: Optional[str] = None) -> str:
    """Append a dated update entry to the single board PR body without losing prior entries."""
    ts = timestamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bullet = f"- **{ts}**: {summary_line.strip()}"
    header = "## Cumulative Board Updates (`feat/board-sync`)"
    if not existing_body or header not in existing_body:
        base = (
            f"{header}\n\n"
            "Single rolling pull request for all task board state transitions (`tasks/board.json`, "
            "`tasks/BOARD.md`, and `tasks/specs/T-*.md`). All sentinels and stewards push board "
            "updates to `feat/board-sync` and reuse this PR until merged.\n\n"
            "### Update Log\n"
            f"{bullet}\n"
        )
        return base
    if summary_line.strip() in existing_body:
        return existing_body
    return existing_body.rstrip() + "\n" + bullet + "\n"


def check_single_branch_policy(repo_root: Path = REPO_ROOT) -> Tuple[bool, List[str]]:
    """Verify sentinel prompts and skills reference `feat/board-sync` and `sync_board_pr.py`."""
    errors: List[str] = []
    prompt_dir = repo_root / "tasks" / "sentinel-prompts"
    if prompt_dir.is_dir():
        for p in sorted(prompt_dir.glob("*.md")):
            txt = p.read_text(encoding="utf-8")
            if "feat/board-sync" not in txt and "sync_board_pr.py" not in txt:
                errors.append(f"{p.relative_to(repo_root).as_posix()}: missing reference to feat/board-sync or sync_board_pr.py")
            if re.search(r"work/sentinel-[a-z-]+-t-\d+-board", txt):
                errors.append(f"{p.relative_to(repo_root).as_posix()}: contains legacy per-task *-board branch pattern")
    return len(errors) == 0, errors


def prepare_board_worktree(repo_root: Path = REPO_ROOT, repo_slug: str = DEFAULT_REPO_SLUG, dry_run: bool = False) -> Path:
    """Prepare `../.worktrees/cf-lab/board-sync` on `feat/board-sync`, synced with origin/main."""
    wt_path = resolve_worktree_path(repo_root)
    if dry_run:
        return wt_path

    subprocess.run(["git", "-C", str(repo_root), "fetch", "origin"], check=True, capture_output=True)
    open_pr = find_open_board_pr(repo_slug=repo_slug, head_branch=BOARD_SYNC_BRANCH)

    if not wt_path.exists():
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "add", "-B", BOARD_SYNC_BRANCH, str(wt_path), "origin/main"],
            check=True,
            capture_output=True,
        )

    subprocess.run(["git", "-C", str(wt_path), "fetch", "origin"], check=True, capture_output=True)

    if open_pr is not None:
        # Sync with remote feat/board-sync if it exists, then merge origin/main
        has_remote = subprocess.run(
            ["git", "-C", str(wt_path), "rev-parse", "--verify", f"origin/{BOARD_SYNC_BRANCH}"],
            capture_output=True,
        ).returncode == 0
        if has_remote:
            subprocess.run(
                ["git", "-C", str(wt_path), "checkout", "-B", BOARD_SYNC_BRANCH, f"origin/{BOARD_SYNC_BRANCH}"],
                check=True,
                capture_output=True,
            )
        merge_res = subprocess.run(
            ["git", "-C", str(wt_path), "merge", "--no-edit", "origin/main"],
            capture_output=True,
            text=True,
        )
        if merge_res.returncode != 0:
            # Resolve BOARD.md by re-rendering after taking ours/theirs on board.json if needed
            subprocess.run(["pwsh", "-NoProfile", "-File", str(wt_path / "tasks" / "render-board.ps1")], cwd=str(wt_path), check=True)
            subprocess.run(["git", "-C", str(wt_path), "add", "tasks/BOARD.md"], check=True)
            subprocess.run(["git", "-C", str(wt_path), "commit", "--no-edit"], check=True, capture_output=True)
    else:
        # No open PR for feat/board-sync: reset cleanly to origin/main
        subprocess.run(
            ["git", "-C", str(wt_path), "checkout", "-B", BOARD_SYNC_BRANCH, "origin/main"],
            check=True,
            capture_output=True,
        )

    return wt_path


def publish_board_pr(
    title: str,
    summary: str,
    repo_root: Path = REPO_ROOT,
    repo_slug: str = DEFAULT_REPO_SLUG,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Render BOARD.md, verify task specs, commit, push `feat/board-sync`, and reuse or open the single PR."""
    wt_path = resolve_worktree_path(repo_root)
    if not wt_path.exists():
        raise FileNotFoundError(f"Board worktree not found at {wt_path}; run --prepare first.")

    subprocess.run(["pwsh", "-NoProfile", "-File", str(wt_path / "tasks" / "render-board.ps1")], cwd=str(wt_path), check=True)
    subprocess.run(["python", str(wt_path / "tasks" / "check_task_specs.py"), "--check"], cwd=str(wt_path), check=True)

    status_out = subprocess.check_output(
        ["git", "-C", str(wt_path), "status", "--porcelain"], text=True, encoding="utf-8"
    ).splitlines()
    changed_paths = [line[3:].strip() for line in status_out if line.strip()]
    disallowed = [p for p in changed_paths if not is_board_only_path(p)]
    if disallowed:
        raise ValueError(f"Refusing to stage non-board files on {BOARD_SYNC_BRANCH}: {disallowed}")

    if dry_run:
        return {
            "status": "dry_run",
            "branch": BOARD_SYNC_BRANCH,
            "worktree": str(wt_path),
            "changed_files": changed_paths,
        }

    if changed_paths:
        subprocess.run(["git", "-C", str(wt_path), "add", "tasks/board.json", "tasks/BOARD.md", "tasks/specs"], check=True)
        subprocess.run(["git", "-C", str(wt_path), "commit", "-m", title], check=True)

    open_pr = find_open_board_pr(repo_slug=repo_slug, head_branch=BOARD_SYNC_BRANCH)
    push_args = ["git", "-C", str(wt_path), "push", "-u", "origin", BOARD_SYNC_BRANCH]
    if open_pr is None:
        # Safe fast-forward/force-with-lease when resetting a closed/merged branch
        push_args = ["git", "-C", str(wt_path), "push", "--force-with-lease", "-u", "origin", BOARD_SYNC_BRANCH]
    subprocess.run(push_args, check=True)

    if open_pr is not None:
        pr_num = open_pr["number"]
        new_body = build_updated_pr_body(open_pr.get("body") or "", summary or title)
        subprocess.run(
            ["gh", "pr", "edit", str(pr_num), "--repo", repo_slug, "--title", title, "--body", new_body],
            check=True,
        )
        return {"status": "reused", "number": pr_num, "url": open_pr.get("url", ""), "branch": BOARD_SYNC_BRANCH}

    new_body = build_updated_pr_body("", summary or title)
    create_out = subprocess.check_output(
        [
            "gh", "pr", "create",
            "--repo", repo_slug,
            "--head", BOARD_SYNC_BRANCH,
            "--base", "main",
            "--title", title,
            "--body", new_body,
        ],
        text=True,
        encoding="utf-8",
    ).strip()
    return {"status": "created", "url": create_out, "branch": BOARD_SYNC_BRANCH}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Single-branch, single-PR board synchronization helper (feat/board-sync)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="Prepare and sync ../worktrees/cf-lab/board-sync on feat/board-sync")
    mode.add_argument("--publish", action="store_true", help="Render, commit, push feat/board-sync, and reuse/create the single board PR")
    mode.add_argument("--check", action="store_true", help="Verify single-board-branch policy across sentinel prompts")
    ap.add_argument("--title", default="chore(board): sync task board state and backlog", help="Commit and PR title for --publish")
    ap.add_argument("--summary", default="", help="Summary line appended to the cumulative PR update log")
    ap.add_argument("--repo", default=DEFAULT_REPO_SLUG, help="GitHub repository slug (default: senseiewok/cf-lab)")
    ap.add_argument("--dry-run", action="store_true", help="Simulate without mutating git remotes or GitHub PRs")
    args = ap.parse_args(argv)

    if args.check:
        ok, errs = check_single_branch_policy(REPO_ROOT)
        if not ok:
            for e in errs:
                print(f"FAIL: {e}", file=sys.stderr)
            return 1
        print(f"PASS: single board branch policy ({BOARD_SYNC_BRANCH}) verified across sentinel prompts.")
        return 0

    if args.prepare:
        wt = prepare_board_worktree(REPO_ROOT, repo_slug=args.repo, dry_run=args.dry_run)
        print(wt.as_posix())
        return 0

    if args.publish:
        res = publish_board_pr(
            title=args.title,
            summary=args.summary or args.title,
            repo_root=REPO_ROOT,
            repo_slug=args.repo,
            dry_run=args.dry_run,
        )
        print(json.dumps(res, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

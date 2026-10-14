#!/usr/bin/env python3
"""Sync and fast-forward pull from origin/main across workspace repositories.

Usage:
    python sync-main.py [--root DIR] [--repo NAME ...] [--check] [--quiet]

Ensures that scheduled sentinels and agents start from the latest merged commits
on GitHub rather than stale local checkouts.

Standard library only. Exit 0 on success; 1 on pull/fetch failure; 2 on usage error.
"""
import argparse
import subprocess
import sys
from pathlib import Path

CORE_REPOS = ["cf-lab", "cf-research", "cf-skills", ".ai"]


class Git:
    """Run git; never raises on a failed command or timeout."""

    def __init__(self, *args, cwd=None):
        try:
            p = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=120,
            )
            self.ok, self.out, self.err = p.returncode == 0, p.stdout.strip(), p.stderr.strip()
        except (OSError, subprocess.SubprocessError) as e:
            self.ok, self.out, self.err = False, "", str(e)


def default_root():
    """Locate the repositories folder containing cf-lab and sibling repos."""
    here = Path(__file__).resolve().parent
    g = Git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=here)
    if g.ok and g.out:
        common = Path(g.out)
    else:
        g = Git("rev-parse", "--git-common-dir", cwd=here)
        common = (here / g.out).resolve() if g.ok and g.out else None
    if common is not None and common.name == ".git":
        return common.parent.parent
    return here.parents[4]


def sync_repo(repo_path, check_only=False):
    """Fetch origin and fast-forward main. Returns (status, message)."""
    name = repo_path.name
    if not (repo_path / ".git").is_dir() and not (repo_path / ".git").is_file():
        return False, f"SKIP {name}: not a git repository"

    # 1. Fetch origin
    f = Git("fetch", "origin", cwd=repo_path)
    if not f.ok:
        return False, f"FAILED {name}: fetch origin failed: {f.err}"

    # Determine default branch (usually main)
    head_ref = Git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=repo_path)
    default_branch = head_ref.out.split("/")[-1] if (head_ref.ok and head_ref.out) else "main"

    # Current branch of this checkout
    cur = Git("branch", "--show-current", cwd=repo_path)
    cur_branch = cur.out if cur.ok else ""

    # Check commit difference
    rev_local = Git("rev-parse", f"refs/heads/{default_branch}", cwd=repo_path)
    rev_origin = Git("rev-parse", f"refs/remotes/origin/{default_branch}", cwd=repo_path)

    if not rev_origin.ok:
        return False, f"FAILED {name}: refs/remotes/origin/{default_branch} not found"

    up_to_date = rev_local.ok and (rev_local.out == rev_origin.out)

    if check_only:
        if up_to_date:
            return True, f"UP-TO-DATE {name} | {default_branch} is at {rev_origin.out[:7]}"
        return True, f"BEHIND {name} | {default_branch} ({rev_local.out[:7] if rev_local.ok else 'none'}) behind origin/{default_branch} ({rev_origin.out[:7]})"

    if up_to_date:
        commit_msg = Git("log", "-1", "--format=%s", f"refs/remotes/origin/{default_branch}", cwd=repo_path).out
        return True, f"UP-TO-DATE {name} | {default_branch} is at {rev_origin.out[:7]} ({commit_msg})"

    # If current checkout is on the default branch:
    if cur_branch == default_branch:
        p = Git("pull", "--ff-only", "origin", default_branch, cwd=repo_path)
        if not p.ok:
            return False, f"FAILED {name}: pull --ff-only failed: {p.err}"
        new_rev = Git("rev-parse", "--short", "HEAD", cwd=repo_path).out
        commit_msg = Git("log", "-1", "--format=%s", "HEAD", cwd=repo_path).out
        return True, f"PULLED {name} | {default_branch} updated to {new_rev} ({commit_msg})"
    else:
        # Checkout is on another branch or detached; fast-forward local default branch ref directly
        f2 = Git("fetch", "origin", f"{default_branch}:{default_branch}", cwd=repo_path)
        if not f2.ok:
            return False, f"FAILED {name}: fast-forwarding ref {default_branch} failed: {f2.err}"
        new_rev = rev_origin.out[:7]
        commit_msg = Git("log", "-1", "--format=%s", f"refs/remotes/origin/{default_branch}", cwd=repo_path).out
        return True, f"SYNCED-REF {name} | {default_branch} updated to {new_rev} ({commit_msg}) [checkout on {cur_branch or 'detached'}]"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, help="repositories directory (default: parent of cf-lab)")
    ap.add_argument("--repo", action="append", help="specific repo to sync (default: core workspace repos)")
    ap.add_argument("--all", action="store_true", help="sync all git repositories found under root")
    ap.add_argument("--check", action="store_true", help="check status without pulling")
    ap.add_argument("--quiet", action="store_true", help="suppress non-error output")
    args = ap.parse_args(argv)

    root = (args.root or default_root()).resolve()
    if not root.is_dir():
        print(f"REFUSED repositories folder {root} does not exist", file=sys.stderr)
        return 2

    if args.repo:
        target_repos = [root / r for r in args.repo]
    elif args.all:
        target_repos = [d for d in sorted(root.iterdir()) if d.is_dir() and ((d / ".git").is_dir() or (d / ".git").is_file())]
    else:
        target_repos = [root / r for r in CORE_REPOS if (root / r).exists()]

    if not target_repos:
        print("NOTE no matching repositories found to sync")
        return 0

    failed = 0
    for repo_dir in target_repos:
        ok, msg = sync_repo(repo_dir, check_only=args.check)
        if not ok:
            failed += 1
            print(msg, file=sys.stderr)
        elif not args.quiet:
            print(msg)

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Keep the lab's git worktrees in one place and clean up the ones that are done.

    worktrees.py list  [--root DIR] [--github | --pr-state FILE]
    worktrees.py clean [--root DIR] [--github | --pr-state FILE] [--yes]
    worktrees.py new REPO TOPIC [--branch NAME] [--base REF] [--no-fetch] [--push] [--root DIR]

DIR is the folder that holds the repositories (default: the parent of the main checkout this script belongs to). A
repository is a folder directly under DIR that has a `.git` directory; a worktree has a `.git` file, so it is never
taken for one. New worktrees go in DIR/.worktrees/REPO/TOPIC so DIR shows only the repositories.

list   one line per worktree: why it is kept, or that it can go.
clean  removes the worktrees marked REMOVE. Without --yes it only prints what it would remove.
new    fetches origin (unless --no-fetch), adds a worktree on a new branch from the base (default: origin's
       default branch), and with --push pushes the branch to origin (-u) immediately.

A worktree is REMOVE only when ALL of these hold:
  - it is not locked, its HEAD is a branch, and git could inspect it (any error keeps it);
  - it has no uncommitted or untracked file and no ignored file other than regenerable caches (__pycache__,
    .pytest_cache, *.pyc), because removing a worktree deletes ignored files too;
  - every commit on it is on some remote-tracking branch, or (with --github) is contained in the head of a pull
    request from this repository that has finished, which covers a branch GitHub deleted after a squash merge;
  - its branch has at least one pull request from this repository and none is open.
Pull request states come from `--github` (read-only `gh pr list`, two calls per repository: all states, then open)
or from a JSON file `--pr-state` shaped {"REPO": {"branch": ["MERGED", ...]}}. With neither, the state is unknown
and every worktree is kept. Nothing is removed with --force, no branch is deleted, the main checkout is never
touched, only paths inside DIR are considered, and `git worktree prune` runs only when every stale entry of that
repository is inside DIR. A squash merge can still lose commits pushed after it: run check-merged.ps1 first.

Standard library only. Exit 0 on success; 2 on a usage error or a refusal; 1 if a removal failed.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DONE = {"MERGED", "CLOSED"}
SAFE_IGNORED = re.compile(r"(^|/)(__pycache__|\.pytest_cache)(/|$)|\.pyc$")
NAME_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
REF_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


class Git:
    """Run git; never raises on a failed command or a timeout (the caller reads ok and err)."""

    def __init__(self, *args, cwd=None):
        try:
            p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               stdin=subprocess.DEVNULL, timeout=120)
            self.ok, self.out, self.err = p.returncode == 0, p.stdout.strip(), p.stderr.strip()
        except (OSError, subprocess.SubprocessError) as e:
            self.ok, self.out, self.err = False, "", str(e)


def default_root():
    """The folder that holds the repositories: the parent of the main checkout this script belongs to (also from a worktree)."""
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


def find_repos(root):
    return [d for d in sorted(root.iterdir()) if d.is_dir() and (d / ".git").is_dir()]


def parse_worktrees(repo):
    """The linked worktrees of one repository (not its main checkout)."""
    g = Git("worktree", "list", "--porcelain", cwd=repo)
    items = []
    for block in g.out.split("\n\n"):
        d = {}
        for line in block.splitlines():
            k, _, v = line.partition(" ")
            d[k] = v
        if "worktree" in d:
            items.append({"path": Path(d["worktree"]), "branch": d.get("branch", "").replace("refs/heads/", ""),
                          "detached": "detached" in d, "prunable": "prunable" in d, "locked": "locked" in d})
    main = repo.resolve()
    return [i for i in items if i["path"].resolve() != main]


def inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def inspect(w):
    """What git says about one worktree; 'error' is set when anything could not be read (then it is kept)."""
    p = w["path"]
    if not p.is_dir():
        return {"error": "its folder is missing"}
    st = Git("status", "--porcelain", "--ignored=matching", "--untracked-files=all", cwd=p)
    if not st.ok:
        return {"error": "could not read status: " + (st.err or "unknown error")}
    dirty, ignored = [], []
    for line in st.out.splitlines():
        (ignored if line.startswith("!! ") else dirty).append(line[3:])
    unsafe = [x for x in ignored if not SAFE_IGNORED.search(x)]
    n = Git("rev-list", "--count", "HEAD", "--not", "--remotes", cwd=p)
    if not n.ok or not n.out.isdigit():
        return {"error": "could not count unpushed commits: " + (n.err or "unknown error")}
    tip = Git("rev-parse", "HEAD", cwd=p)
    return {"dirty": len(dirty), "ignored": unsafe, "unpushed": int(n.out), "tip": tip.out if tip.ok else ""}


def github_slug(repo):
    url = Git("remote", "get-url", "origin", cwd=repo).out
    m = re.match(r"(?i)^(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def _gh(slug, state, limit):
    try:
        p = subprocess.run(["gh", "pr", "list", "--repo", slug, "--state", state, "--limit", str(limit), "--json",
                            "headRefName,state,headRefOid,headRepositoryOwner"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL, timeout=120)
        return json.loads(p.stdout or "[]") if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def github_states(repo):
    """{branch: [{'state', 'oid'}...]} for pull requests whose head is in this repository (read-only); None if unreadable."""
    slug = github_slug(repo)
    if not slug:
        return None
    owner = slug.split("/")[0].lower()
    allp, openp = _gh(slug, "all", 1000), _gh(slug, "open", 1000)
    if allp is None or openp is None:
        return None
    states = {}
    seen = set()
    for pr in openp + allp:
        o = ((pr.get("headRepositoryOwner") or {}).get("login") or "").lower()
        if o != owner:
            continue  # a fork's pull request with the same branch name says nothing about this branch
        key = (pr["headRefName"], pr["headRefOid"], pr["state"])
        if key in seen:
            continue
        seen.add(key)
        states.setdefault(pr["headRefName"], []).append({"state": pr["state"], "oid": pr["headRefOid"]})
    return states


def contains(path, oid, tip):
    """True when the worktree's tip is the pull request's head or an ancestor of it (so nothing local is missing from it)."""
    if not oid or not tip:
        return False
    if Git("cat-file", "-e", oid + "^{commit}", cwd=path).ok is False:
        return False
    return Git("merge-base", "--is-ancestor", tip, oid, cwd=path).ok


def verdict(w, info, states):
    if w["locked"]:
        return "keep", "it is locked"
    if w["prunable"]:
        return "remove", "its folder is gone (git worktree prune)"
    if not w["branch"]:
        return "keep", "detached HEAD (no branch to match to a pull request)"
    if "error" in info:
        return "keep", "could not inspect it: " + info["error"]
    if info["dirty"]:
        return "keep", f"{info['dirty']} uncommitted or untracked file(s)"
    if info["ignored"]:
        return "keep", f"{len(info['ignored'])} ignored file(s) that removing it would delete (e.g. {info['ignored'][0]})"
    if states is None:
        return "keep", "pull request state unknown (use --github or --pr-state)"
    prs = states.get(w["branch"], [])
    if not prs:
        return "keep", "no pull request for this branch"
    norm = [p if isinstance(p, dict) else {"state": p, "oid": ""} for p in prs]
    if any(p["state"] not in DONE for p in norm):
        return "keep", "a pull request is open"
    if info["unpushed"] and not any(contains(w["path"], p["oid"], info["tip"]) for p in norm):
        return "keep", f"{info['unpushed']} commit(s) on no remote branch and not in a finished pull request"
    return "remove", "pull request " + "/".join(sorted({p["state"].lower() for p in norm})) + ", clean, nothing unpushed"


def collect(root, args):
    rows = []
    pr_file = json.loads(Path(args.pr_state).read_text(encoding="utf-8")) if args.pr_state else None
    for repo in find_repos(root):
        states = pr_file.get(repo.name, {}) if pr_file is not None else (github_states(repo) if args.github else None)
        wts = parse_worktrees(repo)
        for w in wts:
            if not inside(w["path"], root):
                rows.append((repo, w, {}, ("keep", "outside the repositories folder")))
            else:
                info = inspect(w) if not w["prunable"] else {}
                rows.append((repo, w, info, verdict(w, info, states)))
    return rows


def show(root, w):
    return w["path"].resolve().relative_to(root.resolve()).as_posix() if inside(w["path"], root) else str(w["path"])


def cmd_list(root, args):
    rows = collect(root, args)
    for repo, w, info, (v, why) in rows:
        print(f"{v.upper():6} {repo.name} | {show(root, w)} | {w['branch'] or 'detached'} | {why}")
    keep = sum(1 for r in rows if r[3][0] == "keep")
    print(f"SUMMARY {len(rows)} worktree(s): {len(rows) - keep} removable, {keep} kept")
    return 0


def safe_to_prune(repo, rows, root):
    """Prune only when every stale entry of the repository is one of ours (inside DIR and not locked)."""
    for w in parse_worktrees(repo):
        if w["prunable"] and (w["locked"] or not inside(w["path"], root)):
            return False
    return True


def cmd_clean(root, args):
    rows = collect(root, args)
    removable = [r for r in rows if r[3][0] == "remove"]
    failed = 0
    for repo, w, info, (v, why) in removable:
        if not args.yes:
            print(f"WOULD REMOVE {repo.name} | {show(root, w)} | {why}")
        elif w["prunable"]:
            print(f"PRUNE {repo.name} | {show(root, w)}")
        else:
            g = Git("worktree", "remove", str(w["path"]), cwd=repo)
            if g.ok:
                print(f"REMOVED {repo.name} | {show(root, w)}")
            else:
                failed += 1
                print(f"FAILED {repo.name} | {show(root, w)} | {g.err}")
    if args.yes:
        for repo in sorted({r[0] for r in removable}, key=lambda r: r.name):
            if safe_to_prune(repo, rows, root):
                Git("worktree", "prune", cwd=repo)
            else:
                print(f"NOTE {repo.name}: stale entries outside {root} or locked are left alone (no git worktree prune)")
    print(f"SUMMARY {len(removable)} of {len(rows)} worktree(s) " + ("removed" if args.yes else "would be removed (run again with --yes)"))
    return 1 if failed else 0


BRANCH_STD_RX = re.compile(r"^(feat|fix|refactor|site|skills|research|atlas|cftr|sec|board|council|docs|ci|editorial|work)/[A-Za-z0-9][A-Za-z0-9._-]*$")


def cmd_new(root, args):
    repos = {d.name: d for d in find_repos(root)}
    if args.repo not in repos:
        print(f"REFUSED {args.repo} is not a repository folder directly under {root}", file=sys.stderr)
        return 2
    repo = repos[args.repo]
    branch = args.branch or args.topic
    if not NAME_RX.fullmatch(args.topic) or not REF_RX.fullmatch(branch) or branch.endswith(("/", ".lock")) or ".." in branch:
        print("REFUSED the topic and branch must be letters, digits, dot, dash, underscore (a branch may also have a slash)", file=sys.stderr)
        return 2
    if (args.branch or args.push) and not BRANCH_STD_RX.fullmatch(branch):
        print("REFUSED branch must follow <prefix>/<topic> (allowed prefixes: feat, fix, refactor, site, skills, research, atlas, cftr, sec, board, council, docs, ci, editorial, work)", file=sys.stderr)
        return 2
    base_dir = root / ".worktrees" / args.repo
    dest = base_dir / args.topic
    if not inside(dest, root / ".worktrees") or dest.exists():
        print(f"REFUSED {dest} is outside .worktrees or already exists", file=sys.stderr)
        return 2
    if not args.no_fetch:
        f = Git("fetch", "origin", cwd=repo)
        if not f.ok:
            print(f"NOTE fetch failed ({f.err}); using the refs already here")
    base = args.base
    if not base:
        head = Git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=repo)
        base = head.out if head.ok and head.out else "origin/main"
    if not REF_RX.fullmatch(base) or not Git("rev-parse", "--verify", "--quiet", base + "^{commit}", cwd=repo).ok:
        print(f"REFUSED the base {base!r} is not a commit in {args.repo}", file=sys.stderr)
        return 2
    g = Git("worktree", "add", "-b", branch, "--", str(dest), base, cwd=repo)
    if not g.ok:
        print(f"FAILED {g.err}", file=sys.stderr)
        return 1
    if args.push:
        p = Git("push", "-u", "origin", branch, cwd=dest)
        if not p.ok:
            Git("worktree", "remove", "--force", str(dest), cwd=repo)
            Git("branch", "-D", branch, cwd=repo)
            print(f"FAILED push to origin/{branch} (rolled back worktree and local branch): {p.err}", file=sys.stderr)
            return 1
        print(f"CREATED {dest} on branch {branch} from {base} (pushed to origin/{branch})")
    else:
        print(f"CREATED {dest} on branch {branch} from {base}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    for name in ("list", "clean"):
        sp = sub.add_parser(name)
        sp.add_argument("--root")
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--github", action="store_true", help="read pull request states with gh (read-only)")
        g.add_argument("--pr-state", help="JSON file {repo: {branch: [states]}} instead of gh")
        if name == "clean":
            sp.add_argument("--yes", action="store_true", help="actually remove; without it only print")
    sp = sub.add_parser("new")
    sp.add_argument("repo")
    sp.add_argument("topic")
    sp.add_argument("--branch")
    sp.add_argument("--base")
    sp.add_argument("--no-fetch", action="store_true")
    sp.add_argument("--push", action="store_true", help="push the new branch to origin (-u) immediately")
    sp.add_argument("--root")
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_usage(sys.stderr)
        return 2
    root = Path(args.root).resolve() if args.root else default_root()
    if not root.is_dir():
        print(f"REFUSED {root} is not a folder", file=sys.stderr)
        return 2
    return {"list": cmd_list, "clean": cmd_clean, "new": cmd_new}[args.cmd](root, args)


if __name__ == "__main__":
    sys.exit(main())

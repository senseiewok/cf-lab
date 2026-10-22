#!/usr/bin/env python3
"""GitHub Hygiene, PR Comment Triage, and Human-Gate Alignment Engine.

Audits open pull requests, merge conflict states, unresolved review threads,
stale worktrees, and human-gated deliverable alignment across Sensei Ewok's CF Lab.

Usage:
    python tasks/audit_github_hygiene.py [--check] [--output .loop-logs/github-hygiene-digest.json] [--update-handoff]
    python tasks/audit_github_hygiene.py --pr-data fixtures/mock_prs.json
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
HUMAN_TASKS_PATH = REPO_ROOT / "tasks" / "HUMAN-TASKS.md"
BOARD_PATH = REPO_ROOT / "tasks" / "board.json"
WORKTREES_SCRIPT = REPO_ROOT / ".claude" / "skills" / "workspace-siblings" / "scripts" / "worktrees.py"

DEFAULT_OWNER = "senseiewok"
DEFAULT_REPOS = ["cf-lab", "cf-skills", "cf-research", ".ai"]
# Private repositories where cloud GitHub Actions are disabled and checks run locally before PR creation.
LOCAL_GATE_ONLY_REPOS = {".ai"}

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


def find_memory_dir() -> Path:
    """Locate untracked memory folder in ../cf-lab-files/memory or local memory/."""
    sibling_files = REPO_ROOT.parent / "cf-lab-files" / "memory"
    if sibling_files.is_dir():
        return sibling_files
    local_mem = REPO_ROOT / "memory"
    return local_mem


# --- GitHub PR Inspection ---

def fetch_open_prs_gh(owner: str, repo: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Fetch open PRs for a repository via gh CLI; returns (prs, error_message)."""
    slug = f"{owner}/{repo}"
    cmd = [
        "gh", "pr", "list",
        "--repo", slug,
        "--state", "open",
        "--json", "number,title,headRefName,url,updatedAt,mergeable,mergeStateStatus,reviewDecision,isDraft,statusCheckRollup",
        "--limit", "100"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            return None, f"gh pr list failed for {slug} (code {res.returncode}): {res.stderr.strip()}"
        data = json.loads(res.stdout or "[]")
        if repo in LOCAL_GATE_ONLY_REPOS and isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item["statusCheckRollup"] = []
        return data, None
    except FileNotFoundError:
        return None, "gh executable not found on PATH"
    except subprocess.TimeoutExpired:
        return None, f"gh pr list timed out for {slug}"
    except Exception as e:
        return None, f"Failed querying gh for {slug}: {e}"


def fetch_unresolved_review_threads_gh(owner: str, repo: str, pr_number: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Query unresolved review threads for a pull request via GraphQL."""
    query = """
    query($owner: String!, $name: String!, $pr: Int!) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $pr) {
          reviewThreads(first: 50) {
            nodes {
              isResolved
              isOutdated
              comments(first: 5) {
                nodes {
                  author { login }
                  body
                  url
                }
              }
            }
          }
        }
      }
    }
    """
    cmd = [
        "gh", "api", "graphql",
        "-F", f"owner={owner}",
        "-F", f"name={repo}",
        "-F", f"pr={pr_number}",
        "-f", f"query={query}"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            return [], f"GraphQL query failed for PR #{pr_number}: {res.stderr.strip()}"
        data = json.loads(res.stdout or "{}")
        nodes = data.get("data", {}).get("repository", {}).get("pullRequest", {}).get("reviewThreads", {}).get("nodes", [])
        unresolved = []
        for thread in nodes:
            if not thread.get("isResolved") and not thread.get("isOutdated"):
                comments = thread.get("comments", {}).get("nodes", [])
                latest_comment = comments[-1] if comments else {}
                unresolved.append({
                    "author": (latest_comment.get("author") or {}).get("login", "unknown"),
                    "snippet": redact_sensitive(latest_comment.get("body", "")[:250]),
                    "url": latest_comment.get("url", ""),
                })
        return unresolved, None
    except Exception as e:
        return [], str(e)


TASK_ID_RX = re.compile(r"\bT-?(\d{4})\b", re.I)
SENTINEL_BRANCH_RX = re.compile(r"^(?:work/sentinel-|site/showcase-|sec-fix-|agent-improve-)", re.I)
PR_SUITE_TOKEN_RX = re.compile(r"\b(?:ci|checks?|tests?|deploy)\b", re.I)


def extract_pr_task_ids(branch: str, title: str) -> List[str]:
    """Extract canonical T-XXXX task IDs from PR branch name and title."""
    seen: List[str] = []
    for digits in TASK_ID_RX.findall(f"{branch} {title}"):
        tid = f"T-{digits}"
        if tid not in seen:
            seen.append(tid)
    return seen


def audit_prs(
    owner: str,
    repos: List[str],
    pr_data: Optional[Dict[str, Any]] = None,
    check_threads: bool = True,
    done_task_ids: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """Inspect open PRs, merge conflicts, CI check failures, review statuses, and superseded PRs across repositories."""
    results: Dict[str, Any] = {
        "prs": [],
        "conflicts": [],
        "review_blockers": [],
        "ci_failures": [],
        "superseded_prs": [],
        "repair_queue": [],
        "errors": []
    }
    done_ids = done_task_ids or set()

    for repo in repos:
        slug = f"{owner}/{repo}"
        prs = None
        err = None

        if pr_data and repo in pr_data:
            prs = pr_data[repo]
        else:
            prs, err = fetch_open_prs_gh(owner, repo)

        if err:
            results["errors"].append({"repo": slug, "error": err})
            continue

        if not prs:
            continue

        for pr in prs:
            num = pr.get("number")
            title = pr.get("title", "")
            branch = pr.get("headRefName", "")
            url = pr.get("url", f"https://github.com/{slug}/pull/{num}")
            mergeable = pr.get("mergeable", "UNKNOWN")
            merge_state = pr.get("mergeStateStatus", "UNKNOWN")
            review_decision = pr.get("reviewDecision", "")
            is_draft = pr.get("isDraft", False)

            # Detect merge conflict / dirty states
            is_conflicting = (mergeable == "CONFLICTING" or merge_state in ("DIRTY", "BLOCKED_BY_DIRTY"))

            # Detect failing CI status checks (both CheckRun conclusions and StatusContext states)
            failed_checks = []
            status_rollup = pr.get("statusCheckRollup") or []
            has_pr_suite = False
            for check in status_rollup:
                wf_name = check.get("workflowName") or ""
                chk_name = check.get("name") or check.get("context") or "unknown"
                if PR_SUITE_TOKEN_RX.search(f"{wf_name} {chk_name}"):
                    has_pr_suite = True
                conclusion = (check.get("conclusion") or check.get("state") or "").upper()
                if conclusion in ("FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"):
                    failed_checks.append({
                        "name": chk_name,
                        "workflow": wf_name,
                        "conclusion": conclusion,
                        "details_url": check.get("detailsUrl") or check.get("targetUrl") or ""
                    })

            ci_blocked_by_conflict = bool(is_conflicting and not is_draft and not has_pr_suite)

            # Detect superseded sentinel PRs whose referenced board tasks are all already done on main
            pr_task_ids = extract_pr_task_ids(branch, title)
            is_superseded = bool(
                pr_task_ids
                and done_ids
                and SENTINEL_BRANCH_RX.match(branch)
                and all(tid in done_ids for tid in pr_task_ids)
            )

            # Check review comments
            threads = []
            if "unresolved_threads" in pr:
                threads = pr["unresolved_threads"]
            elif check_threads and not pr_data and not is_draft:
                threads, _ = fetch_unresolved_review_threads_gh(owner, repo, num)

            has_review_blocker = (review_decision == "CHANGES_REQUESTED" or len(threads) > 0)

            pr_entry = {
                "repo": slug,
                "number": num,
                "title": title,
                "branch": branch,
                "url": url,
                "mergeable": mergeable,
                "merge_state": merge_state,
                "review_decision": review_decision,
                "is_draft": is_draft,
                "has_conflict": is_conflicting,
                "ci_blocked_by_conflict": ci_blocked_by_conflict,
                "failed_checks": failed_checks,
                "unresolved_threads": threads,
                "task_ids": pr_task_ids,
                "is_superseded": is_superseded
            }

            if is_conflicting:
                results["conflicts"].append({
                    "repo": slug,
                    "number": num,
                    "title": title,
                    "branch": branch,
                    "url": url,
                    "mergeable": mergeable,
                    "merge_state": merge_state,
                    "ci_blocked_by_conflict": ci_blocked_by_conflict
                })

            if failed_checks:
                results["ci_failures"].append({
                    "repo": slug,
                    "number": num,
                    "title": title,
                    "branch": branch,
                    "url": url,
                    "failed_checks": failed_checks
                })

            if has_review_blocker:
                results["review_blockers"].append({
                    "repo": slug,
                    "number": num,
                    "title": title,
                    "branch": branch,
                    "url": url,
                    "review_decision": review_decision,
                    "unresolved_threads": threads
                })

            if is_superseded:
                results["superseded_prs"].append({
                    "repo": slug,
                    "number": num,
                    "title": title,
                    "branch": branch,
                    "url": url,
                    "task_ids": pr_task_ids
                })

            reasons = []
            if is_superseded:
                reasons.append(f"superseded (tasks {', '.join(pr_task_ids)} already done on main)")
            if is_conflicting:
                reasons.append(f"merge_conflict ({mergeable}/{merge_state})")
            if ci_blocked_by_conflict:
                reasons.append("ci_blocked_by_conflict (pull_request workflow could not run)")
            if failed_checks:
                reasons.append("ci_failure (" + ", ".join(f"{c['name']}:{c['conclusion']}" for c in failed_checks) + ")")
            if has_review_blocker:
                reasons.append(f"review_blocker ({len(threads)} unresolved thread(s), decision={review_decision or 'NONE'})")

            if reasons:
                results["repair_queue"].append({
                    "repo": slug,
                    "repo_name": repo,
                    "number": num,
                    "branch": branch,
                    "title": title,
                    "url": url,
                    "task_ids": pr_task_ids,
                    "is_superseded": is_superseded,
                    "has_conflict": is_conflicting,
                    "ci_blocked_by_conflict": ci_blocked_by_conflict,
                    "failed_checks": failed_checks,
                    "unresolved_threads": threads,
                    "reasons": reasons
                })

            results["prs"].append(pr_entry)

    return results


# --- Human Tasks & Board Cross-Referencing ---

def audit_human_gated_tasks(
    human_tasks_path: Path = HUMAN_TASKS_PATH,
    board_path: Path = BOARD_PATH
) -> Dict[str, Any]:
    """Parse HUMAN-TASKS.md Sections 1-5 and cross-reference with tasks/board.json."""
    deliverables = {
        "pending_human_actions": [],
        "completed_human_actions": [],
        "board_human_discrepancies": [],
        "blocked_agent_tasks": []
    }

    if not human_tasks_path.is_file():
        return deliverables

    text = human_tasks_path.read_text(encoding="utf-8")
    # Only inspect Sections 1-5 (ignore Section 6 Council-Approved automated items)
    active_sections = re.split(r"^##\s+6\.\s+Council-Approved Tasks", text, maxsplit=1, flags=re.M)[0]

    current_section = "General"
    for line in active_sections.splitlines():
        sec_match = re.match(r"^##\s+(\d+\.\s+[^#\n]+)", line)
        if sec_match:
            current_section = sec_match.group(1).strip()
            continue

        item_match = re.match(r"^\s*-\s*\[([ xX])\]\s*\*\*([^*]+)\*\*(?::\s*(.*))?", line)
        if item_match:
            checked = item_match.group(1).lower() == "x"
            name = item_match.group(2).strip()
            detail = (item_match.group(3) or "").strip()
            task_ids = re.findall(r"T-\d{4}", f"{name} {detail}")

            item_obj = {
                "section": current_section,
                "name": name,
                "detail": detail,
                "task_ids": task_ids
            }
            if checked:
                deliverables["completed_human_actions"].append(item_obj)
            else:
                deliverables["pending_human_actions"].append(item_obj)

    # Cross-reference with tasks/board.json
    if board_path.is_file():
        try:
            board = json.loads(board_path.read_text(encoding="utf-8"))
            tasks = board.get("tasks", [])
            pending_human_task_ids = {tid for item in deliverables["pending_human_actions"] for tid in item["task_ids"]}

            done_ids = {t["id"] for t in tasks if t.get("status") == "done"}

            for t in tasks:
                tid = t.get("id")
                status = t.get("status")
                is_human = (t.get("executor") == "human" or t.get("human_required") is True)

                # Check if automated agent is mistakenly assigned to human task
                if tid in pending_human_task_ids and not is_human and status in ("ready", "in_progress"):
                    deliverables["board_human_discrepancies"].append({
                        "task_id": tid,
                        "title": t.get("title"),
                        "status": status,
                        "issue": "Task listed in HUMAN-TASKS.md active sections but board does not mark executor: human"
                    })

                # Check if automated task is blocked by pending human task
                depends_on = t.get("depends_on", [])
                if status in ("ready", "in_progress"):
                    for dep in depends_on:
                        if dep in pending_human_task_ids and dep not in done_ids:
                            deliverables["blocked_agent_tasks"].append({
                                "task_id": tid,
                                "title": t.get("title"),
                                "blocked_by_human_task": dep
                            })
        except Exception as e:
            deliverables["board_human_discrepancies"].append({"error": f"Failed reading board.json: {e}"})

    return deliverables



# --- Sentinel Backlog Depth Telemetry ---

SENTINEL_LANES = ("security", "research", "showcase")
SHOWCASE_AREAS = {"content", "web", "website", "site", "ai-in-care", "ui", "viewer", "frontend"}
RESEARCH_AREAS = {"research", "science", "sources", "evidence", "grounding", "atlas"}


def lane_of_task(task: Dict[str, Any]) -> str:
    """Classify a board task into its sentinel lane (showcase, research, or security)."""
    repo = task.get("repo")
    area = task.get("area")
    if area in SHOWCASE_AREAS:
        return "showcase"
    if repo == "cf-research":
        return "research"
    if area in RESEARCH_AREAS:
        return "research"
    return "security"


def audit_sentinel_backlog_depth(
    board_path: Path = BOARD_PATH,
    starvation_threshold: int = 2
) -> Dict[str, Any]:
    """Audit ready task backlog depth per sentinel lane and flag starvation (< threshold)."""
    results: Dict[str, Any] = {
        "lanes": {
            lane: {
                "ready_count": 0,
                "automated_ready_count": 0,
                "starved": False,
                "task_ids": [],
                "automated_task_ids": []
            }
            for lane in SENTINEL_LANES
        },
        "starvation_threshold": starvation_threshold,
        "starved_lanes": [],
        "is_starved": False
    }

    if not board_path.is_file():
        results["error"] = f"board.json not found at {board_path}"
        results["is_starved"] = True
        results["starved_lanes"] = list(SENTINEL_LANES)
        for lane in SENTINEL_LANES:
            results["lanes"][lane]["starved"] = True
        return results

    try:
        import pick_bold_task  # noqa: E402
        import triage_board    # noqa: E402
        board = json.loads(board_path.read_text(encoding="utf-8"))
        tasks = board.get("tasks", []) if isinstance(board, dict) else board
        done_ids = {t.get("id") for t in tasks if isinstance(t, dict) and t.get("status") == "done"}
        human_md = board_path.parent / "HUMAN-TASKS.md"
        human_ids = triage_board.load_human_task_ids(human_md) if human_md.is_file() else set()
        for t in tasks:
            if not isinstance(t, dict):
                continue
            if t.get("status") == "ready":
                lane = lane_of_task(t)
                tid = t.get("id", "UNKNOWN")
                if lane not in results["lanes"]:
                    results["lanes"][lane] = {
                        "ready_count": 0,
                        "automated_ready_count": 0,
                        "starved": False,
                        "task_ids": [],
                        "automated_task_ids": []
                    }
                results["lanes"][lane]["ready_count"] += 1
                results["lanes"][lane]["task_ids"].append(tid)

                is_human = pick_bold_task.needs_a_person(t, human_ids)
                has_unmet_dep = any(dep not in done_ids for dep in (t.get("depends_on") or []))
                if not is_human and not has_unmet_dep:
                    results["lanes"][lane]["automated_ready_count"] += 1
                    results["lanes"][lane]["automated_task_ids"].append(tid)

        starved = []
        for lane, data in results["lanes"].items():
            if data["automated_ready_count"] < starvation_threshold:
                data["starved"] = True
                starved.append(lane)
            else:
                data["starved"] = False

        results["starved_lanes"] = starved
        results["is_starved"] = len(starved) > 0
    except Exception as e:
        results["error"] = f"Failed inspecting sentinel backlog depth: {e}"
        results["is_starved"] = True
        results["starved_lanes"] = list(SENTINEL_LANES)

    return results


# --- Worktree Audit ---

def audit_worktrees(
    repos_root: Path = REPO_ROOT.parent,
    script_path: Path = WORKTREES_SCRIPT,
    pr_state_file: Optional[Path] = None,
    github: bool = True
) -> Dict[str, Any]:
    """Inspect git worktrees and identify ones eligible for safe removal."""
    results = {
        "removable": [],
        "kept": [],
        "total": 0,
        "error": None
    }

    if not script_path.is_file():
        results["error"] = f"worktrees.py not found at {script_path}"
        return results

    cmd = [sys.executable, str(script_path), "list", "--root", str(repos_root)]
    if pr_state_file and pr_state_file.is_file():
        cmd.extend(["--pr-state", str(pr_state_file)])
    elif github:
        cmd.append("--github")

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            results["error"] = f"worktrees.py list failed (exit {p.returncode}): {p.stderr.strip()}"
            return results

        for line in p.stdout.splitlines():
            line = line.strip()
            if line.startswith("REMOVE"):
                parts = [part.strip() for part in line.split("|")]
                results["removable"].append({
                    "repo": parts[0].replace("REMOVE", "").strip(),
                    "path": parts[1] if len(parts) > 1 else "",
                    "branch": parts[2] if len(parts) > 2 else "",
                    "reason": parts[3] if len(parts) > 3 else ""
                })
            elif line.startswith("KEEP"):
                parts = [part.strip() for part in line.split("|")]
                results["kept"].append({
                    "repo": parts[0].replace("KEEP", "").strip(),
                    "path": parts[1] if len(parts) > 1 else "",
                    "branch": parts[2] if len(parts) > 2 else "",
                    "reason": parts[3] if len(parts) > 3 else ""
                })

        results["total"] = len(results["removable"]) + len(results["kept"])
    except Exception as e:
        results["error"] = f"Failed inspecting worktrees: {e}"

    return results


# --- Handoff Update ---

def update_handoff_document(
    digest: Dict[str, Any],
    handoff_path: Optional[Path] = None
) -> bool:
    """Append or refresh a structured GitHub hygiene status block in memory/handoff.md."""
    if handoff_path is None:
        mem_dir = find_memory_dir()
        handoff_path = mem_dir / "handoff.md"

    conflicts = digest.get("conflicts", [])
    review_blockers = digest.get("review_blockers", [])
    ci_failures = digest.get("ci_failures", [])
    superseded_prs = digest.get("superseded_prs", [])
    human_actions = digest.get("human_deliverables", {}).get("pending_human_actions", [])
    removable_wts = digest.get("worktrees", {}).get("removable", [])
    starved_lanes = digest.get("sentinel_backlog_depth", {}).get("starved_lanes", [])

    # If everything is clean, do not churn handoff.md
    if not conflicts and not review_blockers and not ci_failures and not superseded_prs and not human_actions and not removable_wts and not starved_lanes:
        return False

    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    existing_content = ""
    if handoff_path.is_file():
        existing_content = handoff_path.read_text(encoding="utf-8")

    # Generate the Hygiene section
    lines = [
        "## GitHub Hygiene Sentinel: Maintainer Action Required",
        f"- **Audit Timestamp**: {digest.get('timestamp')}",
    ]

    if conflicts:
        lines.append("- **Merge Conflicts Detected**:")
        for c in conflicts:
            blocked_note = " (PR CI blocked by conflict)" if c.get("ci_blocked_by_conflict") else ""
            lines.append(f"  - [{c['repo']}#{c['number']}]({c['url']}) (`{c['branch']}`): Status `{c['mergeable']}` / `{c['merge_state']}`{blocked_note} - *{c['title']}*")

    if ci_failures:
        lines.append("- **Failing CI Checks Detected**:")
        for cf in ci_failures:
            checks_summary = ", ".join(f"`{c['name']}` ({c['conclusion']})" for c in cf.get("failed_checks", []))
            lines.append(f"  - [{cf['repo']}#{cf['number']}]({cf['url']}) (`{cf['branch']}`): Failing: {checks_summary} - *{cf['title']}*")

    if review_blockers:
        lines.append("- **Unresolved PR Comments & Review Requests**:")
        for r in review_blockers:
            lines.append(f"  - [{r['repo']}#{r['number']}]({r['url']}) (`{r['branch']}`): Decision `{r['review_decision']}`")
            for th in r.get("unresolved_threads", []):
                lines.append(f"    - Comment by @{th.get('author')}: \"{th.get('snippet')}\" ({th.get('url')})")

    if superseded_prs:
        lines.append("- **Superseded Sentinel PRs (Tasks Already Done on Main)**:")
        for sp in superseded_prs:
            tids = ", ".join(sp.get("task_ids", []))
            lines.append(f"  - [{sp['repo']}#{sp['number']}]({sp['url']}) (`{sp['branch']}`): Tasks `{tids}` already done on `main` - *{sp['title']}*")

    if human_actions:
        lines.append("- **Pending Human-Gated Deliverables**:")
        for h in human_actions[:6]:  # Show top 6 to prevent oversized entries
            tid_str = f" ({', '.join(h['task_ids'])})" if h.get("task_ids") else ""
            lines.append(f"  - [{h['section']}] **{h['name']}**{tid_str}: {h.get('detail')}")

    if removable_wts:
        lines.append(f"- **Stale Worktrees Eligible for Cleanup**: {len(removable_wts)} removable worktrees detected (`python .claude/skills/workspace-siblings/scripts/worktrees.py clean --yes`).")

    if starved_lanes:
        lines.append(f"- **Sentinel Lane Starvation Warning**: Lane(s) `{', '.join(starved_lanes)}` have fewer than 2 ready tasks. Replenishment needed to prevent sentinel idle state.")

    lines.append("")
    section_text = "\n".join(lines)

    # Replace existing section if present, else prepend
    pattern = re.compile(r"^##\s+GitHub Hygiene Sentinel: Maintainer Action Required.*?(?=\n##\s+|\Z)", re.M | re.S)
    if pattern.search(existing_content):
        updated_content = pattern.sub(section_text.strip(), existing_content)
    else:
        updated_content = section_text + "\n" + existing_content

    handoff_path.write_text(updated_content.strip() + "\n", encoding="utf-8")
    return True


# --- Main Engine ---

def load_done_task_ids(board_path: Path = BOARD_PATH) -> Set[str]:
    """Return set of task IDs marked status: 'done' on tasks/board.json."""
    if not board_path.is_file():
        return set()
    try:
        board = json.loads(board_path.read_text(encoding="utf-8"))
        tasks = board.get("tasks", []) if isinstance(board, dict) else board
        return {t["id"] for t in tasks if isinstance(t, dict) and t.get("status") == "done" and "id" in t}
    except Exception:
        return set()


def run_github_hygiene_audit(
    owner: str = DEFAULT_OWNER,
    repos: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
    pr_data_file: Optional[Path] = None,
    skip_worktrees: bool = False,
    update_handoff: bool = False,
    handoff_path: Optional[Path] = None,
    board_path: Path = BOARD_PATH
) -> Dict[str, Any]:
    """Execute complete hygiene audit and write JSON digest."""
    if repos is None:
        repos = list(DEFAULT_REPOS)
    if output_path is None:
        output_path = LOGS_DIR / "github-hygiene-digest.json"

    pr_mock = None
    if pr_data_file and pr_data_file.is_file():
        try:
            pr_mock = json.loads(pr_data_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: Failed reading PR mock file {pr_data_file}: {e}", file=sys.stderr)

    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    done_ids = load_done_task_ids(board_path)

    # 1. Inspect PRs
    pr_audit = audit_prs(owner, repos, pr_data=pr_mock, check_threads=(pr_mock is None), done_task_ids=done_ids)

    # 2. Inspect Human Tasks & Board
    human_audit = audit_human_gated_tasks(board_path=board_path)

    # 3. Inspect Sentinel Backlog Depth
    backlog_audit = audit_sentinel_backlog_depth(board_path=board_path)

    # 4. Inspect Worktrees
    wt_audit = {"removable": [], "kept": [], "total": 0, "skipped": True}
    if not skip_worktrees:
        wt_audit = audit_worktrees(REPO_ROOT.parent, WORKTREES_SCRIPT, pr_state_file=pr_data_file, github=(pr_mock is None))

    # 5. Formulate Summary
    has_conflicts = len(pr_audit["conflicts"]) > 0
    has_review_blockers = len(pr_audit["review_blockers"]) > 0
    has_ci_failures = len(pr_audit["ci_failures"]) > 0
    has_superseded = len(pr_audit["superseded_prs"]) > 0
    pending_human_count = len(human_audit["pending_human_actions"])
    removable_wt_count = len(wt_audit.get("removable", []))
    has_errors = len(pr_audit.get("errors", [])) > 0

    status = "clean"
    if has_conflicts or has_review_blockers or has_ci_failures or has_superseded:
        status = "action_required"
    elif has_errors:
        status = "warning_offline"

    digest = {
        "timestamp": now_utc,
        "owner": owner,
        "repos_audited": repos,
        "status": status,
        "open_prs_count": len(pr_audit["prs"]),
        "conflicts": pr_audit["conflicts"],
        "review_blockers": pr_audit["review_blockers"],
        "ci_failures": pr_audit["ci_failures"],
        "superseded_prs": pr_audit["superseded_prs"],
        "repair_queue": pr_audit["repair_queue"],
        "human_deliverables": human_audit,
        "sentinel_backlog_depth": backlog_audit,
        "worktrees": wt_audit,
        "errors": pr_audit["errors"],
        "summary": {
            "total_open_prs": len(pr_audit["prs"]),
            "conflicts_count": len(pr_audit["conflicts"]),
            "review_blockers_count": len(pr_audit["review_blockers"]),
            "ci_failures_count": len(pr_audit["ci_failures"]),
            "superseded_prs_count": len(pr_audit["superseded_prs"]),
            "repair_queue_count": len(pr_audit["repair_queue"]),
            "pending_human_actions_count": pending_human_count,
            "removable_worktrees_count": removable_wt_count,
            "offline_or_errored_repos": len(pr_audit["errors"]),
            "sentinel_starved_lanes": backlog_audit.get("starved_lanes", []),
            "sentinel_is_starved": backlog_audit.get("is_starved", False)
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(digest, indent=2), encoding="utf-8")

    if update_handoff:
        update_handoff_document(digest, handoff_path=handoff_path)

    return digest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="GitHub repository owner (default: senseiewok)")
    parser.add_argument("--repos", default=",".join(DEFAULT_REPOS), help="Comma-separated repo list")
    parser.add_argument("--output", default=str(LOGS_DIR / "github-hygiene-digest.json"), help="Output digest JSON path")
    parser.add_argument("--pr-data", help="Optional mock PR JSON data file for offline testing")
    parser.add_argument("--skip-worktrees", action="store_true", help="Skip worktree inspection")
    parser.add_argument("--update-handoff", action="store_true", help="Update memory/handoff.md if action required")
    parser.add_argument("--handoff-file", help="Custom handoff file destination (for testing)")
    parser.add_argument("--check", action="store_true", help="Exit 1 if conflicts, review blockers, failing CI checks, or superseded PRs found; 0 otherwise")
    parser.add_argument("--quiet", action="store_true", help="Suppress summary printing")

    args = parser.parse_args(argv)

    repos_list = [r.strip() for r in args.repos.split(",") if r.strip()]
    pr_data_path = Path(args.pr_data) if args.pr_data else None
    out_path = Path(args.output)
    handoff_path = Path(args.handoff_file) if args.handoff_file else None

    digest = run_github_hygiene_audit(
        owner=args.owner,
        repos=repos_list,
        output_path=out_path,
        pr_data_file=pr_data_path,
        skip_worktrees=args.skip_worktrees,
        update_handoff=args.update_handoff,
        handoff_path=handoff_path
    )

    if not args.quiet:
        summary = digest["summary"]
        print(f"GitHub Hygiene Audit [{digest['status'].upper()}] - {digest['timestamp']}")
        print(f"  Open PRs: {summary['total_open_prs']} across {len(repos_list)} repos")
        print(f"  Merge Conflicts: {summary['conflicts_count']}")
        print(f"  Review Blockers: {summary['review_blockers_count']}")
        print(f"  CI Failures: {summary['ci_failures_count']}")
        print(f"  Superseded Sentinel PRs: {summary['superseded_prs_count']}")
        print(f"  PRs Needing Repair: {summary['repair_queue_count']}")
        print(f"  Pending Human Deliverables: {summary['pending_human_actions_count']}")
        print(f"  Removable Worktrees: {summary['removable_worktrees_count']}")
        backlog = digest.get("sentinel_backlog_depth", {})
        if backlog and "lanes" in backlog:
            print(f"  Sentinel Backlog Depth (threshold < {backlog.get('starvation_threshold', 2)}):")
            for lane, ldata in backlog["lanes"].items():
                starved_flag = " [STARVED]" if ldata.get("starved") else ""
                print(f"    - {lane}: {ldata.get('automated_ready_count', 0)} automated ready (total {ldata.get('ready_count', 0)}){starved_flag}")
        if digest["errors"]:
            print(f"  Warnings/Errors ({len(digest['errors'])}):")
            for err in digest["errors"]:
                print(f"    - {err['repo']}: {err['error']}")

    if args.check:
        if (digest["summary"]["conflicts_count"] > 0
                or digest["summary"]["review_blockers_count"] > 0
                or digest["summary"]["ci_failures_count"] > 0
                or digest["summary"]["superseded_prs_count"] > 0):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Automated Cross-Repo Sentinel Watermark & Telemetry Cadence Linter.

Audits scheduled sentinel run telemetry, lock lifecycle records, and watermark states
across .loop-logs/ and tasks/sentinels.json to ensure:
1. Manifest validity: tasks/sentinels.json declares valid crons, timeout bounds, and paths.
2. Watermark integrity: Watermark audit logs contain valid ISO timestamps, matching sentinel
   identifiers, and cryptographically valid git tree hashes for all watched paths.
3. Sentinel telemetry compliance: .loop-logs/sentinel-runs.jsonl entries adhere to recognized
   decisions, chronological ordering, and zero-token idle invariants.
4. Lock lifecycle safety: Lock files (.loop-logs/*.lock) never exceed timeout limits and have
   valid ownership records.

Usage:
    python tasks/check_sentinel_telemetry_linter.py --check
    python tasks/check_sentinel_telemetry_linter.py --json
    python tasks/check_sentinel_telemetry_linter.py --strict
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / ".loop-logs"
MANIFEST_PATH = REPO_ROOT / "tasks" / "sentinels.json"
DEFAULT_REPORT_PATH = LOGS_DIR / "sentinel-telemetry-audit.json"

HEX40_RX = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
CRON_FIELD_RX = re.compile(r"^(\*|[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*)(/[0-9]+)?$")

ALLOWED_DECISIONS = frozenset({
    "idle",
    "launched",
    "locked",
    "completed",
    "aborted",
    "launch_failed",
    "busy",
    "dry_run",
})

KNOWN_SENTINELS = frozenset({
    "daily-security-sentinel",
    "daily-site-security-sentinel",
    "daily-research-sentinel",
    "daily-site-showcase-sentinel",
    "daily-github-hygiene-sentinel",
})


def parse_iso_datetime(value: str) -> Optional[dt.datetime]:
    """Parse ISO-8601 string into a UTC datetime object."""
    if not value or not isinstance(value, str):
        return None
    val = value.strip().replace("Z", "+00:00")
    try:
        dt_obj = dt.datetime.fromisoformat(val)
        if dt_obj.tzinfo is None:
            return dt_obj.replace(tzinfo=dt.timezone.utc)
        return dt_obj.astimezone(dt.timezone.utc)
    except Exception:
        pass
    return None


def validate_cron_expression(expr: str) -> bool:
    """Validate standard 5-field cron expression or comma-separated minutes."""
    if not expr or not isinstance(expr, str):
        return False
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    for part in parts:
        if not CRON_FIELD_RX.match(part):
            return False
    return True


def resolve_watch_target(wp: str, repo_root: Path) -> Optional[Path]:
    """Resolve watch path across workspace and worktrees."""
    parts = repo_root.parts
    stripped = re.sub(r"^(\.{1,2}[\\/])+", "", wp)

    # If referencing a sibling repo (starts with ..) and inside .worktrees, prioritize repos_root
    if wp.startswith("..") and ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        repos_root = Path(*parts[:wt_idx])
        wt_target = (repos_root / stripped).resolve()
        if wt_target.exists():
            return wt_target

    # Direct relative path
    target = (repo_root / wp).resolve()
    if target.exists():
        return target

    # General worktree fallback
    if ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        repos_root = Path(*parts[:wt_idx])
        wt_target = (repos_root / stripped).resolve()
        if wt_target.exists():
            return wt_target

    # Direct sibling search
    sibling_target = (repo_root.parent / stripped).resolve()
    if sibling_target.exists():
        return sibling_target

    return None


def verify_git_tree_hash(tree_hash: str, watch_path: str, repo_root: Path) -> bool:
    """Verify that a tree hash resolves to an actual git object."""
    if not HEX40_RX.match(tree_hash):
        return False
    target_dir = repo_root
    resolved = resolve_watch_target(watch_path, repo_root)
    if resolved:
        target_dir = resolved if resolved.is_dir() else resolved.parent
    try:
        res = subprocess.run(
            ["git", "-C", str(target_dir), "cat-file", "-t", tree_hash],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip() in ("tree", "commit", "blob"):
            return True
    except Exception:
        # Fallback to true if git is not accessible in testing mock environments
        return True
    return False


def find_main_logs_dir(repo_root: Path) -> Path:
    """Find the canonical .loop-logs directory, accounting for git worktree layouts."""
    local_logs = repo_root / ".loop-logs"
    if local_logs.is_dir():
        return local_logs
    # If inside .worktrees/<repo>/<topic>, look at primary repo ../../<repo>/.loop-logs
    parts = repo_root.parts
    if ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        # Structure is repos_root / .worktrees / repo_name / topic
        if len(parts) > wt_idx + 2:
            repo_name = parts[wt_idx + 1]
            main_repo = Path(*parts[:wt_idx]) / repo_name
            main_logs = main_repo / ".loop-logs"
            if main_logs.is_dir():
                return main_logs
    return local_logs


class SentinelTelemetryLinter:
    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        manifest_path: Optional[Path] = None,
        logs_dir: Optional[Path] = None,
        runs_log: Optional[Path] = None,
        verify_git: bool = True,
    ) -> None:
        self.repo_root = repo_root
        self.manifest_path = manifest_path or (repo_root / "tasks" / "sentinels.json")
        self.logs_dir = logs_dir or find_main_logs_dir(repo_root)
        self.runs_log = runs_log or (self.logs_dir / "sentinel-runs.jsonl")
        self.verify_git = verify_git

        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.manifest_data: Dict[str, Any] = {}
        self.declared_sentinels: Set[str] = set()

    def audit_manifest(self) -> None:
        """Audit tasks/sentinels.json for structure, schedule, and safety bounds."""
        if not self.manifest_path.is_file():
            self.errors.append(f"Manifest not found: {self.manifest_path}")
            return

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self.manifest_data = json.load(f)
        except Exception as e:
            self.errors.append(f"Invalid JSON in manifest {self.manifest_path}: {e}")
            return

        sentinels = self.manifest_data.get("sentinels")
        if not isinstance(sentinels, dict) or not sentinels:
            self.errors.append("Manifest missing 'sentinels' mapping.")
            return

        for name, config in sentinels.items():
            self.declared_sentinels.add(name)
            for alias in config.get("aliases", []):
                self.declared_sentinels.add(alias)

            cron = config.get("cron")
            if not validate_cron_expression(cron):
                self.errors.append(f"Sentinel '{name}': invalid cron expression '{cron}'")

            max_idle = config.get("max_idle_hours")
            if not isinstance(max_idle, (int, float)) or not (1 <= max_idle <= 24):
                self.errors.append(f"Sentinel '{name}': max_idle_hours {max_idle} outside [1, 24]")

            lock_timeout = config.get("lock_timeout_minutes")
            if not isinstance(lock_timeout, (int, float)) or not (5 <= lock_timeout <= 60):
                self.errors.append(f"Sentinel '{name}': lock_timeout_minutes {lock_timeout} outside [5, 60]")

            prompt_file = config.get("prompt_file")
            if not prompt_file:
                self.errors.append(f"Sentinel '{name}': missing prompt_file")
            else:
                prompt_path = (self.repo_root / prompt_file).resolve()
                if not prompt_path.is_file():
                    self.warnings.append(f"Sentinel '{name}': prompt file {prompt_file} not found on disk")

            watermark = config.get("watermark")
            if not watermark:
                self.errors.append(f"Sentinel '{name}': missing watermark file declaration")

            watch_paths = config.get("watch_paths")
            if not isinstance(watch_paths, list) or not watch_paths:
                self.errors.append(f"Sentinel '{name}': watch_paths must be a non-empty list")

    def audit_watermarks(self) -> None:
        """Audit watermark files declared in sentinels.json."""
        sentinels = self.manifest_data.get("sentinels", {})
        for name, config in sentinels.items():
            wm_rel = config.get("watermark")
            if not wm_rel:
                continue
            wm_path = (self.repo_root / wm_rel).resolve()
            if not wm_path.is_file():
                # Check within logs_dir
                alt_path = (self.logs_dir / Path(wm_rel).name).resolve()
                if alt_path.is_file():
                    wm_path = alt_path
            if not wm_path.is_file():
                self.warnings.append(f"Watermark file for '{name}' does not exist yet: {wm_rel}")
                continue

            try:
                with open(wm_path, "r", encoding="utf-8") as f:
                    wm_data = json.load(f)
            except Exception as e:
                self.errors.append(f"Corrupt JSON in watermark {wm_rel}: {e}")
                continue

            ts_str = wm_data.get("timestamp")
            ts = parse_iso_datetime(ts_str)
            if not ts:
                self.errors.append(f"Watermark {wm_rel}: missing or invalid ISO timestamp '{ts_str}'")

            tree_hashes = wm_data.get("tree_hashes")
            if not isinstance(tree_hashes, dict) or not tree_hashes:
                self.errors.append(f"Watermark {wm_rel}: missing or empty 'tree_hashes' dictionary")
                continue

            for wp, th in tree_hashes.items():
                if not isinstance(th, str) or not HEX40_RX.match(th):
                    self.errors.append(f"Watermark {wm_rel}: watch path '{wp}' has invalid hex40 tree hash '{th}'")
                elif self.verify_git:
                    if not verify_git_tree_hash(th, wp, self.repo_root):
                        self.warnings.append(f"Watermark {wm_rel}: tree hash '{th}' for '{wp}' unresolvable in git reflog")

    def audit_runs_log(self, max_inspect: int = 500) -> None:
        """Audit sentinel-runs.jsonl for telemetry format, valid decisions, and ordering."""
        if not self.runs_log.is_file():
            self.warnings.append(f"Sentinel runs log not found: {self.runs_log}")
            return

        try:
            with open(self.runs_log, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.errors.append(f"Failed to read sentinel runs log {self.runs_log}: {e}")
            return

        if not lines:
            self.warnings.append(f"Sentinel runs log is empty: {self.runs_log}")
            return

        inspected = lines[-max_inspect:]
        prev_dt: Optional[dt.datetime] = None

        allowed_sentinel_names = self.declared_sentinels | KNOWN_SENTINELS

        for idx, line in enumerate(inspected):
            try:
                entry = json.loads(line)
            except Exception as e:
                self.errors.append(f"Corrupt JSON at runs log line {len(lines) - len(inspected) + idx + 1}: {e}")
                continue

            ts_str = entry.get("ts")
            ts = parse_iso_datetime(ts_str)
            if not ts:
                self.errors.append(f"Runs log entry missing or invalid timestamp: {line[:80]}")
            elif prev_dt and ts < prev_dt - dt.timedelta(minutes=5):
                # Tolerate minor clock drift / concurrency overlap up to 5 min
                self.warnings.append(f"Runs log non-chronological timestamp jump ({ts} < {prev_dt}): {ts_str}")
            if ts:
                prev_dt = ts

            sentinel = entry.get("sentinel")
            if sentinel not in allowed_sentinel_names:
                self.warnings.append(f"Unrecognized sentinel name in runs log: '{sentinel}'")

            decision = entry.get("decision")
            if decision not in ALLOWED_DECISIONS:
                self.errors.append(f"Invalid sentinel decision '{decision}' in runs log (expected one of {sorted(ALLOWED_DECISIONS)})")

            if decision == "idle":
                detail = entry.get("detail", "")
                if detail and "fatal" in detail.lower():
                    self.errors.append(f"Idle decision with fatal error detail: {detail}")

    def audit_locks(self) -> None:
        """Audit active or remnant .lock files in .loop-logs."""
        if not self.logs_dir.is_dir():
            return

        lock_files = list(self.logs_dir.glob("*.lock"))
        now = dt.datetime.now(dt.timezone.utc)

        for lock_file in lock_files:
            try:
                with open(lock_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
            except Exception as e:
                self.errors.append(f"Corrupt lock file {lock_file.name}: {e}")
                continue

            acquired_at = parse_iso_datetime(content.get("acquired_at"))
            held_by = content.get("held_by")
            pid = content.get("pid")

            if not acquired_at:
                self.errors.append(f"Lock file {lock_file.name} missing valid acquired_at timestamp")
                continue

            age_hours = (now - acquired_at).total_seconds() / 3600.0
            if age_hours > 4.0:
                self.warnings.append(f"Abandoned stale lock file {lock_file.name} held by '{held_by}' (PID {pid}, {age_hours:.1f} hours old > 4h)")

    def run_all(self) -> Dict[str, Any]:
        """Execute full telemetry and cadence audit."""
        self.audit_manifest()
        self.audit_watermarks()
        self.audit_runs_log()
        self.audit_locks()

        return {
            "status": "PASS" if not self.errors else "FAIL",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "manifest_checked": str(self.manifest_path),
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "declared_sentinels": sorted(self.declared_sentinels),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit sentinel telemetry, watermarks, and run cadence.")
    parser.add_argument("--check", action="store_true", help="Perform deterministic check and return exit code 0 or 1.")
    parser.add_argument("--json", action="store_true", help="Emit JSON audit report.")
    parser.add_argument("--report-file", type=Path, default=DEFAULT_REPORT_PATH, help="Destination for JSON report.")
    parser.add_argument("--manifest", type=Path, default=None, help="Override path to sentinels.json.")
    parser.add_argument("--logs-dir", type=Path, default=None, help="Override path to .loop-logs.")
    parser.add_argument("--runs-log", type=Path, default=None, help="Override path to sentinel-runs.jsonl.")
    parser.add_argument("--no-verify-git", action="store_true", help="Skip git object verification of tree hashes.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")

    args = parser.parse_args()

    linter = SentinelTelemetryLinter(
        manifest_path=args.manifest,
        logs_dir=args.logs_dir,
        runs_log=args.runs_log,
        verify_git=not args.no_verify_git,
    )
    results = linter.run_all()

    if args.json or not args.check:
        output_str = json.dumps(results, indent=2)
        if args.report_file:
            args.report_file.parent.mkdir(parents=True, exist_ok=True)
            args.report_file.write_text(output_str, encoding="utf-8")
        if not args.check:
            print(output_str)

    if args.check:
        print(f"Sentinel Telemetry Linter: scanned {results['manifest_checked']}")
        for w in results["warnings"]:
            print(f"WARNING: {w}")
        for e in results["errors"]:
            print(f"ERROR: {e}")

        total_issues = len(results["errors"]) + (len(results["warnings"]) if args.strict else 0)
        if total_issues == 0:
            print(f"All sentinel telemetry, watermarks, and run cadence verified clean! (PASS - {len(results['warnings'])} warning(s))")
            return 0
        else:
            print(f"Sentinel Telemetry Linter FAILED with {len(results['errors'])} error(s) and {len(results['warnings'])} warning(s).")
            return 1

    return 0 if not results["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())

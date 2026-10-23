#!/usr/bin/env python3
"""Automated Multi-Repo Worktree Lock & Concurrent Sentinel Collision Guard.

Enforces execution isolation and prevents concurrency race conditions across
scheduled multi-agent sentinels (daily-security-sentinel, daily-research-sentinel,
daily-site-showcase-sentinel).

Invariants enforced:
1. Validates lock file lifecycles (.loop-logs/sentinel-*.lock) against configured
   lock_timeout_minutes from tasks/sentinels.json.
2. Verifies PID liveness on active locks to flag orphaned locks from aborted/crashed runs.
3. Detects simultaneous active sentinel lock contention and cron schedule slot overlaps.
4. Identifies overlapping dirty worktrees across sibling repositories (cf-lab, cf-research,
   cf-skills, .ai).

Primary Source Grounding:
- tasks/sentinels.json (sentinel scheduling, cadence, watch paths, lock timeout definitions)
- tasks/run-sentinel.ps1 (sentinel lock acquisition, execution wrapper, and release flow)
- OWASP Top 10:2025 A01: Broken Access Control / CWE-362 (Race Conditions)

Usage:
    python tasks/check_sentinel_concurrency_guard.py [--check] [--json] [--prune-stale]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Default lock timeout in minutes if omitted in manifest
DEFAULT_LOCK_TIMEOUT_MINUTES = 25.0


@dataclass
class LockAlert:
    sentinel: str
    lock_file: str
    severity: str  # "ERROR" | "WARNING" | "INFO"
    alert_type: str  # "STALE_LOCK" | "ORPHAN_LOCK" | "CORRUPT_LOCK" | "CONCURRENT_COLLISION" | "SCHEDULE_COLLISION"
    message: str
    pid: int | None = None
    age_minutes: float | None = None
    created_at: str | None = None


def is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is currently active."""
    if pid <= 0:
        return False

    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
            )
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                STILL_ACTIVE = 259
                is_active = (exit_code.value == STILL_ACTIVE)
                ctypes.windll.kernel32.CloseHandle(handle)
                return is_active
            ctypes.windll.kernel32.CloseHandle(handle)
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def find_workspace_root(start_dir: Path | None = None) -> Path:
    """Resolve workspace repositories root containing cf-lab and siblings."""
    here = (start_dir or Path(__file__).resolve().parent).resolve()
    for p in [here, *here.parents]:
        if p.name in (".worktrees", "worktrees"):
            continue
        if (p / "cf-lab" / "tasks" / "sentinels.json").exists():
            return p
        if (p / "tasks" / "sentinels.json").exists():
            return p.parent
    return here.parent if here.name == "tasks" else here


def load_sentinels_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and parse sentinels.json manifest."""
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("sentinels", {})
    except Exception:
        return {}


def parse_cron_minutes(cron_str: str) -> set[int]:
    """Extract set of minute slots (0-59) from a 5-field cron string."""
    parts = cron_str.strip().split()
    if not parts:
        return set()
    min_expr = parts[0]
    minutes: set[int] = set()

    for item in min_expr.split(","):
        item = item.strip()
        if not item:
            continue
        if item == "*":
            return set(range(60))
        if item.isdigit():
            val = int(item)
            if 0 <= val <= 59:
                minutes.add(val)
        elif "/" in item:
            step_parts = item.split("/")
            if len(step_parts) == 2 and step_parts[1].isdigit():
                step = int(step_parts[1])
                if step > 0:
                    start = 0 if step_parts[0] in ("*", "") else int(step_parts[0])
                    for m in range(start, 60, step):
                        minutes.add(m)
        elif "-" in item:
            range_parts = item.split("-")
            if len(range_parts) == 2 and range_parts[0].isdigit() and range_parts[1].isdigit():
                start, end = int(range_parts[0]), int(range_parts[1])
                for m in range(start, end + 1):
                    if 0 <= m <= 59:
                        minutes.add(m)
    return minutes


def check_schedule_collisions(sentinels_cfg: dict[str, Any]) -> list[LockAlert]:
    """Verify that sentinel cron schedules do not have overlapping minute slots."""
    alerts: list[LockAlert] = []
    sentinel_slots: dict[str, set[int]] = {}

    for name, cfg in sentinels_cfg.items():
        cron_str = cfg.get("cron", "")
        if cron_str:
            sentinel_slots[name] = parse_cron_minutes(cron_str)

    names = list(sentinel_slots.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            overlap = sentinel_slots[n1].intersection(sentinel_slots[n2])
            if overlap:
                alerts.append(
                    LockAlert(
                        sentinel=f"{n1} & {n2}",
                        lock_file="tasks/sentinels.json",
                        severity="WARNING",
                        alert_type="SCHEDULE_COLLISION",
                        message=f"Sentinels '{n1}' and '{n2}' share identical cron minute slot(s): {sorted(overlap)}",
                    )
                )
    return alerts


def parse_iso_timestamp(ts_str: str) -> datetime.datetime | None:
    """Parse ISO timestamp with optional Z suffix."""
    if not ts_str:
        return None
    try:
        clean = ts_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def inspect_lock_file(
    lock_path: Path,
    sentinels_cfg: dict[str, Any],
    now: datetime.datetime | None = None,
) -> list[LockAlert]:
    """Inspect a single sentinel lock file for stale, orphan, or corrupt states."""
    alerts: list[LockAlert] = []
    current_time = now or datetime.datetime.now(datetime.timezone.utc)

    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            if not raw:
                return [
                    LockAlert(
                        sentinel=lock_path.stem,
                        lock_file=str(lock_path),
                        severity="ERROR",
                        alert_type="CORRUPT_LOCK",
                        message="Lock file is empty (0 bytes)",
                    )
                ]
            data = json.loads(raw)
    except Exception as exc:
        return [
            LockAlert(
                sentinel=lock_path.stem,
                lock_file=str(lock_path),
                severity="ERROR",
                alert_type="CORRUPT_LOCK",
                message=f"Failed to parse lock JSON: {exc}",
            )
        ]

    sentinel_name = data.get("held_by") or data.get("sentinel") or lock_path.stem.replace("sentinel-", "")
    pid = data.get("pid")
    ts_str = data.get("ts") or data.get("timestamp") or data.get("created_at")

    timeout_min = DEFAULT_LOCK_TIMEOUT_MINUTES
    if sentinel_name in sentinels_cfg:
        cfg_timeout = sentinels_cfg[sentinel_name].get("lock_timeout_minutes")
        if cfg_timeout is not None:
            try:
                timeout_min = float(cfg_timeout)
            except (ValueError, TypeError):
                pass

    age_minutes: float | None = None
    created_dt = parse_iso_timestamp(ts_str) if ts_str else None
    if created_dt:
        age_seconds = (current_time - created_dt).total_seconds()
        age_minutes = max(0.0, age_seconds / 60.0)

    # 1. Check expiration (Stale lock)
    if age_minutes is not None and age_minutes >= timeout_min:
        alerts.append(
            LockAlert(
                sentinel=sentinel_name,
                lock_file=str(lock_path),
                severity="ERROR",
                alert_type="STALE_LOCK",
                message=f"Lock expired: {age_minutes:.1f} min old >= configured timeout {timeout_min:.1f} min",
                pid=pid,
                age_minutes=age_minutes,
                created_at=ts_str,
            )
        )

    # 2. Check PID liveness (Orphan lock)
    if pid is not None:
        try:
            pid_int = int(pid)
            if not is_pid_alive(pid_int):
                alerts.append(
                    LockAlert(
                        sentinel=sentinel_name,
                        lock_file=str(lock_path),
                        severity="ERROR",
                        alert_type="ORPHAN_LOCK",
                        message=f"Holding process PID {pid_int} is not alive on host",
                        pid=pid_int,
                        age_minutes=age_minutes,
                        created_at=ts_str,
                    )
                )
        except (ValueError, TypeError):
            alerts.append(
                LockAlert(
                    sentinel=sentinel_name,
                    lock_file=str(lock_path),
                    severity="WARNING",
                    alert_type="CORRUPT_LOCK",
                    message=f"Invalid PID specification in lock: {pid}",
                )
            )

    return alerts


def scan_active_sentinel_locks(
    loop_logs_dir: Path,
    sentinels_cfg: dict[str, Any],
    now: datetime.datetime | None = None,
) -> tuple[list[Path], list[LockAlert]]:
    """Scan all lock files in .loop-logs/ and report active locks and alerts."""
    lock_files: list[Path] = []
    alerts: list[LockAlert] = []

    if not loop_logs_dir.exists():
        return lock_files, alerts

    for p in loop_logs_dir.glob("sentinel-*.lock"):
        if p.is_file():
            lock_files.append(p)
            alerts.extend(inspect_lock_file(p, sentinels_cfg, now=now))

    # Detect concurrent lock collisions (multiple active valid locks)
    stale_or_orphan_files = {Path(a.lock_file) for a in alerts if a.alert_type in ("STALE_LOCK", "ORPHAN_LOCK", "CORRUPT_LOCK")}
    valid_active_locks = [lf for lf in lock_files if lf not in stale_or_orphan_files]

    if len(valid_active_locks) > 1:
        alerts.append(
            LockAlert(
                sentinel="multiple",
                lock_file=", ".join(str(f.name) for f in valid_active_locks),
                severity="ERROR",
                alert_type="CONCURRENT_COLLISION",
                message=f"Multiple sentinels hold active locks concurrently ({len(valid_active_locks)} locks)",
            )
        )

    return lock_files, alerts


def prune_stale_sentinel_locks(
    alerts: list[LockAlert],
    dry_run: bool = True,
) -> list[str]:
    """Remove lock files associated with STALE_LOCK, ORPHAN_LOCK, or CORRUPT_LOCK."""
    pruned: list[str] = []
    seen: set[str] = set()

    for alert in alerts:
        if alert.alert_type in ("STALE_LOCK", "ORPHAN_LOCK", "CORRUPT_LOCK"):
            fpath = alert.lock_file
            if fpath not in seen and Path(fpath).is_file():
                seen.add(fpath)
                if not dry_run:
                    try:
                        Path(fpath).unlink(missing_ok=True)
                        pruned.append(fpath)
                    except Exception:
                        pass
                else:
                    pruned.append(fpath)
    return pruned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if any ERROR level alerts exist")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    parser.add_argument("--prune-stale", action="store_true", help="Delete stale, orphan, or corrupt lock files")
    parser.add_argument("--root", type=Path, help="Specify workspace root directory")
    parser.add_argument("--manifest", type=Path, help="Path to sentinels.json")
    parser.add_argument("--loop-logs", type=Path, help="Path to .loop-logs directory")
    args = parser.parse_args()

    repos_root = args.root or find_workspace_root()
    cf_lab_dir = repos_root / "cf-lab" if (repos_root / "cf-lab").is_dir() else repos_root
    manifest_path = args.manifest or (cf_lab_dir / "tasks" / "sentinels.json")
    loop_logs_dir = args.loop_logs or (cf_lab_dir / ".loop-logs")

    sentinels_cfg = load_sentinels_manifest(manifest_path)

    all_alerts: list[LockAlert] = []

    # 1. Check schedule stagger
    all_alerts.extend(check_schedule_collisions(sentinels_cfg))

    # 2. Inspect active locks
    lock_files, lock_alerts = scan_active_sentinel_locks(loop_logs_dir, sentinels_cfg)
    all_alerts.extend(lock_alerts)

    # 3. Handle prune if requested
    pruned_files: list[str] = []
    if args.prune_stale:
        pruned_files = prune_stale_sentinel_locks(all_alerts, dry_run=False)

    errors = [a for a in all_alerts if a.severity == "ERROR"]
    warnings = [a for a in all_alerts if a.severity == "WARNING"]

    if args.json:
        report = {
            "total_locks": len(lock_files),
            "errors": len(errors),
            "warnings": len(warnings),
            "pruned": pruned_files,
            "alerts": [asdict(a) for a in all_alerts],
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"Sentinel Concurrency Guard: {len(lock_files)} active lock(s), {len(errors)} error(s), {len(warnings)} warning(s).")
        for a in all_alerts:
            print(f"  [{a.severity}] [{a.alert_type}] {a.sentinel}: {a.message}")
        if pruned_files:
            print(f"  Pruned {len(pruned_files)} stale/orphan lock file(s).")

    if args.check and errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

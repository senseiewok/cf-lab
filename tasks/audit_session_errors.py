#!/usr/bin/env python3
"""Session Forensic Error Mining & Continuous Improvement Engine.

Scans recent Antigravity conversation transcripts and task execution logs
across all workspace roots to identify runtime errors, broken tool calls,
syntax mistakes, command failures, and git friction. Formulates concrete
system, script, and skill improvements.

Usage:
    python tasks/audit_session_errors.py [--hours 24] [--output .loop-logs/session-error-digest.json]
    python tasks/audit_session_errors.py --check
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_BRAIN_DIR = Path(os.environ.get("ANTIGRAVITY_BRAIN_DIR", str(Path.home() / ".gemini" / "antigravity" / "brain")))
REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / ".loop-logs"

REDACT_PATTERNS = [
    (re.compile(r"(ghp_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_\-]{20,}|sk-[A-Za-z0-9_\-]{20,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.I), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(password|secret|token)\s*[:=]\s*[^\s,;]+", re.I), r"\1=[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED_EMAIL]"),
]


def redact_sensitive(text: str) -> str:
    """Strip API keys, tokens, passwords, and emails from logged error snippets."""
    for pattern, replacement in REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


ERROR_PATTERNS = [
    (re.compile(r"Traceback \(most recent call last\):", re.I), "Python Traceback"),
    (re.compile(r"SyntaxError:", re.I), "Python SyntaxError"),
    (re.compile(r'File "<string>", line \d+', re.I), "Inline Python -c Error"),
    (re.compile(r"ParserError:", re.I), "PowerShell ParserError"),
    (re.compile(r"The term '(?:grep|rg)' is not recognized", re.I), "Missing Shell Utility (grep/rg)"),
    (re.compile(r"The command exited with code [1-9]\d*", re.I), "Non-Zero Exit Code"),
    (re.compile(r"ScriptBlock should only be specified", re.I), "PowerShell ScriptBlock Syntax"),
    (re.compile(r"cannot find path|file not found|no such file", re.I), "Path Not Found"),
    (re.compile(r"Lock acquisition collision|Lock actively held", re.I), "Git/Sentinel Lock Contention"),
    (re.compile(r"JSONDecodeError|Expecting value", re.I), "JSON Parsing Error"),
    (re.compile(r"PermissionDenied|Access is denied", re.I), "Permission Error"),
]

READONLY_VIEW_RX = re.compile(
    r"^\s*(?:Created At:[^\n]*\r?\n\s*Completed At:[^\n]*\r?\n\s*)?(?:File Path:|Showing lines \d+|Partial read \(lines \d+)",
    re.I,
)
NONZERO_EXIT_RX = re.compile(r"(?:The )?command exited with code [1-9]\d*", re.I)
ZERO_EXIT_RX = re.compile(r"(?:The )?command exited with code 0\b", re.I)
STRONG_RUNTIME_ERROR_RX = re.compile(
    r"(?:^Traceback \(most recent call last\):|\bSyntaxError:|File \"<string>\", line \d+|The term '(?:grep|rg)' is not recognized|\bParserError:)",
    re.I | re.M,
)


def is_readonly_file_view(content: str) -> bool:
    """Return True if tool output is a read_file view (with or without Created/Completed At timestamps)."""
    return bool(READONLY_VIEW_RX.match(content or ""))


def scan_transcript(transcript_path: Path) -> List[Dict[str, Any]]:
    """Scan a transcript.jsonl file for error steps and failure patterns."""
    findings = []
    if not transcript_path.is_file():
        return findings

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    step = json.loads(line)
                except Exception:
                    continue

                step_status = step.get("status", "")
                content = str(step.get("content", ""))
                step_type = step.get("type", "")

                # Ignore user/system prompt steps, read-only file views, and successful (exit 0) self-audit/test runs
                # unless the step itself explicitly failed with status == "ERROR" or contains a strong runtime error.
                if step_status != "ERROR":
                    if step_type in ("USER_INPUT", "SYSTEM_MESSAGE", "USER_MESSAGE"):
                        continue
                    if is_readonly_file_view(content):
                        continue
                    if "Sensei Ewok CF Lab - Session Error & Improvement Audit" in content:
                        continue
                    if (
                        ZERO_EXIT_RX.search(content)
                        and not NONZERO_EXIT_RX.search(content)
                        and not STRONG_RUNTIME_ERROR_RX.search(content)
                    ):
                        continue

                matched_categories = []
                for pattern, cat in ERROR_PATTERNS:
                    if pattern.search(content):
                        matched_categories.append(cat)

                if step_status == "ERROR" or matched_categories:
                    # Truncate and sanitize content for digest (redact full content before truncation)
                    snippet = redact_sensitive(content.strip())[:300] if content else ""
                    findings.append({
                        "step_index": step.get("step_index", idx),
                        "type": step_type,
                        "status": step_status,
                        "categories": matched_categories if matched_categories else ["Step Error"],
                        "snippet": snippet,
                    })
    except Exception as e:
        findings.append({"error": f"Failed reading transcript: {e}"})

    return findings


def scan_task_logs(session_dir: Path) -> List[Dict[str, Any]]:
    """Scan .system_generated/tasks/*.log for command failures."""
    task_findings = []
    tasks_dir = session_dir / ".system_generated" / "tasks"
    if not tasks_dir.is_dir():
        return task_findings

    for log_file in tasks_dir.glob("*.log"):
        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
            if "Sensei Ewok CF Lab - Session Error & Improvement Audit" in content:
                continue
            if (
                ZERO_EXIT_RX.search(content)
                and not NONZERO_EXIT_RX.search(content)
                and not STRONG_RUNTIME_ERROR_RX.search(content)
            ):
                continue
            matched_categories = []
            for pattern, cat in ERROR_PATTERNS:
                if pattern.search(content):
                    matched_categories.append(cat)

            if matched_categories:
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                error_lines = [l for l in lines if any(p.search(l) for p, _ in ERROR_PATTERNS)]
                raw_summary = error_lines[:3] if error_lines else lines[-3:]
                task_findings.append({
                    "task_file": log_file.name,
                    "categories": matched_categories,
                    "error_summary": [redact_sensitive(l) for l in raw_summary],
                })
        except Exception:
            continue

    return task_findings


def audit_sessions(brain_dir: Path, max_age_hours: float = 24.0) -> Dict[str, Any]:
    """Audit all brain session directories modified within max_age_hours."""
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(hours=max_age_hours)

    sessions_audited = 0
    total_error_steps = 0
    python_error_steps = 0
    inline_python_steps = 0
    category_counts: Dict[str, int] = {}
    session_reports = []

    if brain_dir.is_dir():
        for session_path in brain_dir.iterdir():
            if not session_path.is_dir():
                continue

            try:
                mtime = datetime.datetime.fromtimestamp(session_path.stat().st_mtime)
            except Exception:
                continue

            if mtime < cutoff:
                continue

            sessions_audited += 1
            transcript_file = session_path / ".system_generated" / "logs" / "transcript.jsonl"
            step_errors = scan_transcript(transcript_file)
            task_errors = scan_task_logs(session_path)

            if step_errors or task_errors:
                total_error_steps += len(step_errors)
                for err in step_errors:
                    cats = set(err.get("categories", []))
                    if cats & {"Python Traceback", "Python SyntaxError", "Inline Python -c Error"}:
                        python_error_steps += 1
                    if "Inline Python -c Error" in cats:
                        inline_python_steps += 1
                    for cat in err.get("categories", []):
                        category_counts[cat] = category_counts.get(cat, 0) + 1

                session_reports.append({
                    "conversation_id": session_path.name,
                    "modified_at": mtime.isoformat(),
                    "error_steps_count": len(step_errors),
                    "task_failures_count": len(task_errors),
                    "sample_step_errors": step_errors[:5],
                    "task_failures": task_errors[:5],
                })

    # Derive actionable improvements from category counts
    recommended_improvements = []
    if category_counts.get("PowerShell ScriptBlock Syntax", 0) > 0 or category_counts.get("PowerShell ParserError", 0) > 0:
        recommended_improvements.append({
            "area": "powershell_tooling",
            "observation": f"Detected {category_counts.get('PowerShell ScriptBlock Syntax', 0) + category_counts.get('PowerShell ParserError', 0)} PowerShell syntax/scriptblock failures.",
            "recommendation": "Avoid complex inline python -c '...' or pwsh -Command '...' string quoting in run_command. Write arguments to structured python scripts or pass script paths.",
            "action": "Hardened tasks/ scripts with structured argument parsing and documented PowerShell quoting guardrails in windows-powershell-commands skill."
        })

    if category_counts.get("Missing Shell Utility (grep/rg)", 0) > 0:
        recommended_improvements.append({
            "area": "shell_search_utilities",
            "observation": f"Detected {category_counts.get('Missing Shell Utility (grep/rg)', 0)} calls to missing 'grep' or 'rg' binaries in PowerShell.",
            "recommendation": "Use the native Grep tool, 'git grep', or PowerShell 'Select-String' instead of bare 'grep' or 'rg' in run_command.",
            "action": "Enforced PowerShell search equivalents across sentinel instructions and windows-powershell-commands skill."
        })

    if python_error_steps > 0:
        recommended_improvements.append({
            "area": "python_execution",
            "observation": f"Detected {python_error_steps} Python error step(s) ({inline_python_steps} from inline python -c).",
            "recommendation": "Use dedicated CLI scripts with argparse and unit tests rather than raw inline command string execution.",
            "action": "Author and run dedicated helper scripts under tasks/ or tools/."
        })

    if category_counts.get("Path Not Found", 0) > 0:
        recommended_improvements.append({
            "area": "path_resolution",
            "observation": f"Detected {category_counts.get('Path Not Found', 0)} path resolution errors.",
            "recommendation": "Resolve sibling repository paths dynamically via workspace-siblings/scripts/check-workspace.py or Path(__file__).resolve().parents[N].",
            "action": "Ensure relative sibling paths check ../<repo> existence before executing commands."
        })

    if category_counts.get("Git/Sentinel Lock Contention", 0) > 0:
        recommended_improvements.append({
            "area": "lock_coordination",
            "observation": "Detected sentinel lock contention events.",
            "recommendation": "Stagger sentinel schedules with >=30 minute separation and use dedicated lock files per sidecar.",
            "action": "Decoupled daily-site-showcase-sentinel to :30 odd hours, separate from daily-research-sentinel."
        })

    digest = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "brain_dir": str(brain_dir),
        "audit_window_hours": max_age_hours,
        "summary": {
            "sessions_scanned": sessions_audited,
            "sessions_with_errors": len(session_reports),
            "total_error_steps": total_error_steps,
            "category_distribution": category_counts,
        },
        "recommended_improvements": recommended_improvements,
        "session_details": session_reports[:10],
    }

    return digest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit agent sessions for errors and formulate improvements.")
    parser.add_argument("--brain-dir", default=str(DEFAULT_BRAIN_DIR), help="Path to Antigravity brain directory")
    parser.add_argument("--hours", type=float, default=24.0, help="Audit window in hours")
    parser.add_argument("--output", default=str(LOGS_DIR / "session-error-digest.json"), help="Output digest JSON path")
    parser.add_argument("--check", action="store_true", help="Run audit in read-only mode without writing output file")
    args = parser.parse_args(argv)

    brain_path = Path(args.brain_dir)
    digest = audit_sessions(brain_path, max_age_hours=args.hours)

    print("==================================================")
    print("Sensei Ewok CF Lab - Session Error & Improvement Audit")
    print("==================================================")
    print(f"Audit Window:            Last {args.hours} hours")
    print(f"Sessions Scanned:        {digest['summary']['sessions_scanned']}")
    print(f"Sessions with Errors:    {digest['summary']['sessions_with_errors']}")
    print(f"Total Error Steps:       {digest['summary']['total_error_steps']}")
    print("Category Breakdown:")
    for cat, count in digest['summary']['category_distribution'].items():
        print(f"  - {cat}: {count}")
    print("--------------------------------------------------")
    print(f"Actionable Improvements Identified: {len(digest['recommended_improvements'])}")
    for imp in digest["recommended_improvements"]:
        print(f"  * [{imp['area']}] {imp['recommendation']}")
    print("--------------------------------------------------")

    if not args.check:
        out_file = Path(args.output)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(digest, indent=2) + "\n", encoding="utf-8")
        print(f"Saved full digest to {out_file}")
    else:
        print("[CHECK MODE] Read-only audit complete. Output file not modified.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

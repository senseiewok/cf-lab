#!/usr/bin/env python3
"""Verify .github/PULL_REQUEST_TEMPLATE.md and validate pull request bodies (T-0143).

Checks:
  1. .github/PULL_REQUEST_TEMPLATE.md exists and contains the required prompts:
     - checks run with their output lines
     - reviewer(s) and rounds (pr-review-loop)
     - diff size
     - files copied from another repo: none, or a list with the source commit
     - agent instructions changed: yes/no
  2. When passed --body-file PATH or --body TEXT (and optional --diff-lines N --max-diff-lines CAP):
     - Refuses a PR body missing any required record heading or provenance declaration.
     - Refuses a PR whose diff exceeds --max-diff-lines (default 1500) unless the body
       includes an explicit 'Diff Size Reason:' or 'Large Diff Rationale:' explanation.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
DEFAULT_MAX_DIFF_LINES = 1500

REQUIRED_BODY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Summary heading", re.compile(r"(?im)^##\s+Summary\b")),
    ("Review Loop Record (pr-review-loop)", re.compile(r"(?im)^##\s+Review\s+Loop\s+Record\b")),
    ("Deterministic Verification & Checks", re.compile(r"(?im)^##\s+Deterministic\s+(?:Verification|Checks)\b")),
    ("Diff Size line", re.compile(r"(?im)\*\*Diff Size\*\*\s*:\s*\S+|\bDiff Size\s*:\s*\S+")),
    (
        "Files Copied From Another Repo line",
        re.compile(r"(?im)\*\*Files Copied From Another Repo\*\*\s*:\s*\S+|\bFiles Copied From Another Repo\s*:\s*\S+"),
    ),
    (
        "Agent Instructions Changed line",
        re.compile(
            r"(?im)\*\*Agent Instructions(?:\s*/\s*Security Rules)?\s+Changed\*\*\s*:\s*(?:`?(?:yes|no)\b|\S+)"
            r"|\bAgent Instructions(?:\s*/\s*Security Rules)?\s+Changed\s*:\s*(?:`?(?:yes|no)\b|\S+)"
        ),
    ),
]


def check_template(template_path: Path = DEFAULT_TEMPLATE) -> tuple[bool, list[str]]:
    if not template_path.is_file():
        return False, [f"missing PR template: {template_path}"]
    text = template_path.read_text(encoding="utf-8")
    errors: list[str] = []
    for label, pat in REQUIRED_BODY_PATTERNS:
        if not pat.search(text):
            errors.append(f"template missing '{label}'")
    return len(errors) == 0, errors


def check_body(
    body_text: str,
    diff_lines: int | None = None,
    max_diff_lines: int = DEFAULT_MAX_DIFF_LINES,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    # Strip HTML comments before checking filled values
    cleaned = re.sub(r"<!--.*?-->", "", body_text, flags=re.DOTALL)

    for label, pat in REQUIRED_BODY_PATTERNS:
        if not pat.search(cleaned):
            errors.append(f"PR body missing required item: {label}")

    # Reject unfilled template placeholders
    unfilled_markers = [
        ("T-XXXX", r"\bT-XXXX\b"),
        ("+lines / -lines", r"\+lines\s*/\s*-lines"),
        ("[Blind Challenger: Claude Opus / Gemini]", r"\[Blind Challenger:\s*Claude Opus\s*/\s*Gemini\]"),
    ]
    for marker_name, marker_pat in unfilled_markers:
        if re.search(marker_pat, cleaned, flags=re.I):
            errors.append(f"PR body still contains unfilled template placeholder '{marker_name}'")

    # Require non-empty content inside '## Deterministic Verification & Checks'
    sec_match = re.search(
        r"(?ims)^##\s+Deterministic\s+(?:Verification|Checks)[^\n]*\n(.*?)(?=^##\s+|\Z)",
        cleaned,
    )
    if sec_match is not None:
        sec_body = re.sub(r"^---+\s*$", "", sec_match.group(1), flags=re.M).strip()
        if not sec_body or sec_body == "```text\n```":
            errors.append("PR body 'Deterministic Verification & Checks' section is empty")

    # Require numeric Diff Size (+N / -M) and parse diff lines if not explicitly passed
    diff_match = re.search(r"(?i)Diff Size\**\s*:\s*`?\+(\d+)\s*/\s*-(\d+)", cleaned)
    if not diff_match:
        errors.append("PR body 'Diff Size' must report numeric additions/deletions (e.g. '+120 / -10, 2 files')")

    inferred_diff = diff_lines
    if inferred_diff is None and diff_match:
        inferred_diff = int(diff_match.group(1)) + int(diff_match.group(2))

    if inferred_diff is not None and inferred_diff > max_diff_lines:
        has_reason = bool(
            re.search(
                r"(?i)(?:Diff Size Reason|Large Diff Rationale|Size Rationale)\**\s*:\s*\S+",
                cleaned,
            )
        )
        if not has_reason:
            errors.append(
                f"PR diff size ({inferred_diff} lines) exceeds cap ({max_diff_lines}) with no stated 'Diff Size Reason:'"
            )

    return len(errors) == 0, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify PR template and PR body compliance (T-0143).")
    ap.add_argument("--self-test", action="store_true", help="Run template self-check")
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Path to PULL_REQUEST_TEMPLATE.md")
    ap.add_argument("--body-file", type=Path, default=None, help="Optional PR body markdown file to validate")
    ap.add_argument("--body", type=str, default=None, help="Optional PR body text to validate")
    ap.add_argument("--diff-lines", type=int, default=None, help="Total diff lines (+ and -) to check against cap")
    ap.add_argument("--max-diff-lines", type=int, default=DEFAULT_MAX_DIFF_LINES, help="Max diff lines without rationale")
    args = ap.parse_args(argv)

    ok_tpl, tpl_errors = check_template(args.template)
    if not ok_tpl:
        for err in tpl_errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1

    if args.body_file is not None or args.body is not None:
        text = args.body if args.body is not None else args.body_file.read_text(encoding="utf-8")
        ok_body, body_errors = check_body(text, diff_lines=args.diff_lines, max_diff_lines=args.max_diff_lines)
        if not ok_body:
            for err in body_errors:
                print(f"FAIL: {err}", file=sys.stderr)
            return 1
        print("PASS: PR template and PR body verified.")
        return 0

    print(f"PASS: {args.template.name} verified with all required pr-review-loop and provenance headings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

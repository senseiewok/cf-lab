#!/usr/bin/env python3
"""Verify GitHub Actions CI workflows across public repos (T-0114).

Asserts that each workflow file under .github/workflows/:
  1. Triggers on pull_request.
  2. Declares top-level read-only permissions (contents: read) and no write permissions.
  3. Pins every 'uses: owner/repo@<ref>' step to a full 40-character hexadecimal commit SHA.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
USES_RE = re.compile(r"^\s*-\s*uses:\s*([^\s#]+)|\buses:\s*([^\s#]+)", re.M)
SHA_ACTION_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9a-f]{40}$")


def _strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.lstrip().startswith("#"):
            continue
        # Strip inline YAML comments preceded by whitespace
        cleaned = re.sub(r"\s+#.*$", "", raw_line)
        lines.append(cleaned)
    return "\n".join(lines)


def check_workflow_text(text: str, label: str = "ci.yml") -> list[str]:
    errors: list[str] = []
    uncommented = _strip_comments(text)
    if not re.search(r"(?m)^\s*pull_request\s*:", uncommented):
        errors.append(f"{label}: missing pull_request trigger")
    if not re.search(r"(?m)^permissions\s*:\s*\n\s+contents\s*:\s*read\b", uncommented):
        errors.append(f"{label}: missing top-level 'permissions: contents: read'")
    if re.search(r"(?m):\s*write\b|\bwrite-all\b", uncommented):
        errors.append(f"{label}: write permission is forbidden in read-only test CI")

    uses_matches = [m.group(1) or m.group(2) for m in USES_RE.finditer(uncommented)]
    if not uses_matches:
        errors.append(f"{label}: no 'uses:' action steps found")
    for ref in uses_matches:
        if not SHA_ACTION_RE.match(ref):
            errors.append(f"{label}: action '{ref}' is not pinned by a 40-char commit SHA")
    return errors


def find_public_repo_workflows(repo_root: Path = REPO_ROOT) -> list[Path]:
    paths: list[Path] = []
    local_wf = repo_root / ".github" / "workflows" / "ci.yml"
    if local_wf.is_file():
        paths.append(local_wf)

    for sib_name in ("cf-research", "cf-skills"):
        for base in (repo_root.parent, repo_root.parent.parent, repo_root.parent.parent.parent):
            cand = base / sib_name / ".github" / "workflows" / "ci.yml"
            if cand.is_file():
                paths.append(cand)
                break
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify read-only SHA-pinned CI workflows (T-0114).")
    ap.add_argument("files", nargs="*", type=Path, help="Optional workflow files to check")
    args = ap.parse_args(argv)

    targets = args.files if args.files else find_public_repo_workflows()
    if not targets:
        print("FAIL: no .github/workflows/ci.yml files found", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for p in targets:
        if not p.is_file():
            all_errors.append(f"{p}: file not found")
            continue
        all_errors.extend(check_workflow_text(p.read_text(encoding="utf-8"), str(p)))

    if all_errors:
        for e in all_errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print(f"PASS: {len(targets)} CI workflow(s) verified (pull_request, contents: read, 40-hex SHA-pinned actions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

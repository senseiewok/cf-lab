#!/usr/bin/env python3
"""Check SKILL.md frontmatter: starts with '---', parses as YAML, name matches the folder.

With --against REV, also assert that `license` and `compatibility` equal the values
in that git revision (the finalize packet requires them unchanged).

Usage:
    python tasks/check-skill-frontmatter.py                  every .claude/skills/*/SKILL.md
    python tasks/check-skill-frontmatter.py PATH [PATH ...]  only the given SKILL.md files
    python tasks/check-skill-frontmatter.py --against main PATH [PATH ...]

Needs PyYAML (`python -m pip install "PyYAML>=6.0"`, the pin in the sibling repo's
../cf-research/tools/sources/requirements.txt). Exits 1 on any failure.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PRESERVED = ("license", "compatibility")


def parse_frontmatter(text: str) -> dict:
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("file does not start with '---'")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("frontmatter is not closed by a second '---'") from None
    data = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a YAML mapping")
    return data


def committed_frontmatter(rev: str, path: Path) -> dict | None:
    rel = path.resolve().relative_to(REPO_ROOT).as_posix()
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{rev}:{rel}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        return None  # new file at that revision: nothing to preserve
    return parse_frontmatter(proc.stdout)


def check(path: Path, against: str | None) -> list[str]:
    problems: list[str] = []
    try:
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [str(exc)]
    folder = path.resolve().parent.name
    if fm.get("name") != folder:
        problems.append(f"name {fm.get('name')!r} != folder {folder!r}")
    if not fm.get("description"):
        problems.append("description is missing or empty")
    elif len(str(fm["description"])) > 1024:
        problems.append(f"description is {len(str(fm['description']))} characters; the spec allows 1 to 1024")
    if fm.get("compatibility") is not None and len(str(fm["compatibility"])) > 500:
        problems.append(f"compatibility is {len(str(fm['compatibility']))} characters; the spec allows at most 500")
    if against:
        old = committed_frontmatter(against, path)
        if old is not None:
            for key in PRESERVED:
                if fm.get(key) != old.get(key):
                    problems.append(f"{key} changed relative to {against}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--against", metavar="REV", help="git revision whose license/compatibility must be preserved")
    args = parser.parse_args()

    paths = args.paths or sorted((REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md"))
    failures = 0
    for path in paths:
        problems = check(path, args.against)
        label = f"{path.resolve().parent.name}/SKILL.md"
        if problems:
            failures += 1
            print(f"FAIL {label}: {'; '.join(problems)}")
        else:
            print(f"PASS {label}")
    print(f"{len(paths) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

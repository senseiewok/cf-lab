#!/usr/bin/env python3
"""Verify that locally installed third-party skill folders match the SHA-256 hashes pinned in THIRD_PARTY_SKILLS.md (T-0116).

Each third-party skill folder in `.claude/skills/<name>` is git-ignored so nothing from it is committed.
When a folder is present on disk (either in the current checkout's `.claude/skills/` or in the shared git common-dir
main checkout when running inside a git worktree), its canonical folder SHA-256 must match the digest pinned in
`THIRD_PARTY_SKILLS.md`.

Exit codes:
  0 - All present third-party skill folders match their pinned SHA-256 hashes (missing git-ignored folders are skipped unless --require-installed).
  1 - One or more installed third-party skill folders differ from their pinned hash, or a required folder is missing.
  2 - `THIRD_PARTY_SKILLS.md` is missing or contains no valid pinned SHA-256 table rows.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC = ROOT / "THIRD_PARTY_SKILLS.md"
DEFAULT_SKILLS_DIR = ROOT / ".claude" / "skills"

ROW_RE = re.compile(
    r"^\|\s*`([a-z0-9][a-z0-9_-]*)`\s*\|[^|]+\|\s*`([0-9a-f]{64})`\s*\|",
    re.MULTILINE,
)


def hash_skill_dir(skill_dir: Path) -> str:
    """Compute canonical SHA-256 over sorted POSIX relative paths and LF-normalised UTF-8 (or raw binary) contents."""
    manifest = hashlib.sha256()
    files = sorted(
        (
            p
            for p in skill_dir.rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and ".git" not in p.parts
            and p.suffix.lower() != ".pyc"
            and p.name != ".DS_Store"
        ),
        key=lambda p: p.relative_to(skill_dir).as_posix(),
    )
    if not files:
        raise ValueError(f"empty skill directory: {skill_dir}")
    for f in files:
        rel = f.relative_to(skill_dir).as_posix()
        raw = f.read_bytes()
        try:
            text = raw.decode("utf-8")
            norm = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        except UnicodeDecodeError:
            norm = raw
        file_sha = hashlib.sha256(norm).hexdigest()
        manifest.update(f"{rel}\0{file_sha}\n".encode("utf-8"))
    return manifest.hexdigest()


def parse_pinned_hashes(doc_path: Path) -> dict[str, str]:
    """Parse `| `skill-name` | ... | `<64-hex-sha256>` | ... |` rows from THIRD_PARTY_SKILLS.md."""
    if not doc_path.is_file():
        raise FileNotFoundError(f"missing {doc_path}")
    text = doc_path.read_text(encoding="utf-8")
    pins: dict[str, str] = {}
    for m in ROW_RE.finditer(text):
        skill_name, sha = m.group(1), m.group(2)
        if skill_name in pins and pins[skill_name] != sha:
            raise ValueError(f"conflicting hashes for {skill_name} in {doc_path}")
        pins[skill_name] = sha
    if not pins:
        raise ValueError(f"no pinned SHA-256 rows found in {doc_path}")
    return pins


def _common_checkout_skills_dir(repo_root: Path) -> Path | None:
    """If running in a git worktree where git-ignored skills live in the main checkout, locate `<main>/.claude/skills`."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        common_git = (repo_root / r.stdout.strip()).resolve()
        if common_git.name == ".git":
            candidate = common_git.parent / ".claude" / "skills"
            if candidate.is_dir():
                return candidate
    except Exception:
        return None
    return None


def check_third_party_skills(
    doc_path: Path = DEFAULT_DOC,
    skills_dir: Path | None = None,
    require_installed: bool = False,
) -> tuple[int, list[str]]:
    """Return `(exit_code, messages)` after checking pinned hashes."""
    try:
        pins = parse_pinned_hashes(doc_path)
    except (FileNotFoundError, ValueError) as exc:
        return 2, [f"ERROR: {exc}"]

    use_fallback = skills_dir is None
    primary_dir = skills_dir if skills_dir is not None else DEFAULT_SKILLS_DIR
    fallback_dir = _common_checkout_skills_dir(ROOT) if use_fallback else None

    messages: list[str] = []
    failures = 0
    verified = 0

    for name, expected_sha in pins.items():
        target = primary_dir / name
        if not target.is_dir() and fallback_dir is not None:
            alt = fallback_dir / name
            if alt.is_dir():
                target = alt

        if not target.is_dir():
            if require_installed:
                messages.append(f"FAIL {name}: folder not installed at {primary_dir / name}")
                failures += 1
            else:
                messages.append(f"SKIP {name}: not installed locally (git-ignored)")
            continue

        try:
            actual_sha = hash_skill_dir(target)
        except ValueError as exc:
            messages.append(f"FAIL {name}: {exc}")
            failures += 1
            continue

        if actual_sha != expected_sha:
            messages.append(
                f"FAIL {name}: hash mismatch (expected {expected_sha}, got {actual_sha})"
            )
            failures += 1
        else:
            messages.append(f"PASS {name}: {actual_sha}")
            verified += 1

    if failures > 0:
        messages.append(f"RESULT FAIL ({failures} failed, {verified} verified)")
        return 1, messages

    messages.append(f"RESULT PASS ({verified} verified, {len(pins) - verified} skipped)")
    return 0, messages


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", type=Path, default=DEFAULT_DOC, help="Path to THIRD_PARTY_SKILLS.md")
    ap.add_argument(
        "--skills-dir",
        type=Path,
        default=None,
        help="Path to .claude/skills directory (defaults to repo .claude/skills with worktree main-checkout fallback)",
    )
    ap.add_argument(
        "--require-installed",
        action="store_true",
        help="Fail if any pinned third-party skill folder is not installed locally",
    )
    args = ap.parse_args(argv)
    code, msgs = check_third_party_skills(
        doc_path=args.doc,
        skills_dir=args.skills_dir,
        require_installed=args.require_installed,
    )
    for m in msgs:
        print(m)
    return code


if __name__ == "__main__":
    sys.exit(main())

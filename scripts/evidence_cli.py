#!/usr/bin/env python3
"""Control-repo launcher for the cf-evidence-loop skill in ../cf-skills (T-0051 & T-0140).

Invokes cf-evidence-loop directly from the sibling ../cf-skills repository without
copying the skill or maintaining a duplicate catalog:
  - Uses EVIDENCE_CATALOG if already set in the environment.
  - Otherwise resolves ../cf-research/sources/catalog.yaml when the sibling repo is present.
  - Falls back to cf-lab/sources/catalog.snapshot.yaml only after verifying its SHA-256
    integrity and freshness via tasks/sync_catalog_snapshot.py (failing closed with
    'refresh the catalog' when stale or tampered).

Usage from cf-lab root:
    python scripts/evidence_cli.py retractions 10.1016/S0140-6736(97)11096-0
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_sibling_repo(name: str, repo_root: Path = REPO_ROOT) -> Path | None:
    """Find a sibling repo ('cf-skills' or 'cf-research') from a main checkout or worktree."""
    for base in (repo_root.parent, repo_root.parent.parent, repo_root.parent.parent.parent):
        cand = base / name
        if cand.is_dir() and (cand / ".git").exists():
            return cand
    return None


def resolve_catalog(repo_root: Path = REPO_ROOT) -> tuple[Path | None, str | None]:
    """Return (catalog_path, error_message)."""
    env_cat = os.environ.get("EVIDENCE_CATALOG", "").strip()
    if env_cat:
        p = Path(env_cat)
        if p.is_file():
            return p.resolve(), None
        return None, f"error: EVIDENCE_CATALOG points to missing file: {env_cat}"

    cf_research = find_sibling_repo("cf-research", repo_root)
    if cf_research is not None:
        cat = cf_research / "sources" / "catalog.yaml"
        if cat.is_file():
            return cat.resolve(), None

    snapshot = repo_root / "sources" / "catalog.snapshot.yaml"
    tasks_dir = repo_root / "tasks"
    if str(tasks_dir) not in sys.path:
        sys.path.insert(0, str(tasks_dir))
    import sync_catalog_snapshot  # noqa: E402

    ok, msg = sync_catalog_snapshot.check_snapshot(snapshot_path=snapshot)
    if not ok:
        return None, msg
    return snapshot.resolve(), None


def main(argv: list[str] | None = None) -> int:
    cf_skills = find_sibling_repo("cf-skills")
    if cf_skills is None:
        print(
            "error: sibling repository ../cf-skills not found; run setup.cmd or ./setup.sh first.",
            file=sys.stderr,
        )
        return 2

    skill_scripts = cf_skills / ".claude" / "skills" / "cf-evidence-loop" / "scripts"
    if not (skill_scripts / "evidence" / "cli.py").is_file():
        print(f"error: cf-evidence-loop CLI not found under {skill_scripts}", file=sys.stderr)
        return 2

    cat_path, err = resolve_catalog()
    if err or cat_path is None:
        print(err or "error: could not resolve source catalog", file=sys.stderr)
        return 3

    os.environ["EVIDENCE_CATALOG"] = str(cat_path)
    if str(skill_scripts) not in sys.path:
        sys.path.insert(0, str(skill_scripts))

    from evidence import cli  # type: ignore[import-not-found]

    return int(cli.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())

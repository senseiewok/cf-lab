#!/usr/bin/env python3
"""Generate and verify cf-lab/sources/catalog.snapshot.yaml (T-0140).

Writes a read-only fallback snapshot of ../cf-research/sources/catalog.yaml
with a header naming the source repository (senseiewok/cf-research), commit SHA,
date, SHA-256 digest of the canonical payload, and the marker 'generated, do not edit'.

When run with --check:
  1. Verifies the snapshot exists, carries the mandatory header ('generated, do not edit',
     source repository, commit SHA, date, and sha256), and that its body matches the
     recorded sha256 (a 1-byte edit fails immediately).
  2. Verifies the snapshot date is not older than --max-age-days (default 30); if stale,
     fails closed with 'refresh the catalog'.
  3. When the sibling ../cf-research/sources/catalog.yaml is present, verifies that the
     snapshot body is byte-identical to ../cf-research/sources/catalog.yaml.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "sources" / "catalog.snapshot.yaml"
SOURCE_REPO_NAME = "senseiewok/cf-research"
DEFAULT_MAX_AGE_DAYS = 30


def find_sibling_catalog(repo_root: Path = REPO_ROOT) -> Path | None:
    """Locate ../cf-research/sources/catalog.yaml from main checkout or a worktree."""
    candidates = [
        repo_root.parent / "cf-research" / "sources" / "catalog.yaml",
        repo_root.parent.parent / "cf-research" / "sources" / "catalog.yaml",
        repo_root.parent.parent.parent / "cf-research" / "sources" / "catalog.yaml",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def get_git_head_sha(catalog_path: Path) -> str:
    """Return the HEAD commit SHA of the cf-research repository containing catalog_path."""
    res_repo = catalog_path.parent.parent
    try:
        proc = subprocess.run(
            ["git", "-C", str(res_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        sha = proc.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
    except Exception:
        pass
    return "0" * 40


def normalize_bytes(raw: bytes) -> bytes:
    """Normalize CRLF to LF for deterministic cross-platform hashing."""
    return raw.replace(b"\r\n", b"\n")


def render_snapshot(body_bytes: bytes, commit_sha: str, generated_date: str) -> bytes:
    norm_body = normalize_bytes(body_bytes)
    digest = hashlib.sha256(norm_body).hexdigest()
    header = (
        f"# generated, do not edit\n"
        f"# source_repository: {SOURCE_REPO_NAME}\n"
        f"# source_commit: {commit_sha}\n"
        f"# generated_date: {generated_date}\n"
        f"# payload_sha256: {digest}\n"
    ).encode("utf-8")
    return header + norm_body


def parse_snapshot(raw: bytes) -> tuple[dict[str, str], bytes]:
    norm = normalize_bytes(raw)
    lines = norm.split(b"\n")
    meta: dict[str, str] = {}
    idx = 0
    while idx < len(lines) and idx < 10 and lines[idx].startswith(b"#"):
        line_str = lines[idx].decode("utf-8", errors="replace").strip()
        if "generated, do not edit" in line_str.lower():
            meta["marker"] = "generated, do not edit"
        m = re.match(r"^#\s*([a-z0-9_]+):\s*(.+)$", line_str)
        if m:
            meta[m.group(1)] = m.group(2).strip()
        idx += 1
        if "payload_sha256" in meta:
            break
    body = b"\n".join(lines[idx:])
    return meta, body


def write_snapshot(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    source_catalog: Path | None = None,
    generated_date: str | None = None,
    commit_sha: str | None = None,
) -> int:
    src = source_catalog or find_sibling_catalog()
    if src is None or not src.is_file():
        print("FAIL: sibling ../cf-research/sources/catalog.yaml not found; cannot generate snapshot.", file=sys.stderr)
        return 1
    sha = commit_sha or get_git_head_sha(src)
    date_str = generated_date or dt.date.today().isoformat()
    body = src.read_bytes()
    out = render_snapshot(body, sha, date_str)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(out)
    print(f"WROTE {snapshot_path} from {SOURCE_REPO_NAME}@{sha[:12]} ({date_str})")
    return 0


def check_snapshot(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    source_catalog: Path | None = None,
    require_sibling: bool = False,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    today: dt.date | None = None,
) -> tuple[bool, str]:
    if not snapshot_path.is_file():
        return False, f"FAIL: snapshot missing at {snapshot_path}; refresh the catalog"

    meta, body = parse_snapshot(snapshot_path.read_bytes())
    if meta.get("marker") != "generated, do not edit":
        return False, "FAIL: snapshot header lacks 'generated, do not edit'"
    if meta.get("source_repository") != SOURCE_REPO_NAME:
        return False, f"FAIL: snapshot header source_repository must be '{SOURCE_REPO_NAME}'"
    sha = meta.get("source_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return False, f"FAIL: snapshot header source_commit is not a 40-char hex SHA: {sha!r}"
    gen_date_str = meta.get("generated_date", "")
    try:
        gen_date = dt.date.fromisoformat(gen_date_str)
    except ValueError:
        return False, f"FAIL: snapshot header generated_date is not ISO YYYY-MM-DD: {gen_date_str!r}"

    recorded_hash = meta.get("payload_sha256", "")
    actual_hash = hashlib.sha256(body).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", recorded_hash) or recorded_hash != actual_hash:
        return False, (
            f"FAIL: snapshot payload_sha256 mismatch (recorded {recorded_hash[:12]}..., "
            f"actual {actual_hash[:12]}...); refresh the catalog"
        )

    ref_today = today or dt.date.today()
    age_days = (ref_today - gen_date).days
    if age_days > max_age_days:
        return False, (
            f"FAIL: snapshot is {age_days} days old (limit {max_age_days} days, generated {gen_date_str}); "
            f"refresh the catalog"
        )

    src = source_catalog if source_catalog is not None else find_sibling_catalog()
    if src is not None and src.is_file():
        expected_body = normalize_bytes(src.read_bytes())
        if body != expected_body:
            return False, (
                f"FAIL: snapshot differs from {src}; run 'python tasks/sync_catalog_snapshot.py' to refresh the catalog"
            )
        return True, f"PASS: catalog.snapshot.yaml matches {SOURCE_REPO_NAME}@{sha[:12]} ({gen_date_str}, sha256={actual_hash[:12]}...)"

    if require_sibling:
        return False, "FAIL: sibling ../cf-research/sources/catalog.yaml required but not found"

    return True, f"PASS (standalone): catalog.snapshot.yaml verified offline ({SOURCE_REPO_NAME}@{sha[:12]}, {gen_date_str})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate or verify cf-lab/sources/catalog.snapshot.yaml (T-0140).")
    ap.add_argument("--check", action="store_true", help="Verify snapshot integrity, freshness, and sibling match.")
    ap.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT, help="Path to catalog.snapshot.yaml")
    ap.add_argument("--source", type=Path, default=None, help="Explicit path to upstream catalog.yaml")
    ap.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS, help="Max age in days before stale failure")
    args = ap.parse_args(argv)

    if args.check:
        ok, msg = check_snapshot(
            snapshot_path=args.snapshot,
            source_catalog=args.source,
            max_age_days=args.max_age_days,
        )
        print(msg, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    return write_snapshot(snapshot_path=args.snapshot, source_catalog=args.source)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Automated Cross-Repo Evidence Catalog Schema & External Source Lock Linter.

Validates evidence source integrity, catalog schema consistency, license
declarations, terms-of-use flags, and cryptographic pin consistency across
all workspace repositories (cf-research, cf-skills, cf-lab).

Usage:
    python tasks/check_catalog_schema_lock.py --check
    python tasks/check_catalog_schema_lock.py --json
    python tasks/check_catalog_schema_lock.py --catalog path/to/catalog.yaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / ".loop-logs"
DEFAULT_REPORT_PATH = LOGS_DIR / "catalog-schema-audit.json"

PERMITTED_ACCESS_MODES = frozenset({"fetch", "api", "manual", "request", "forbidden", "open"})
PERMITTED_ROBOTS = frozenset({"allow", "disallow", "unknown", "unreadable"})
PERMITTED_CLAIM_LABELS = frozenset({"verified", "unverified", "hypothesis"})
PERMITTED_AUTH_MODES = frozenset({"none", "optional_api_key", "api_key_required"})

SLUG_RX = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.I)


def normalize_bytes(raw: bytes) -> bytes:
    """Normalize CRLF to LF for deterministic cross-platform hashing."""
    return raw.replace(b"\r\n", b"\n")


def compute_sha256(raw: bytes) -> str:
    """Return SHA-256 hex digest of normalized bytes."""
    return hashlib.sha256(normalize_bytes(raw)).hexdigest()


def find_sibling_path(rel_candidates: List[Path], base_root: Path = REPO_ROOT) -> Optional[Path]:
    """Find a sibling file checking workspace layouts and worktrees."""
    roots = [
        base_root,
        base_root.parent,
        base_root.parent.parent,
        base_root.parent.parent.parent,
    ]
    for r in roots:
        for cand in rel_candidates:
            p = (r / cand).resolve()
            if p.is_file():
                return p
    return None


def resolve_canonical_catalog(custom: Optional[Path] = None) -> Optional[Path]:
    if custom and custom.is_file():
        return custom.resolve()
    candidates = [
        Path("cf-research/sources/catalog.yaml"),
        Path("sources/catalog.yaml"),
    ]
    return find_sibling_path(candidates)


def resolve_skills_catalog(custom: Optional[Path] = None) -> Optional[Path]:
    if custom and custom.is_file():
        return custom.resolve()
    candidates = [
        Path("cf-skills/.claude/skills/cf-evidence-loop/catalog.yaml"),
        Path(".claude/skills/cf-evidence-loop/catalog.yaml"),
    ]
    return find_sibling_path(candidates)


def resolve_lock_file(custom: Optional[Path] = None) -> Optional[Path]:
    if custom and custom.is_file():
        return custom.resolve()
    candidates = [
        Path("cf-skills/.claude/skills/cf-evidence-loop/catalog.lock.json"),
        Path(".claude/skills/cf-evidence-loop/catalog.lock.json"),
    ]
    return find_sibling_path(candidates)


def resolve_snapshot_file(custom: Optional[Path] = None) -> Optional[Path]:
    if custom and custom.is_file():
        return custom.resolve()
    candidates = [
        Path("sources/catalog.snapshot.yaml"),
        Path("cf-lab/sources/catalog.snapshot.yaml"),
    ]
    return find_sibling_path(candidates)


def validate_catalog_schema(
    catalog_path: Path,
    label: str = "canonical",
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Validate a catalog YAML file against the evidence catalog schema.
    
    Returns:
        (violations, warnings, parsed_data)
    """
    violations: List[str] = []
    warnings: List[str] = []

    if not catalog_path.is_file():
        violations.append(f"[{label}] Catalog file does not exist: {catalog_path}")
        return violations, warnings, {}

    try:
        raw_text = catalog_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text)
    except Exception as e:
        violations.append(f"[{label}] Failed to parse YAML at {catalog_path}: {e}")
        return violations, warnings, {}

    if not isinstance(data, dict):
        violations.append(f"[{label}] Root YAML must be a mapping, got {type(data).__name__}")
        return violations, warnings, {}

    # 1. Top-level fields
    schema_version = data.get("schema_version")
    if schema_version != 1:
        violations.append(f"[{label}] schema_version must be 1, got {schema_version!r}")

    updated = data.get("updated")
    if not updated or not DATE_RX.match(str(updated)):
        violations.append(f"[{label}] updated must match YYYY-MM-DD, got {updated!r}")

    defaults = data.get("defaults")
    if defaults is not None and not isinstance(defaults, dict):
        violations.append(f"[{label}] defaults must be a mapping, got {type(defaults).__name__}")

    sources = data.get("sources")
    if not isinstance(sources, list) or len(sources) == 0:
        violations.append(f"[{label}] sources must be a non-empty list")
        return violations, warnings, data

    # 2. Source entry validations
    seen_ids: Set[str] = set()

    for idx, s in enumerate(sources):
        if not isinstance(s, dict):
            violations.append(f"[{label}] Source #{idx} must be a mapping, got {type(s).__name__}")
            continue

        sid = s.get("id")
        if not sid or not isinstance(sid, str):
            violations.append(f"[{label}] Source #{idx} missing required string id")
            continue

        if not SLUG_RX.match(sid):
            violations.append(f"[{label}] Source '{sid}' id is not a valid slug format")

        if sid in seen_ids:
            violations.append(f"[{label}] Duplicate source id: '{sid}'")
        seen_ids.add(sid)

        # Mandatory fields
        for req in ("title", "publisher", "kind", "access"):
            val = s.get(req)
            if val is None or (isinstance(val, str) and not val.strip()):
                violations.append(f"[{label}] Source '{sid}' missing required field: '{req}'")

        # access validation
        access = str(s.get("access", "")).strip().lower()
        if access and access not in PERMITTED_ACCESS_MODES:
            violations.append(f"[{label}] Source '{sid}' invalid access mode: {access!r}")

        # robots validation
        robots = s.get("robots")
        if robots is not None and str(robots).strip().lower() not in PERMITTED_ROBOTS:
            violations.append(f"[{label}] Source '{sid}' invalid robots value: {robots!r}")

        # claim_label validation
        claim_label = s.get("claim_label")
        if claim_label is not None and str(claim_label).strip().lower() not in PERMITTED_CLAIM_LABELS:
            violations.append(f"[{label}] Source '{sid}' invalid claim_label: {claim_label!r}")

        # auth validation
        auth = s.get("auth")
        if auth is not None and str(auth).strip().lower() not in PERMITTED_AUTH_MODES:
            violations.append(f"[{label}] Source '{sid}' invalid auth mode: {auth!r}")

        # programmatic access invariants per security-browsing and security-baseline
        if access == "api":
            has_endpoint = bool(s.get("base_url") or s.get("api_root"))
            if not has_endpoint:
                violations.append(f"[{label}] Source '{sid}' with access 'api' must declare 'base_url' or 'api_root'")
            if not s.get("terms_url"):
                violations.append(f"[{label}] Source '{sid}' with access 'api' must declare 'terms_url'")
            if robots == "disallow" and not s.get("terms_url"):
                violations.append(f"[{label}] Source '{sid}' with access 'api' declares robots: disallow without terms_url")

        if access == "fetch":
            has_url = bool(s.get("url") or s.get("landing_page"))
            if not has_url:
                violations.append(f"[{label}] Source '{sid}' with access 'fetch' must declare 'url' or 'landing_page'")
            if robots == "disallow":
                violations.append(f"[{label}] Source '{sid}' with access 'fetch' declares robots: disallow (forbidden to fetch)")

        # URL format checks
        for url_field in ("url", "landing_page", "base_url", "terms_url"):
            u = s.get(url_field)
            if u is not None and isinstance(u, str) and u.strip():
                if not URL_RX.match(u.strip()):
                    violations.append(f"[{label}] Source '{sid}' has invalid {url_field} format: {u!r}")

        # redistribute guardrails
        redistribute = s.get("redistribute", defaults.get("redistribute", False) if defaults else False)
        if redistribute:
            if claim_label != "verified":
                warnings.append(f"[{label}] Source '{sid}' has redistribute=true but claim_label is not verified")

    return violations, warnings, data


def verify_cryptographic_locks(
    canonical_catalog: Path,
    skills_catalog: Optional[Path],
    lock_file: Optional[Path],
    snapshot_file: Optional[Path],
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Verify cryptographic SHA-256 pins in catalog.lock.json and snapshot header."""
    violations: List[str] = []
    warnings: List[str] = []
    lock_info: Dict[str, Any] = {}

    if not canonical_catalog.is_file():
        violations.append(f"Canonical catalog missing for lock verification: {canonical_catalog}")
        return violations, warnings, lock_info

    canonical_bytes = canonical_catalog.read_bytes()
    canonical_hash = compute_sha256(canonical_bytes)
    lock_info["canonical_hash"] = canonical_hash

    # 1. Check skills catalog and lock.json
    if lock_file and lock_file.is_file():
        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            lock_info["lock_data"] = lock_data

            # Check inputs["sources/catalog.yaml"]
            inputs = lock_data.get("inputs", {})
            pinned_canonical = inputs.get("sources/catalog.yaml")
            if not pinned_canonical:
                violations.append(f"Lock file {lock_file.name} missing inputs['sources/catalog.yaml']")
            elif pinned_canonical != canonical_hash:
                violations.append(
                    f"Lock file input hash mismatch: lock records {pinned_canonical}, actual {canonical_hash}"
                )

            # Check copy_sha256
            if skills_catalog and skills_catalog.is_file():
                skills_bytes = skills_catalog.read_bytes()
                skills_hash = compute_sha256(skills_bytes)
                lock_info["skills_hash"] = skills_hash

                expected_copy_hash = lock_data.get("copy_sha256")
                if expected_copy_hash and expected_copy_hash != skills_hash:
                    violations.append(
                        f"Skills catalog copy hash mismatch: lock records {expected_copy_hash}, actual {skills_hash}"
                    )
            else:
                warnings.append("Skills catalog not found for lock verification")

        except Exception as e:
            violations.append(f"Failed to read/parse {lock_file}: {e}")
    else:
        warnings.append("Cryptographic lock file catalog.lock.json not found")

    # 2. Check snapshot file header if present
    if snapshot_file and snapshot_file.is_file():
        try:
            snap_bytes = snapshot_file.read_bytes()
            norm = normalize_bytes(snap_bytes)
            lines = norm.split(b"\n")
            meta: Dict[str, str] = {}
            idx = 0
            while idx < len(lines) and idx < 10 and lines[idx].startswith(b"#"):
                line_str = lines[idx].decode("utf-8", errors="replace").strip()
                m = re.match(r"^#\s*([a-z0-9_]+):\s*(.+)$", line_str)
                if m:
                    meta[m.group(1)] = m.group(2).strip()
                idx += 1
                if "payload_sha256" in meta:
                    break
            body = b"\n".join(lines[idx:])
            body_digest = hashlib.sha256(body).hexdigest()

            recorded_sha = meta.get("payload_sha256")
            if not recorded_sha:
                violations.append(f"Snapshot {snapshot_file.name} missing payload_sha256 header")
            elif recorded_sha != body_digest:
                violations.append(
                    f"Snapshot body hash mismatch: header recorded {recorded_sha}, body computes {body_digest}"
                )
            lock_info["snapshot_sha256"] = body_digest
        except Exception as e:
            violations.append(f"Failed to read/parse snapshot at {snapshot_file}: {e}")

    return violations, warnings, lock_info


def audit_catalog_schema_lock(
    canonical_catalog: Optional[Path] = None,
    skills_catalog: Optional[Path] = None,
    lock_file: Optional[Path] = None,
    snapshot_file: Optional[Path] = None,
    report_path: Optional[Path] = DEFAULT_REPORT_PATH,
) -> Dict[str, Any]:
    """Run full catalog schema and lock audit."""
    c_cat = resolve_canonical_catalog(canonical_catalog)
    s_cat = resolve_skills_catalog(skills_catalog)
    l_file = resolve_lock_file(lock_file)
    snap_file = resolve_snapshot_file(snapshot_file)

    all_violations: List[str] = []
    all_warnings: List[str] = []
    catalogs_checked: List[str] = []
    locks_checked: List[str] = []
    sources_count = 0

    if not c_cat or not c_cat.is_file():
        all_violations.append("Canonical catalog (cf-research/sources/catalog.yaml) could not be found")
    else:
        catalogs_checked.append(str(c_cat))
        v, w, c_data = validate_catalog_schema(c_cat, label="canonical")
        all_violations.extend(v)
        all_warnings.extend(w)
        sources_count = len(c_data.get("sources", []))

    if s_cat and s_cat.is_file():
        catalogs_checked.append(str(s_cat))
        v, w, s_data = validate_catalog_schema(s_cat, label="skills")
        all_violations.extend(v)
        all_warnings.extend(w)

        # Cross-catalog consistency
        if c_cat and c_cat.is_file():
            c_sources = {s["id"] for s in c_data.get("sources", []) if isinstance(s, dict) and "id" in s}
            s_sources = {s["id"] for s in s_data.get("sources", []) if isinstance(s, dict) and "id" in s}
            if c_sources != s_sources:
                diff_c = c_sources - s_sources
                diff_s = s_sources - c_sources
                if diff_c:
                    all_violations.append(f"Canonical catalog has sources missing from skills catalog: {sorted(diff_c)}")
                if diff_s:
                    all_violations.append(f"Skills catalog has extra uncataloged sources: {sorted(diff_s)}")

    if l_file and l_file.is_file():
        locks_checked.append(str(l_file))

    if c_cat and c_cat.is_file():
        lv, lw, _ = verify_cryptographic_locks(c_cat, s_cat, l_file, snap_file)
        all_violations.extend(lv)
        all_warnings.extend(lw)

    status = "PASS" if len(all_violations) == 0 else "FAIL"

    report: Dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status,
        "sources_scanned": sources_count,
        "catalogs_checked": catalogs_checked,
        "locks_checked": locks_checked,
        "schema_version": 1,
        "violations": all_violations,
        "warnings": all_warnings,
    }

    if report_path:
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except Exception as e:
            all_warnings.append(f"Could not write report to {report_path}: {e}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence catalog schema and external source lock linter")
    parser.add_argument("--catalog", type=Path, help="Path to canonical catalog.yaml")
    parser.add_argument("--skills-catalog", type=Path, help="Path to skills catalog.yaml")
    parser.add_argument("--lock-file", type=Path, help="Path to catalog.lock.json")
    parser.add_argument("--snapshot-file", type=Path, help="Path to catalog.snapshot.yaml")
    parser.add_argument("--check", action="store_true", help="Assert clean schema and valid cryptographic locks")
    parser.add_argument("--json", action="store_true", help="Print json diagnostic report to stdout")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH, help="Path to write report json")

    args = parser.parse_args()

    report = audit_catalog_schema_lock(
        canonical_catalog=args.catalog,
        skills_catalog=args.skills_catalog,
        lock_file=args.lock_file,
        snapshot_file=args.snapshot_file,
        report_path=args.report,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status_symbol = "PASS" if report["status"] == "PASS" else "FAIL"
        print(f"Catalog Schema & Lock Linter [{status_symbol}]")
        print(f"  Sources Scanned: {report['sources_scanned']}")
        print(f"  Catalogs Checked: {len(report['catalogs_checked'])}")
        print(f"  Locks Checked:    {len(report['locks_checked'])}")
        print(f"  Violations:       {len(report['violations'])}")
        print(f"  Warnings:         {len(report['warnings'])}")
        for v in report["violations"]:
            print(f"  * [VIOLATION] {v}")
        for w in report["warnings"]:
            print(f"  * [WARNING] {w}")

    if args.check and report["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

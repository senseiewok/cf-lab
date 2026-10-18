#!/usr/bin/env python3
"""Automated data-i18n Spanish translation completeness & orphan key verifier across .ai HTML routes.

Verifies that every declarative data-i18n attribute (including data-i18n-title,
data-i18n-body, data-i18n-aria-label) across all canonical .ai HTML routes resolves
to a verified, non-empty Mexican Spanish (es-MX) translation in data/i18n/es-MX.json.
Also scans for unreferenced orphan translation keys.

Standard library only.
Usage:
  python tasks/check_i18n_parity.py            # Print summary and audit details
  python tasks/check_i18n_parity.py --check    # Exit 1 if any missing/empty translation
  python tasks/check_i18n_parity.py --json     # Output JSON digest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

CANONICAL_ROUTES = [
    "index.html",
    "cf/index.html",
    "cf/tree/index.html",
    "cf/ptc/index.html",
    "cf/cftr/index.html",
    "cf/delivery/index.html",
    "cf/trials/index.html",
    "cf/registries/index.html",
    "resources/index.html",
    "ai-in-care/index.html",
    "tools/index.html",
    "evidence/index.html",
    "ai-loop/index.html",
    "about/index.html",
    "contact/index.html",
    "404.html",
    "letter/index.html",
    "preview/index.html",
    "atlas/index.html",
]

FALLBACK_SECTIONS = [
    "tree",
    "ptc",
    "delivery",
    "trials",
    "registries",
    "cf",
    "chrome",
    "home",
    "cftr",
    "ai_loop",
]


def find_ai_root(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Dynamically resolve the .ai repository root directory across standard sibling and worktree layouts."""
    env_root = os.environ.get("AI_ROOT")
    if env_root:
        p = Path(env_root)
        if p.is_dir() and (p / "src").is_dir() and (p / "data" / "i18n" / "es-MX.json").is_file():
            return p.resolve()

    search_dirs = []
    if start_dir:
        search_dirs.append(start_dir)
    search_dirs.append(Path(__file__).resolve().parent)
    search_dirs.append(Path.cwd())

    for base in search_dirs:
        for parent in [base] + list(base.parents):
            candidate = parent / ".ai"
            if (
                candidate.is_dir()
                and (candidate / "src").is_dir()
                and (candidate / "data" / "i18n" / "es-MX.json").is_file()
            ):
                return candidate.resolve()

    return None


def load_catalog(catalog_path: Path) -> Dict[str, Any]:
    """Load and parse the JSON translation catalog."""
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Translation catalog not found at {catalog_path}")
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def resolve_key(key_path: str, catalog: Dict[str, Any]) -> Optional[Any]:
    """Resolve a key against the catalog using i18n.js runtime resolution rules.

    Supports dot-delimited paths ('chrome.banner_copy', 'cf.ptc_title') and
    falls back to searching common sections if the key is unqualified.
    """
    val: Any = catalog
    for part in key_path.split("."):
        if isinstance(val, dict) and part in val:
            val = val[part]
        else:
            val = None
            break

    if val is None and "." not in key_path:
        for section in FALLBACK_SECTIONS:
            if (
                section in catalog
                and isinstance(catalog[section], dict)
                and key_path in catalog[section]
            ):
                val = catalog[section][key_path]
                break

    return val


def extract_i18n_attributes(html_content: str) -> List[Tuple[str, str]]:
    """Extract all (attribute_name, key_path) tuples from HTML text."""
    pattern = re.compile(r'(data-i18n(?:-[a-z0-9_-]+)?)=["\']([^"\']+)["\']', re.IGNORECASE)
    matches = pattern.findall(html_content)
    return matches


def flatten_catalog(d: Dict[str, Any], prefix: str = "") -> List[Tuple[str, str, Any]]:
    """Flatten a nested dictionary into [(full_dotted_key, short_key, value)]."""
    items = []
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.extend(flatten_catalog(v, full_key))
        else:
            items.append((full_key, k, v))
    return items


def scan_routes(
    src_dir: Path, routes: Optional[List[str]] = None
) -> Dict[str, List[Tuple[str, str]]]:
    """Scan HTML routes for all i18n attributes."""
    if routes is None:
        routes = CANONICAL_ROUTES

    route_map: Dict[str, List[Tuple[str, str]]] = {}
    for rel_route in routes:
        html_file = src_dir / rel_route
        if not html_file.is_file():
            continue
        content = html_file.read_text(encoding="utf-8")
        attrs = extract_i18n_attributes(content)
        route_map[rel_route] = attrs

    return route_map


def audit_parity(
    ai_root: Path, routes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Perform full completeness and orphan key verification audit."""
    src_dir = ai_root / "src"
    catalog_path = ai_root / "data" / "i18n" / "es-MX.json"
    catalog = load_catalog(catalog_path)

    route_map = scan_routes(src_dir, routes)

    unique_keys_scanned: Set[str] = set()
    total_attribute_uses = 0
    missing_keys: List[Dict[str, str]] = []
    resolved_count = 0

    for route, attrs in route_map.items():
        for attr_name, key_path in attrs:
            total_attribute_uses += 1
            unique_keys_scanned.add(key_path)
            val = resolve_key(key_path, catalog)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing_keys.append({
                    "route": route,
                    "attribute": attr_name,
                    "key": key_path,
                    "reason": "Missing from catalog" if val is None else "Empty string",
                })
            else:
                resolved_count += 1

    # Orphan key analysis
    flat_catalog = flatten_catalog(catalog)
    total_catalog_keys = len(flat_catalog)

    # Gather all potential code references across scripts and HTML
    referenced_keys: Set[str] = set()
    all_texts: List[str] = []

    scripts_dir = src_dir / "scripts"
    if scripts_dir.is_dir():
        for script_file in scripts_dir.glob("*.js"):
            all_texts.append(script_file.read_text(encoding="utf-8"))

    for html_file in src_dir.glob("**/*.html"):
        all_texts.append(html_file.read_text(encoding="utf-8"))

    combined_code_corpus = "\n".join(all_texts)

    orphan_keys: List[Dict[str, str]] = []
    for full_key, short_key, val in flat_catalog:
        if full_key in unique_keys_scanned or short_key in unique_keys_scanned:
            referenced_keys.add(full_key)
            continue

        if full_key in combined_code_corpus:
            referenced_keys.add(full_key)
            continue

        # For short_key, look for quoted property name, dot property access, or identifier boundary
        escaped_short = re.escape(short_key)
        short_pattern = re.compile(
            r'(\b' + escaped_short + r'\b|[\'"]' + escaped_short + r'[\'"]|\.' + escaped_short + r'\b)'
        )
        if short_pattern.search(combined_code_corpus):
            referenced_keys.add(full_key)
        else:
            orphan_keys.append({
                "full_key": full_key,
                "short_key": short_key,
                "preview": str(val)[:40] if val is not None else "",
            })

    status = "CLEAN" if not missing_keys else "FAIL"

    return {
        "status": status,
        "ai_root": str(ai_root),
        "catalog_path": str(catalog_path),
        "routes_scanned": len(route_map),
        "total_attribute_uses": total_attribute_uses,
        "unique_keys_scanned": len(unique_keys_scanned),
        "resolved_attribute_uses": resolved_count,
        "missing_keys_count": len(missing_keys),
        "missing_keys": missing_keys,
        "total_catalog_keys": total_catalog_keys,
        "referenced_catalog_keys": len(referenced_keys),
        "orphan_keys_count": len(orphan_keys),
        "orphan_keys": orphan_keys,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify data-i18n Spanish translation completeness and orphan keys across .ai routes."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any missing/unresolved translations or parity defects are found.",
    )
    parser.add_argument(
        "--strict-orphans",
        action="store_true",
        help="Also exit non-zero if any unreferenced orphan keys exist in the catalog.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON digest.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Path to .ai repository root.",
    )

    args = parser.parse_args(argv)

    ai_root = args.root or find_ai_root()
    if not ai_root or not (ai_root / "src").is_dir() or not (ai_root / "data" / "i18n" / "es-MX.json").is_file():
        if args.json:
            print(json.dumps({
                "status": "SKIPPED",
                "reason": "Could not locate .ai repository root with src/ and data/i18n/es-MX.json",
                "routes_scanned": 0,
                "total_attribute_uses": 0,
                "missing_keys_count": 0,
                "orphan_keys_count": 0,
            }, indent=2))
            return 0
        repo_root = Path(__file__).resolve().parents[1]
        print(f"SKIP: .ai repository root not found (looked around {repo_root}); skipping cross-repo check in standalone clone")
        return 0

    try:
        digest = audit_parity(ai_root)
    except Exception as exc:
        sys.stderr.write(f"Error during i18n parity audit: {exc}\n")
        return 2

    if args.json:
        print(json.dumps(digest, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("Sensei Ewok CF Lab - data-i18n Translation Parity Audit")
        print("=" * 60)
        print(f"Status:                 {digest['status']}")
        print(f"Routes Scanned:         {digest['routes_scanned']}")
        print(f"Total Attribute Uses:   {digest['total_attribute_uses']}")
        print(f"Unique Keys Scanned:    {digest['unique_keys_scanned']}")
        print(f"Resolved Uses:          {digest['resolved_attribute_uses']}")
        print(f"Missing / Unresolved:   {digest['missing_keys_count']}")
        print(f"Total Catalog Keys:     {digest['total_catalog_keys']}")
        print(f"Referenced Keys:        {digest['referenced_catalog_keys']}")
        print(f"Orphan Keys:            {digest['orphan_keys_count']}")
        print("-" * 60)

        if digest["missing_keys"]:
            print("MISSING / UNRESOLVED TRANSLATION KEYS:")
            for m in digest["missing_keys"]:
                print(f"  [{m['route']}] {m['attribute']}=\"{m['key']}\" -> {m['reason']}")
            print("-" * 60)

        if digest["orphan_keys"]:
            print(f"ORPHAN KEYS DETECTED ({digest['orphan_keys_count']}):")
            for o in digest["orphan_keys"][:10]:
                print(f"  {o['full_key']} (preview: {o['preview']})")
            if len(digest["orphan_keys"]) > 10:
                print(f"  ... and {len(digest['orphan_keys']) - 10} more.")
            print("-" * 60)

    if args.check:
        if digest["missing_keys_count"] > 0:
            return 1
        if args.strict_orphans and digest["orphan_keys_count"] > 0:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

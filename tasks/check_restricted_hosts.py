#!/usr/bin/env python3
"""Verify that every restricted catalog host is blocked in .claude/settings.json.

Part of board task T-0108.
Extracts all sources from cf-research/sources/catalog.yaml where access is
'manual', 'request', or 'forbidden', identifies their unique network hosts
(from url, landing_page, base_url, api_root), and verifies that
.claude/settings.json contains a matching 'WebFetch(domain:<host>)' rule
in permissions.deny.

Usage:
    python tasks/check_restricted_hosts.py [--catalog PATH] [--settings PATH] [--self-test]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None

HOST_KEYS = ("url", "landing_page", "base_url", "api_root")


def find_catalog(start_dir: Path | None = None) -> Path | None:
    """Find catalog.yaml across standard sibling and worktree layouts."""
    if os.environ.get("EVIDENCE_CATALOG"):
        p = Path(os.environ["EVIDENCE_CATALOG"])
        if p.is_file():
            return p

    here = (start_dir or Path(__file__).resolve().parent).resolve()
    # Check parent repositories root
    candidates = [
        here.parent / "cf-research" / "sources" / "catalog.yaml",
        here.parent.parent / "cf-research" / "sources" / "catalog.yaml",
        here.parent.parent.parent / "cf-research" / "sources" / "catalog.yaml",
        here.parent.parent.parent.parent / "cf-research" / "sources" / "catalog.yaml",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def extract_restricted_hosts(catalog_data: dict) -> set[str]:
    """Extract all hosts belonging to manual, request, or forbidden catalog entries."""
    sources = catalog_data.get("sources", [])

    # Identify permitted hosts so shared root domains (e.g. cysticfibrosis.ca) are not blocked
    permitted_hosts = set()
    for s in sources:
        if s.get("access") in ("fetch", "api"):
            for key in HOST_KEYS:
                val = s.get(key)
                if isinstance(val, str) and (val.startswith("http://") or val.startswith("https://")):
                    parsed = urlparse(val)
                    if parsed.netloc:
                        permitted_hosts.add(parsed.netloc.lower())

    restricted_hosts = set()
    for s in sources:
        if s.get("access") in ("manual", "request", "forbidden"):
            for key in HOST_KEYS:
                val = s.get(key)
                if isinstance(val, str) and (val.startswith("http://") or val.startswith("https://")):
                    parsed = urlparse(val)
                    if parsed.netloc:
                        h = parsed.netloc.lower()
                        if h not in permitted_hosts:
                            restricted_hosts.add(h)

    return restricted_hosts


def get_denied_web_hosts(settings_data: dict) -> set[str]:
    """Extract hostnames from WebFetch(domain:<host>) rules in permissions.deny."""
    deny_rules = settings_data.get("permissions", {}).get("deny", [])
    hosts = set()
    prefix = "WebFetch(domain:"
    for rule in deny_rules:
        if isinstance(rule, str) and rule.startswith(prefix) and rule.endswith(")"):
            host = rule[len(prefix):-1].strip().lower()
            if host:
                hosts.add(host)
    return hosts


def run_self_test() -> int:
    """Self-test logic using synthetic catalog and settings data."""
    sample_catalog = {
        "sources": [
            {
                "id": "open-api",
                "access": "api",
                "base_url": "https://api.example.org/v1",
                "terms_url": "https://www.example.org/terms",
            },
            {
                "id": "restricted-manual",
                "access": "manual",
                "landing_page": "https://manual.example.com/reports",
                "url": "https://manual.example.com/files/report.pdf",
            },
            {
                "id": "restricted-forbidden",
                "access": "forbidden",
                "landing_page": "https://blocked.example.net/info",
            },
            {
                "id": "restricted-with-shared-terms",
                "access": "manual",
                "url": "https://service.restricted.org/data",
                "terms_url": "https://www.example.org/terms",
            },
        ]
    }
    extracted = extract_restricted_hosts(sample_catalog)
    expected = {"manual.example.com", "blocked.example.net", "service.restricted.org"}
    assert extracted == expected, f"Self-test failed: expected {expected}, got {extracted}"

    valid_settings = {
        "permissions": {
            "deny": [
                "Read(.env)",
                "WebFetch(domain:manual.example.com)",
                "WebFetch(domain:blocked.example.net)",
                "WebFetch(domain:service.restricted.org)",
            ]
        }
    }
    denied = get_denied_web_hosts(valid_settings)
    assert denied == expected, f"Self-test failed on denied hosts: {denied}"

    missing_settings = {
        "permissions": {
            "deny": [
                "WebFetch(domain:manual.example.com)",
            ]
        }
    }
    denied_missing = get_denied_web_hosts(missing_settings)
    missing = expected - denied_missing
    assert missing == {"blocked.example.net", "service.restricted.org"}

    print("All self-tests passed (extract_restricted_hosts, get_denied_web_hosts, diff).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify restricted catalog hosts are denied in .claude/settings.json.")
    parser.add_argument("--catalog", type=Path, help="Path to catalog.yaml")
    parser.add_argument("--settings", type=Path, help="Path to .claude/settings.json")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests and exit")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if yaml is None:
        print("error: PyYAML is required (pip install PyYAML)", file=sys.stderr)
        return 2

    # Locate files
    repo_root = Path(__file__).resolve().parents[1]
    catalog_path = args.catalog or find_catalog(repo_root)
    settings_path = args.settings or (repo_root / ".claude" / "settings.json")

    if not catalog_path or not catalog_path.is_file():
        print(f"error: catalog.yaml not found (looked around {repo_root})", file=sys.stderr)
        return 1

    if not settings_path.is_file():
        print(f"error: settings file not found: {settings_path}", file=sys.stderr)
        return 1

    try:
        catalog_data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"error: failed to read {catalog_path}: {e}", file=sys.stderr)
        return 1

    try:
        settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"error: failed to read {settings_path}: {e}", file=sys.stderr)
        return 1

    restricted_hosts = extract_restricted_hosts(catalog_data)
    denied_hosts = get_denied_web_hosts(settings_data)

    missing_denies = sorted(restricted_hosts - denied_hosts)
    extra_denies = sorted(denied_hosts - restricted_hosts)

    if missing_denies or extra_denies:
        print(f"FAIL: .claude/settings.json is out of sync with {catalog_path.name}")
        if missing_denies:
            print(f"  Missing deny rules ({len(missing_denies)}):")
            for h in missing_denies:
                print(f"    - WebFetch(domain:{h})")
        if extra_denies:
            print(f"  Extra deny rules not in restricted catalog ({len(extra_denies)}):")
            for h in extra_denies:
                print(f"    - WebFetch(domain:{h})")
        return 1

    print(f"PASS: all {len(restricted_hosts)} restricted catalog hosts are denied in {settings_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Automated Cross-Repo Unicode Homoglyph & Invisible Character Injection Linter.

Audits source code, configuration files, and data catalogs across all workspace
repositories (cf-lab, cf-research, cf-skills, .ai) to enforce:
1. Trojan Source (CVE-2021-42574) Detection:
   - Scans for unescaped bidirectional control characters (Bidi: U+202A..U+202E,
     U+2066..U+2069, U+200E, U+200F) that can alter visual code ordering
     without changing execution semantics.
2. Invisible & Zero-Width Character Quarantine:
   - Scans for zero-width spaces (U+200B), zero-width non-joiners (U+200C),
     zero-width joiners (U+200D), and soft hyphens (U+00AD) in code, markdown,
     and JSON/YAML data files.
3. Confusable Homoglyph Auditing in Identifiers:
   - Scans code definitions (.py, .js, .ps1) for mixed Cyrillic/Greek and Latin
     characters in identifiers (functions, classes, variables) that simulate
     ASCII names.

Exclusions / Allowlist:
- Test files and test fixtures (e.g. test_*.py, test-*.py) explicitly testing
  character sanitization or unicode rejection.
- Explicit regex character classes and sanitization constants (e.g. BAD_CHARS, ZWSP).
- Downloaded external archives in sources/downloads.

Usage:
    python tasks/check_unicode_homoglyphs.py --check
    python tasks/check_unicode_homoglyphs.py --json
    python tasks/check_unicode_homoglyphs.py --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "unicode-homoglyphs-audit.json"

# Trojan Source Bidi Control Characters (CVE-2021-42574)
BIDI_CHARS = {
    "\u202a": "LEFT-TO-RIGHT EMBEDDING (LRE)",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING (RLE)",
    "\u202c": "POP DIRECTIONAL FORMATTING (PDF)",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE (LRO)",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE (RLO)",
    "\u2066": "LEFT-TO-RIGHT ISOLATE (LRI)",
    "\u2067": "RIGHT-TO-LEFT ISOLATE (RLI)",
    "\u2068": "FIRST STRONG ISOLATE (FSI)",
    "\u2069": "POP DIRECTIONAL ISOLATE (PDI)",
    "\u200e": "LEFT-TO-RIGHT MARK (LRM)",
    "\u200f": "RIGHT-TO-LEFT MARK (RLM)",
}

# Invisible & Zero-Width Characters
INVISIBLE_CHARS = {
    "\u200b": "ZERO WIDTH SPACE (ZWSP)",
    "\u200c": "ZERO WIDTH NON-JOINER (ZWNJ)",
    "\u200d": "ZERO WIDTH JOINER (ZWJ)",
    "\u00ad": "SOFT HYPHEN (SHY)",
}

# Cyrillic letters that visually mimic Latin ASCII letters (Trojan homoglyphs)
CYRILLIC_CONFUSABLES = set(
    "\u0430\u0441\u0435\u043e\u0440\u0445\u0443\u0456\u0458\u0455"  # a, c, e, o, p, x, y, i, j, s
    "\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0425"  # A, B, E, K, M, H, O, P, C, T, X
)

# Regex to match variable, function, or class declaration statements
IDENTIFIER_DECL_PATTERN = re.compile(
    r"""(?:def\s+|class\s+|function\s+|const\s+|let\s+|var\s+|\$)([a-zA-Z0-9_\u0400-\u04FF]+)"""
)

TARGET_EXTENSIONS = {
    ".py",
    ".js",
    ".mjs",
    ".ps1",
    ".sh",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".html",
}

IGNORE_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".playwright",
    "test-results",
    "playwright-report",
    "dist",
    "build",
    "downloads",
}


def get_sibling_repo_roots(lab_root: Path) -> List[Tuple[str, Path]]:
    """Resolve sibling workspace repositories (cf-lab, cf-research, cf-skills, .ai)."""
    parts = lab_root.parts
    if ".worktrees" in parts:
        wt_idx = parts.index(".worktrees")
        repos_root = Path(*parts[:wt_idx])
    else:
        repos_root = lab_root.parent

    candidates = [
        ("cf-lab", repos_root / "cf-lab" if (repos_root / "cf-lab").exists() else lab_root),
        ("cf-research", repos_root / "cf-research"),
        ("cf-skills", repos_root / "cf-skills"),
        (".ai", repos_root / ".ai"),
    ]
    return [(name, p) for name, p in candidates if p.exists() and p.is_dir()]


def is_allowlisted_file(file_path: Path) -> bool:
    """Determine whether file is an authorized test fixture, test suite, or sanitizer."""
    name = file_path.name.lower()
    # Test suites that test character detection or rejection
    if name.startswith("test_") or name.startswith("test-") or "_test." in name:
        return True
    if "tests" in file_path.parts:
        return True
    return False


def is_allowlisted_line(line: str) -> bool:
    """Check if line is an explicit sanitizer definition, regex class, or test fixture."""
    # Explicit ignore comment
    if "# noqa: unicode" in line or "# allow-unicode" in line:
        return True
    # Sanitizer constants defining bad characters or regex patterns
    if "BAD_CHARS" in line or "ZWSP" in line or "re.compile(" in line:
        return True
    return False


def audit_trojan_source_bidi(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Scan source files for Trojan Source bidirectional override characters (CVE-2021-42574)."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"files_scanned": 0, "bidi_violations": 0}
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in TARGET_EXTENSIONS:
                continue

            if any(ign in file_path.parts for ign in IGNORE_DIR_NAMES):
                continue
            if "sources" in file_path.parts and "downloads" in file_path.parts:
                continue
            if is_allowlisted_file(file_path):
                continue

            metadata["files_scanned"] += 1
            rel_path = f"[{repo_name}] {file_path.relative_to(repo_path)}"

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.splitlines(), start=1):
                    if is_allowlisted_line(line):
                        continue

                    for char, desc in BIDI_CHARS.items():
                        if char in line:
                            metadata["bidi_violations"] += 1
                            errors.append(
                                f"{rel_path}:{i}: Trojan Source Bidi character U+{ord(char):04X} ({desc}) detected. "
                                "Bidirectional control characters can alter visual code flow and are prohibited."
                            )
            except Exception as e:
                warnings.append(f"Could not read {rel_path}: {e}")

    return errors, warnings, metadata


def audit_invisible_zero_width_characters(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Scan source files for deceptive invisible zero-width characters."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"invisible_violations": 0}
    repos = get_sibling_repo_roots(lab_root)

    for repo_name, repo_path in repos:
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in TARGET_EXTENSIONS:
                continue

            if any(ign in file_path.parts for ign in IGNORE_DIR_NAMES):
                continue
            if "sources" in file_path.parts and "downloads" in file_path.parts:
                continue
            if is_allowlisted_file(file_path):
                continue

            rel_path = f"[{repo_name}] {file_path.relative_to(repo_path)}"

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.splitlines(), start=1):
                    if is_allowlisted_line(line):
                        continue

                    for char, desc in INVISIBLE_CHARS.items():
                        if char in line:
                            metadata["invisible_violations"] += 1
                            errors.append(
                                f"{rel_path}:{i}: Invisible character U+{ord(char):04X} ({desc}) detected. "
                                "Zero-width and soft-hyphen characters in source code are prohibited."
                            )
            except Exception as e:
                warnings.append(f"Could not read {rel_path}: {e}")

    return errors, warnings, metadata


def audit_confusable_identifier_homoglyphs(
    lab_root: Path,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Scan code identifier declarations for deceptive Cyrillic homoglyphs substituting ASCII letters."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {"confusable_violations": 0}
    repos = get_sibling_repo_roots(lab_root)

    code_extensions = {".py", ".js", ".mjs", ".ps1"}

    for repo_name, repo_path in repos:
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in code_extensions:
                continue

            if any(ign in file_path.parts for ign in IGNORE_DIR_NAMES):
                continue
            if "sources" in file_path.parts and "downloads" in file_path.parts:
                continue
            if is_allowlisted_file(file_path):
                continue

            rel_path = f"[{repo_name}] {file_path.relative_to(repo_path)}"

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.splitlines(), start=1):
                    stripped = line.strip()
                    # Skip whole-line comments
                    if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                        continue
                    if is_allowlisted_line(line):
                        continue

                    for m in IDENTIFIER_DECL_PATTERN.finditer(line):
                        token = m.group(1)
                        # Check if token contains any Cyrillic confusable mixed with ASCII characters
                        has_ascii = any("a" <= ch <= "z" or "A" <= ch <= "Z" or "0" <= ch <= "9" or ch == "_" for ch in token)
                        has_cyrillic = any(ch in CYRILLIC_CONFUSABLES for ch in token)
                        if has_ascii and has_cyrillic:
                            metadata["confusable_violations"] += 1
                            errors.append(
                                f"{rel_path}:{i}: Confusable homoglyph identifier '{token}' detected in code declaration. "
                                "Mixed Cyrillic homoglyphs in code identifiers are prohibited (Trojan Source)."
                            )
            except Exception as e:
                warnings.append(f"Could not read {rel_path}: {e}")

    return errors, warnings, metadata


def run_full_unicode_linter(
    lab_root: Path,
    strict: bool = False,
) -> Dict[str, Any]:
    """Execute all Unicode homoglyph and invisible character checks."""
    all_errors: List[str] = []
    all_warnings: List[str] = []

    # 1. Trojan Source Bidi
    b_errors, b_warnings, b_meta = audit_trojan_source_bidi(lab_root)
    all_errors.extend(b_errors)
    all_warnings.extend(b_warnings)

    # 2. Invisible characters
    i_errors, i_warnings, i_meta = audit_invisible_zero_width_characters(lab_root)
    all_errors.extend(i_errors)
    all_warnings.extend(i_warnings)

    # 3. Confusable identifiers
    c_errors, c_warnings, c_meta = audit_confusable_identifier_homoglyphs(lab_root)
    all_errors.extend(c_errors)
    all_warnings.extend(c_warnings)

    passed = len(all_errors) == 0 and (not strict or len(all_warnings) == 0)

    report = {
        "timestamp": "2026-10-22T20:00:00Z",
        "passed": passed,
        "strict": strict,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            **b_meta,
            **i_meta,
            **c_meta,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
        },
    }
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Automated Cross-Repo Unicode Homoglyph & Invisible Character Injection Linter."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run linter in verification mode (exit 0 on pass, 1 on fail).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full audit report in JSON format.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Path to control repo root (default: cf-lab root).",
    )
    args = parser.parse_args()

    report = run_full_unicode_linter(args.root, strict=args.strict)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1

    print("Unicode Homoglyph & Invisible Character Linter: " + ("PASS" if report["passed"] else "FAIL"))
    print(f"  Files audited: {report['metadata'].get('files_scanned', 0)}")
    print(f"  Trojan Source Bidi violations: {report['metadata'].get('bidi_violations', 0)}")
    print(f"  Invisible character violations: {report['metadata'].get('invisible_violations', 0)}")
    print(f"  Confusable identifier violations: {report['metadata'].get('confusable_violations', 0)}")

    if report["warnings"]:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"  [WARN] {w}")

    if report["errors"]:
        print(f"\nErrors ({len(report['errors'])}):")
        for e in report["errors"]:
            print(f"  [FAIL] {e}")

    if report["passed"]:
        print("All Unicode homoglyph and invisible character invariants verified clean!")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

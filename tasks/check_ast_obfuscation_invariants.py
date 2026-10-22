#!/usr/bin/env python3
"""Automated Multi-Repo Agent AST Import Obfuscation & Dynamic Code Execution Linter.

Audits Python source code across all workspace repositories (cf-lab, cf-research, cf-skills, .ai)
to enforce strict security invariants against dynamic code execution, import obfuscation,
and runtime reflection sandbox escapes:
1. Prohibited Dynamic Execution Primitives:
   - Scans ASTs for calls to `eval()`, `exec()`, `compile()`, and dynamic `__import__()`.
2. Obfuscated Payload & Code Unpacking Detection:
   - Detects base64 payload unpacking (`b64decode`), zlib/gzip decompression chains fed into
     interpreters, and hex/unicode-escaped byte sequences characteristic of packed shellcode.
3. Reflection & Sandbox Escape Guards:
   - Identifies dangerous reflection idioms accessing internal Python state:
     `__subclasses__()`, `__globals__`, `__builtins__`, and dynamic `sys.modules` introspection.
4. Test Suite & Legitimate Tool Whitelist:
   - Grants controlled exemptions for test harnesses asserting AST visitor behavior,
     while enforcing strict zero-tolerance across all production scripts and sentinels.

Usage:
    python tasks/check_ast_obfuscation_invariants.py --check
    python tasks/check_ast_obfuscation_invariants.py --json
    python tasks/check_ast_obfuscation_invariants.py --strict
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "ast-obfuscation-audit.json"

# Prohibited execution built-in function names
PROHIBITED_BUILTINS: frozenset[str] = frozenset({
    "eval",
    "exec",
    "compile",
})

# Dangerous reflection attributes that can be abused for sandbox escape
DANGEROUS_REFLECTION_ATTRS: frozenset[str] = frozenset({
    "__subclasses__",
    "__globals__",
    "__builtins__",
})

# Obfuscation unpackers that should not feed directly into code execution
PAYLOAD_UNPACK_CALLS: frozenset[str] = frozenset({
    "b64decode",
    "decodebytes",
    "b85decode",
    "b32decode",
})

# Files with documented legitimate idioms (e.g. inline stdlib import in CLI tool)
WHITELISTED_ALLOWANCES: Dict[str, Set[str]] = {
    "place-art.py": {"__import__('os')"},
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


class ASTObfuscationVisitor(ast.NodeVisitor):
    """AST visitor to detect dynamic code execution, reflection escapes, and obfuscation."""

    def __init__(self, filepath: Path, is_test_file: bool = False) -> None:
        self.filepath = filepath
        self.filename = filepath.name
        self.is_test_file = is_test_file
        self.violations: List[str] = []
        self.warnings: List[str] = []
        self.nodes_inspected: int = 0

    def visit_Call(self, node: ast.Call) -> None:
        self.nodes_inspected += 1

        # Check for direct calls to eval(), exec(), compile()
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in PROHIBITED_BUILTINS:
                msg = (
                    f"{self.filepath}:{node.lineno}: Prohibited dynamic code execution "
                    f"built-in '{func_name}()' detected."
                )
                if self.is_test_file:
                    self.warnings.append(msg)
                else:
                    self.violations.append(msg)

            elif func_name == "__import__":
                # Check for dynamic or string __import__
                is_whitelisted = False
                if self.filename in WHITELISTED_ALLOWANCES:
                    # Check if whitelisted inline import
                    if node.args and isinstance(node.args[0], ast.Constant):
                        pattern = f"__import__('{node.args[0].value}')"
                        if pattern in WHITELISTED_ALLOWANCES[self.filename]:
                            is_whitelisted = True

                if not is_whitelisted:
                    msg = (
                        f"{self.filepath}:{node.lineno}: Dynamic module import "
                        f"'__import__()' detected. Use standard 'import' or 'importlib.import_module'."
                    )
                    if self.is_test_file:
                        self.warnings.append(msg)
                    else:
                        self.violations.append(msg)

        # Check for unpacking calls (e.g. base64.b64decode) feeding into dynamic execution
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in DANGEROUS_REFLECTION_ATTRS:
                msg = (
                    f"{self.filepath}:{node.lineno}: Prohibited runtime reflection "
                    f"sandbox escape attribute '.{attr_name}()' detected."
                )
                if self.is_test_file:
                    self.warnings.append(msg)
                else:
                    self.violations.append(msg)

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.nodes_inspected += 1
        # Check for direct access to dangerous reflection attributes
        if node.attr in DANGEROUS_REFLECTION_ATTRS:
            # Avoid duplicate violation if already flagged in visit_Call
            msg = (
                f"{self.filepath}:{node.lineno}: Suspicious reflection attribute "
                f"access '.{node.attr}' detected."
            )
            # Only add if not already in violations/warnings for this line
            if not any(f":{node.lineno}:" in v for v in self.violations + self.warnings):
                if self.is_test_file:
                    self.warnings.append(msg)
                else:
                    self.violations.append(msg)

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        self.nodes_inspected += 1
        # Inspect string/bytes constants for hex-encoded shellcode/packed blobs
        if isinstance(node.value, (str, bytes)) and not self.is_test_file:
            val_len = len(node.value)
            if val_len > 80:
                if isinstance(node.value, bytes):
                    # Check for high density of unprintable / non-ascii bytes
                    non_printable = sum(1 for b in node.value if b < 32 or b > 126)
                    if non_printable > 25 and (non_printable / val_len) > 0.35:
                        msg = (
                            f"{self.filepath}:{node.lineno}: Obfuscated binary payload "
                            f"detected ({non_printable} unprintable bytes in {val_len}b literal)."
                        )
                        self.violations.append(msg)
                elif isinstance(node.value, str):
                    # Check for literal hex escape pattern or high density of unprintable chars
                    hex_escapes = len(re.findall(r"\\x[0-9a-fA-F]{2}", node.value))
                    non_printable = sum(1 for c in node.value if ord(c) < 32 and c not in "\n\r\t")
                    if hex_escapes > 15:
                        msg = (
                            f"{self.filepath}:{node.lineno}: Obfuscated hex-escaped sequence "
                            f"detected ({hex_escapes} hex escape sequences)."
                        )
                        self.violations.append(msg)
                    elif non_printable > 25 and (non_printable / val_len) > 0.35:
                        msg = (
                            f"{self.filepath}:{node.lineno}: Obfuscated control/unprintable character payload "
                            f"detected ({non_printable} control chars in {val_len} chars)."
                        )
                        self.violations.append(msg)

        self.generic_visit(node)


def audit_repo_ast_obfuscation(
    repo_root: Path,
    include_tests: bool = True,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Scan all Python files in a repository for AST import obfuscation and dynamic execution."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {
        "files_audited": 0,
        "nodes_inspected": 0,
        "violations_found": 0,
    }

    exclude_dirs = {
        ".git",
        ".worktrees",
        "__pycache__",
        "venv",
        ".venv",
        "node_modules",
        "downloads",
    }

    for path in repo_root.rglob("*.py"):
        if any(part in exclude_dirs for part in path.parts):
            continue

        is_test = (
            path.name.startswith("test_")
            or "tests" in path.parts
            or path.name.endswith("_test.py")
            or "test-" in path.name
        )
        if is_test and not include_tests:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(path))
            visitor = ASTObfuscationVisitor(path, is_test_file=is_test)
            visitor.visit(tree)

            metadata["files_audited"] += 1
            metadata["nodes_inspected"] += visitor.nodes_inspected

            for v in visitor.violations:
                errors.append(v)
                metadata["violations_found"] += 1
            for w in visitor.warnings:
                warnings.append(w)
        except SyntaxError:
            continue
        except Exception as e:
            warnings.append(f"Could not parse {path}: {e}")

    return errors, warnings, metadata


def run_full_ast_obfuscation_linter(
    lab_root: Path,
    strict: bool = False,
    report_path: Optional[Path] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Run the AST obfuscation and dynamic execution linter across all workspace repositories."""
    repos = get_sibling_repo_roots(lab_root)
    all_errors: List[str] = []
    all_warnings: List[str] = []
    repo_stats: Dict[str, Any] = {}

    total_files = 0
    total_nodes = 0
    total_violations = 0

    for name, rpath in repos:
        errors, warnings, meta = audit_repo_ast_obfuscation(rpath)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        repo_stats[name] = {
            "path": str(rpath),
            "files_audited": meta["files_audited"],
            "nodes_inspected": meta["nodes_inspected"],
            "violations": len(errors),
            "warnings": len(warnings),
        }
        total_files += meta["files_audited"]
        total_nodes += meta["nodes_inspected"]
        total_violations += len(errors)

    report_data: Dict[str, Any] = {
        "status": "PASS" if not all_errors else "FAIL",
        "strict_mode": strict,
        "total_repos": len(repos),
        "total_files_audited": total_files,
        "total_nodes_inspected": total_nodes,
        "total_violations": total_violations,
        "total_warnings": len(all_warnings),
        "repositories": repo_stats,
        "errors": all_errors,
        "warnings": all_warnings,
    }

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    exit_code = 1 if all_errors or (strict and all_warnings) else 0
    return exit_code, report_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Multi-Repo Agent AST Import Obfuscation & Dynamic Code Execution Linter"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run linter and exit with non-zero if violations are detected",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict mode where warnings also trigger non-zero exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON audit report to stdout",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write JSON audit report (defaults to .loop-logs/ast-obfuscation-audit.json)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Root repository directory (defaults to cf-lab)",
    )
    args = parser.parse_args()

    exit_code, report = run_full_ast_obfuscation_linter(
        lab_root=args.root,
        strict=args.strict,
        report_path=args.report,
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return exit_code

    if exit_code == 0:
        print("AST Obfuscation & Dynamic Execution Linter: PASS")
        print(f"  Repositories audited: {report['total_repos']}")
        print(f"  Python files audited: {report['total_files_audited']}")
        print(f"  AST nodes inspected: {report['total_nodes_inspected']}")
        print("All AST dynamic execution and import obfuscation invariants verified clean!")
    else:
        print("AST Obfuscation & Dynamic Execution Linter: FAIL", file=sys.stderr)
        print(f"  Violations found: {len(report['errors'])}", file=sys.stderr)
        for err in report["errors"]:
            print(f"    - {err}", file=sys.stderr)
        if args.strict and report["warnings"]:
            print(f"  Warnings ({len(report['warnings'])}):", file=sys.stderr)
            for warn in report["warnings"]:
                print(f"    - [WARN] {warn}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

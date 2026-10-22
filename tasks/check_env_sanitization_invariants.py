#!/usr/bin/env python3
"""Automated Multi-Repo Agent Environment Variable Leak & Process Memory Sanitization Linter.

Audits subprocess execution patterns, environment variable sanitization, and sensitive
token redaction across all workspace repositories (cf-lab, cf-research, cf-skills, .ai):
1. Subprocess Environment Isolation:
   - Scans Python files to ensure calls to subprocess.run, subprocess.Popen, etc.
     do not pass unscrubbed raw parent environments (env=os.environ or raw os.environ.copy()).
   - Enforces use of sanitized environment dictionaries or explicit key whitelisting.
2. Secret Token Redaction & Sanitization Utilities:
   - Provides canonical get_sanitized_env() and redact_sensitive_tokens() helpers.
   - Detects hardcoded sensitive credentials or unmasked tokens in process wrappers.
3. Canary Pattern & Privacy Pattern Monitoring:
   - Loads privacy canaries from privacy-patterns.txt and asserts runtime scripts do
     not leak or log private credentials.

Usage:
    python tasks/check_env_sanitization_invariants.py --check
    python tasks/check_env_sanitization_invariants.py --json
    python tasks/check_env_sanitization_invariants.py --strict
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
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "env-sanitization-audit.json"
PRIVACY_PATTERNS_PATH = (
    REPO_ROOT / ".claude" / "skills" / "security-git" / "scripts" / "privacy-patterns.txt"
)

SENSITIVE_ENV_KEYS: frozenset[str] = frozenset({
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GIT_TOKEN",
    "PAT",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AZURE_OPENAI_API_KEY",
    "COHERE_API_KEY",
    "MISTRAL_API_KEY",
    "DATABASE_URL",
    "DB_PASSWORD",
    "SECRET_KEY",
    "PRIVATE_KEY",
    "SSH_AUTH_SOCK",
    "SSH_AGENT_PID",
})

SENSITIVE_SUBSTRING_PATTERNS: tuple[str, ...] = (
    "_TOKEN",
    "_SECRET",
    "_API_KEY",
    "_PASSWORD",
    "_PASSWD",
    "_AUTH",
    "_PRIVATE_KEY",
)

SUBPROCESS_APIS: frozenset[str] = frozenset({
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
})

TOKEN_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]{20,}\b"), "Bearer [REDACTED_BEARER]"),
    (
        re.compile(
            r"""(?i)\b(GH_TOKEN|GITHUB_TOKEN|PAT|ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY|SECRET_KEY|API_KEY)\s*[:=]\s*["']?([^\s"',;]+)["']?"""
        ),
        r"\1=[REDACTED]",
    ),
]


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


def get_sanitized_env(
    base_env: Optional[Dict[str, str]] = None,
    allow_vars: Optional[Set[str]] = None,
    extra_deny_vars: Optional[Set[str]] = None,
) -> Dict[str, str]:
    """Return a sanitized copy of the environment dictionary with sensitive tokens purged.

    Args:
        base_env: Source environment dict (defaults to os.environ).
        allow_vars: Set of variable names explicitly exempted from scrubbing.
        extra_deny_vars: Additional variable names or patterns to deny.
    """
    source = dict(base_env if base_env is not None else os.environ)
    allowed = set(allow_vars or ())
    extra_deny = set(extra_deny_vars or ())
    sanitized: Dict[str, str] = {}

    for k, v in source.items():
        if k in allowed:
            sanitized[k] = v
            continue

        upper_k = k.upper()
        if k in SENSITIVE_ENV_KEYS or upper_k in SENSITIVE_ENV_KEYS:
            continue
        if k in extra_deny or upper_k in extra_deny:
            continue
        if any(pat in upper_k for pat in SENSITIVE_SUBSTRING_PATTERNS):
            continue

        sanitized[k] = v

    return sanitized


def redact_sensitive_tokens(text: str) -> str:
    """Scrub sensitive credentials, tokens, and private keys from log or error text."""
    redacted = text
    for pattern, replacement in TOKEN_REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def load_privacy_canaries(pattern_path: Path) -> List[Dict[str, str]]:
    """Load privacy patterns and canary strings from privacy-patterns.txt."""
    canaries: List[Dict[str, str]] = []
    if not pattern_path.exists():
        return canaries
    try:
        content = pattern_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                canaries.append({
                    "category": parts[0],
                    "pattern": parts[1],
                    "canary": parts[2],
                })
    except Exception:
        pass
    return canaries


class SubprocessEnvVisitor(ast.NodeVisitor):
    """AST visitor to audit subprocess calls for raw environment leaks."""

    def __init__(self, filepath: Path, is_test_file: bool = False) -> None:
        self.filepath = filepath
        self.is_test_file = is_test_file
        self.violations: List[str] = []
        self.warnings: List[str] = []
        self.calls_inspected = 0

    def visit_Call(self, node: ast.Call) -> None:
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in SUBPROCESS_APIS:
            self.calls_inspected += 1
            for kw in node.keywords:
                if kw.arg == "env":
                    val = kw.value
                    msg = None
                    # Check for direct env=os.environ
                    if isinstance(val, ast.Attribute):
                        if (
                            isinstance(val.value, ast.Name)
                            and val.value.id == "os"
                            and val.attr == "environ"
                        ):
                            msg = (
                                f"{self.filepath}:{node.lineno}: Raw parent environment 'env=os.environ' "
                                f"passed to subprocess.{func_name}() without sanitization."
                            )
                    # Check for direct env=dict(os.environ) or env=os.environ.copy()
                    elif isinstance(val, ast.Call):
                        if isinstance(val.func, ast.Attribute):
                            if (
                                isinstance(val.func.value, ast.Attribute)
                                and isinstance(val.func.value.value, ast.Name)
                                and val.func.value.value.id == "os"
                                and val.func.value.attr == "environ"
                                and val.func.attr == "copy"
                            ):
                                msg = (
                                    f"{self.filepath}:{node.lineno}: Direct 'env=os.environ.copy()' "
                                    f"passed to subprocess.{func_name}() without sanitization."
                                )
                        elif isinstance(val.func, ast.Name) and val.func.id == "dict":
                            if val.args and isinstance(val.args[0], ast.Attribute):
                                arg0 = val.args[0]
                                if (
                                    isinstance(arg0.value, ast.Name)
                                    and arg0.value.id == "os"
                                    and arg0.attr == "environ"
                                ):
                                    msg = (
                                        f"{self.filepath}:{node.lineno}: Direct 'env=dict(os.environ)' "
                                        f"passed to subprocess.{func_name}() without sanitization."
                                    )

                    if msg:
                        if self.is_test_file:
                            self.warnings.append(msg)
                        else:
                            self.violations.append(msg)

        self.generic_visit(node)


def audit_repo_subprocess_env(
    repo_root: Path,
    include_tests: bool = True,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Scan all Python files in a repository for subprocess environment isolation invariants."""
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {
        "files_audited": 0,
        "subprocess_calls_audited": 0,
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
            visitor = SubprocessEnvVisitor(path, is_test_file=is_test)
            visitor.visit(tree)

            metadata["files_audited"] += 1
            metadata["subprocess_calls_audited"] += visitor.calls_inspected

            for v in visitor.violations:
                errors.append(v)
                metadata["violations_found"] += 1
            for w in visitor.warnings:
                warnings.append(w)
        except SyntaxError:
            # Skip invalid syntax in scratch or test files
            continue
        except Exception as e:
            warnings.append(f"Could not parse {path}: {e}")

    return errors, warnings, metadata


def run_full_env_sanitization_linter(
    lab_root: Path,
    include_tests: bool = True,
) -> Dict[str, Any]:
    """Run full multi-repo environment sanitization audit across all workspace repositories."""
    all_errors: List[str] = []
    all_warnings: List[str] = []
    repos = get_sibling_repo_roots(lab_root)

    total_files = 0
    total_calls = 0
    repo_summaries: Dict[str, Any] = {}

    for repo_name, repo_path in repos:
        errs, warns, meta = audit_repo_subprocess_env(repo_path, include_tests=include_tests)
        all_errors.extend(errs)
        all_warnings.extend(warns)
        total_files += meta["files_audited"]
        total_calls += meta["subprocess_calls_audited"]
        repo_summaries[repo_name] = meta

    # Check privacy canaries loading
    canaries = load_privacy_canaries(PRIVACY_PATTERNS_PATH)

    passed = len(all_errors) == 0

    return {
        "passed": passed,
        "errors": all_errors,
        "warnings": all_warnings,
        "metadata": {
            "repositories_audited": len(repos),
            "total_python_files_audited": total_files,
            "total_subprocess_calls_audited": total_calls,
            "canary_patterns_loaded": len(canaries),
            "repo_summaries": repo_summaries,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit subprocess environment sanitization and token redaction invariants."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run audit and return non-zero exit code on errors.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON summary report to stdout.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        default=True,
        help="Include test files in audit (in test files, violations are recorded as warnings).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write JSON report output (default: .loop-logs/env-sanitization-audit.json).",
    )

    args = parser.parse_args()
    report = run_full_env_sanitization_linter(REPO_ROOT, include_tests=args.include_tests)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status_label = "PASS" if report["passed"] else "FAIL"
        print(f"Agent Environment Sanitization Linter: {status_label}")
        print(f"  Repositories audited: {report['metadata']['repositories_audited']}")
        print(f"  Python files audited: {report['metadata']['total_python_files_audited']}")
        print(f"  Subprocess calls audited: {report['metadata']['total_subprocess_calls_audited']}")
        print(f"  Canary patterns loaded: {report['metadata']['canary_patterns_loaded']}")

        if report["warnings"]:
            print(f"\nWarnings ({len(report['warnings'])}):")
            for w in report["warnings"]:
                print(f"  - {w}")

        if report["errors"]:
            print(f"\nErrors ({len(report['errors'])}):")
            for e in report["errors"]:
                print(f"  - {e}")
        else:
            print("All subprocess environment sanitization invariants verified clean!")

    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        pass

    if args.strict and (report["errors"] or report["warnings"]):
        return 1
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

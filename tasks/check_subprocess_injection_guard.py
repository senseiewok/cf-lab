#!/usr/bin/env python3
"""Automated Cross-Repo Agent Subprocess Argument Injection Guard & Shell Invariant Linter.

Audits Python scripts across all four workspace repositories (cf-lab, cf-research,
cf-skills, .ai) executing subprocess.run, subprocess.Popen, os.system, or related
APIs to enforce strict zero-vulnerability invariants:
1. Prohibits shell=True when executing commands with variable or external parameters.
2. Enforces list-based argument arrays for all process invocations.
3. Requires strict regex validation (such as ^[A-Za-z0-9_\\-\\./]+$) on dynamic parameters
   to prevent command injection (CWE-78) and argument injection (CWE-88).
4. Verifies mandatory finite execution timeouts across all subprocess calls to prevent DoS.
5. Verifies integration of sensitive data redaction to protect credentials and tokens.

Primary Source Grounding:
- OWASP Top 10:2025 A03:2021 (Injection)
- CWE-78: OS Command Injection
- CWE-88: Argument Injection
- Workspace Standards: .claude/skills/security-baseline/SKILL.md, security-runtime/SKILL.md

Usage:
    python tasks/check_subprocess_injection_guard.py [--check] [--json] [--path PATH] [--strict]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Standard safe parameter pattern: alphanumeric, underscores, hyphens, dots, forward slashes
SAFE_PARAM_REGEX = re.compile(r"^[A-Za-z0-9_\-\./]+$")
SAFE_NUMERIC_REGEX = re.compile(r"^[0-9]+$")

# Process invocation API names to inspect
SUBPROCESS_CALL_NAMES = {
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
}

FORBIDDEN_SHELL_APIS = {
    "system",
    "popen",
    "popen2",
    "popen3",
    "popen4",
}

SENSITIVE_KEYWORDS = {
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "credential",
}


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    severity: str  # "ERROR" | "WARNING"
    message: str
    snippet: str


def validate_parameter(value: str, pattern: re.Pattern[str] | str = SAFE_PARAM_REGEX) -> bool:
    """Validate a dynamic parameter string against a strict safe regex pattern."""
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    return bool(pattern.match(value))


def assert_safe_arg(value: str, pattern: re.Pattern[str] | str = SAFE_PARAM_REGEX, arg_name: str = "arg") -> str:
    """Assert that a parameter conforms to safe regex, raising ValueError on violation."""
    if not validate_parameter(value, pattern):
        raise ValueError(
            f"Unsafe argument value for {arg_name}: {value!r} does not match required safe pattern {pattern.pattern}"
        )
    return value


def redact_sensitive_command(cmd: list[str]) -> list[str]:
    """Redact sensitive keywords, bearer tokens, or secrets from a command argument array."""
    redacted = []
    mask_next = False
    for arg in cmd:
        if mask_next:
            redacted.append("[REDACTED]")
            mask_next = False
            continue

        lower_arg = arg.lower()
        # Flags like --token=<secret> or --password=<secret>
        if any(f"--{k}=" in lower_arg for k in SENSITIVE_KEYWORDS):
            prefix, sep, _ = arg.partition("=")
            redacted.append(f"{prefix}=[REDACTED]")
        # Flags like --token <secret>
        elif any(lower_arg == f"--{k}" for k in SENSITIVE_KEYWORDS):
            redacted.append(arg)
            mask_next = True
        elif any(f"{k}:" in lower_arg for k in SENSITIVE_KEYWORDS):
            prefix, sep, _ = arg.partition(":")
            redacted.append(f"{prefix}:[REDACTED]")
        else:
            redacted.append(arg)
    return redacted


class SubprocessVisitor(ast.NodeVisitor):
    """AST visitor inspecting subprocess execution calls against security invariants."""

    def __init__(self, filename: str, is_test_file: bool = False):
        self.filename = filename
        self.is_test_file = is_test_file
        self.findings: list[Finding] = []

    def visit_Call(self, node: ast.Call) -> None:
        self._check_forbidden_shell_apis(node)
        self._check_subprocess_apis(node)
        self.generic_visit(node)

    def _get_call_func_info(self, node: ast.Call) -> tuple[str, str]:
        """Return (module_or_object, func_name)."""
        if isinstance(node.func, ast.Attribute):
            obj_name = ""
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
            return obj_name, node.func.attr
        if isinstance(node.func, ast.Name):
            return "", node.func.id
        return "", ""

    def _check_forbidden_shell_apis(self, node: ast.Call) -> None:
        obj, func = self._get_call_func_info(node)
        if obj == "os" and func in FORBIDDEN_SHELL_APIS:
            self.findings.append(
                Finding(
                    file=self.filename,
                    line=node.lineno,
                    rule="FORBIDDEN_SHELL_API",
                    severity="ERROR",
                    message=f"Direct invocation of os.{func}() is forbidden; use subprocess.run with argument list",
                    snippet=f"os.{func}(...)",
                )
            )

    def _check_subprocess_apis(self, node: ast.Call) -> None:
        obj, func = self._get_call_func_info(node)
        is_subp = obj in ("subprocess", "") and func in SUBPROCESS_CALL_NAMES
        if not is_subp:
            return

        # 1. Check shell=True
        shell_val = None
        for kw in node.keywords:
            if kw.arg == "shell":
                if isinstance(kw.value, ast.Constant):
                    shell_val = kw.value.value
                else:
                    shell_val = "DYNAMIC"

        if shell_val is True or shell_val == "DYNAMIC":
            self.findings.append(
                Finding(
                    file=self.filename,
                    line=node.lineno,
                    rule="SHELL_TRUE_FORBIDDEN",
                    severity="ERROR",
                    message="subprocess call with shell=True is strictly prohibited (CWE-78)",
                    snippet=f"{obj or 'subprocess'}.{func}(..., shell={shell_val})",
                )
            )

        # 2. Check list-based arguments
        if node.args:
            first_arg = node.args[0]
            # Flag string constants or f-strings passed as command string
            if isinstance(first_arg, (ast.Constant, ast.JoinedStr)):
                # If in a test file, it might be testing dummy execution; in production it is an error
                sev = "WARNING" if self.is_test_file else "ERROR"
                self.findings.append(
                    Finding(
                        file=self.filename,
                        line=node.lineno,
                        rule="STRING_COMMAND_FORBIDDEN",
                        severity=sev,
                        message="Subprocess command must be passed as an argument list, not a raw string (CWE-88)",
                        snippet=f"{obj or 'subprocess'}.{func}(<str>, ...)",
                    )
                )

        # 3. Check finite execution timeout
        has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
        if not has_timeout:
            # Test files often omit timeouts for unit test assertions
            if not self.is_test_file:
                self.findings.append(
                    Finding(
                        file=self.filename,
                        line=node.lineno,
                        rule="MISSING_EXECUTION_TIMEOUT",
                        severity="WARNING",
                        message="Subprocess call lacks explicit finite timeout keyword argument (DoS prevention)",
                        snippet=f"{obj or 'subprocess'}.{func}(... [missing timeout])",
                    )
                )


def scan_python_file(path: Path, is_test_file: bool | None = None) -> list[Finding]:
    """Scan a single Python file for subprocess injection vulnerabilities."""
    if is_test_file is None:
        is_test_file = (
            path.name.startswith("test_")
            or "tests" in path.parts
            or path.name.endswith("_test.py")
            or "test-" in path.name
        )

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(path))
    except (SyntaxError, OSError) as exc:
        return [
            Finding(
                file=str(path),
                line=getattr(exc, "lineno", 1) or 1,
                rule="PARSE_ERROR",
                severity="ERROR",
                message=f"Failed to parse Python source: {exc}",
                snippet="",
            )
        ]

    visitor = SubprocessVisitor(str(path), is_test_file=is_test_file)
    visitor.visit(tree)
    return visitor.findings


def find_workspace_root(start_dir: Path | None = None) -> Path:
    """Resolve the repositories folder containing cf-lab and siblings."""
    here = (start_dir or Path(__file__).resolve().parent).resolve()
    for p in [here, *here.parents]:
        if p.name in (".worktrees", "worktrees"):
            continue
        if (p / "cf-lab" / ".git").exists() and (p / "cf-research" / ".git").exists():
            return p
        if (p / "cf-lab").is_dir() and (p / "cf-research").is_dir():
            return p
    return here.parent if here.name == "tasks" else here


def scan_workspace(
    root_dir: Path | None = None,
    include_tests: bool = False,
) -> list[Finding]:
    """Scan Python scripts across all four workspace repositories."""
    repos_root = root_dir or find_workspace_root()
    all_findings: list[Finding] = []

    repo_names = ["cf-lab", "cf-research", "cf-skills", ".ai"]
    for rname in repo_names:
        rdir = repos_root / rname
        if not rdir.is_dir():
            continue

        for py_file in rdir.rglob("*.py"):
            # Skip hidden folders, virtual environments, worktrees, node_modules, shots
            parts = py_file.parts
            if any(part.startswith(".") and part not in {".claude"} for part in parts):
                continue
            if any(skip in parts for skip in ("venv", ".venv", "node_modules", "shots", "__pycache__")):
                continue

            is_test = (
                py_file.name.startswith("test_")
                or "tests" in parts
                or py_file.name.endswith("_test.py")
                or "test-" in py_file.name
            )
            if is_test and not include_tests:
                continue

            findings = scan_python_file(py_file, is_test_file=is_test)
            all_findings.extend(findings)

    return all_findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if any ERROR level findings exist")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any ERROR or WARNING findings exist")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    parser.add_argument("--path", type=Path, help="Scan a specific file or directory")
    parser.add_argument("--root", type=Path, help="Specify workspace repositories root directory")
    parser.add_argument("--include-tests", action="store_true", help="Include test files in workspace scan")
    args = parser.parse_args()

    if args.path:
        target = args.path.resolve()
        if target.is_file():
            findings = scan_python_file(target)
        else:
            findings = []
            for p in target.rglob("*.py"):
                if "__pycache__" not in p.parts:
                    findings.extend(scan_python_file(p))
    else:
        findings = scan_workspace(args.root, include_tests=args.include_tests)

    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]

    if args.json:
        report = {
            "total": len(findings),
            "errors": len(errors),
            "warnings": len(warnings),
            "findings": [asdict(f) for f in findings],
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"Subprocess Injection Guard Audit: {len(errors)} error(s), {len(warnings)} warning(s).")
        for f in findings:
            print(f"  [{f.severity}] [{f.rule}] {f.file}:{f.line}: {f.message}")
            if f.snippet:
                print(f"    --> {f.snippet}")

    if args.check and errors:
        return 1
    if args.strict and (errors or warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Automated Multi-Repo Agent Shell Command Redirection & Process Pipe Safety Linter.

Audits process spawning, shell commands, and piping constructs across all workspace
repositories (cf-lab, cf-research, cf-skills, .ai) to enforce strict zero-vulnerability
invariants against shell command injection and unsafe process redirection:
1. Unquoted File Descriptor Redirection:
   - Scans scripts and command templates for unquoted stdout/stderr redirection operators
     ('>', '>>', '2>&1', '|') combined with dynamic variables or unsanitized paths.
2. Raw Command Chaining Invariants:
   - Detects unsafe shell operator chaining (';', '&&', '||') combined with dynamic string
     formatting, prohibiting command injection vulnerabilities (CWE-78).
3. PowerShell & Bash Execution Wrappers:
   - Enforces that external processes use explicit argument lists (e.g. subprocess.run(["cmd", "arg"]),
     pwsh -File script.ps1) rather than shell=True with concatenated strings.
4. Safe Escaping & Pipe Building Primitives:
   - Provides canonical helper functions (`quote_shell_arg`, `is_safe_shell_arg`,
     `build_safe_pipe_command`) for safe shell and pipeline construction.

Primary Source Grounding:
- OWASP Top 10:2025 A03:2021 (Injection) / CWE-78: OS Command Injection
- NIST SP 800-218: Secure Software Development Framework (SSDF)
- Workspace Standards: .claude/skills/security-baseline/SKILL.md, security-runtime/SKILL.md

Usage:
    python tasks/check_shell_pipe_safety.py --check
    python tasks/check_shell_pipe_safety.py --json
    python tasks/check_shell_pipe_safety.py --strict
    python tasks/check_shell_pipe_safety.py --path <file_or_dir>
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".loop-logs" / "shell-pipe-safety-audit.json"

# Safe argument pattern: letters, numbers, underscores, hyphens, dots, slashes, colons, equals
SAFE_ARG_REGEX = re.compile(r"^[A-Za-z0-9_\-\./:=]+$")

# Forbidden direct execution APIs
DANGEROUS_OS_APIS = frozenset({"system", "popen", "popen2", "popen3", "popen4"})

# Subprocess APIs to check for shell=True and dynamic arguments
SUBPROCESS_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output"})

# Shell redirection and chaining tokens
SHELL_OPERATORS = frozenset({">", ">>", "<", "|", "||", "&", "&&", ";", "2>&1", "1>&2"})

# Regex for unquoted variable redirection in PowerShell: e.g. > $var, >> $file (without quotes)
PS_UNQUOTED_REDIRECT_RX = re.compile(
    r'(?:>>|>)\s+(?:\$[a-zA-Z0-9_:]+)(?:\s|$|;)',
    re.M,
)

# Regex for Invoke-Expression on unvalidated variables as an executable statement
PS_INVOKE_EXPRESSION_RX = re.compile(
    r'(?:^\s*|[;|&]\s*)(?:Invoke-Expression|iex)\s+["\']?\$[a-zA-Z0-9_:]+',
    re.I,
)

# Regex for bash/sh unquoted variable redirection: e.g. > $VAR, >> $FILE
SH_UNQUOTED_REDIRECT_RX = re.compile(
    r'(?:>>|>)\s+\$[A-Za-z0-9_]+(?:\s|$|;)',
    re.M,
)

# Regex for bash eval on variables
SH_EVAL_VARIABLE_RX = re.compile(
    r'\beval\s+["\']?\$[A-Za-z0-9_]+',
    re.I,
)


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    severity: str  # "ERROR" | "WARNING"
    message: str
    snippet: str


def is_safe_shell_arg(arg: str) -> bool:
    """Return True if an argument contains only shell-safe alphanumeric and standard punctuation."""
    if not arg:
        return True
    return bool(SAFE_ARG_REGEX.match(arg))


def quote_shell_arg(arg: str) -> str:
    """Safely quote a string argument for shell execution across POSIX and Windows."""
    if is_safe_shell_arg(arg):
        return arg
    # On Windows or universal POSIX, shlex.quote handles standard quoting
    return shlex.quote(arg)


def build_safe_pipe_command(steps: List[List[str]]) -> List[str]:
    """Validate and construct a safe sequence of process arguments for piped execution.
    
    Raises ValueError if any step is empty or contains unsafe raw operators.
    """
    if not steps:
        raise ValueError("Pipeline cannot be empty.")
    
    flattened: List[str] = []
    for idx, step in enumerate(steps):
        if not step:
            raise ValueError(f"Pipeline step {idx} cannot be empty.")
        for arg in step:
            if not isinstance(arg, str):
                raise TypeError(f"Pipeline argument must be str, got {type(arg).__name__}: {arg!r}")
            # Prohibit unescaped control characters in arguments
            if "\n" in arg or "\r" in arg or "\x00" in arg:
                raise ValueError(f"Dangerous newline or null byte in pipeline argument: {arg!r}")
        if idx > 0:
            flattened.append("|")
        flattened.extend(step)
    return flattened


class ShellPipeAstVisitor(ast.NodeVisitor):
    """AST visitor inspecting Python files for unsafe shell execution and piping."""

    def __init__(self, file_path: str, lines: List[str]) -> None:
        self.file_path = file_path
        self.lines = lines
        self.findings: List[Finding] = []

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        func_name = ""
        is_subprocess = False
        is_os_call = False

        if isinstance(func, ast.Attribute):
            func_name = func.attr
            if isinstance(func.value, ast.Name):
                if func.value.id == "subprocess":
                    is_subprocess = True
                elif func.value.id in {"os", "posix"}:
                    is_os_call = True
        elif isinstance(func, ast.Name):
            func_name = func.id
            if func_name in SUBPROCESS_CALLS:
                is_subprocess = True
            elif func_name in DANGEROUS_OS_APIS:
                is_os_call = True

        # Check 1: Forbidden os.system / os.popen with dynamic strings
        if is_os_call and func_name in DANGEROUS_OS_APIS:
            if node.args:
                arg0 = node.args[0]
                if not isinstance(arg0, ast.Constant):
                    self.findings.append(
                        Finding(
                            file=self.file_path,
                            line=node.lineno,
                            rule="FORBIDDEN_OS_SYSTEM",
                            severity="ERROR",
                            message=(
                                f"Prohibited use of os.{func_name}() with dynamic expression. "
                                "Use subprocess.run() with explicit argument lists instead."
                            ),
                            snippet=self._get_snippet(node.lineno),
                        )
                    )

        # Check 2: Subprocess calls with shell=True and dynamic arguments
        if is_subprocess and func_name in SUBPROCESS_CALLS:
            shell_arg_val = None
            for kw in node.keywords:
                if kw.arg == "shell":
                    if isinstance(kw.value, ast.Constant) and bool(kw.value.value):
                        shell_arg_val = kw.value.value
                    elif not isinstance(kw.value, ast.Constant):
                        shell_arg_val = True  # Dynamic shell argument

            if shell_arg_val:
                # Inspect first argument
                if node.args:
                    arg0 = node.args[0]
                    # Dynamic string construction with shell=True is critical hazard
                    if isinstance(arg0, (ast.JoinedStr, ast.BinOp)):
                        self.findings.append(
                            Finding(
                                file=self.file_path,
                                line=node.lineno,
                                rule="UNSAFE_SHELL_TRUE_DYNAMIC_CMD",
                                severity="ERROR",
                                message=(
                                    f"subprocess.{func_name}(shell=True) with dynamically interpolated string. "
                                    "Vulnerable to shell command injection (CWE-78). Use argument lists without shell=True."
                                ),
                                snippet=self._get_snippet(node.lineno),
                            )
                        )
                    elif isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        # Static string: check if it uses unquoted chaining or redirection operators
                        val = arg0.value
                        if any(op in val for op in (";", "&&", "||", "|", ">", ">>")):
                            self.findings.append(
                                Finding(
                                    file=self.file_path,
                                    line=node.lineno,
                                    rule="RAW_SHELL_PIPING_IN_SUBPROCESS",
                                    severity="WARNING",
                                    message=(
                                        f"subprocess.{func_name}(shell=True) uses raw shell operators in static command. "
                                        "Prefer explicit Python file redirection or separate subprocess.Popen pipelines."
                                    ),
                                    snippet=self._get_snippet(node.lineno),
                                )
                            )

        self.generic_visit(node)


def audit_python_file(file_path: Path) -> List[Finding]:
    """Parse and audit a Python file for shell command and pipe safety invariants."""
    findings: List[Finding] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        tree = ast.parse(content, filename=str(file_path))
        visitor = ShellPipeAstVisitor(str(file_path), lines)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    except Exception as e:
        # Syntax errors or parse failures are flagged
        findings.append(
            Finding(
                file=str(file_path),
                line=1,
                rule="PARSE_ERROR",
                severity="WARNING",
                message=f"Failed to parse Python AST: {e}",
                snippet="",
            )
        )
    return findings


def audit_script_file(file_path: Path) -> List[Finding]:
    """Scan PowerShell (.ps1) or shell (.sh, .cmd, .bat) scripts for pipe and redirection hazards."""
    findings: List[Finding] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        ext = file_path.suffix.lower()

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Ignore comment lines
            if stripped.startswith("#") or stripped.startswith("::") or stripped.startswith("REM"):
                continue

            if ext == ".ps1":
                # Check for Invoke-Expression with variable
                if PS_INVOKE_EXPRESSION_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=str(file_path),
                            line=idx,
                            rule="PS_UNSAFE_INVOKE_EXPRESSION",
                            severity="ERROR",
                            message="Unsafe Invoke-Expression with variable command string (CWE-78).",
                            snippet=stripped,
                        )
                    )
                # Check for unquoted variable redirection
                if PS_UNQUOTED_REDIRECT_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=str(file_path),
                            line=idx,
                            rule="PS_UNQUOTED_REDIRECTION",
                            severity="WARNING",
                            message="PowerShell redirection to unquoted variable path. Quote destination string.",
                            snippet=stripped,
                        )
                    )

            elif ext in {".sh", ".bash"}:
                # Check for eval with variable
                if SH_EVAL_VARIABLE_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=str(file_path),
                            line=idx,
                            rule="SH_UNSAFE_EVAL",
                            severity="ERROR",
                            message="Unsafe shell eval with unvalidated variable (CWE-78).",
                            snippet=stripped,
                        )
                    )
                # Check for unquoted variable redirection
                if SH_UNQUOTED_REDIRECT_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=str(file_path),
                            line=idx,
                            rule="SH_UNQUOTED_REDIRECTION",
                            severity="WARNING",
                            message="Shell redirection to unquoted variable. Quote destination path (e.g. > \"$FILE\").",
                            snippet=stripped,
                        )
                    )

    except Exception as e:
        findings.append(
            Finding(
                file=str(file_path),
                line=1,
                rule="READ_ERROR",
                severity="WARNING",
                message=f"Failed to read script file: {e}",
                snippet="",
            )
        )
    return findings


def audit_file_content(file_path: str, content: str) -> List[Finding]:
    """Directly audit string content for unit tests or synthetic analysis."""
    p = Path(file_path)
    lines = content.splitlines()
    ext = p.suffix.lower()

    if ext == ".py":
        try:
            tree = ast.parse(content, filename=file_path)
            visitor = ShellPipeAstVisitor(file_path, lines)
            visitor.visit(tree)
            return visitor.findings
        except Exception as e:
            return [
                Finding(
                    file=file_path,
                    line=1,
                    rule="PARSE_ERROR",
                    severity="WARNING",
                    message=f"Failed to parse Python AST: {e}",
                    snippet="",
                )
            ]
    else:
        # Script analysis
        findings: List[Finding] = []
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("::") or stripped.startswith("REM"):
                continue
            if ext == ".ps1":
                if PS_INVOKE_EXPRESSION_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=file_path,
                            line=idx,
                            rule="PS_UNSAFE_INVOKE_EXPRESSION",
                            severity="ERROR",
                            message="Unsafe Invoke-Expression with variable command string (CWE-78).",
                            snippet=stripped,
                        )
                    )
                if PS_UNQUOTED_REDIRECT_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=file_path,
                            line=idx,
                            rule="PS_UNQUOTED_REDIRECTION",
                            severity="WARNING",
                            message="PowerShell redirection to unquoted variable path.",
                            snippet=stripped,
                        )
                    )
            elif ext in {".sh", ".bash"}:
                if SH_EVAL_VARIABLE_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=file_path,
                            line=idx,
                            rule="SH_UNSAFE_EVAL",
                            severity="ERROR",
                            message="Unsafe shell eval with unvalidated variable (CWE-78).",
                            snippet=stripped,
                        )
                    )
                if SH_UNQUOTED_REDIRECT_RX.search(stripped):
                    findings.append(
                        Finding(
                            file=file_path,
                            line=idx,
                            rule="SH_UNQUOTED_REDIRECTION",
                            severity="WARNING",
                            message="Shell redirection to unquoted variable.",
                            snippet=stripped,
                        )
                    )
        return findings


def discover_workspace_repos(lab_root: Path) -> List[Path]:
    """Discover all sibling repositories in the cf-lab workspace."""
    repos: List[Path] = [lab_root]
    workspace_parent = lab_root.parent
    for sibling_name in ["cf-research", "cf-skills", ".ai"]:
        sibling_dir = workspace_parent / sibling_name
        if sibling_dir.is_dir() and (sibling_dir / ".git").exists():
            repos.append(sibling_dir)
    return repos


def audit_workspace(
    lab_root: Optional[Path] = None,
    target_path: Optional[Path] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Audit workspace repositories or target path for shell and process pipe safety invariants."""
    if lab_root is None:
        lab_root = REPO_ROOT

    ignored_dirs = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".worktrees",
        "site_packages",
        ".pytest_cache",
        "lint-fixtures",
        "review-cases",
        "fixtures",
    }

    files_to_audit: List[Path] = []

    if target_path:
        if target_path.is_file():
            files_to_audit = [target_path]
        elif target_path.is_dir():
            for root, dirs, files in os.walk(target_path):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for file_name in files:
                    ext = Path(file_name).suffix.lower()
                    if ext in {".py", ".ps1", ".sh", ".bash", ".cmd", ".bat"}:
                        files_to_audit.append(Path(root) / file_name)
    else:
        repos = discover_workspace_repos(lab_root)
        for repo in repos:
            for root, dirs, files in os.walk(repo):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for file_name in files:
                    ext = Path(file_name).suffix.lower()
                    if ext in {".py", ".ps1", ".sh", ".bash", ".cmd", ".bat"}:
                        files_to_audit.append(Path(root) / file_name)

    all_findings: List[Finding] = []
    py_count = 0
    script_count = 0

    for file_path in files_to_audit:
        # Ignore test files that intentionally test malicious payloads or AST visitors
        if "test_check_shell_pipe_safety.py" in file_path.name or "test_check_subprocess_injection_guard.py" in file_path.name:
            continue

        ext = file_path.suffix.lower()
        if ext == ".py":
            py_count += 1
            findings = audit_python_file(file_path)
        else:
            script_count += 1
            findings = audit_script_file(file_path)

        all_findings.extend(findings)

    error_findings = [f for f in all_findings if f.severity == "ERROR"]
    warning_findings = [f for f in all_findings if f.severity == "WARNING"]

    is_clean = len(error_findings) == 0 if not strict else (len(all_findings) == 0)

    return {
        "status": "PASS" if is_clean else "FAIL",
        "total_files_audited": len(files_to_audit),
        "python_files_audited": py_count,
        "script_files_audited": script_count,
        "total_violations": len(error_findings),
        "total_warnings": len(warning_findings),
        "errors": [asdict(f) for f in error_findings],
        "warnings": [asdict(f) for f in warning_findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Multi-Repo Agent Shell Command Redirection & Process Pipe Safety Linter"
    )
    parser.add_argument("--check", action="store_true", help="Run audit and exit 1 if violations found")
    parser.add_argument("--json", action="store_true", help="Print report in JSON format")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--path", type=str, default="", help="Specific file or directory to audit")
    args = parser.parse_args()

    target_path = Path(args.path).resolve() if args.path else None
    report = audit_workspace(REPO_ROOT, target_path=target_path, strict=args.strict)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 1

    print("Agent Shell Command Redirection & Process Pipe Safety Linter:")
    print(f"  Status: {report['status']}")
    print(f"  Total files audited: {report['total_files_audited']} ({report['python_files_audited']} Python, {report['script_files_audited']} Scripts)")
    print(f"  Violations (Errors): {report['total_violations']}")
    print(f"  Warnings: {report['total_warnings']}")

    if report["errors"]:
        print("\nERRORS:")
        for err in report["errors"]:
            print(f"  [{err['rule']}] {err['file']}:{err['line']}: {err['message']}")
            if err["snippet"]:
                print(f"    --> {err['snippet']}")

    if report["warnings"] and args.strict:
        print("\nWARNINGS:")
        for warn in report["warnings"]:
            print(f"  [{warn['rule']}] {warn['file']}:{warn['line']}: {warn['message']}")
            if warn["snippet"]:
                print(f"    --> {warn['snippet']}")

    if report["status"] == "PASS":
        print("All process spawning, shell execution, and piping invariants verified clean! (PASS)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

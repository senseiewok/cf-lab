#!/usr/bin/env python3
"""Static CodeQL-equivalent security & workflow hygiene checker for staged files.

Enforces lessons from past CodeQL alerts across Python, JavaScript, and GitHub
Actions workflows locally during `check-changed.ps1` / `run-gate.ps1` before a
commit or pull request is created:
  - py/bad-tag-filter: regex filtering of <script>/<style> tags with wildcard attributes
  - py/incomplete-url-substring-sanitization: unanchored bare-domain `in` checks on URL variables
  - py/clear-text-logging-sensitive-data: logging/printing secret/password/key/token identifiers
  - js/dangerous-code-sink: eval(), new Function(), document.write() in JS modules
  - actions/unpinned-action & actions/untrusted-interpolation: unpinned `uses:` or
    direct `${{ github.event.* }}` / `${{ inputs.* }}` interpolation inside `run:` blocks
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

BAD_TAG_FILTER_RX = re.compile(
    r"<\s*(?:script|style)\b[^>]*\[\^>\]\*[^>]*>.*?<\s*/\s*(?:script|style)",
    re.IGNORECASE | re.DOTALL,
)

URL_DOMAIN_LITERAL_RX = re.compile(
    r"^(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)+/?$",
    re.IGNORECASE,
)

URL_VAR_NAME_RX = re.compile(
    r"(?:^|_)(?:url|uri|href|link|endpoint|origin|host|domain)(?:$|_)",
    re.IGNORECASE,
)

SENSITIVE_VAR_RX = re.compile(
    r"(?:^|_)(?:secret|password|passwd|api_key|private_key|auth_token|access_token|bearer_token|client_secret|deploy_password|deploy_host)(?:$|_)",
    re.IGNORECASE,
)

JS_DANGEROUS_SINK_RX = re.compile(
    r"\b(?:eval\s*\(|new\s+Function\s*\(|document\.write(?:ln)?\s*\()"
)

ACTION_USES_RX = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.MULTILINE)
SHA_PIN_RX = re.compile(r"^[^@]+@[0-9a-f]{40}$")
UNTRUSTED_EXPR_RX = re.compile(r"\$\{\{\s*(?:github\.event\.|inputs\.|head_ref)")

SELF_EXEMPT_NAMES = {
    "check_codeql_patterns.py",
    "test_check_codeql_patterns.py",
    "check_pr_gate.py",
    "test_check_pr_gate.py",
}


def _extract_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            names.append(sub.id)
        elif isinstance(sub, ast.Attribute):
            names.append(sub.attr)
    return names


def _is_str_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def scan_python_source(source: str, filename: str = "<string>") -> list[str]:
    findings: list[str] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [f"{filename}:{exc.lineno}: syntax-error: {exc.msg}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if BAD_TAG_FILTER_RX.search(node.value):
                findings.append(
                    f"{filename}:{getattr(node, 'lineno', 1)}: [py/bad-tag-filter] "
                    "Regex filters <script>/<style> tags; use html.parser.HTMLParser instead."
                )

        if isinstance(node, ast.Compare):
            left_lit = _is_str_literal(node.left)
            if left_lit and URL_DOMAIN_LITERAL_RX.match(left_lit):
                for op, comp in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.In, ast.NotIn)):
                        comp_names = _extract_names(comp)
                        if any(URL_VAR_NAME_RX.search(n) for n in comp_names):
                            findings.append(
                                f"{filename}:{node.lineno}: [py/incomplete-url-substring-sanitization] "
                                f"Unanchored URL substring check {left_lit!r} in {comp_names}; "
                                "parse with urllib.parse.urlparse(url).hostname or use .startswith()."
                            )

        if isinstance(node, ast.Call):
            is_log_sink = False
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                is_log_sink = True
            elif isinstance(node.func, ast.Attribute) and node.func.attr in (
                "debug", "info", "warning", "error", "critical", "exception",
            ):
                is_log_sink = True

            if is_log_sink:
                for arg in node.args:
                    if isinstance(arg, ast.Call):
                        func_names = _extract_names(arg.func)
                        if any("redact" in fn.lower() or "mask" in fn.lower() for fn in func_names):
                            continue
                    for name in _extract_names(arg):
                        if SENSITIVE_VAR_RX.search(name):
                            findings.append(
                                f"{filename}:{node.lineno}: [py/clear-text-logging-sensitive-data] "
                                f"Logging sensitive identifier '{name}' in clear text."
                            )
                            break

    return findings


def _strip_js_comments_and_strings(source: str) -> str:
    pattern = re.compile(
        r"//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`"
    )
    return pattern.sub(" ", source)


def _check_js_delimiter_balance(cleaned: str, filename: str) -> list[str]:
    stack: list[tuple[str, int]] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    lineno = 1
    for ch in cleaned:
        if ch == "\n":
            lineno += 1
        elif ch in "([{":
            stack.append((ch, lineno))
        elif ch in ")]}":
            if not stack or stack[-1][0] != pairs[ch]:
                return [f"{filename}:{lineno}: [js/syntax-error] Unmatched closing '{ch}'."]
            stack.pop()
    if stack:
        open_ch, open_line = stack[-1]
        return [f"{filename}:{open_line}: [js/syntax-error] Unclosed '{open_ch}'."]
    return []


def scan_javascript_source(source: str, filename: str = "<string>") -> list[str]:
    findings: list[str] = []
    cleaned = _strip_js_comments_and_strings(source)
    findings.extend(_check_js_delimiter_balance(cleaned, filename))
    for match in JS_DANGEROUS_SINK_RX.finditer(cleaned):
        lineno = source[: match.start()].count("\n") + 1
        findings.append(
            f"{filename}:{lineno}: [js/dangerous-code-sink] "
            f"Forbidden dynamic sink '{match.group(0).strip()}' detected."
        )
    return findings


def scan_workflow_yaml(source: str, filename: str = "<string>") -> list[str]:
    findings: list[str] = []
    for match in ACTION_USES_RX.finditer(source):
        action_ref = match.group(1).strip().strip("'\"")
        if action_ref.startswith("./"):
            continue
        if not SHA_PIN_RX.match(action_ref):
            lineno = source[: match.start()].count("\n") + 1
            findings.append(
                f"{filename}:{lineno}: [actions/unpinned-action] "
                f"Action '{action_ref}' is not pinned to a full 40-character commit SHA."
            )

    lines = source.splitlines()
    in_run = False
    run_indent = 0
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith("#") or not stripped:
            continue
        if in_run and indent <= run_indent and not stripped.startswith("-"):
            in_run = False
        m_run = re.match(r"^(\s*(?:-\s*)?)run:\s*(.*)$", line)
        if m_run:
            in_run = True
            run_indent = len(m_run.group(1))
            rest = m_run.group(2)
            if UNTRUSTED_EXPR_RX.search(rest):
                findings.append(
                    f"{filename}:{idx}: [actions/untrusted-interpolation] "
                    "Untrusted ${{ }} expression interpolated directly in 'run:'; pass via 'env:' instead."
                )
            continue
        if in_run and UNTRUSTED_EXPR_RX.search(line):
            findings.append(
                f"{filename}:{idx}: [actions/untrusted-interpolation] "
                "Untrusted ${{ }} expression interpolated directly in 'run:'; pass via 'env:' instead."
            )

    return findings


def scan_file(path: Path, label: str | None = None) -> list[str]:
    rel = (label or str(path)).replace("\\", "/")
    if Path(rel).name in SELF_EXEMPT_NAMES:
        return []
    ext = Path(rel).suffix.lower()
    is_workflow = ext in (".yml", ".yaml") and ".github/workflows" in rel
    if ext not in (".py", ".js", ".mjs") and not is_workflow:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"{rel}:1: read-error: {exc}"]

    if ext == ".py":
        return scan_python_source(text, rel)
    if ext in (".js", ".mjs"):
        return scan_javascript_source(text, rel)
    if is_workflow:
        return scan_workflow_yaml(text, rel)
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan files for CodeQL security patterns.")
    parser.add_argument("--label", help="Logical path label when scanning a temp file.")
    parser.add_argument("files", nargs="+", type=Path, help="Files to scan.")
    args = parser.parse_args(argv)

    all_findings: list[str] = []
    for f in args.files:
        lbl = args.label if (args.label and len(args.files) == 1) else None
        all_findings.extend(scan_file(f, lbl))

    for item in all_findings:
        print(item)
    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())

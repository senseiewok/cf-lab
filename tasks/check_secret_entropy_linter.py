#!/usr/bin/env python3
"""Automated Cross-Repo Agent API Key & Token Entropy Linter.

Continuously enforces the lab's secret-free git invariant by scanning staged
files, session logs, and repositories using Shannon entropy analysis ($H > 4.5$)
and targeted regex signatures for known API keys, tokens, and private keys:
- GitHub Personal Access Tokens (ghp_, gho_, ghu_, ghs_, ghr_)
- Anthropic API Keys (sk-ant-...)
- OpenAI API Keys (sk-...)
- Google API Keys (AIza...)
- AWS Access Keys (AKIA...)
- Private Key Blocks (-----BEGIN ... PRIVATE KEY-----)

Features calibrated allowlists for Git commit SHAs, UUIDs, SVG coordinate paths,
and test canaries to prevent false positives.

Primary Source Grounding:
- .claude/skills/security-git/SKILL.md (secret isolation and canary verification)
- .claude/skills/security-baseline/SKILL.md (credential protection & OWASP A07)
- Shannon CE (1948). A Mathematical Theory of Communication. DOI: 10.1002/j.1538-7305.1948.tb01338.x

Usage:
    python tasks/check_secret_entropy_linter.py [--check] [--staged] [--diff] [--path PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Entropy threshold for candidate tokens of length >= 20
DEFAULT_ENTROPY_THRESHOLD = 4.5
MIN_TOKEN_LENGTH = 20

# Known secret prefix and signature patterns (using negative lookahead on OpenAI key to avoid matching sk-ant-)
KNOWN_SECRET_PATTERNS = [
    (re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b"), "GITHUB_TOKEN"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), "ANTHROPIC_API_KEY"),
    (re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{32,}\b"), "OPENAI_API_KEY"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "GOOGLE_API_KEY"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS_ACCESS_KEY"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "PRIVATE_KEY_HEADER"),
    (re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b"), "SLACK_TOKEN"),
]

# High-entropy candidate extractor: alphanumeric + symbols commonly in base64 / token strings
TOKEN_CANDIDATE_REGEX = re.compile(r"[A-Za-z0-9_\-\+/=]{20,}")

# Allowlist patterns
HEX_SHA_REGEX = re.compile(r"^[0-9a-fA-F]{20,}$")
UUID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
URL_PREFIX_REGEX = re.compile(r"^https?://", re.IGNORECASE)

# Ignored filenames / extensions
IGNORED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".lock",
}

IGNORED_FILENAMES = {
    ".env.example",
    ".env.sample",
    "package-lock.json",
    "pnpm-lock.yaml",
    "catalog.lock.json",
    "delivery.lock.json",
}

CANARY_TERMS = {
    "canary",
    "example",
    "sample",
    "placeholder",
    "dummy",
    "mock",
    "test-secret",
    "fake",
}


@dataclass
class SecretFinding:
    file: str
    line: int
    rule: str
    severity: str  # "ERROR" | "WARNING"
    token_preview: str
    entropy: float
    message: str


def calculate_shannon_entropy(data: str) -> float:
    """Calculate the Shannon entropy H(X) in bits per character."""
    if not data:
        return 0.0
    length = len(data)
    counts = Counter(data)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def is_allowed_token(token: str, line_content: str = "") -> bool:
    """Check if token is a false positive (commit SHA, UUID, SVG path, or canary)."""
    line_lower = line_content.lower()

    # 0. Explicit scan allow directives
    if "privacy-scan: allow" in line_lower or "secret-scan: allow" in line_lower:
        return True

    # 1. Canary or test token indicator
    lower = token.lower()
    if any(canary in lower or canary in line_lower for canary in CANARY_TERMS):
        return True

    # 2. Pure hex string (Git commit SHA, checksum)
    if HEX_SHA_REGEX.match(token):
        return True

    # 3. UUID
    if UUID_REGEX.match(token):
        return True

    # 4. URL path component
    if URL_PREFIX_REGEX.match(token) or "http://" in line_content or "https://" in line_content:
        if token.startswith("http") or ("/" in token and "." in token):
            return True

    # 5. SVG path coordinate (in SVG path context)
    if 'd="' in line_content or "d='" in line_content or "<path" in line_content:
        cleaned = re.sub(r"[0-9\s,\.\-MmLlHhVvCcSsQqTtAaZz]", "", token)
        if len(cleaned) == 0:
            return True

    return False


def is_test_file(path: Path | str) -> bool:
    """Determine whether path represents a test file or test directory."""
    p = Path(path)
    parts = p.parts
    return (
        p.name.startswith("test_")
        or p.name.endswith("_test.py")
        or "test-" in p.name
        or "tests" in parts
    )


def scan_text(
    text: str,
    file_path: str = "<unknown>",
    entropy_threshold: float = DEFAULT_ENTROPY_THRESHOLD,
) -> list[SecretFinding]:
    """Scan arbitrary text content line by line for secrets and high-entropy tokens."""
    findings: list[SecretFinding] = []

    for line_idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue

        # 1. Check known signature patterns first
        matched_known = False
        for pattern, rule_name in KNOWN_SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                raw_token = match.group(0)
                if not is_allowed_token(raw_token, line):
                    masked = raw_token[:6] + "..." + raw_token[-4:] if len(raw_token) > 10 else "***"
                    findings.append(
                        SecretFinding(
                            file=file_path,
                            line=line_idx,
                            rule=rule_name,
                            severity="ERROR",
                            token_preview=masked,
                            entropy=calculate_shannon_entropy(raw_token),
                            message=f"Detected pattern for {rule_name}",
                        )
                    )
                    matched_known = True

        if matched_known:
            continue

        # 2. Check candidate tokens for Shannon entropy
        for match in TOKEN_CANDIDATE_REGEX.finditer(line):
            candidate = match.group(0)
            if len(candidate) < MIN_TOKEN_LENGTH:
                continue

            if is_allowed_token(candidate, line):
                continue

            entropy = calculate_shannon_entropy(candidate)
            if entropy >= entropy_threshold:
                # Mask token preview
                masked = candidate[:6] + "..." + candidate[-4:] if len(candidate) > 10 else "***"
                findings.append(
                    SecretFinding(
                        file=file_path,
                        line=line_idx,
                        rule="HIGH_ENTROPY_SECRET",
                        severity="ERROR",
                        token_preview=masked,
                        entropy=round(entropy, 2),
                        message=f"High entropy token (H={entropy:.2f} >= {entropy_threshold:.2f})",
                    )
                )

    return findings


def scan_git_diff(
    diff_text: str,
    entropy_threshold: float = DEFAULT_ENTROPY_THRESHOLD,
    include_tests: bool = False,
) -> list[SecretFinding]:
    """Scan git diff output (unified diff format) respecting file boundaries and test exclusions."""
    findings: list[SecretFinding] = []
    current_file = "<diff>"
    skip_current_file = False

    file_header_re = re.compile(r"^\+\+\+\s+b/(.*)$")

    for line_idx, line in enumerate(diff_text.splitlines(), start=1):
        # Check diff file headers
        m_file = file_header_re.match(line)
        if m_file:
            current_file = m_file.group(1).strip()
            skip_current_file = is_test_file(current_file) and not include_tests
            continue

        if skip_current_file:
            continue

        # Only inspect added lines
        if line.startswith("+") and not line.startswith("+++"):
            added_line = line[1:]
            line_findings = scan_text(added_line, file_path=current_file, entropy_threshold=entropy_threshold)
            for f in line_findings:
                f.line = line_idx
            findings.extend(line_findings)

    return findings


def scan_file(
    file_path: Path,
    entropy_threshold: float = DEFAULT_ENTROPY_THRESHOLD,
    include_tests: bool = False,
) -> list[SecretFinding]:
    """Scan a single file from disk."""
    if not file_path.is_file():
        return []

    # Check ignored extensions and filenames
    if file_path.suffix.lower() in IGNORED_EXTENSIONS:
        return []
    if file_path.name in IGNORED_FILENAMES:
        return []

    if is_test_file(file_path) and not include_tests:
        return []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return scan_text(content, str(file_path), entropy_threshold)
    except Exception:
        return []


def get_git_staged_diff(cwd: Path | None = None) -> str:
    """Retrieve git diff of staged changes."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout
    except Exception:
        return ""


def get_git_uncommitted_diff(cwd: Path | None = None) -> str:
    """Retrieve git diff of all uncommitted changes against HEAD."""
    try:
        res = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout
    except Exception:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if any ERROR level findings exist")
    parser.add_argument("--staged", action="store_true", help="Scan git staged changes only")
    parser.add_argument("--diff", action="store_true", help="Scan git uncommitted changes against HEAD")
    parser.add_argument("--path", type=Path, help="Scan a specific file or directory")
    parser.add_argument("--include-tests", action="store_true", help="Include test files in scan")
    parser.add_argument("--threshold", type=float, default=DEFAULT_ENTROPY_THRESHOLD, help="Entropy threshold (default 4.5)")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    args = parser.parse_args()

    all_findings: list[SecretFinding] = []

    if args.staged:
        diff_text = get_git_staged_diff()
        all_findings.extend(scan_git_diff(diff_text, entropy_threshold=args.threshold, include_tests=args.include_tests))
    elif args.diff:
        diff_text = get_git_uncommitted_diff()
        all_findings.extend(scan_git_diff(diff_text, entropy_threshold=args.threshold, include_tests=args.include_tests))
    elif args.path:
        target = args.path.resolve()
        if target.is_file():
            all_findings.extend(scan_file(target, entropy_threshold=args.threshold, include_tests=args.include_tests))
        elif target.is_dir():
            for p in target.rglob("*"):
                if p.is_file() and ".git" not in p.parts:
                    all_findings.extend(scan_file(p, entropy_threshold=args.threshold, include_tests=args.include_tests))
    else:
        # Default: scan staged changes, or current repo tasks & skills if staged is empty
        diff_text = get_git_staged_diff()
        if diff_text.strip():
            all_findings.extend(scan_git_diff(diff_text, entropy_threshold=args.threshold, include_tests=args.include_tests))
        else:
            tasks_dir = Path("tasks")
            if tasks_dir.is_dir():
                for p in tasks_dir.rglob("*.py"):
                    all_findings.extend(scan_file(p, entropy_threshold=args.threshold, include_tests=args.include_tests))

    errors = [f for f in all_findings if f.severity == "ERROR"]

    if args.json:
        report = {
            "total_findings": len(all_findings),
            "errors": len(errors),
            "findings": [asdict(f) for f in all_findings],
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"Secret Entropy Linter: {len(all_findings)} finding(s), {len(errors)} error(s).")
        for f in all_findings:
            print(f"  [{f.severity}] [{f.rule}] {f.file}:{f.line}: {f.message} (token: {f.token_preview})")

    if args.check and errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Automated Cross-Repo Markdown Link & Internal Anchor Integrity Linter (T-0301).

Audits markdown documentation, task specifications, skills, and architectural designs
across Sensei Ewok's CF Lab repositories to enforce link and anchor invariants:
1. All local relative markdown and file links ([label](path/to/file)) must resolve to existing files.
2. Cross-file and same-file anchor fragments ([label](path/to/file#anchor) or [label](#anchor))
   must resolve to valid GitHub-flavored markdown heading slugs or explicit HTML anchor IDs.
3. Reference-style markdown definitions ([ref]: path/to/file) are fully resolved and validated.
4. External web protocols (http://, https://, mailto:), file:// URIs, and template placeholders (<...>)
   are safely quarantined and filtered out.
5. Deterministic exit codes: returns exit 0 on clean verification, or exit 1 when broken links are detected.

Usage:
    python tasks/check_markdown_link_integrity.py [--check] [--root ROOT] [--json] [--quiet]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Patterns to extract markdown links:
# Standard inline links: [text](target) or ![alt](target)
INLINE_LINK_PATTERN = re.compile(r"!?\[(?P<text>[^\]]*)\]\((?P<target>[^\s\)\"\']+)(?:\s+[\"\'][^\"\']*[\"\'])?\)")
# Reference-style definition: [ref]: target
REF_DEF_PATTERN = re.compile(r"^\s*\[(?P<ref>[^\]]+)\]:\s*(?P<target>[^\s\"\'<>]+)", re.MULTILINE)
# Heading pattern: # Heading
HEADING_PATTERN = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+)$", re.MULTILINE)
# Explicit HTML id/name anchors: <a name="...">, <a id="...">, <... id="...">
HTML_ANCHOR_PATTERN = re.compile(r"""(?:<a\s+[^>]*(?:name|id)=["']([^"']+)["']|<[a-zA-Z0-9_-]+\s+[^>]*id=["']([^"']+)["'])""", re.IGNORECASE)

# Ignored schemes and template protocols
IGNORED_SCHEMES = (
    "http://",
    "https://",
    "mailto:",
    "ftp://",
    "data:",
    "javascript:",
    "file://",
    "irc://",
    "ssh://",
    "git@",
    "sidecar://",
    "conversation://",
)

# Common markdown directories to ignore (e.g. git, caches, test virtualenvs)
DEFAULT_IGNORE_DIRS = {
    ".git",
    ".worktrees",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "dist",
    "build",
}


def slugify_heading(heading_text: str) -> str:
    """Convert heading text into a GitHub-compatible markdown anchor slug."""
    # Normalize multiple whitespace in the raw heading first
    text = re.sub(r"\s+", " ", heading_text).strip()
    # Strip markdown formatting: bold/italic, code ticks, images, links
    text = re.sub(r"\[(?P<label>[^\]]*)\]\([^\)]*\)", r"\g<label>", text)
    text = re.sub(r"[*_~`]", "", text)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Lowercase
    slug = text.lower()
    # Remove characters that are not letters, numbers, hyphens, underscores, or spaces
    slug = re.sub(r"[^\w\s\-]", "", slug)
    # In GitHub flavored markdown, each space becomes a hyphen
    slug = slug.replace(" ", "-")
    slug = slug.strip("-")
    return slug


def extract_anchors_from_markdown(content: str) -> Set[str]:
    """Extract all valid anchor slugs (headings and explicit HTML IDs) from markdown content."""
    anchors: Set[str] = set()
    slug_counts: Dict[str, int] = {}

    for line in content.splitlines():
        # Check headings
        h_match = HEADING_PATTERN.match(line.strip())
        if h_match:
            title = h_match.group("title").strip()
            base_slug = slugify_heading(title)
            if base_slug:
                count = slug_counts.get(base_slug, 0)
                slug_counts[base_slug] = count + 1
                unique_slug = base_slug if count == 0 else f"{base_slug}-{count}"
                anchors.add(unique_slug)
                # Also accept collapsed hyphens variant (e.g. foo-bar for foo--bar)
                collapsed = re.sub(r"-+", "-", unique_slug)
                if collapsed:
                    anchors.add(collapsed)

        # Check explicit HTML anchors
        for match in HTML_ANCHOR_PATTERN.finditer(line):
            name_val = match.group(1) or match.group(2)
            if name_val:
                anchors.add(name_val.strip().lower())
                anchors.add(name_val.strip())

    return anchors


@dataclass
class LinkFinding:
    """Represents a broken link or anchor finding."""
    file_path: str
    line_number: int
    link_text: str
    raw_target: str
    resolved_path: str
    anchor: Optional[str]
    error_type: str  # "FILE_NOT_FOUND", "MISSING_ANCHOR", "INVALID_PATH"
    detail: str


def is_ignored_target(target: str) -> bool:
    """Check if target should be ignored (external URLs, template variables, etc.)."""
    t = target.strip()
    if not t:
        return True
    for scheme in IGNORED_SCHEMES:
        if t.startswith(scheme):
            return True
    # Ignore template placeholders like <path>, <conversation-id>, {id}, $VAR, or example paths
    if re.search(r"<[A-Za-z0-9_-]+>|\{[A-Za-z0-9_-]+\}|\$[A-Za-z0-9_]+", t):
        return True
    if t.startswith("path/to/") or t.startswith("relative/file") or "example.com" in t or "example.org" in t:
        return True
    # Ignore standalone # or javascript:void(0)
    if t in ("#", "##"):
        return True
    return False


def audit_markdown_file(
    md_file: Path,
    repo_root: Path,
    content_cache: Optional[Dict[Path, str]] = None,
    anchor_cache: Optional[Dict[Path, Set[str]]] = None
) -> List[LinkFinding]:
    """Inspect all markdown links and anchors within a single markdown file."""
    findings: List[LinkFinding] = []
    if content_cache is None:
        content_cache = {}
    if anchor_cache is None:
        anchor_cache = {}

    try:
        content = md_file.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [
            LinkFinding(
                file_path=str(md_file.relative_to(repo_root)),
                line_number=1,
                link_text="",
                raw_target="",
                resolved_path=str(md_file),
                anchor=None,
                error_type="FILE_READ_ERROR",
                detail=f"Could not read markdown file: {e}"
            )
        ]

    content_cache[md_file] = content
    if md_file not in anchor_cache:
        anchor_cache[md_file] = extract_anchors_from_markdown(content)

    lines = content.splitlines()
    in_fenced_code_block = False

    # Track extracted links with approximate line numbers
    for line_idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Toggle fenced code blocks (``` or ~~~)
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fenced_code_block = not in_fenced_code_block
            continue

        if in_fenced_code_block:
            continue

        # Strip inline code spans (`...`) so code examples are not mistaken for real links
        line_clean = re.sub(r"`[^`]*`", "", line)

        # 1. Inline links
        for match in INLINE_LINK_PATTERN.finditer(line_clean):
            text = match.group("text")
            raw_target = match.group("target").strip()

            if is_ignored_target(raw_target):
                continue

            # Parse path and anchor
            target_path_part = raw_target
            anchor_part: Optional[str] = None
            if "#" in raw_target:
                parts = raw_target.split("#", 1)
                target_path_part = parts[0]
                anchor_part = parts[1].strip()

            finding = verify_link_target(
                md_file=md_file,
                repo_root=repo_root,
                line_idx=line_idx,
                text=text,
                raw_target=raw_target,
                target_path_part=target_path_part,
                anchor_part=anchor_part,
                content_cache=content_cache,
                anchor_cache=anchor_cache
            )
            if finding:
                findings.append(finding)

        # 2. Reference definition targets: [ref]: target
        for ref_match in REF_DEF_PATTERN.finditer(line):
            ref_name = ref_match.group("ref")
            raw_target = ref_match.group("target").strip()

            if is_ignored_target(raw_target):
                continue

            target_path_part = raw_target
            anchor_part = None
            if "#" in raw_target:
                parts = raw_target.split("#", 1)
                target_path_part = parts[0]
                anchor_part = parts[1].strip()

            finding = verify_link_target(
                md_file=md_file,
                repo_root=repo_root,
                line_idx=line_idx,
                text=f"[{ref_name}]",
                raw_target=raw_target,
                target_path_part=target_path_part,
                anchor_part=anchor_part,
                content_cache=content_cache,
                anchor_cache=anchor_cache
            )
            if finding:
                findings.append(finding)

    return findings


def verify_link_target(
    md_file: Path,
    repo_root: Path,
    line_idx: int,
    text: str,
    raw_target: str,
    target_path_part: str,
    anchor_part: Optional[str],
    content_cache: Dict[Path, str],
    anchor_cache: Dict[Path, Set[str]]
) -> Optional[LinkFinding]:
    """Verify that target file and anchor exist."""
    rel_file = str(md_file.relative_to(repo_root))

    # Same-file anchor check: [heading](#my-heading)
    if not target_path_part:
        if anchor_part:
            slug = anchor_part.lower()
            known_anchors = anchor_cache.get(md_file, set())
            if slug not in known_anchors and anchor_part not in known_anchors:
                return LinkFinding(
                    file_path=rel_file,
                    line_number=line_idx,
                    link_text=text,
                    raw_target=raw_target,
                    resolved_path=rel_file,
                    anchor=anchor_part,
                    error_type="MISSING_ANCHOR",
                    detail=f"Anchor #{anchor_part} does not exist in {rel_file}"
                )
        return None

    # Resolve relative path
    try:
        resolved_path = (md_file.parent / target_path_part).resolve()
    except Exception as e:
        return LinkFinding(
            file_path=rel_file,
            line_number=line_idx,
            link_text=text,
            raw_target=raw_target,
            resolved_path=target_path_part,
            anchor=anchor_part,
            error_type="INVALID_PATH",
            detail=f"Cannot resolve path: {e}"
        )

    # Check file/directory existence
    if not resolved_path.exists():
        # Check if it was targeting an extensionless markdown file or directory
        alt_md = resolved_path.with_suffix(".md")
        if not alt_md.exists():
            return LinkFinding(
                file_path=rel_file,
                line_number=line_idx,
                link_text=text,
                raw_target=raw_target,
                resolved_path=str(resolved_path),
                anchor=anchor_part,
                error_type="FILE_NOT_FOUND",
                detail=f"Target file does not exist: {target_path_part}"
            )

    # If it's a markdown file and has an anchor, verify anchor existence in target
    if anchor_part and resolved_path.is_file() and resolved_path.suffix.lower() == ".md":
        if resolved_path not in anchor_cache:
            try:
                target_content = resolved_path.read_text(encoding="utf-8", errors="replace")
                content_cache[resolved_path] = target_content
                anchor_cache[resolved_path] = extract_anchors_from_markdown(target_content)
            except Exception:
                anchor_cache[resolved_path] = set()

        target_anchors = anchor_cache.get(resolved_path, set())
        slug = anchor_part.lower()
        if slug not in target_anchors and anchor_part not in target_anchors:
            return LinkFinding(
                file_path=rel_file,
                line_number=line_idx,
                link_text=text,
                raw_target=raw_target,
                resolved_path=str(resolved_path),
                anchor=anchor_part,
                error_type="MISSING_ANCHOR",
                detail=f"Anchor #{anchor_part} not found in target file {target_path_part}"
            )

    return None


def scan_markdown_links(
    root_path: Path,
    ignore_dirs: Optional[Set[str]] = None
) -> Tuple[List[LinkFinding], int]:
    """Scan all markdown files under root_path for broken links and anchors."""
    if ignore_dirs is None:
        ignore_dirs = set(DEFAULT_IGNORE_DIRS)

    all_findings: List[LinkFinding] = []
    scanned_files_count = 0
    content_cache: Dict[Path, str] = {}
    anchor_cache: Dict[Path, Set[str]] = {}

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter directories in-place
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]

        for fn in filenames:
            if fn.lower().endswith(".md"):
                file_path = Path(dirpath) / fn
                scanned_files_count += 1
                findings = audit_markdown_file(
                    md_file=file_path,
                    repo_root=root_path,
                    content_cache=content_cache,
                    anchor_cache=anchor_cache
                )
                all_findings.extend(findings)

    return all_findings, scanned_files_count


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument("--check", action="store_true", help="Exit with code 1 if broken links or anchors are found")
    parser.add_argument("--json", action="store_true", help="Emit JSON output report")
    parser.add_argument("--quiet", action="store_true", help="Suppress file listing")

    args = parser.parse_args(argv)
    root_dir = Path(args.root).resolve()

    findings, total_scanned = scan_markdown_links(root_dir)

    if args.json:
        report = {
            "root": str(root_dir),
            "files_scanned": total_scanned,
            "broken_links_count": len(findings),
            "findings": [asdict(f) for f in findings],
            "passed": len(findings) == 0
        }
        print(json.dumps(report, indent=2))
    else:
        if not args.quiet:
            print(f"Markdown Link Integrity Linter: scanned {total_scanned} file(s) under {root_dir.name}")
            if findings:
                print(f"\nDetected {len(findings)} broken link/anchor issue(s):")
                for f in findings:
                    print(f"  {f.file_path}:{f.line_number} [{f.error_type}]: '{f.raw_target}' -> {f.detail}")
            else:
                print("All local markdown links and heading anchors verified clean! (PASS)")

    if args.check and len(findings) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

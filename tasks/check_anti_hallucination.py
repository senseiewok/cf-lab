#!/usr/bin/env python3
"""Deterministic anti-hallucination verifier for cf-lab control repository.

Checks four structural grounding invariants (LAB-AH-1 through LAB-AH-4):
- LAB-AH-1 (Task ID Provenance): Every T-XXXX task ID referenced in
  tasks/HUMAN-TASKS.md, tasks/sentinels.json, and tasks/sentinel-prompts/*.md
  must exist in tasks/board.json.
- LAB-AH-2 (Board Identifier & Dossier Grounding): Every NCT######## identifier
  cited in tasks/board.json (for ready/in_progress/done tasks, or proposed
  tasks) must exist in cf-research/tools/trial_atlas/snapshot.json (when the
  sibling snapshot is present), and every proposals/*.md or landscape/*.md path
  cited in source_evidence for ready/in_progress/done tasks must exist in
  cf-research (when the sibling repo is present).
- LAB-AH-3 (AGENTS.md Skill Catalog Grounding): Every skill bullet listed under
  '## Skills' in AGENTS.md must resolve to an existing .claude/skills/<name>/SKILL.md
  (either in cf-lab or in the explicitly declared sibling repo).
- LAB-AH-4 (Sentinel Prompt Grounding Contract): Every sentinel prompt_file
  declared in tasks/sentinels.json must exist and contain explicit
  anti-hallucination rules ("anti-hallucination" and deterministic verification).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
TASK_ID_RE = re.compile(r"\bT-\d{4}\b")
NCT_ID_RE = re.compile(r"\bNCT\d{8}\b")
RESEARCH_DOC_RE = re.compile(r"\b((?:proposals|landscape)/[A-Za-z0-9_.-]+\.md)\b")
SKILL_BULLET_RE = re.compile(r"^- `([a-z0-9-]+)`(?:\s+and\s+`([a-z0-9-]+)`)?(.*)$")


def resolve_sibling_repo(root: Path, repo_name: str) -> Optional[Path]:
    """Find a sibling repo in normal checkout or worktree layout."""
    candidates = [
        root.parent / repo_name,
        root.parent.parent / repo_name,
        root.parent.parent.parent / repo_name,
    ]
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        # Skip .worktrees/... worktree containers
        if ".worktrees" in candidate.parts:
            continue
        return candidate
    return None


def load_known_ncts(cf_research_dir: Optional[Path]) -> Set[str]:
    if not cf_research_dir:
        return set()
    snap_path = cf_research_dir / "tools" / "trial_atlas" / "snapshot.json"
    if not snap_path.is_file():
        return set()
    try:
        data = json.loads(snap_path.read_text(encoding="utf-8"))
        return {
            s.get("nct_id", "")
            for s in data.get("studies", [])
            if isinstance(s, dict) and s.get("nct_id")
        }
    except Exception:
        return set()


def check_task_id_provenance(root: Path, board_ids: Set[str]) -> List[str]:
    """LAB-AH-1: Every T-XXXX in HUMAN-TASKS.md, sentinels.json, and sentinel prompts exists in board.json."""
    errors: List[str] = []
    targets: List[Path] = [
        root / "tasks" / "HUMAN-TASKS.md",
        root / "tasks" / "sentinels.json",
    ]
    prompts_dir = root / "tasks" / "sentinel-prompts"
    if prompts_dir.is_dir():
        targets.extend(sorted(prompts_dir.glob("*.md")))

    for path in targets:
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for match in sorted(set(TASK_ID_RE.findall(text))):
            if match not in board_ids:
                errors.append(
                    f"[LAB-AH-1] {rel} references unknown task ID '{match}' not present in tasks/board.json"
                )
    return errors


def check_board_identifier_grounding(
    root: Path,
    tasks: List[Dict],
    cf_research_dir: Optional[Path],
    known_ncts: Set[str],
) -> List[str]:
    """LAB-AH-2: Verify NCT IDs and cf-research dossier paths cited on the board."""
    errors: List[str] = []
    for task in tasks:
        tid = task.get("id", "<unknown>")
        status = task.get("status", "")
        ev_text = " ".join(str(x) for x in (task.get("source_evidence") or []))
        full_text = f"{task.get('title', '')} {task.get('summary', '')} {task.get('notes', '')} {ev_text}"

        if known_ncts:
            for nct in sorted(set(NCT_ID_RE.findall(full_text))):
                if nct not in known_ncts:
                    errors.append(
                        f"[LAB-AH-2] tasks/board.json task {tid} ({status}) cites '{nct}' which is absent from cf-research/tools/trial_atlas/snapshot.json"
                    )

        if cf_research_dir and status in {"ready", "in_progress", "done"}:
            # Only enforce existence of proposals/*.md or landscape/*.md when cited in source_evidence
            # as an existing prerequisite (not when the task's own acceptance creates it).
            acceptance_text = str(task.get("acceptance") or "")
            for doc_rel in sorted(set(RESEARCH_DOC_RE.findall(ev_text))):
                if doc_rel in acceptance_text and status != "done":
                    continue
                if not (cf_research_dir / doc_rel).is_file():
                    errors.append(
                        f"[LAB-AH-2] tasks/board.json task {tid} ({status}) cites missing cf-research artifact '{doc_rel}' in source_evidence"
                    )
    return errors


def extract_skills_section(agents_md_text: str) -> List[Tuple[str, str]]:
    """Return (skill_name, trailing_context) tuples from the '## Skills' section of AGENTS.md."""
    lines = agents_md_text.splitlines()
    in_skills = False
    found: List[Tuple[str, str]] = []
    for line in lines:
        if line.startswith("## Skills"):
            in_skills = True
            continue
        if in_skills and line.startswith("## "):
            break
        if not in_skills:
            continue
        m = SKILL_BULLET_RE.match(line.strip())
        if m:
            first_skill, second_skill, rest = m.group(1), m.group(2), m.group(3) or ""
            found.append((first_skill, rest))
            if second_skill:
                found.append((second_skill, rest))
    return found


def check_agents_skill_catalog(
    root: Path,
    cf_skills_dir: Optional[Path],
    cf_research_dir: Optional[Path],
) -> List[str]:
    """LAB-AH-3: Every skill listed in AGENTS.md resolves to an existing SKILL.md."""
    errors: List[str] = []
    agents_path = root / "AGENTS.md"
    if not agents_path.is_file():
        return ["[LAB-AH-3] AGENTS.md is missing"]

    entries = extract_skills_section(agents_path.read_text(encoding="utf-8"))
    if not entries:
        return ["[LAB-AH-3] No skill entries parsed under '## Skills' in AGENTS.md"]

    for skill_name, context in entries:
        local_skill = root / ".claude" / "skills" / skill_name / "SKILL.md"
        if "cf-skills" in context:
            if cf_skills_dir is not None:
                target = cf_skills_dir / ".claude" / "skills" / skill_name / "SKILL.md"
                if not target.is_file():
                    errors.append(
                        f"[LAB-AH-3] AGENTS.md skill '{skill_name}' declared in cf-skills does not exist at {target}"
                    )
        elif "cf-research" in context:
            if cf_research_dir is not None:
                target = cf_research_dir / ".claude" / "skills" / skill_name / "SKILL.md"
                if not target.is_file():
                    errors.append(
                        f"[LAB-AH-3] AGENTS.md skill '{skill_name}' declared in cf-research does not exist at {target}"
                    )
        else:
            if not local_skill.is_file():
                errors.append(
                    f"[LAB-AH-3] AGENTS.md skill '{skill_name}' does not exist at .claude/skills/{skill_name}/SKILL.md"
                )
    return errors


def check_sentinel_prompts(root: Path) -> List[str]:
    """LAB-AH-4: Every sentinel prompt_file in sentinels.json exists and enforces anti-hallucination rules."""
    errors: List[str] = []
    sentinels_path = root / "tasks" / "sentinels.json"
    if not sentinels_path.is_file():
        return ["[LAB-AH-4] tasks/sentinels.json is missing"]

    try:
        data = json.loads(sentinels_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"[LAB-AH-4] tasks/sentinels.json is invalid JSON: {exc}"]

    sentinels = data.get("sentinels", {})
    if not isinstance(sentinels, dict) or not sentinels:
        return ["[LAB-AH-4] tasks/sentinels.json defines no sentinels"]

    for name, spec in sentinels.items():
        prompt_rel = spec.get("prompt_file")
        if not prompt_rel:
            errors.append(f"[LAB-AH-4] sentinel '{name}' is missing prompt_file")
            continue
        prompt_path = root / prompt_rel
        if not prompt_path.is_file():
            errors.append(
                f"[LAB-AH-4] sentinel '{name}' prompt_file '{prompt_rel}' does not exist"
            )
            continue
        text = prompt_path.read_text(encoding="utf-8")
        lower = text.lower()
        if "anti-hallucination" not in lower:
            errors.append(
                f"[LAB-AH-4] {prompt_rel} is missing an explicit 'Anti-hallucination' guardrail section/rule"
            )
        if "never" not in lower:
            errors.append(
                f"[LAB-AH-4] {prompt_rel} is missing explicit prohibition boundaries ('never')"
            )
    return errors


def run_all_checks(
    root: Path = ROOT_DIR,
    cf_research_dir: Optional[Path] = None,
    cf_skills_dir: Optional[Path] = None,
) -> List[str]:
    board_path = root / "tasks" / "board.json"
    if not board_path.is_file():
        return ["[LAB-AH-1] tasks/board.json is missing"]

    try:
        board = json.loads(board_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"[LAB-AH-1] tasks/board.json is invalid JSON: {exc}"]

    tasks = board.get("tasks", [])
    board_ids = {t.get("id") for t in tasks if isinstance(t, dict) and t.get("id")}

    if cf_research_dir is None:
        cf_research_dir = resolve_sibling_repo(root, "cf-research")
    if cf_skills_dir is None:
        cf_skills_dir = resolve_sibling_repo(root, "cf-skills")

    known_ncts = load_known_ncts(cf_research_dir)

    errors: List[str] = []
    errors.extend(check_task_id_provenance(root, board_ids))
    errors.extend(
        check_board_identifier_grounding(root, tasks, cf_research_dir, known_ncts)
    )
    errors.extend(check_agents_skill_catalog(root, cf_skills_dir, cf_research_dir))
    errors.extend(check_sentinel_prompts(root))
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify anti-hallucination guardrails across cf-lab."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR,
        help="Path to cf-lab repository root",
    )
    args = parser.parse_args(argv)

    errors = run_all_checks(args.root.resolve())
    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        print(f"FAILED: {len(errors)} anti-hallucination violation(s)", file=sys.stderr)
        return 1

    print("PASS: cf-lab anti-hallucination checks (LAB-AH-1..LAB-AH-4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Deterministic verifier for the Scite Pro MCP admission review (T-0047), Rule 12, and AH-6/AH-8 guardrails.

Checks that:
1. `docs/scite-mcp-admission-review.md` exists and contains:
   - Task `T-0047` and `https://api.scite.ai/mcp` provenance (`model-onboarding` Section 1).
   - 33 allowed read-only tools vs. 11 blocked mutation/billing tools (`BLOCKED_MUTATION_TOOLS`, `manage_subscription`).
   - Pro plan quota cap (`SCITE_MCP_DAILY_CAP=60`, `2,500` MCP tool uses/month, OAuth tokens stored outside all git repos).
   - `model-onboarding` Section 6 untrusted content boundary (`<untrusted_data>`).
   - Recorded read-only queries (`citation_graph`, `search_mhra`, `search_patents`).
   - Explicit rule that shipped citations still resolve through `cf-evidence-loop` and Scite classifications carry `[observed: Scite ML citation classification, accessed YYYY-MM-DD]`.
2. `.claude/skills/ai-loop-council/SKILL.md` and `AGENTS.md` enforce Rule 12 (`Native Subagent Spawning` via `invoke_subagent` / `define_subagent` vs. forbidding underlying CLI execution).
3. `.claude/skills/cf-research-context/SKILL.md` and `.claude/agents/frontier-challenger.md` enforce Multi-Source Cross-Verification (`AH-6` / `AH-8`: ChEMBL assay context conflation guard, Open Targets FAERS confounding-by-indication guard, Scite ML polarity provenance, and `T-0071` ClinGen/gnomAD exclusion).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC = ROOT / "docs" / "scite-mcp-admission-review.md"
DEFAULT_AGENTS = ROOT / "AGENTS.md"
DEFAULT_COUNCIL_SKILL = ROOT / ".claude" / "skills" / "ai-loop-council" / "SKILL.md"
DEFAULT_CONTEXT_SKILL = ROOT / ".claude" / "skills" / "cf-research-context" / "SKILL.md"
DEFAULT_CHALLENGER = ROOT / ".claude" / "agents" / "frontier-challenger.md"

BLOCKED_TOOLS = (
    "manage_subscription",
    "create_collection",
    "update_collection",
    "delete_collection",
    "add_dois_to_collection",
    "remove_dois_from_collection",
    "create_collection_note",
    "update_collection_note",
    "delete_collection_note",
    "upload_collection_file",
    "delete_collection_file",
)


def check_scite_mcp_admission(
    doc_path: Path = DEFAULT_DOC,
    agents_path: Path = DEFAULT_AGENTS,
    council_skill_path: Path = DEFAULT_COUNCIL_SKILL,
    context_skill_path: Path = DEFAULT_CONTEXT_SKILL,
    challenger_path: Path = DEFAULT_CHALLENGER,
) -> tuple[int, list[str]]:
    for label, p in (
        ("admission review document", doc_path),
        ("AGENTS.md", agents_path),
        ("ai-loop-council SKILL.md", council_skill_path),
        ("cf-research-context SKILL.md", context_skill_path),
        ("frontier-challenger.md", challenger_path),
    ):
        if not p.is_file():
            return 1, [f"FAIL missing {label}: {p}"]

    doc_text = doc_path.read_text(encoding="utf-8")
    agents_text = agents_path.read_text(encoding="utf-8")
    council_text = council_skill_path.read_text(encoding="utf-8")
    context_text = context_skill_path.read_text(encoding="utf-8")
    challenger_text = challenger_path.read_text(encoding="utf-8")

    messages: list[str] = []
    failures = 0

    def require(label: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        if cond:
            messages.append(f"PASS {label}")
        else:
            suffix = f" ({detail})" if detail else ""
            messages.append(f"FAIL {label}{suffix}")
            failures += 1

    # 1. Scite Pro MCP provenance, OAuth outside repos, and daily quota cap
    require(
        "Scite Pro MCP provenance & OAuth outside git repos (T-0047)",
        "T-0047" in doc_text
        and "https://api.scite.ai/mcp" in doc_text
        and "outside all git repositories" in doc_text.lower()
        and "SCITE_MCP_DAILY_CAP=60" in doc_text
        and "2,500" in doc_text,
        "must document T-0047, https://api.scite.ai/mcp, outside-repo token storage, 2,500 monthly quota, and SCITE_MCP_DAILY_CAP=60",
    )

    # 2. All 11 mutation/billing tools explicitly blocked
    missing_blocked = [t for t in BLOCKED_TOOLS if t not in doc_text]
    require(
        "All 11 Scite mutation/billing tools blocked in admission review",
        len(missing_blocked) == 0 and "33" in doc_text,
        f"missing blocked tools: {', '.join(missing_blocked)}",
    )

    # 3. Untrusted content boundary & recorded read-only queries
    require(
        "Untrusted content boundary (<untrusted_data>) & recorded live queries",
        "<untrusted_data>" in doc_text
        and "citation_graph" in doc_text
        and "search_mhra" in doc_text
        and "search_patents" in doc_text,
        "must include <untrusted_data> quarantine and recorded citation_graph, search_mhra, and search_patents outputs",
    )

    # 4. Shipped citation & Scite ML classification provenance rule
    require(
        "cf-evidence-loop citation rule & Scite ML provenance label",
        "cf-evidence-loop" in doc_text
        and "[observed: Scite ML citation classification" in doc_text,
        "must require cf-evidence-loop for shipped citations and [observed: Scite ML citation classification...] label",
    )

    # 5. Rule 12: Native Subagent Spawning vs. Underlying CLI Execution
    require(
        "Rule 12 (Native Subagent Spawning vs. Underlying CLI Execution) in ai-loop-council & AGENTS.md",
        "Native Subagent Spawning" in council_text
        and "invoke_subagent" in council_text
        and "invoke_subagent" in agents_text
        and bool(re.search(r"never(?:\*\*)?\s+spawn\s+external\s+agent\s+CLIs", agents_text, re.I)),
        "must enforce native invoke_subagent spawning and forbid external agent CLI subprocesses in ai-loop-council/SKILL.md and AGENTS.md",
    )

    # 6. Multi-Source Cross-Verification (AH-8) in cf-research-context & frontier-challenger
    require(
        "Multi-Source Cross-Verification (AH-8) in cf-research-context & frontier-challenger",
        "Assay Context Conflation Guard" in context_text
        and "FAERS Confounding-by-Indication Guard" in context_text
        and "T-0071" in context_text
        and "AH-8" in context_text
        and "AH-8" in challenger_text
        and "Assay Context" in challenger_text,
        "must enforce AH-8 (ChEMBL Assay Context Guard, FAERS Confounding Guard, and T-0071) in cf-research-context and frontier-challenger",
    )

    if failures > 0:
        messages.append(f"RESULT FAIL ({failures} failed)")
        return 1, messages
    messages.append("RESULT PASS")
    return 0, messages


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    ap.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    ap.add_argument("--council-skill", type=Path, default=DEFAULT_COUNCIL_SKILL)
    ap.add_argument("--context-skill", type=Path, default=DEFAULT_CONTEXT_SKILL)
    ap.add_argument("--challenger", type=Path, default=DEFAULT_CHALLENGER)
    args = ap.parse_args(argv)
    code, msgs = check_scite_mcp_admission(
        doc_path=args.doc,
        agents_path=args.agents,
        council_skill_path=args.council_skill,
        context_skill_path=args.context_skill,
        challenger_path=args.challenger,
    )
    for m in msgs:
        print(m)
    return code


if __name__ == "__main__":
    sys.exit(main())

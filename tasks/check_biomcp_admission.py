#!/usr/bin/env python3
"""Deterministic verifier for the BioMCP admission review (T-0042 and T-0071).

Checks that:
1. `docs/biomcp-admission-review.md` exists and contains:
   - `model-onboarding` section 1 (pinned release version `0.7.3` and 64-hex SHA-256 wheel/sdist digests) and section 6 (`injection-probe.ps1` output and untrusted-content boundary).
   - Completed `security-runtime` MCP checklist.
   - Written complement-or-not decision with the explicit rule that shipped citations still come from `cf-evidence-loop` records.
   - Documentation of BioMCP's rate limiting, robots handling, retry, and User-Agent behaviour against every rule R1 through R9 of `NETWORK-RULES.md`, with any rule it cannot demonstrate listed as a condition of use.
   - Explicit block of ClinGen (`clingen`) and gnomAD (`gnomad`) tools until catalog entries change, and the rule that the wrapper's own requests must follow `NETWORK-RULES.md` R1-R9 (`T-0071`).
2. `tasks/board.json` task `T-0042` acceptance text explicitly includes the `T-0071` ClinGen and gnomAD catalog conflict blocks and the `NETWORK-RULES` R1-R9 wrapper requirement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC = ROOT / "docs" / "biomcp-admission-review.md"
DEFAULT_BOARD = ROOT / "tasks" / "board.json"

REQUIRED_RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9")


def check_biomcp_admission(
    doc_path: Path = DEFAULT_DOC,
    board_path: Path = DEFAULT_BOARD,
) -> tuple[int, list[str]]:
    if not doc_path.is_file():
        return 1, [f"FAIL missing admission review document: {doc_path}"]
    if not board_path.is_file():
        return 1, [f"FAIL missing board file: {board_path}"]

    text = doc_path.read_text(encoding="utf-8")
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

    # 1. Pinned release & SHA-256 digests (model-onboarding section 1)
    require(
        "model-onboarding section 1 provenance & pinned release",
        "model-onboarding" in text
        and "0.7.3" in text
        and len(set(re.findall(r"\b[0-9a-f]{64}\b", text))) >= 2,
        "must record pinned version 0.7.3 and distinct wheel/sdist SHA-256 hashes",
    )

    # 2. model-onboarding section 6 injection probe
    require(
        "model-onboarding section 6 injection-probe output",
        "injection-probe.ps1" in text and "Section 6" in text,
        "must record injection-probe.ps1 verification and untrusted-content boundary",
    )

    # 3. security-runtime MCP checklist
    require(
        "security-runtime MCP checklist completed",
        "security-runtime" in text and "load_dotenv" in text and "alphagenome_predictor" in text,
        "must complete security-runtime MCP checklist including .env and tool hazards",
    )

    # 4. Written complement-or-not decision + cf-evidence-loop citation rule
    require(
        "complement-or-not decision & cf-evidence-loop citation rule",
        "cf-evidence-loop" in text
        and bool(re.search(r"shipped citations?[^\n]*cf-evidence-loop", text, re.I)),
        "must state complement-or-not decision and that shipped citations come from cf-evidence-loop records",
    )

    # 5. NETWORK-RULES.md R1-R9 coverage + rate limiting, robots, retry, user-agent + conditions of use
    missing_rules = [
        r for r in REQUIRED_RULES if not re.search(rf"\|\s*\*\*{r}\*\*\s*\|", text)
    ]
    require(
        "NETWORK-RULES.md R1-R9 table rows present",
        len(missing_rules) == 0,
        f"missing rules: {', '.join(missing_rules)}",
    )
    for topic, pattern in (
        ("rate limiting", r"rate_limiter\.py.*max_rps|max_rps.*rate_limiter\.py"),
        ("robots handling", r"robots\.txt"),
        ("retry behaviour", r"retry\.py.*Retry-After|Retry-After.*retry\.py"),
        ("user-agent behaviour", r"User-Agent.*drug_shortages\.py|drug_shortages\.py.*User-Agent"),
        ("condition of use column", r"Condition of Use"),
    ):
        require(
            f"NETWORK-RULES audit documents {topic}",
            bool(re.search(pattern, text, re.I | re.S)),
            f"pattern not found: {pattern}",
        )

    # 6. T-0071 ClinGen and gnomAD catalog blocks in review doc and T-0042 board acceptance text
    require(
        "review doc blocks ClinGen and gnomAD tools until catalog changes (T-0071)",
        bool(re.search(r"ClinGen[^\n]*\bblocked\b", text, re.I))
        and bool(re.search(r"gnomAD[^\n]*\bblocked\b", text, re.I))
        and not bool(re.search(r"(?:ClinGen|gnomAD)[^\n]*\b(?:not\s+blocked|unblocked)\b", text, re.I)),
        "must list ClinGen and gnomAD tools as blocked until catalog entries change",
    )

    try:
        board = json.loads(board_path.read_text(encoding="utf-8"))
        t42 = next((t for t in board.get("tasks", []) if t.get("id") == "T-0042"), None)
    except Exception as exc:
        messages.append(f"FAIL invalid board JSON: {exc}")
        return 1, messages

    acc = (t42 or {}).get("acceptance", "")
    require(
        "T-0042 board acceptance text includes ClinGen and gnomAD blocks and R1-R9 wrapper rule (T-0071)",
        t42 is not None
        and "ClinGen" in acc
        and "gnomAD" in acc
        and bool(re.search(r"\bblocked\b", acc, re.I))
        and not bool(re.search(r"\b(?:not\s+blocked|unblocked)\b", acc, re.I))
        and "R1-R9" in acc,
        f"T-0042 acceptance: {acc!r}",
    )

    if failures > 0:
        messages.append(f"RESULT FAIL ({failures} failed)")
        return 1, messages
    messages.append("RESULT PASS")
    return 0, messages


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    ap.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    args = ap.parse_args(argv)
    code, msgs = check_biomcp_admission(doc_path=args.doc, board_path=args.board)
    for m in msgs:
        print(m)
    return code


if __name__ == "__main__":
    sys.exit(main())

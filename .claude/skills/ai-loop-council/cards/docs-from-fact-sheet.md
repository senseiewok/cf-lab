---
card: docs-from-fact-sheet
class: convert
when: README, PR description, or documentation generated strictly from a fact sheet with no invented facts or framing.
not_when: Creative marketing copy, speculative research proposals, or clinical advice.
verifier: scripts/verify-docs-from-fact-sheet.py
profiles: fast,fast,medium
max_output: 8192
budget_calls: 5
status: validated
validated_against: bare-pr-descriptions-20261005 (bare 3/3 with 4 reading defects vs card 3/3 with 0 reading defects)
---

## Packet skeleton

```markdown
Generate structured documentation strictly from the provided fact sheet.
Requirements:
1. Include required sections: `## Overview`, `## Verification`, `## Limitations`.
2. Take every single number, date, and metric directly from lines in the fact sheet. Do not estimate or extrapolate.
3. If a fact or dimension is not stated in the source sheet, write "not stated".
4. Maintain strict medical boundaries: independent research, no cure or clinical efficacy claims.
```

## Worked example

```markdown
## Overview
The trial endpoint pipeline monitors 14 CFTR modulation studies across 3 registries.
All records were accessed on 2026-10-15 from public clinical trial registries.

## Verification
- Crossref Retraction Watch audited: 8 benchmark DOIs verified with 0 retractions.
- Unit tests: 42 deterministic tests passing.
- Output hashes match canonical checksums.

## Limitations
- Registry data reflects reported sponsor filings; clinical outcomes are not independently verified.
- Independent computational research only; not clinical guidance.
```

## Decomposition

1. Extract verbatim source facts, numbers, dates, and metrics from the provided fact sheet.
2. Structure the target document with required headings (`## Overview`, `## Verification`, `## Limitations`).
3. Fill each section only using mapped fact sheet lines, inserting "not stated" where silent.
4. Verify numbers against the input allow-list and remove any speculative framing.
5. Confirm medical boundary disclaimer is present without hype or treatment promises.

## Verifier contract

- `FAIL R-01 missing required heading`: Verifies that `## Overview`, `## Verification`, and `## Limitations` exist.
- `FAIL R-02 sentence contains ungrounded claim`: Verifies that prose statements are traceable to provided input data.
- `FAIL R-03 forbidden medical claim or hype`: Verifies absence of ungrounded treatment, cure, or clinical efficacy claims.
- `FAIL R-04 invented number or metric`: Verifies that every number in the document exists in the source fact sheet.
- `FAIL R-06 sentence has no source line`: Verifies that assertions map to explicit source lines.

## Known failure modes

| Symptom | Cause | Repair Instruction |
|---|---|---|
| `FAIL R-01 missing required heading` | Omitted required section heading | Add exact markdown heading: `## Overview`, `## Verification`, or `## Limitations`. |
| `FAIL R-02 sentence contains ungrounded claim` | Inferred assertion not grounded in fact sheet | Remove speculative sentence or qualify as "not stated in source". |
| `FAIL R-03 forbidden medical claim or hype` | Optimistic medical or clinical phrasing used | Replace with standard boundary: "Independent research; not clinical guidance or cure". |
| `FAIL R-04 invented number or metric` | Model generated estimated or hallucinated numeric metric | Check numbers against input sheet; replace estimated numbers with verbatim values. |
| `FAIL R-06 sentence has no source line` | Extrapolated context not in source | Delete unsupported narrative lines and restrict prose strictly to source facts. |

## Do-not examples

```markdown
# Do NOT invent unstated numbers:
We analyzed 150 papers (estimate).  # FAILS R-04: number not in fact sheet

# Do NOT make medical cure claims:
This model promises a cure for CFTR.  # FAILS R-03: forbidden medical claim
```

## Escalation

- Escalate to the human maintainer if source fact sheet contains internal contradictions.
- Escalate immediately if prompt asks to author clinical medical advice or treatment efficacy claims.

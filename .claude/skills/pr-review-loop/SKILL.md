---
name: pr-review-loop
description: A frugal review loop to run before opening a pull request - deterministic checks first, a self-review for trivial changes, one blind reviewer on the diff, every finding verified against the code, at most two rounds, and the loop recorded in the pull request body. Use before opening or pushing a pull request, when asked to review a diff, or when deciding whether a change needs a model review at all.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.). Needs git; the reviewer can be any model that did not write the change.
---

# Pull request review loop

A review costs tokens and attention. Spend them where a script cannot decide, and spend them once.

The review tiers in `AGENTS.md` (Routine, Elevated, Full) decide **who** reviews whenever a tier applies. This loop only orders the rounds and keeps them cheap; it never lowers a tier. Step 2 below is the Routine tier's self-review variant, agreed with the maintainer on 2026-10-11, for docs or wording under about 20 lines with no security, privacy, licence, source-terms or public-claim content.

## The loop

| Step | Do | Do not |
| --- | --- | --- |
| 1. Checks | Run the tests, linters and the repo's own gate (here: `pwsh -NoProfile -File ./check-all.ps1`, or `-Only` the rows you touched). Fix until they pass. | Spend a model on anything a script decides: syntax, formatting, counts, links, test results. |
| 2. Size it | Docs or wording under about 20 changed lines, no code, and nothing that touches security, privacy, a licence, a source's terms or a public-facing claim: read the diff yourself once and write "self-reviewed, no model review" in the body. Skip to step 6. | Call a reviewer for a typo. Or skip one for a short change in those five areas: it still gets a reviewer. |
| 3. Round 1 | One blind reviewer reads only the diff and the pull request's stated purpose. | Send whole files, the chat history or your own opinion of the change. |
| 4. Verify | Check every finding against the code yourself. Reject false ones with the evidence; fix confirmed ones with a test that failed before the fix. | Act on a finding you have not reproduced, or decide by vote. |
| 5. Round 2 | Only if round 1 confirmed a blocking, wrong-number or fail-open issue, or the fixes changed more than about 30 lines. The reviewer sees only the delta and the list of what was meant to change. | Run a third round. Anything left goes in the body. |
| 6. Record | Put the loop table (below) in the body. | Claim "reviewed" for a scope nobody looked at. |
| 7. Open | Open or push the pull request only now. | Push before the loop ends, unless the maintainer said to push while tests run. |

### Who reviews

- **The tier decides.** When a review tier in `AGENTS.md` applies, it sets the reviewers.
- **A named default.** Where the maintainer has named a reviewer as the default authority, use that one. Never use the model that wrote the change.
- **Add at least one second-family reviewer** when the change touches security, privacy, a licence, a source's terms, a claim the public will read, deployment, credentials or patient data (the Full tier may require more). A model from the same family as the author shares its blind spots.
- **Split the packet** when the change has a deploy or security surface: a code packet (behaviour, tests) and a security packet (secrets, permissions, network, what gets published), each to its own reviewer call.

### What to ask for

At most about 10 findings, each with:

1. the exact quoted line from the diff,
2. a concrete input that makes it fail,
3. a severity: blocking, wrong number, fail-open, minor.

Tell the reviewer what is intentionally outside the packet and why (generated files, unchanged callers, files in another repo). A finding about a file that is not in the packet is checked against the full tree before it is accepted.

### Round 2 packet

Build the round-1 packet and the round-2 packet the same way and send the diff between them, plus a short list: "finding 3: the regex now has a length cap; finding 5: the URL check now runs after redirects". Ask whether each item was really fixed and whether a fix opened a new hole. Round-2 findings are often bypasses of round-1 fixes, so test each fix with the adversarial input that motivated it.

### Visual changes

When a change alters how a page looks, run a visual check and attach a few small screenshots. Follow `playwright-browser-testing`: its `references/visual-qa-sweep.md` for the frugal sweep and `scripts/pr-screenshots.py` to capture and attach the images. A text-only review does not clear a visual one.

## Pull request body template

```markdown
## What and why
One paragraph: the purpose, the evidence it rests on.

## Checks
- `check-all.ps1`: N passed, 0 failed, M skipped (skipped: needs a browser)

## Review loop
| Round | Who | Findings | Accepted | Rejected |
| --- | --- | --- | --- | --- |
| 1 | the tier's reviewer, blind, diff only | 7 | 3 (fixed, each with a test) | 4 (evidence below) |
| 2 | same reviewer, delta only | 2 | 1 | 1 |

Not reviewed: the generated catalog file; the visual change on tablet width; anything outside this repo.
Left open: finding 2.4 (minor, tracked as a board task).

## Screenshots
(only for a visual change; small crops, phone and desktop)
```

## Pitfalls

- **Missing context read as a bug.** A reviewer who sees only the diff will flag what the diff omits. Name the omissions up front and check such findings against the tree.
- **A fix that passes only the friendly test.** Re-run each fix against the hostile input that motivated it, and time patterns on hostile input with a stricter limit than the test's.
- **Anything that publishes.** A new rule that publishes, pushes or posts needs a second look at what a forged input could do.
- **Unbounded loops.** Two rounds, then stop and write down what is left.

Candidate lessons, not yet promoted: [references/lessons.md](references/lessons.md).

## Verification

- The body has the loop table, including a "Not reviewed" line.
- Every accepted finding has a commit and a test that fails without it.
- Every rejected finding names the line or command output that disproves it.
- The deterministic checks were re-run after the last fix, and their summary line is in the body.

# Copilot Instructions — Sensei Ewok's CF Lab

[AGENTS.md](../AGENTS.md) is the single rule source for this multi-root workspace (`cf-lab.code-workspace`). Sibling folders:

- `../cf-skills` — `senseiewok/cf-skills` (public GitHub Skills repo)
- `../cf-research` — `senseiewok/cf-research` (CF research notes, source catalog, and small tools)
- `../cf-lab-files` — untracked local memory and session scratch (never published)

## Ground rules

1. **Read [AGENTS.md](../AGENTS.md) first.** Every rule on setup, sibling worktrees, task board (`tasks/board.json`), security, scientific grounding, and the AI loop lives in [AGENTS.md](../AGENTS.md). This file holds no rule that is not in [AGENTS.md](../AGENTS.md).
2. **Load skills from `.claude/skills/<name>/SKILL.md`.** GitHub Copilot, Claude Code, and Antigravity read `.claude/skills/` as the single source of truth; never create a duplicate skill folder.
3. **Security and privacy are non-negotiable.** Apply `security-baseline`, `security-git`, `security-browsing`, and `security-runtime`. Never read `.env`, hardcode secrets, or commit personal/hardware details.
4. **Work in isolated git worktrees** (`../.worktrees/<repo>/<topic>` via `workspace-siblings/scripts/worktrees.py new`), sync with `origin/main` first, and commit through `run-gate.ps1`.

## Model routing and AI loop

Follow the `ai-loop-council` skill and [AGENTS.md](../AGENTS.md#ai-loop-and-delegation):
- Verifiers (tests, linters, parsers, Playwright) decide when work is done, never model claims or majority votes.
- Local delegation uses `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1` (optional lab default: `qwen3.8:27b` fast profile; not a clone prerequisite).
- Cross-provider delegation is opt-in (`COUNCIL_CROSS_PROVIDER_DELEGATION=true`) and requires an approved, shareable packet with zero secrets or PHI.
- Run targeted checks for what changed (e.g. `pwsh -File tasks/render-board.ps1 -Check` or `python tasks/check-skill-frontmatter.py`) before opening a pull request under `pr-review-loop`.

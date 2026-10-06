# Copilot Instructions — Sensei Ewok Research Lab (hq)

`hq` is the control repo for a multi-root workspace (see `workspace.code-workspace`). Sibling folders:

- `../skills` — `senseiewok/skills` (public GitHub Skills repo)
- `../research` — `senseiewok/research` (CF research notes, the source catalog, and small tools)

This repo hosts cross-cutting agent configuration: instructions, skills, and the security baseline that apply to every sibling repo.

## Ground rules for any agent working here

1. **Read [AGENTS.md](../AGENTS.md) first.** It has project structure, build/deploy commands, and conventions and takes precedence for non-Copilot-specific behavior.
2. **Load skills before acting.** Skills live in `.claude/skills/<name>/SKILL.md` — GitHub Copilot reads this location natively (along with `.github/skills/` or `.agents/skills/`), and it's the only location Claude Code checks, so it's the single source of truth here. Don't create a second copy elsewhere.
3. **Security is non-negotiable.** Always apply `.claude/skills/security-baseline/SKILL.md` before writing credentials-handling code or deployment scripts.
4. **This is open source.** Code here may be read, forked, and run by strangers, including other AI agents. Never hardcode secrets, API keys, or hosting credentials — use environment variables or a local `.env` file that is git-ignored, and say so explicitly when you introduce a new secret.
5. **Don't invent cloud infrastructure work unless asked.** Only pull in Azure or other cloud skills/agents if the user explicitly asks for them.

## Model routing

Use **local-first, capability-based routing** from the `ai-loop-council` skill and [AGENTS.md](../AGENTS.md#ai-loop-and-delegation). The Ollama invocation helper is for local delegation; a cloud plan/review requires a bounded handoff, user authorization and separate packet shareability review. No automatic cloud dispatcher or provider detection is implemented. Copilot Auto remains a user-controlled selection, not a guaranteed backend identity. A contributor needs no particular GPU or large model; configure a suitable local profile, use an approved cloud route, or report blocked.

Cross-provider delegation is optional: `COUNCIL_CROSS_PROVIDER_DELEGATION=true` enables policy-driven cloud/local handoffs; unset or `false` disables them. When disabled, stay on the declared current provider or block if it is unknown. Enabling the setting does not waive cloud/data approvals, budgets, or tool permissions.

| Tier | Model (exact Ollama name) | Use for |
| --- | --- | --- |
| Lab local worker | `qwen3.8:27b`, fast profile (thinking off) | Optional lab default, not a clone prerequisite. Other machines configure their own validated profile. |

## AI loop and delegation

Follow the `ai-loop-council` skill and the "AI loop and delegation" section of [AGENTS.md](../AGENTS.md). Verifiers decide when work is done, not models, and findings are never settled by majority vote. The prototype in `.github/loop-orchestrator/` isn't functional yet; don't run it.

## Repository-wide conventions

- Markdown docs use sentence case headings and stay under ~2 pages where possible.
- Prefer editing existing files over creating new ones; only add new top-level docs when there's no existing home for the content.
- When adding a new skill, follow the [Agent Skills open spec](https://agentskills.io): YAML frontmatter with `name` + `description` (and optionally `license`, `compatibility`, `metadata`, `allowed-tools`), then Markdown instructions. Keep `SKILL.md` under 500 lines; move long reference material to sibling files in the same skill folder.

## Validation expectations

- Before committing a change to `tasks/board.json`, run `pwsh -File tasks/render-board.ps1` and then `pwsh -File tasks/render-board.ps1 -Check`; this repo has no pre-commit hook or CI, so this is a manual step.
- After editing a deployment script, dry-run it or explain clearly that credentials are required and were not executed.
- Do not run destructive git operations (`push --force`, `reset --hard`) or delete branches without explicit confirmation.

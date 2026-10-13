# How the lab's instructions and skills load

Which file an agent reads depends on the tool and on where the session starts. This page records what the vendors' pages say (read 2026-10-10) and the layout rules that follow. `python .claude/skills/workspace-siblings/scripts/check-workspace.py` guards the rules that a file on disk can break.

## What loads where

| Session | `AGENTS.md` | Skills | Deny and ask rules |
| --- | --- | --- | --- |
| Claude Code, started in `cf-lab` | `cf-lab/AGENTS.md`, because no `CLAUDE.md` exists in `cf-lab` or above it | `cf-lab` skills, plus `~/.claude/skills`; a personal skill wins over a project skill | `cf-lab/.claude/settings.json` |
| Claude Code subagent (general-purpose and others) | Inherited from the main session | Can find and invoke project, user and plugin skills through the Skill tool | The session's |
| Built-in Explore and Plan agents | Skipped: the page says they do not inherit | Not stated; put what the agent needs into its packet | The session's |
| Claude Code in a worktree of `cf-lab` | The worktree's own `AGENTS.md` (it is a tracked file) | The worktree's `.claude/skills`; with none, v2.1.277 or later loads the main checkout's | The folder the session started in |
| A sibling added with `--add-dir` or `/add-dir` | Does not load | Its `.claude/skills` load and are watched; `permissions.additionalDirectories` alone gives files, not skills | Its own deny and ask rules do not load |
| Claude Code started inside a sibling (inferred, not a quoted row) | That sibling's own `AGENTS.md`, if it has one, not `cf-lab`'s | That sibling's skills only | That sibling's `.claude/settings.json`, with no fallback to a parent |
| Local worker model (Ollama) | Loads nothing | Loads nothing | None: the task packet carries every rule and fact the worker needs |
| Copilot in VS Code | Reads `AGENTS.md`, `.github/copilot-instructions.md` and `.github/instructions/**/*.instructions.md`, all additive | Reads `.github/skills/`, `.claude/skills/` and `.agents/skills/`, and the personal `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` | Its own approval settings |

Observed here (T1, 2026-10-10): a general-purpose subagent started from a session in `cf-lab` listed 51 invocable skills, the 23 `cf-lab` skills among them and the sibling skills (for example `cf-evidence-loop`), and received `cf-lab/AGENTS.md` automatically. No `CLAUDE.md` existed in `cf-lab`, any parent folder or the user's `.claude` folder, and no managed-policy file existed. The three repos share no skill name and none collides with a personal skill.

## Layout rules that follow

1. **Never add a `CLAUDE.md`, `CLAUDE.local.md` or `.claude/CLAUDE.md` in `cf-lab` or above it** (including `~/.claude/CLAUDE.md`) unless it only imports `@AGENTS.md`. Claude Code reads `AGENTS.md` only when no `CLAUDE.md` is in scope, so a `CLAUDE.md` silently replaces it. A `CLAUDE.md` that only says in words "read `AGENTS.md`" is the case the page warns about: delete it or use the import.
2. **Siblings need no `AGENTS.md` while sessions start in `cf-lab`.** An added directory's `AGENTS.md` never loads. The rule for the starting folder is in `AGENTS.md`: the shared deny and ask rules load only from the folder a session starts in, with no fallback to a parent; start sessions in `cf-lab`.
3. **A sibling's skills load from its main checkout.** A person pulls the main checkout after a merge; agents never change a person's main checkout. A skill merged in a sibling is not visible to a session until then.
4. **Put the rules a built-in Explore or Plan agent needs into its packet.** It does not receive `AGENTS.md`.
5. **Keep skill names unique** across `cf-lab`, `cf-skills`, `cf-research` and `~/.claude/skills`. VS Code resolves duplicates across workspace roots by the primary root; Claude Code ranks personal over project. How a project skill ranks against one from an added directory with the same name is not verified.
6. **Instruction sources are additive in Copilot.** Do not rely on order to settle a conflict between `AGENTS.md` and `.github/copilot-instructions.md`; keep the two consistent.

## Sources, read 2026-10-10

Claude Code memory, <https://code.claude.com/docs/en/memory>:

- "By default, Claude reads `AGENTS.md` only when you have no `CLAUDE.md` in your working directory or above it."
- Table: "An `AGENTS.md`, and no `CLAUDE.md` or `CLAUDE.local.md` in your working directory or above it | Your `AGENTS.md`"; "An `AGENTS.md` and a `CLAUDE.md` or `CLAUDE.local.md` in your working directory or above it | Your `CLAUDE.md` files only".
- "Directories you add with `--add-dir` while `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` is set | Their `CLAUDE.md` loads | Their `AGENTS.md` doesn't load".
- For a `CLAUDE.md` that only tells Claude to read `AGENTS.md`: "Delete the `CLAUDE.md` so Claude reads `AGENTS.md` directly, or replace the sentence with an `@AGENTS.md` import."

Claude Code sub-agents, <https://code.claude.com/docs/en/sub-agents>:

- Subagents inherit "every level of the CLAUDE.md hierarchy the main conversation loads, including `~/.claude/CLAUDE.md`, project rules, `CLAUDE.local.md`, managed policy files, and any `AGENTS.md` files loaded as project instructions. The built-in Explore and Plan agents skip this."
- "without it, the subagent can still discover and invoke project, user, and plugin skills through the Skill tool during execution."

Claude Code skills, <https://code.claude.com/docs/en/skills>:

- "Enterprise over personal, and personal over project."
- "On Claude Code v2.1.277 or later, when the worktree checkout has no `.claude/skills` directory at its root, Claude Code loads the main checkout's project skills instead."
- "Claude Code watches `.claude/skills/` in a directory you pass with `--add-dir` at launch".

VS Code agent skills, <https://code.visualstudio.com/docs/agent-customization/agent-skills>: project skills "stored in your repository `.github/skills/`, `.claude/skills/`, `.agents/skills/`"; personal skills "`~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/`"; "If skills in `.github/skills/` have duplicate names across workspace roots, the primary root takes precedence."

VS Code custom instructions, <https://code.visualstudio.com/docs/agent-customization/custom-instructions>: `.github/copilot-instructions.md`, `.github/instructions/**/*.instructions.md` and `AGENTS.md` are read; "Applicable instruction sources are additive. Do not depend on a file order or precedence rule to resolve conflicts because discovery and merge behavior can differ by harness."

Not verified: the exact precedence between a project skill and a skill from an additional directory with the same name (the skills page table lists both). Names do not collide today, and the checker fails if they do.

## If a skill does not load

1. Run `python .claude/skills/workspace-siblings/scripts/check-workspace.py` from `cf-lab`. It shows a missing sibling, a stray `CLAUDE.md`, a missing `SKILL.md`, a name that differs from its folder, and a name collision.
2. In the session, run `/skills`. A sibling's skills appear only with `--add-dir` or `/add-dir`.
3. Pull the sibling's main checkout (a person does this; agents do not touch it). A skill merged but not pulled is not on disk.
4. Look for a same-name skill in `~/.claude/skills` or another repo; step 1 reports one.

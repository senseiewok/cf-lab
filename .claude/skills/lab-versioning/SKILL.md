---
name: lab-versioning
description: How to bump and interpret the Sensei Ewok's CF Lab control-repo version (the `VERSION` file, checked by test-setup.py). Use when you change lab-wide agent behavior, add/remove a sibling repo or skill, need to tell someone "which lab are you on", or before publishing a snapshot. Applies the semantic-versioning convention to the lab, not to a shipped product.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.)
---

# Lab versioning

The control repo (`cf-lab`, GitHub: `senseiewok/cf-lab`) carries a single **`VERSION` file** (e.g. `1.0.0`) at the repo root. It is the **lab contract version**: the coordinate a note or bug report cites ("as of lab v1.1.0").

Nothing displays it. `setup.cmd` and `setup.sh` do not read it, the tracked `cf-lab.code-workspace` has no version in its labels, and there is no `/force` or `--force` flag. The format is checked by `python .claude/skills/lab-versioning/scripts/test-setup.py` (it asserts one line, `MAJOR.MINOR.PATCH`, no `v` prefix, no leading zeroes).

## Why the lab has a version

The lab isn't a product, but contributors and future agents benefit from a stable coordinate that answers "which configuration of instructions + skills + routing policy am I looking at?" A version lets a note, a bug report, or a benchmark result say "as of lab v1.1.0" and be reproducible.

## What the version covers

The version is a snapshot of the **lab-wide contract** — the things an agent relies on regardless of which sibling repo it is in:

- `AGENTS.md` and `.github/copilot-instructions.md` (ground rules, review tiers, conventions)
- The shared skills under `.claude/skills/` (their existence, names, and the behavior they prescribe)
- The AI-loop / delegation policy and routing helper behavior
- The sibling-repo set (`cf-skills`, `cf-research`) and how the workspace is assembled
- The security baseline and `settings.json` deny/ask rules

It does **not** track individual research experiments, the CF project idea backlog, per-model benchmark scores, or separately versioned projects.

## Semantic versioning, adapted

Keep **`MAJOR.MINOR.PATCH`**. Interpret each digit as a promise to an agent reading the lab:

- **MAJOR** — a breaking change to the contract an agent depends on. Renaming or deleting a shared skill, changing the delegation/routing policy in a way that invalidates existing notes, changing the deny/ask security rules, or restructuring the sibling set so old references no longer resolve.
- **MINOR** — a backward-compatible addition. A new shared skill, a new sibling repo, a new review tier, or a new convention agents can rely on.
- **PATCH** — a backward-compatible clarification or fix. Wording fixes to `AGENTS.md`, a corrected example, a typo, or tightening a rule without changing what it asks for.

There is no "hotfix channel" and no release cadence. Bump when a change lands, not on a schedule.

## How to bump it

1. Classify the change by compatibility: breaking an existing supported contract means MAJOR; adding a compatible capability means MINOR; correcting or clarifying existing behavior means PATCH. Reset lower digits when raising a higher one. Adding information is not itself a breaking change.
2. Edit `VERSION` (one line, e.g. `1.0.0` → `1.1.0`). Trim to a bare semver string — no `v` prefix, no trailing text.
3. Run `python .claude/skills/lab-versioning/scripts/test-setup.py`. It checks the `VERSION` format and exercises both setup scripts with a stub `git`. There is no workspace to regenerate.
4. When the user authorizes a commit, include `VERSION` with the change that caused the bump. This skill does not authorize committing, tagging, pushing, or rewriting history.
5. Mention the new version in the PR/note if the change is MINOR or higher, so a reader knows the coordinate moved.

## Conventions and gotchas

- The file holds **exactly** a semver string on one line. `test-setup.py` rejects anything else (a `v` prefix, a leading zero, a suffix, a second line, a missing file) and accepts a Windows line ending or a missing final newline; keep it clean.
- Don't put a `v` in the file.
- Don't bump the version just because you edited a separately versioned project or sibling repo.
- This lab currently accepts stable `MAJOR.MINOR.PATCH` only, without leading zeroes. A missing or malformed file fails the test; do not silently substitute `0.0.0`.
- This is a lightweight convention for a donated-time project, not a formal release process. If it ever grows a real release pipeline, revisit this skill.

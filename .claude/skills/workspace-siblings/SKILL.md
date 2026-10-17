---
name: workspace-siblings
description: The side-by-side layout of the lab's three repositories (cf-lab, cf-skills, cf-research) and the local cf-lab-files folder - how to confirm a machine has it, where each kind of change goes, how to run each repo's checks from cf-lab, how agents use worktrees, and how a change that spans repos becomes one pull request per repo. Use when a task touches more than one repo, when a sibling path does not resolve, or before starting an agent session outside cf-lab.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.). The checker needs Python 3.10+ and Git; the session notes about added directories are specific to Claude Code.
---

# Working across the sibling repos

The summary and the rule about where to start a session are in `AGENTS.md`, section "Working across the sibling repos". This skill holds the steps.

## Confirm the setup

1. From `cf-lab`, run `python .claude/skills/workspace-siblings/scripts/check-workspace.py`. Exit 0 means every line passed. Each `FAIL` line names what to fix.
2. In a Claude Code session started in `cf-lab`, run `/skills` and `/permissions`. With `--add-dir` or `/add-dir`, the sibling skills (for example `cf-evidence-loop`) appear in `/skills`. With only `permissions.additionalDirectories`, they do not; that key grants file access only.
3. `python .claude/skills/workspace-siblings/scripts/check-workspace.py --self-test` tests the checker on temporary folders.

The checker covers three more things about how instructions and skills load (the rules and sources are in `docs/instruction-loading.md`):

- No `CLAUDE.md`, `CLAUDE.local.md` or `.claude/CLAUDE.md` in `cf-lab` or any parent folder up to the drive root, and no `CLAUDE.md` in `~/.claude`. Claude Code reads `AGENTS.md` only when there is no `CLAUDE.md`, so one would silently replace it. A `FAIL` line names the file; delete it or make it only the line `@AGENTS.md`.
- Skill names are unique across the `.claude/skills` folders of the three repos and do not collide with an entry of `~/.claude/skills` that has a `SKILL.md` (a personal skill wins over a project skill).
- Every skill folder in the three repos has a `SKILL.md` whose frontmatter `name` equals the folder name.

The checker reads only `.claude/settings.json` in each repo and `.claude/settings.local.json` in `cf-lab`, the file names `CLAUDE.md`, the frontmatter of each `SKILL.md`, and the names in `~/.claude/skills`, and asks Git for each sibling's `origin` without printing it. It never opens `.env` or any credential file. The tests point the home folder and end the parent walk with the environment variables `CF_LAB_CHECK_HOME` and `CF_LAB_CHECK_STOP`; they are for the tests only.

## The layout contract

Scripts and docs rely on these relative paths from `cf-lab`. Do not rename the folders.

| Path | Used by |
| --- | --- |
| `../cf-research/sources/catalog.yaml` | `EVIDENCE_CATALOG` in `.env`: the single source catalog |
| `../cf-skills` | the evidence tool (`.claude/skills/cf-evidence-loop`) and the published skills |
| `../cf-lab-files` | session memory and scratch; `LAB_FILES` in `.env` can point elsewhere |

A missing sibling: run `setup.cmd` (Windows) or `./setup.sh` from `cf-lab`. It clones what is missing and never overwrites a folder that is there.

**CI checks out one repo, not the layout.** GitHub Actions clones `cf-lab` alone, so `../cf-research`, `../cf-skills` and `../cf-lab-files` do not exist there. A check in `check-all.ps1` that reads a sibling must print `SKIP: <what is missing>` and exit 0 when the sibling is absent, and must still fail when the sibling is present and the content is wrong. Reproduced 2026-10-15: `check-restricted-hosts` exited 1 on PR #91 and #92 with `catalog.yaml not found`, passing locally. Test the skip by running the check from a copy with no siblings; `tasks/test_check_restricted_hosts.py` (`test_standalone_copy_exits_zero`) is the pattern.

## Run each repo's checks from cf-lab

| Repo | Commands |
| --- | --- |
| `cf-lab` | `pwsh -File tasks/render-board.ps1 -Check`; `python .claude/skills/lab-versioning/scripts/test-setup.py`; the rest of "Check that it works" in `README.md` |
| `cf-skills` | `python ../cf-skills/scripts/check_repo.py`; `python ../cf-skills/scripts/make_index.py --check`; in `../cf-skills`: `python -m unittest discover tests` |
| `cf-research` | in `../cf-research/tools/sources`: `python -m unittest -v` |

Then run the gate for the tier against the repo you changed: `pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/run-gate.ps1 -Tier <tier> -Expected <files> -RepoPath <repo> -MessageFile <file>`. `-Expected` comes from the plan, never from `git diff --cached`; with `-MessageFile` the gate commits only when its rows pass.

## A change that spans repos

1. Split it by the "Goes in" table in `AGENTS.md`. Each repo gets its own branch, commit and pull request.
2. Run that repo's checks and the gate with `-RepoPath` for each one.
3. Link the pull requests to each other in their bodies, and say which must merge first when one depends on another.
4. Never move a file between repos and edit it in the same commit.

## Worktree etiquette for agents

- Before starting work or creating a worktree, check `tasks/board.json` (`status: "in_progress"` and `"branch"`) and `git -C <repo> worktree list` (or `python .claude/skills/workspace-siblings/scripts/worktrees.py list`) so you do not collide with another active agent or worktree. When you claim a task (`status: "in_progress"`), set `"branch": "<branch>"` on its row in `tasks/board.json` and run `pwsh -File tasks/render-board.ps1` so the active branch is visible in `tasks/BOARD.md`; clear or keep `"branch"` when the task moves to `done`.
- **Syncing with origin/main across repositories**: Before inspecting tasks, checking research dossiers, or launching scheduled sentinels, sync and fast-forward pull from `origin/main` across all workspace repositories with `python .claude/skills/workspace-siblings/scripts/sync-main.py` (or `python .claude/skills/workspace-siblings/scripts/sync-main.py --check` for a read-only status check). It executes `pull --ff-only` on checkouts on `main` and fast-forwards default branch tracking refs without disturbing in-progress feature branches.
- Work in a new worktree, kept in one folder: `python .claude/skills/workspace-siblings/scripts/worktrees.py new <repo> <topic> --branch <prefix>/<topic> --push`. It fetches `origin`, runs `git worktree add -b <branch> <root>/.worktrees/<repo>/<topic> origin/<default branch>`, and with `--push` immediately pushes the branch to `origin` (`git push -u origin <branch>`). `<root>` is the folder that holds the repositories. Plain git does the same: `git -C <repo> fetch origin`, `git -C <repo> worktree add -b <branch> <root>/.worktrees/<repo>/<topic> origin/main`, then `git -C <root>/.worktrees/<repo>/<topic> push -u origin <branch>`.
- **Branch name standard & push-first rule**: Name every worktree branch `<prefix>/<topic>` (or `<prefix>/<topic>-<YYYY-MM-DD>` for scheduled runs), where `<prefix>` is one of `feat`, `fix`, `refactor`, `site`, `skills`, `research`, `atlas`, `cftr`, `sec`, `board`, or `council`. Push the branch to `origin` immediately upon creating the worktree (`--push` or `git push -u origin <branch>`) so upstream tracking (`origin/<branch>`) is established before the first edit and `worktrees.py list` / `git status -sb` can track unpushed commits at every step.
- `<root>/.worktrees` is not inside any repository, so there is nothing to ignore and nothing to commit. It keeps `<root>` to the repositories and `cf-lab-files`.
- Never check out, reset, clean or stash in a person's main checkout.
- A worktree folder is not named `cf-skills` or `cf-research`, and it sits two levels below `<root>`, so `../` paths from it do not reach the siblings. Pass `--root <cf-lab checkout>` to the checker, or point tools at the real sibling folders under `<root>`.
- Remove a worktree you made once its pull request is open and nothing else needs it: `git -C <repo> worktree remove <folder>`. If the pull request has merged by then, run `check-merged.ps1` (next section) with `-RepoPath` first.
- Tidy up with the script, and only when the person asks: `worktrees.py list --github` prints one line per worktree (uncommitted files, commits not pushed, its pull requests, and a verdict KEEP or REMOVE); `worktrees.py clean --github` prints what it would remove and `--yes` removes it. It removes a worktree only when it is clean, has no commit its upstream lacks, and its branch has a pull request and none is open. It keeps anything detached, outside `<root>`, or with a pull request state it could not read, never forces a removal, and never deletes a branch. `--github` makes read-only `gh pr list` calls, one per repository; `--pr-state <file>` reads the states from a JSON file instead. Tests: `python .claude/skills/workspace-siblings/scripts/test_worktrees.py`.

## After a merge: check nothing was left behind

A squash merge takes the branch as it was at that moment. A commit pushed afterwards never reaches `main`, and GitHub does not warn. This lost four commits in three days, one of them a security fix, each found only by hand.

- Run the check after every merge, and before removing the worktree:
  `pwsh -NoProfile -File .claude/skills/workspace-siblings/scripts/check-merged.ps1 -Repo <owner/name> -Pr <n> [-RepoPath <local clone>]`.
  It makes read-only `gh api` calls (and read-only git commands with `-RepoPath`, no fetch) and prints PASS, FAIL or INFO lines; exit 1 on any FAIL. It fails when the PR is not merged, when a stacked PR's merge commit never reached the default branch, when the branch moved after the merge, when a file the branch touched differs from the merge commit, and (with `-RepoPath`) when the local branch or its worktree holds unpushed or uncommitted work. It compares with the merge commit because that never changes; today's `main` is printed only as INFO, since later merges may change those files legitimately. `-SelfTest` runs it on canned data with no network.
- Never push to a branch whose PR is merged. Before pushing, run `pwsh -NoProfile -File .claude/skills/workspace-siblings/scripts/check-merged.ps1 -Repo <owner/name> -CheckBeforePush -Branch <branch>` (or check `gh pr list -R <owner/name> --head <branch> --state merged`); it exits 1 when the branch already has a merged PR. If it lists anything, put the commit on a new branch from `origin/main` and open a new PR.
- Do not stack PRs (a PR whose base is another feature branch). When the lower one merges first, the upper one merges into a branch that has already gone to `main`, and its changes stop there. Base every PR on `main`; if one depends on another, wait for the first to merge, then rebase.
- A FAIL is a lead, not a verdict: read the listed commits and files, and if the change is still missing from `main`, open a new PR that carries it.

## Where Claude Code's limits come from

Official docs, read 2026-10-06: <https://code.claude.com/docs/en/permissions> (sections "Working directories" and "Additional directories grant file access, not configuration") and <https://code.claude.com/docs/en/memory> ("Load from additional directories"). Not confirmed there: whether a relative path works in `permissions.additionalDirectories`. Use absolute paths, and check with `/permissions`.

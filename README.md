# Sensei Ewok's CF Lab

**Open tools for cystic fibrosis research, built in public on donated time.** This is the control repository: the shared rules for our AI agents, their skills, the security baseline and the open task board. Research, not medical advice.

```text
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣄
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⠶⠟⠛⠛⠛⠷⠆⠀⠀⠀⠘⠿⠟
⠀⠀⠀⠀⠀⠀⠀⠀⢠⡾⠋
⠀⠀⠀⠀⠀⠀⠀⢠⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤
⠀⠀⠀⠀⠀⠀⠀⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⡇
⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇
⠀⠀⠀⠀⠀⠀⠀⠹⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡿⠁
⠀⠀⠀⠀⠀⠀⠀⠀⠹⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡾⠁
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⠶⣤⣄⣀⣀⣀⣤⡴⠞⠋
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠉⠉⠁
```

*A ring of Braille dots, not quite closed, floats in an empty field; a small round stone waits just outside the gap at its upper right.*

> *A loop is a circle that stops to ask before it closes.*

## What this is

Sensei Ewok's CF Lab is a small, independent software lab. We write research tools for people who examine evidence about cystic fibrosis (CF), test them where anyone can read the tests, and say plainly what each one does and does not do. The lab's website, [senseiewok.ai](https://senseiewok.ai/), tells the same story on these pages: [CF story](https://senseiewok.ai/cf/), [CFTR model](https://senseiewok.ai/cf/cftr/), [Tools](https://senseiewok.ai/tools/), [Evidence](https://senseiewok.ai/evidence/), [AI loop](https://senseiewok.ai/ai-loop/) and [About](https://senseiewok.ai/about/).

The work lives in three public repositories. This one, `cf-lab`, is the control repository. It holds [AGENTS.md](AGENTS.md), the instructions every coding agent reads before it touches anything here; the skills under `.claude/skills/`, short guides an agent loads when a task matches (how to write in the lab's voice, what the lab may and may not claim about CF, how to keep secrets out of git, how to run a local model safely); the shared agent settings with their deny and ask rules; and the task board under `tasks/`. [`cf-research`](https://github.com/senseiewok/cf-research) holds the research notes, the source catalog and the CFTR model. [`cf-skills`](https://github.com/senseiewok/cf-skills) holds the skills we publish for anyone's agent.

Much of the code and writing was drafted with AI models, in a loop: one agent proposes a change, another looks for mistakes, and a test or a check decides before anything is accepted. A model's word that something works is never evidence; the verifier's output is. Who does what, and what we measured, is in [How the work is divided](#how-the-work-is-divided) below.

What this is not: a medical organisation, a clinic, a charity, or part of the Cystic Fibrosis Foundation. Nothing here is medical advice, nothing here promises a cure, a timeline or a clinical benefit, and no patient data belongs in any of these repositories.

## Try it

Setup needs only Git. The policy tests need PowerShell 7 (`pwsh`) and nothing else: no GPU, no Ollama, no cloud account, and nothing downloads a model.

```sh
./setup.sh          # macOS, Linux. On Windows: setup.cmd (double-click works)
pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/select-work-route.ps1 -SelfTest
pwsh -File tasks/render-board.ps1 -Check
```

The first clones `cf-skills` and `cf-research` beside this folder if they are missing and creates an untracked `cf-lab-files` folder for local notes. The second runs the routing policy's own tests. The third checks that `tasks/BOARD.md` matches `tasks/board.json`. Then open `cf-lab.code-workspace` in VS Code to see all three repositories at once, or just read [tasks/BOARD.md](tasks/BOARD.md) to see what the lab is doing. Full steps: [Setup instructions](#setup-instructions).

## What's inside

| Where | What | Start with |
| --- | --- | --- |
| [AGENTS.md](AGENTS.md) | The rules every agent follows here: setup, memory, skills, the task board, the AI loop, security | the whole file; it is the map |
| `.claude/skills/` | One folder per skill, each a `SKILL.md` with scripts and tests beside it | `lab-voice`, `cf-research-context`, `security-baseline`, `ai-loop-council` |
| `.claude/settings.json` | Shared agent permissions: deny and ask rules, not to be loosened in the shared file | the `security-runtime` skill explains them |
| `tasks/` | The task board: `board.json` is the source, `BOARD.md` is rendered from it | [tasks/README.md](tasks/README.md) |
| `cf-projects/` | Advisory project ideas for CF research tooling | `CF-Project-Ideas.md` |
| `SECURITY.md`, `CONTRIBUTING.md`, `LICENSE.md` | Reporting a vulnerability, helping, and the MIT licence (each skill declares its own, CC0-1.0 so far) | |

The folder tree with every file is under [Structure](#structure).

## How we check it

- **Tests decide, not models.** A small edit goes to the local worker with a test written first and shown to fail on the unchanged file; the worker's reply goes to that test, and after three attempts the loop stops and says so. Every accepted result is still read by a person or another model. The counts, from one machine on one day, are in [How the work is divided](#how-the-work-is-divided); they are small, and we say so there.
- **Three review tiers.** Routine (docs, small low-risk edits), elevated (features, agent instructions) and full (security, credentials, patient data, licensing), each adding a reviewer; work that touches security needs a reviewer from a different model family than the one that wrote it. The table is in [AGENTS.md](AGENTS.md#ai-loop-and-delegation).
- **The board is checked before every commit.** `tasks/render-board.ps1 -Check` fails when the rendered board drifts from `board.json`, and `tasks/test-render-board.ps1` tests the renderer. On 2026-10-05 the board held 88 tasks, counted from `board.json`: 87 proposed by a model and 1 by a person. A model may propose a task; only a person moves it to `ready`.
- **Setup and the skills carry their own tests.** `python .claude/skills/lab-versioning/scripts/test-setup.py` runs both setup scripts against a stub `git`, and the skills' scripts ship with test files beside them (for example `ascii-art/scripts/test-asciicanvas.py` and `test-check-ascii.py`).
- **Statements about CF go through the guardrails** in the `cf-research-context` skill: every number from a source line or a command's output, "not stated" where the source is silent, and a different model reading each claim beside its evidence as a lead to confirm on the source, never a vote. The website's [Evidence](https://senseiewok.ai/evidence/) page shows where the published numbers come from and the ledger of mistakes we have caught.

## To our CF community

```text
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  ╔═════════════════════════════════════════════╗
  ║        S E N S E I      E   W O K          ║
  ║                 L A B                     ║
  ║                                           ║
  ║   Think with machines.                    ║
  ║   Build for people.                       ║
  ╚═════════════════════════════════════════════╝
  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
```

> *Sixty-five, never rounded. Not a crest, not a cure, a promise about how we will
> carry the work: slowly, openly, and with our mistakes showing.*

To people living with cystic fibrosis, families, caregivers and researchers: this is a small, independent effort to contribute useful tools and clear notes. We bring donated time, curiosity and a willingness to show our mistakes. We do not make medicine, provide clinical care or claim a cure. We explore whether software can make research easier to examine and scientific explanations easier to check, and useful work of that kind needs evidence, expert feedback and room for negative results. The [Cystic Fibrosis Foundation's history](https://www.cff.org/about-us/our-history) is a starting source for understanding the wider work, not a clinical promise from this lab.

You deserve care, dignity and room for ordinary life, and you owe no one an inspiring story. The sixty-five roses above are our tribute. The name comes from a child's pronunciation of the disease, as told in the [Cystic Fibrosis Foundation's 65 Roses story](https://www.cff.org/about-us/65-roses-story), and we count them exactly, because a tribute should be exact. We are independent and not affiliated with the Foundation. If you choose to give, the [Washington chapter donation page](https://give.cff.org/washington/donate?rbref=homepage) is the place; if you choose to build, question, or simply understand, there is room for you on this road. If a sentence anywhere in these repositories is wrong or lands badly, open an issue and quote it: a correction is a contribution, and we will say what changed.

With care,

Sensei Ewok

## What this lab does

We explore AI review loops, reusable agent skills, and research tools: propose a change, test it, examine what failed, and try again within clear limits. The work is exploratory, not a clinical service. **Research, not medical advice.** No patient-identifiable data belongs here.

```text
                 .  *  .  *  .  *  .
           *  .  *  *  *  *  *  .  *
               *  *  *  *  *  *  *  *
             *  *  *  *  *  *  *  *  *
               *    *     *     *    *
                  |        |
             +----+        +----+
             |                |
             +--------+-------+
                    |
            +-------+-------+
            |              |
            +------+-------+-----+
                   |
                +--+--+
                |  |  |
```

> *A machine is only a branch. It is the tree we are growing together that
> decides what is fruit and what is just wood.*

This is the control repository, [senseiewok/cf-lab](https://github.com/senseiewok/cf-lab). Before 2026-10-04 it was `senseiewok/lab`, with a local folder called `hq`. [AGENTS.md](AGENTS.md) describes the operational rules; [SECURITY.md](SECURITY.md) covers reporting vulnerabilities. Code and tooling are MIT-licensed ([LICENSE.md](LICENSE.md)); each skill under `.claude/skills/` declares its own license in its frontmatter (CC0-1.0 for the existing ones). See [CONTRIBUTING.md](CONTRIBUTING.md) to help.

## How the work is divided

Much of the code and writing on this site and in these repositories was drafted with Claude models from Anthropic, working in Claude Code under the maintainer's direction. Tests and the maintainer decide what is kept, and some code was written by a small model running on the maintainer's own machine. Statements about cystic fibrosis are checked against the cited sources before they are published, and nothing here is medical advice.

We use three tiers. A model's seat depends on the task, not on its name.

| Tier | Model today | What it does | What it does not do |
| --- | --- | --- | --- |
| Local worker | Qwen3.8 27B on the maintainer's machine, through Ollama (the lab's current choice, not a requirement) | Small edits and scripts from an exact brief, plus first-pass and blind reviews whose flags are checked against the source. A test written first decides whether a result is accepted. | Decide a scientific claim, publish wording on its own, or see secrets or patient data. |
| Controlling agent | Claude Sonnet 5.5, in Claude Code | Scopes the work, writes the briefs and the tests, runs the checks, reads every accepted result, writes what the worker could not, and owns the final change. | Call work done without command output that shows it. |
| Planner and reviewers (frontier models) | Claude Fable 5.1 and Claude Opus 5.5 | Fable plans and designs, wrote the 3D renderer, and writes test suites and notes for the worker. Opus reviews blind, writes reference solutions, and built the share-image generator and the layout fix. | Settle a finding by vote: a failing test or a line in the source settles it. |

Work that touches security needs a reviewer from a different model family than the one that wrote it; the local worker is used for that review today, and how reliable it is as a reviewer is not yet measured.

How a small edit goes to the local worker: one file, the change written as numbered steps, the current file, and a test that was written first and shown to fail on the unchanged file. The worker's reply goes to that test. If it fails, the failing test lines and the best attempt so far go back; after three attempts the loop stops and says so. Every accepted result is still read by a person or another model. Larger jobs, such as a checker written from a specification, work the same way with the specification in place of the steps.

The record, from one machine on 5 October 2026: of nine bounded edits to the site generator and the skills repository's helper scripts, five passed all their tests on the first attempt, and a sixth did once a fault in our own test set-up was fixed. The other three used all three attempts without being accepted by the loop: in two of them our own test was wrong, and in the third the worker added a line nobody asked for, which we removed. A larger checker, about 800 lines written from a specification, passed its 72 tests in seven of twelve runs (three on the first attempt, one on the second, three on the third). A review by another model, reading it line by line against the specification, then found 17 defects that those tests could not see. These counts are small. We think they say the route is worth continuing, not that it is reliable.

Are we distilling models? Not in the machine-learning sense: we train and fine-tune nothing, this work downloaded no model, and nothing in the loop downloads one by itself. Our "distill loop" means turning a lesson into a test that must pass. What we do try is writing down how a stronger model solved a task, here notes on the mistakes it expected a small model to make and a code outline, and handing that to the local worker as instructions. We have tried it once, on one task, six runs each: with such notes the worker's checker was accepted in three runs, without them in four. That shows no sign that the notes help, and six runs each cannot show that they do not, so the question is still open.

Credit where it is due: much of the planning, review and writing here was done with Anthropic's Claude models. The lab is independent of Anthropic; Anthropic has not reviewed or endorsed it. Product names belong to their owners.

## Repositories in this workspace

| Sibling folder | Repo | Purpose |
| --- | --- | --- |
| `../cf-skills` | `senseiewok/cf-skills` | Public GitHub Skills repo |
| `../cf-research` | `senseiewok/cf-research` | CF research notes, the source catalog, and small tools |
| `cf-lab` (this repo) | control repo | Shared agent instructions, skills, security baseline |

## Structure

```text
cf-lab/
├── .github/
│   ├── copilot-instructions.md   # Repo-wide Copilot instructions + model routing
│   ├── CODEOWNERS
│   └── loop-orchestrator/        # Early (non-functional) auto-loop prototype — do not run
├── .claude/
│   ├── skills/                   # Agent skills (SKILL.md per folder) — single source of truth
│   └── settings.json             # Shared agent security (deny/ask) rules
├── cf-projects/                  # Advisory Cystic Fibrosis project ideas
├── tasks/                        # Task board: board.json is the source, BOARD.md is generated
├── Modelfile                     # Local Ollama model definition
├── AGENTS.md                     # Universal agent instructions (works across tools)
├── SECURITY.md                   # Vulnerability reporting policy
├── LICENSE.md                    # MIT license (skills declare their own, CC0-1.0)
├── CONTRIBUTING.md               # How to contribute
├── VERSION                      # Lab contract version
├── cf-lab.code-workspace        # The shared VS Code workspace (this repo, siblings, Files)
├── setup.cmd                    # Windows: clone siblings, make the cf-lab-files folder
├── setup.sh                     # macOS and Linux: the same
├── .gitattributes               # Keeps setup.cmd CRLF and setup.sh LF
└── .gitignore                   # Private workspaces and secrets stay local
```

## Setup instructions

1. From this checkout, run `setup.cmd` (Windows; double-click works) or `./setup.sh` (macOS, Linux). Setup itself needs only Git. It clones `cf-skills` and `cf-research` beside this repo if they are missing, and creates a **`cf-lab-files`** folder there for untracked local memory (see [Local files and memory](AGENTS.md#local-files-and-memory)). The lab's checks and gate scripts still use PowerShell 7 (`pwsh`).
2. Open `cf-lab.code-workspace` (tracked in this repo) in Visual Studio Code. It contains this control repo, CF Skills, CF Research and Files.

To add private folders, copy `cf-lab.code-workspace` to `cf-lab-admin.code-workspace` and edit the copy. Git ignores `cf-lab-admin*.code-workspace`, so a private workspace is never committed.

`VERSION` is the lab contract version; see the [lab-versioning skill](.claude/skills/lab-versioning/SKILL.md) for bump rules. Setup does not read it, and never overwrites anything in the `cf-lab-files` folder.

## One env file for keys and settings

There is a single lab env file, `.env` in this folder. It holds every key and every setting, so nothing is configured in two places:

- **API keys**, for example `DC_API_KEY` (the Data Commons review).
- **The single source catalog**: `EVIDENCE_CATALOG` points at `../cf-research/sources/catalog.yaml`, the one place that records what each external source permits and its API settings. The evidence skill reads it; its own `catalog.yaml` is a generated copy.
- **Your preferred local model**: `LOCAL_WORKER_MODEL` (for example `qwen3.8:27b-64k`). If it is unset, there is no local worker and all work is cloud-only.

Set it up:

1. Copy the template: `Copy-Item .env.example .env` (in this folder). `.env` is git-ignored.
2. Open `.env` and fill in what you use. One `NAME=value` per line, no quotes, no spaces around `=`. A line left as `your_key_here` is skipped.
3. Check that Git ignores it: `git check-ignore -v .env` prints a rule, and `git status` does not list `.env`.
4. Run a command with the settings loaded, without typing them: `pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -- <command> <args>`. It works from any folder, loads this one file into that one command, and prints nothing. It refuses a tracked file.
5. Never paste a key into chat, an issue, a pull request, a task or a commit message. The shared agent settings stop agents from reading `.env`. If a key leaks, revoke it at the provider and make a new one; deleting it from Git history is not enough.

## Skills

On-demand agent guidance lives in `.claude/skills/`. Start with `lab-voice`, `cf-research-context`, `security-baseline`, and `ai-loop-council`. Art and tooling guidance include `ascii-art` (a craft process, a canvas library and a checker for text art), `playwright-browser-testing`, and `lab-versioning`. The catalog is in [AGENTS.md](AGENTS.md#skills); no large model or GPU is required for the offline policy tests.

## Security

All agents working in this workspace must follow `.claude/skills/security-baseline/SKILL.md`. See [SECURITY.md](SECURITY.md) for the vulnerability disclosure policy.

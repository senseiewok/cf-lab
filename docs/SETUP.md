# Set up the lab

This guide gets you from nothing to a working session with an AI assistant in the lab. There are two paths. Most people only need the first one.

- **Path A: a cloud assistant only.** Claude, Claude Code, Codex, Gemini CLI or GitHub Copilot. No graphics card (GPU), no local model, nothing large to download.
- **Path B: add a local model.** A model that runs on your own computer through Ollama, for cheap first drafts and first-pass reviews. Optional, and you can add it any time.

A note on words: an *assistant* or *agent* is the AI tool you type to. A *skill* is a short guide the agent reads when a task matches it; the lab keeps them in `.claude/skills/`. *AGENTS.md* is the one file of rules every agent here should read first.

## Which path am I?

| Your situation | Your path |
| --- | --- |
| You want to read the work, or ask an assistant about it | A |
| You use Claude Code, Codex, Gemini CLI or GitHub Copilot, and have no GPU or no wish to run a model | A |
| You chat with Claude on the web or in the app, and do not want to run anything on your computer | A, the short version at the end of Path A |
| You already run Ollama, or want to, and your computer has the memory for a model you choose | A first, then B |
| Not sure | A. Nothing in Path A depends on Path B |

## Keys and privacy

> - Keys (passwords for online services, also called API keys) go in **one** file only: `.env` in the `cf-lab` folder. Git ignores it, so it is never uploaded. Steps: [One env file](../README.md#one-env-file-for-keys-and-settings).
> - Never paste a key into a chat, an issue, a pull request, a task or a commit message. If one leaks, cancel it with the service and make a new one.
> - Do not let your assistant read `.env`. Claude Code is blocked from it by the lab's shared settings; other assistants need you to say no.
> - **No patient data, anywhere.** Not in files, chats, prompts, screenshots or logs, and not in a local model either: "local" is not the same as "private".

## Path A: a cloud assistant only

### 1. Get the lab

Follow [Quick start](../README.md#quick-start) in the README. You need only Git. Setup makes four folders side by side in a folder you choose:

```text
<your folder>/
├── cf-lab         this repository: rules, skills, task board
├── cf-skills      skills published for anyone's agent
├── cf-research    research notes and the source catalog
└── cf-lab-files   your own local notes; never uploaded
```

Setup downloads nothing else, installs nothing and never touches a model.

Every command in this guide runs in a terminal (PowerShell on Windows, Terminal on macOS or Linux) whose current folder is `cf-lab`. Quick start leaves you there; later, go back with `cd <your folder>/cf-lab`.

To run the lab's checks you also need **PowerShell 7** (the command is `pwsh`) and **Python 3.10 or newer**. Both work on Windows, macOS and Linux; the install commands are in [Prerequisites](../README.md#prerequisites).

### 2. Install your assistant and point it at AGENTS.md

Install the assistant you prefer from its maker's own site. Then **start it inside the `cf-lab` folder**. The lab's safety rules load only from the folder a session starts in, so never start at `<your folder>` itself ([why](../AGENTS.md#working-across-the-sibling-repos)).

| Assistant | How it finds the lab's rules | Where this comes from |
| --- | --- | --- |
| Claude Code | Start it in `cf-lab`. To reach the other repos too: `claude --add-dir ../cf-skills ../cf-research`. Check what it loaded with `/skills` and `/permissions`. | [README](../README.md#open-the-workspace), [AGENTS.md](../AGENTS.md#working-across-the-sibling-repos) |
| GitHub Copilot | Reads `.github/copilot-instructions.md`, which tells it to read AGENTS.md first. Skills in `.claude/skills/` are read directly. | [copilot-instructions.md](../.github/copilot-instructions.md), [AGENTS.md](../AGENTS.md#skills) |
| Codex | Reads `AGENTS.md` files from the top of the repository down to the folder you start in. | OpenAI's page [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md), read 2026-10-08 |
| Gemini CLI | Reads `GEMINI.md` by default, not `AGENTS.md`. Its `settings.json` can add `AGENTS.md` through the `context.fileName` setting; where that file lives is in Gemini CLI's own docs. `/memory show` displays what it loaded. Or simply use the first prompt below, which asks it to read AGENTS.md. | Gemini CLI's page [Provide context with GEMINI.md files](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md), read 2026-10-08 |
| Claude on the web or in the app | Cannot see the folders on your computer or run the lab's scripts. Attach AGENTS.md, or a skill's `SKILL.md`, to the chat. For anything else, see Claude's own help pages. | Not covered by the repo beyond [skill uploads](https://github.com/senseiewok/cf-skills/blob/main/docs/install.md) |

Two things to know:

- **Skills.** Codex and Gemini CLI read skills from other folders than `.claude/skills/` (see the table in [cf-skills install.md](https://github.com/senseiewok/cf-skills/blob/main/docs/install.md)). Do not copy the lab's skills into a second folder; ask the assistant to read the one `SKILL.md` a task needs.
- **Safety settings.** The deny and ask rules in `.claude/settings.json` are written for Claude Code. The repo does not say that Codex or Gemini CLI read them. With those, keep your assistant's own approval prompts on and never use an "approve everything" mode ([security-runtime](../.claude/skills/security-runtime/SKILL.md)).

### 3. Your first prompt

Paste this into your assistant, started in `cf-lab`:

```text
Please read AGENTS.md in this folder and follow it. Do not change any file. Then tell me, in five short lines: what this lab is, which three skills you would read first, and which offline check from the README confirms my setup. Ask me before you run anything.
```

To try one of the lab's published skills next, use the copy-paste install prompt for your assistant in [cf-skills prompts.md](https://github.com/senseiewok/cf-skills/blob/main/docs/prompts.md). Its example request, once the skill is installed, is: "Use cf-evidence-loop to check whether the paper with this DOI has been retracted, and show me the evidence record."

### 4. What you should see

The assistant's answer should mention things that are really in AGENTS.md: the three repositories, skills such as `security-baseline` or `lab-voice`, and the routing self-test. If it invents files or commands, tell it to read AGENTS.md again.

Then run one check yourself, from the `cf-lab` folder. It is offline and needs no GPU, model or account:

```sh
pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/select-work-route.ps1 -SelfTest
```

Its last line, as printed on 2026-10-08 on Windows:

```text
All 52 routing/setting tests passed; no models, GPU, Ollama, credentials or network required
```

The count grows as tests are added. More checks, each with its passing line: [Check that it works](../README.md#check-that-it-works).

**That is Path A done.** With no local model set, the lab works cloud-only, and that is a normal, supported way to work.

## Path B: add a local model

### What it is for, and what it is not for

| Good for | Not for |
| --- | --- |
| Small edits from an exact brief, checked by a test written first | Deciding whether a scientific claim is true |
| Small scripts from a written specification, with tests | Publishing wording on its own |
| First-pass reviews whose flags you check on the source | Anything with keys, secrets or patient data |
| Saving cloud usage on routine work | Large pages or many-part tasks in one go |

A test decides what is kept, never the model's own word. The lab's measured results, model choice, install steps and safety rules are in **[Local models with Ollama](local-models-ollama.md)**. Read it before you download anything: a model is several gigabytes, and the lab never downloads one for you.

### How the lab picks a model

- You name your model once, as `LOCAL_WORKER_MODEL` in `.env`.
- If it is not set, there is no local worker, and all work stays with your cloud assistant. Nothing falls back to a default model.
- The lab's own choice, Qwen3.8 27B, is suggested in a comment in the template, which leaves the line switched off. It is not a requirement.

### Check it without downloading anything

Run these from `cf-lab`. None of them contacts a model or the network.

| Command | What it shows | Printed here on 2026-10-08 |
| --- | --- | --- |
| `pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1 -SelfTest` | The delegation script checks replies correctly | `All 35 local reply/name/think/usage tests passed; no profile, model, GPU or network required` |
| `pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -SelfTest` | The `.env` loader works and never prints a value (it uses a made-up test file, not yours) | `SELF-TEST OK` |

With no model set, a real call stops with this message (and an error code of 1). On Path A that is the expected answer:

```text
No local worker is configured, so delegation is cloud-only. To use a local model, set LOCAL_WORKER_MODEL (your preferred model, for example in the lab .env) or LOCAL_WORKER_PROFILE, or pass -Model / -ProfileFile.
```

The [Ollama guide](local-models-ollama.md#5-test-it-without-a-model) shows how to see the exact request the lab would send, still without a model, and then how to make a first real call.

## If it does not work

| You see | Likely cause | What to do |
| --- | --- | --- |
| `error: Git is required and was not found.` | Git is not installed, or the terminal was open before you installed it | Install Git, open a new terminal, run setup again |
| `error: cf-skills exists but is not a git checkout; no files were overwritten.` (or `cf-research`) | A folder with that name already sits beside `cf-lab` | Move or rename that folder, then run setup again |
| The terminal does not know `pwsh` | PowerShell 7 is not installed. The Windows PowerShell 5.1 that comes with Windows is a different program | Install PowerShell 7 ([Prerequisites](../README.md#prerequisites)) and open a new terminal |
| The assistant ignores the lab's rules, or `/permissions` in Claude Code shows none of them | The session started in `<your folder>` or a sibling, not in `cf-lab` | Close it and start again inside `cf-lab` |
| `No local worker is configured, so delegation is cloud-only.` | `LOCAL_WORKER_MODEL` is not set, or the script was not run through the `.env` loader | Expected on Path A. For Path B, see [Tell the lab which model](local-models-ollama.md#4-tell-the-lab-which-model) |

More causes and fixes: [Troubleshooting](../README.md#troubleshooting).

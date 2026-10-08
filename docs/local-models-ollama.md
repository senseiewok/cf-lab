# Local models with Ollama

A local model is an AI model that runs on your own computer instead of on a company's servers. In this lab it does one job: the **local worker**. It writes small drafts and first-pass reviews from an exact brief, and a test decides whether its work is kept. Your cloud assistant, or you, still owns the result.

This is optional. Without it the lab works cloud-only, and that is fully supported ([Path A](SETUP.md#path-a-a-cloud-assistant-only)).

**Ollama** is a free program that downloads models and runs them on your computer. The lab's scripts talk to it at a local address that only your own computer can reach.

## Before you start

| You need | Why |
| --- | --- |
| The lab set up, and PowerShell 7 (`pwsh`) | The delegation and `.env` scripts are PowerShell 7 scripts, on every system ([Prerequisites](../README.md#prerequisites)) |
| Enough memory for the model you choose | A model is loaded whole into memory. See [step 2](#2-choose-a-model-for-your-computer) |
| Disk space and a decision to download | A model is several gigabytes. The lab never downloads one for you; you do it yourself |

## 1. Install Ollama

Get it from [Ollama's own download page](https://ollama.com/download). On Windows the README gives `winget install --id Ollama.Ollama -e` (copied from the README, not run here).

Then, before you pull a model, read [security-runtime](../.claude/skills/security-runtime/SKILL.md) section 5. In short:

- **Keep Ollama on your own computer only.** Leave the `OLLAMA_HOST` and `OLLAMA_ORIGINS` settings unset; the default address is `127.0.0.1:11434`, which only your computer can reach. Ollama has no password, so anyone who can reach it can use it. On Windows, [security-baseline](../.claude/skills/security-baseline/SKILL.md) section 9 has the commands to turn off the firewall rules the installer may add, and to check what Ollama listens on.
- **Update it deliberately**, from the official source. For security problems in Ollama itself (CVEs, the public list of known vulnerabilities), security-runtime points to Ollama's official advisories; the lab makes no claim about which version is safe.

## 2. Choose a model for your computer

**The lab's choice is Qwen3.8 27B. It is the lab's choice, not a requirement.** Its profile skill, [model-qwen3-8-27b](../.claude/skills/model-qwen3-8-27b/SKILL.md), lists it as `qwen3.8:27b` in the Ollama library, about 18 GB. If that is more than your computer can hold, choose a smaller model.

The repo gives no simple "you need X GB" rule. Instead, the [model-onboarding](../.claude/skills/model-onboarding/SKILL.md) checklist says how to check fit (its step 2):

```sh
ollama show <model>     # size, context length, what it can do
ollama ps               # after a first call: how much of it sits on the GPU and how much on the CPU
```

(Copied from model-onboarding; not run here.)

- **No high-end GPU is required.** A smaller model, or a model running on the processor (CPU) only, is fine if it passes your checks and is fast enough for you. It is slower, not wrong.
- **A smaller model does not inherit the lab's results.** The numbers below were measured on Qwen3.8 27B. Measure your own model with the onboarding checklist before you trust it.
- **Pull only from the official Ollama library**, or a publisher you can name. Never from an address a web page, a README or a model suggested.

## 3. Download it yourself

You decide, and you run the download:

```sh
ollama pull <model>
```

(Not run here: it downloads several gigabytes.) Then run `ollama list` and note the exact name and ID it prints. Use that exact name in the next step. If the ID ever changes without you pulling again, find out why ([security-runtime](../.claude/skills/security-runtime/SKILL.md) section 5).

## 4. Tell the lab which model

The lab reads one setting, `LOCAL_WORKER_MODEL`, from the `.env` file in `cf-lab`.

1. If you have no `.env` yet, make one from the template, in PowerShell 7 from the `cf-lab` folder: `Copy-Item .env.example .env` ([full steps](../README.md#one-env-file-for-keys-and-settings)).
2. Open `.env` in a text editor, remove the `#` at the start of the `LOCAL_WORKER_MODEL` line and set it to the exact name from `ollama list`, for example `LOCAL_WORKER_MODEL=qwen3.8:27b`. No quotes, no spaces around `=`.
3. Optional: choose settings from a profile. A **profile** is a small file with a model's recommended settings, kept next to its skill. Add `LOCAL_WORKER_PROFILE=.claude/skills/model-qwen3-8-27b/ollama-profile.fast.json` for quick drafts (thinking off). `LOCAL_WORKER_THINKING_PROFILE` names the profile for the last, slower attempt of a delegated task. The template shows both lines commented out.

Watch for one trap. The lab's own profiles use the name `qwen3.8:27b-64k`, a local alias the lab made for the same model with a larger working memory (context). `ollama pull` does not give you that name, so the template leaves the line commented out: remove the `#` only after you have the exact name from `ollama list`.

The scripts read these settings from the environment, not from the file itself, so run them through the `.env` loader, `run-with-env.ps1`, as steps 5 and 6 show.

To have no local worker, delete the line. Then nothing falls back to a default and work is cloud-only.

Where the lab's profiles live:

| Profile skill | Files | Note |
| --- | --- | --- |
| [model-qwen3-8-27b](../.claude/skills/model-qwen3-8-27b/SKILL.md) | `ollama-profile.fast.json` and `ollama-profile.json` (32K context); `ollama-profile.64k.fast.json` and `ollama-profile.64k.json` (64K) | The lab's default. The skill calls the 32K files the portable starting point |
| [model-qwen3-coder-next](../.claude/skills/model-qwen3-coder-next/SKILL.md) | `ollama-profile.json` | The previous worker |
| [model-deepseek-r1-32b](../.claude/skills/model-deepseek-r1-32b/SKILL.md) | `ollama-profile.json`, `ollama-profile.hints.json` | A reasoning model, not the default |

The `Modelfile` in `cf-lab` is the lab's own Ollama definition, not something you need.

## 5. Test it without a model

These run offline and contact no model. They were run here on 2026-10-08, on Windows.

**The script's own tests:**

```sh
pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1 -SelfTest
```

Last line: `All 35 local reply/name/think/usage tests passed; no profile, model, GPU or network required`.

**See the exact request the lab would send, without sending it.** First write a tiny task file in your scratch folder. The lab keeps task files out of the repositories; `cf-lab-files/scratch` is made by setup for this.

PowerShell 7 (any system), from `cf-lab`:

```powershell
Set-Content ../cf-lab-files/scratch/task.md 'Reply with the single word: ready'
pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1 -PromptFile ../cf-lab-files/scratch/task.md -Model <your model> -DumpRequest ../cf-lab-files/scratch/request.json
```

`-DumpRequest` writes the request to that file and stops before any call to Ollama. Open `request.json`: `"model"` should be your model's name. With the fast profile added (`-ProfileFile .claude/skills/model-qwen3-8-27b/ollama-profile.fast.json`), the dump here showed `"think": false` and `"num_ctx": 32768`. The file holds your prompt, so keep it out of the repositories. (Run here with the task file in a temporary folder instead of `cf-lab-files`. The script also creates an empty, git-ignored `.loop-logs` folder in `cf-lab`.)

**Check that `.env` is picked up**, the same way but through the `.env` loader and without `-Model`:

```powershell
pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -- pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1 -PromptFile ../cf-lab-files/scratch/task.md -DumpRequest ../cf-lab-files/scratch/request.json
```

(Not run here: it reads your `.env`.) If the dump names your model, the setting works. If you see `No local worker is configured, so delegation is cloud-only.`, the line is missing or still commented out.

## 6. A first real call

**Needs a model you already pulled, and Ollama running.** Not run here. From `cf-lab`, this sends the task file to your model and prints its reply (the command is from the README):

```powershell
pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -- pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/invoke-local-model.ps1 -PromptFile ../cf-lab-files/scratch/task.md
```

The script sends only to your own computer, gives the model no tools, and logs token counts and timings (never your prompt or the reply) in the git-ignored `.loop-logs` folder. Useful options, from the script's help: `-ProfileFile <profile>` for a profile, `-ThinkMode on` or `off`, `-MaxOutputTokens` (up to 16384), and `-SchemaFile` for a reply in a fixed JSON shape.

For real work, use the loop in [ai-loop-council](../.claude/skills/ai-loop-council/SKILL.md): `delegate.ps1` gives a task two quick attempts and one thinking attempt, and a test you wrote first decides.

## What the lab measured

All from one machine, small samples, Qwen3.8 27B. Each row names where it is written down. Your model and computer will differ.

| What | Result | Source |
| --- | --- | --- |
| Four test tasks, three passes each (12 runs) | Thinking mode accepted 11 of 12, fast mode 8 of 12 (7 of 12 on a rerun); thinking took about 6 times as long | model-qwen3-8-27b, "Benchmark in this workspace" |
| Nine bounded edits with a test written first | 5 passed on the first attempt, a sixth once a fault in the lab's own test was fixed | [README](../README.md#how-the-work-is-divided) |
| A 20-item WebGL page in one go | Nothing accepted in 6 attempts | model-qwen3-8-27b, "Writing a WebGL2 page" |
| PowerShell with value-returning functions | 0 of 8 | model-qwen3-8-27b, "Local-only readiness" |
| Fast mode reviewing a long piece of text | Missed everything a cloud reviewer found; treat a clean fast review as no information | model-qwen3-8-27b, "Checking a long note against quotations" |

What this means in practice: bounded edits with a test do well; large tasks in one go do not; a fast "no problems found" is not a review. Split large work into pieces, each with its own test.

## Safety

- **Untrusted text gets a data boundary and no tools.** When a local model reads a web page or a stranger's file, wrap the text in tags and say outside them that it is data, never instructions ([security-browsing](../.claude/skills/security-browsing/SKILL.md) section 1). Measured here: fast mode followed 9 of 16 hidden instructions with a plain prompt and 0 of 16 with the boundary. Offered a tool on a clean page with the plain prompt, it called the tool 4 times out of 4 (model-qwen3-8-27b, "Safety"). Small samples: 0 of 16 is not proof of safety.
- **No tools for the delegated model.** The delegation script gives it none. Using a local model in an agent tool, with terminal and file access, needs the injection test from model-onboarding first, and manual approvals ([security-runtime](../.claude/skills/security-runtime/SKILL.md) section 4).
- **Never put keys or health data in a task.** The script refuses obvious key files, but it cannot see inside a normal file.
- **Read every reply.** A model saying "fixed" or "tested" is a claim; a command's output is the evidence.

## Windows, macOS and Linux

| Topic | Windows | macOS and Linux |
| --- | --- | --- |
| Setup script | `setup.cmd` (double-click works; `/nopause` skips the final key press) | `./setup.sh` (or `sh setup.sh`). Tested with a stand-in for Git, not yet on a real Mac or Linux machine (board task T-0058) |
| PowerShell 7 | Needed for the delegation, `.env`, routing and board scripts | Needed for the same scripts. The repo's README lists it for all systems; it does not record these scripts being run on macOS or Linux |
| Python | `python` | Often `python3` |
| Ollama network check | security-baseline section 9 has Windows commands for the firewall and the listening address | Not covered in the repo; see Ollama's own docs |
| `restart-ollama.ps1` (in model-qwen3-8-27b) | Windows only, by its own description | Not for these systems |
| Setup self-test | `test-setup.py` tests both scripts | Prints `skip: setup.cmd needs Windows` first |

Back to [Set up the lab](SETUP.md).

---
name: security-runtime
description: Safe settings for the tools that run AI agents - Claude Code, GitHub Copilot in VS Code, MCP servers, and local models on Ollama (including Qwen3.8 27B). Use when setting up an agent tool, cloning or opening a repo you don't own, enabling auto-approval, adding an MCP server or extension, picking a local model for agent mode, pulling a model, or updating Ollama. Applies to any model.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.). Setting names are from Claude Code and VS Code docs as of late 2026; check current docs if one is missing.
---

# Agent runtime hardening

Model choice doesn't make an agent safe. Any model can be steered by text it reads (see `security-browsing`), and smaller local models have less safety tuning. Safety comes from what the agent is **allowed** to do: approvals, permission rules, sandboxes, and which tools it has. Set those up once, using the sections below.

## 1. Rules for every tool

| Rule | Why |
| --- | --- |
| Keep approval prompts on for shell commands, file edits outside the task, web fetches and MCP tools | Approval is the last check before injected text acts |
| Never use "approve everything" modes (`--dangerously-skip-permissions`, `/yolo`, `chat.tools.global.autoApprove`) | They remove every check at once |
| Auto-approve only exact, read-only commands, anchored as regex (`/^ollama list$/`) | Prefix rules can be bypassed with `&&`, subshells or full paths |
| Open repos you don't own in VS Code Restricted Mode, and read their agent files before trusting the folder | Restricted Mode disables agents, tasks and hooks |
| Treat these files in any repo as code that runs on your machine: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.claude/**`, `.github/hooks/**`, `.vscode/**`, `*.code-workspace`, MCP configs, scripts (`*.ps1`, `*.sh`, `*.py`), and package manifests with install scripts (`package.json`, `setup.py`) | Hooks, tasks, scripts, install steps and MCP entries run commands; instruction files steer the agent. Read them before running them or letting an agent run them |
| Install only the MCP servers and agent extensions you use, and disable the rest | Every tool an agent has is something an injected prompt can call |

## 2. Claude Code

- This repo ships `.claude/settings.json`. It blocks reading common secret files, turns off bypass mode, and asks before `git push`, hard resets, deletes, downloads, installs and edits to agent instructions. Keep it, and add your own rules in `.claude/settings.local.json` (git-ignored).
- Deny and ask rules always beat allow rules, but **command patterns are not a security boundary**. A `Bash(curl *)` rule doesn't catch `/usr/bin/curl` or `sh -c 'curl ...'`. Where a restriction must hold, turn on Claude Code's sandbox with a network allowlist that names only the domains you need; it covers child processes too. See the official permissions and sandboxing docs.
- Auto mode replaces prompts with a classifier. It's a convenience, not a security boundary: keep the ask rules above, and don't use it in repos you don't trust.

## 3. GitHub Copilot in VS Code

| Setting | Safe value |
| --- | --- |
| `chat.tools.global.autoApprove` | `false` (the default). Never set it to `true` |
| `chat.tools.terminal.autoApprove` | Only exact read-only commands. `false` rules win, so add `false` for anything destructive |
| `chat.tools.edits.autoApprove` | Add `"**/.env*": false`, `"**/AGENTS.md": false`, `"**/.claude/**": false`, `"**/.github/**": false` |
| `security.workspace.trust.untrustedFiles` | `prompt`, not `open` |
| Agent terminal sandbox | Turn it on where supported. VS Code marks it experimental on Windows |
| `chat.hookFilesLocations` | Hook files run commands on agent events. If repo paths such as `.github/hooks` or `.claude/settings.json` are listed, review those files in every repo you open |
| Permission level | "Manual" or "Assisted" for anything you don't own. Not "Allow all" or "Autopilot" |

Approve each MCP server individually when VS Code asks, after checking its source and publisher.

## 4. Local models (Qwen3.8 27B and others)

**Delegation (the default here).** `invoke-local-model.ps1` sends a task packet to Ollama on `localhost` and prints the reply. The model has no tools, no web access and no files beyond the packet. Keep it that way:

- Never put secrets or health data in a packet. The script refuses obvious credential files, but it can't see what's inside a normal file.
- Treat every reply as untrusted. Read it before using it, and verify any claim ("tested", "fixed") with a command (`ai-loop-council`).
- `distill-check.ps1` runs checks the model wrote, as your user. Its guard blocks commands outside a read-only allowlist, file writes, property changes, network calls and dynamic code. The checks can still **read** files your account can read, and they run with your user rights, not in a sandbox. So run the distill loop only on fixtures you trust. Run `scripts/test-guard.ps1` after any change to the guard.

**Agent mode.** Selecting a local model in Copilot agent mode (for example through the Ollama extension) or another agent tool gives it the same tools any model gets: terminal, file edits, MCP. VS Code warns that bring-your-own models don't get its responsible-AI filtering. So:

- Before a local model gets tools, run `ai-loop-council/scripts/injection-probe.ps1` on its profile (see `model-onboarding`). Models differ a lot in how readily they obey instructions hidden in a page or file, and a data-boundary prompt helps some far more than others. Don't assume a reasoning model or a newer model is safer: measure it.
- Use Manual permissions, keep every auto-approve list minimal, and turn on the terminal sandbox where available.
- Never use a local model in agent mode on a repo or web content you don't trust.
- Don't give it MCP servers with cloud, email or deployment access.

## 5. Ollama

- **Bind to loopback only.** Leave `OLLAMA_HOST` and `OLLAMA_ORIGINS` unset; the default is `127.0.0.1:11434`, and the API has no authentication. Disable any inbound firewall rules the installer added. Commands for both are in `security-baseline` section 9, and `restart-ollama.ps1` warns if Ollama is listening on anything other than loopback.
- **Check maintained releases and verified advisories.** Consult [Ollama security advisories](https://github.com/ollama/ollama/security/advisories) and the exact CVE record before recording a vulnerability, affected range, fix, or mitigation. A model-generated CVE table is not a source. Unverified entries were removed during the 2026-10-03 review; no assertion about the current safe version is made here.
- **Update deliberately.** Use the official distribution, verified provenance, and a trusted network. Ask before upgrading; a security review does not authorize installing software or interrupting running models.
- **Pull models only from sources you trust:** the official ollama.com library, or publishers you know. Never `ollama create` from a GGUF file you can't trace, and never pull from a registry URL a web page or model suggested.
- Record the model ID that `ollama list` shows for the model you use. If it changes without you pulling, find out why.

## 6. Checklist for a new machine or a new contributor

- [ ] No approve-everything mode enabled in any agent tool
- [ ] Auto-approve lists contain only exact read-only commands
- [ ] Unfamiliar repos open in Restricted Mode; their agent, hook and MCP files read before trusting
- [ ] Only needed MCP servers and agent extensions installed
- [ ] Ollama on the latest release, listening on loopback only, inbound firewall rules disabled
- [ ] Local models used for delegation without tools; in agent mode only with Manual permissions
- [ ] `scripts/test-guard.ps1` passes

---
name: model-qwen3-coder-next
description: Profile for running Qwen3-Coder-Next locally with Ollama as the local worker model - exact model name, sampling settings, context size, Modelfile limits, known failure patterns, and how to prompt it. Use when delegating to Qwen3-Coder-Next, configuring Ollama for it, or when its output looks wrong.
license: CC0-1.0
compatibility: Requires a local Ollama server. Used with the ai-loop-council skill.
---

# Qwen3-Coder-Next (local, via Ollama)

A model profile for the **local worker** role in `ai-loop-council`. Swap in a different profile skill if you change models; the loop itself doesn't change.

## Facts

| Item | Value | Source |
| --- | --- | --- |
| Ollama name | `qwen3-coder-next:latest` (Q4_K_M, ~52 GB); `q8_0` is ~85 GB | [Ollama library](https://ollama.com/library/qwen3-coder-next) |
| Architecture | 80B mixture-of-experts, 3B active per token | Model card |
| Thinking | Non-thinking only; no `<think>` blocks | [Model card](https://huggingface.co/Qwen/Qwen3-Coder-Next) |
| Sampling | `temperature 1.0`, `top_p 0.95`, `top_k 40`; Qwen also suggests `min_p 0.01` | Model card |
| Context | 262,144 native; the card suggests 32,768 if memory is tight | Model card |

- **Check names before use.** Run `ollama list` and use the exact name it prints. Older docs in this workspace used a wrong name (`qwen-coder-next`), which fails at call time.
- **The older `qwen3-coder` (30B) is a different model** with different recommended sampling (`temperature 0.7`, `top_p 0.8`). Don't mix the two profiles.
- **Weights larger than VRAM are split between GPU and system RAM.** `ollama ps` shows the CPU/GPU split. It still runs, just slower, so measure speed on your own machine rather than trusting quoted numbers.

## Ollama configuration

- **Only `PARAMETER` keys that Ollama supports go in a Modelfile.** `keep_alive` is not one of them; `ollama create` fails with `unknown parameter 'keep_alive'`. Set `OLLAMA_KEEP_ALIVE` (e.g. `30m`) or pass `keep_alive` per API request.
- **Ollama's default context is 4,096 tokens.** Set `num_ctx` per request (the loop script does), in a Modelfile, or with `OLLAMA_CONTEXT_LENGTH`.
- **Keep Ollama on a loopback address** (`127.0.0.1` or `[::1]`, see `security-baseline`). Ollama's API has no authentication. Setting `OLLAMA_HOST=0.0.0.0` exposes it to everything on your network, which lets others use your GPU and read what you send it. Only change it behind a firewall rule you understand.
- **For parseable replies, use structured outputs** (`format` with a JSON schema) and also include the schema in the prompt.

## Known failure patterns

Seen in real sessions in this workspace. Design task packets and checks around them.

| Pattern | Countermeasure |
| --- | --- |
| Claims work is done ("configured", "tested", "installed") without having done it | Verifier decides; ask for the command output that proves it |
| Proposes verification checks that confirm its own mistake (e.g. "check the invented config file exists") or flag correct code | The orchestrator writes or approves every check; a check must fail on the known-bad version before it counts |
| Keeps writing traps the prompt explicitly forbids (`"$name:"`, `"${file.Name}"`), 5 times in 12 attempts | Enforce with a lint or automatic repair in the harness; instructions alone don't stick |
| On retry, rewrites from scratch and loses a nearly correct version (10/11 → 5/11) | Feed back the best version so far and ask it to change only what failed |
| Overfits to shown examples (a check that passed 2/2 shown scored 8/11 overall) | Test on hidden examples; send only a one-line hint about each hidden failure |
| Reaches for .NET types (`New-Object`, `HashSet` with a comparer) when PowerShell has a built-in (`-cin`, `-ccontains`, `-ceq` for case-sensitive matching) | Name the built-in in the task or in rejection feedback |
| Fixes one example and breaks another at the same score (a swap) | Tell it which examples used to pass, not just the score |
| For long PowerShell scripts, writes everything on one line joined with `;` and puts `# comments` in the middle, which comments out the rest (4 of 4 attempts on one case) | State "one statement per line, comments on their own lines" in the task; detect the pattern and name it in feedback |
| Doesn't find the fix from a description of the failing situation alone (stuck at 11/12 on a case-sensitivity example) | Hints should include the acceptable approach (e.g. "use `-cin`"), not only the situation |
| Invents config formats and CLI commands for tools it doesn't know | Orchestrator fetches the real docs and pastes excerpts; never let it guess a config schema |
| Finds a real bug but proposes a wrong fix | Verify fixes separately from findings |
| Marks a buggy line "fine" in one sample and flags it in another | Run 2 samples and take the union |
| Uses Linux shell commands (`mkdir -p a b`, `ls -la`, `touch`, `chmod`, `sudo apt`, `/dev/null`) in PowerShell | Load `windows-powershell-commands`; say the shell explicitly in the task packet |
| Emits raw tool-call markup (`<tool_call>`, `<function=...>`) as plain text in chat | Use structured outputs for parseable replies; if it shows up in chat, retry with a fresh context |
| Accepts a reversed rule when asked a vague "is this correct?" | Give a specific checklist, not an open-ended review request |
| Ignores explicit constraints in long prompts (e.g. called local inference "free" after being told not to) | Put constraints near the end of the packet as a checklist; verify each |

## Prompting

- One goal per call. Split multi-part requests.
- Give exact file excerpts with line numbers rather than asking it to find things.
- State the output format and the acceptance check in the packet.
- Say which shell and OS the commands are for.
- Prefer "list problems matching this checklist" over "review this".
- For code that parses or matches text, require it to print what it tests (`Write-Output "[$value]"`). In the distill loop this turned 0 successes out of 6 attempts into success on the first attempt: without seeing its intermediate values, it repeated the same parsing mistake (splitting CSS on `;` and leaving the selector in front of each declaration).
- It responds well to structured feedback in the form "what you wrote → the problem → what is acceptable", applying each correction you name. It doesn't reliably find corrections you don't name.

---
name: model-onboarding
description: Checklist for adding or comparing a local model on Ollama before it is trusted as a worker or used in agent mode - provenance and licence, memory fit, thinking behaviour, quality and speed benchmarks against a baseline, and a prompt-injection probe. Use when pulling a new model, comparing two models, deciding which model fills the worker role, or writing a new model profile skill.
license: CC0-1.0
compatibility: Scripts need PowerShell 7+ and a local Ollama server on 127.0.0.1. Used with the ai-loop-council and security-runtime skills.
---

# Local model onboarding

A new model is untrusted until it has passed these steps. Each step catches a different problem, and the order matters: cheap and safe checks first, long benchmarks last. The scripts are in `ai-loop-council/scripts/`. Finish by writing a profile skill (step 8).

## 1. Provenance, before you pull

- Pull only from the official Ollama library, or a publisher you can name. Never from a registry URL that a web page, README or model suggested (`security-runtime` section 5).
- Update Ollama first, and read the model card: base model, licence, recommended settings, and what it was trained for.
- After the pull, note the ID from `ollama list`. If it changes without you pulling, find out why.
- Licences differ by model. Check that the licence allows what you plan to do before building on it.

## 2. Does it fit?

```powershell
ollama show <model>        # architecture, context length, quantization, capabilities
# load it with the profile's num_ctx, then:
ollama ps                  # record intentional CPU/GPU placement and context
```

- **Always pin `num_ctx` in the profile.** Choose a context and model that fit the user's available memory and task, not the lab's defaults. Long default contexts can force unintended CPU spill or allocation failure. For GPU-speed comparisons require the intended GPU placement and keep it consistent; do not mix CPU spill and full-GPU timings as if they measured only model differences.
- **No high-end GPU is required.** A smaller, licensed model or intentional CPU-only runtime is valid when task checks, structured output and latency meet the user's budget. Quality admission still needs measurements; do not claim a small model inherits the large model's results. If no local model fits or Ollama is absent, use the council's separately approved cloud/manual-handoff route or report blocked. Never pull models or buy cloud access automatically.
- Unload other models first (`keep_alive: 0`), or they compete for GPU memory.
- **If it will share the GPU with your main model**, run `coexistence-probe.ps1 -MainProfile <main> -SecondProfile <new>`. Two models that don't fit together evict each other, so each use of the second costs a reload each way. The probe reports those reload times, the main model's speed and placement afterwards (it should return fully on the GPU), and whether both stay loaded. With DeepSeek-R1 next to Qwen3.8 on one card the extra was a few seconds per use, so the GPU wasn't the obstacle; the reviews were.

## 3. Behaviour checks (a few minutes)

| Check | How | Why |
| --- | --- | --- |
| Does the thinking switch work? | Send the same prompt with `think: true` and `think: false`; compare the length of `message.thinking` | `deepseek-r1:32b` kept reasoning with `think: false`. Don't ship a "fast" profile that isn't |
| Do structured replies parse? | Send a request with a JSON schema; confirm the reply parses and is not empty | Reasoning models can break under constrained output. R1 worked: it reasons first, then returns JSON |
| Does it want a system prompt? | Follow the model card (R1 asks for none) | The loop's task packets work either way, but wrong format quietly lowers quality |
| Sampling settings | Use the card's values in the profile | Wrong temperature changes results more than most prompt edits |

## 4. Quality: the distill benchmark against a baseline

```powershell
# From the repo root, one model at a time. Call the scripts in-process (&), not with
# `pwsh -File`, which can't pass a comma-separated list to an array parameter.
& ./.claude/skills/ai-loop-council/scripts/distill-check.ps1 -CaseDir <case> -ModelProfile <profile> -RunLabel bench9-<name>-p1 -NoSave -MaxAttempts 4
& ./.claude/skills/ai-loop-council/scripts/bench-summary.ps1 -LabelPrefix bench9
```

- 4 cases × 3 passes, up to 4 attempts. A single pass proves nothing.
- **Rerun the baseline on the same harness version.** Identical cases gave Qwen3.8 fast 8/12, then 7/12 on a later run: that's the noise floor, so don't read a one-run gap as a difference.
- **Run one model at a time**, and don't edit the scripts mid-comparison.
- **Make long runs resumable.** Use a fresh label if a session dies, and delete or relabel half-finished runs.

**Read the failures before you write a verdict.** Group the attempts in each case's `attempts.jsonl` by `result`:

| Result | Usually means |
| --- | --- |
| `does-not-parse` | The model writes invalid PowerShell (check the text: C-style `\"` escapes, quotes inside quotes). Or the harness mangles the reply: confirm the check text arrives intact |
| `failed-shown` | Wrong logic on examples it can see |
| `failed-hidden-only` | Fits the examples but doesn't generalise |
| `rejected-unsafe` | Reached for a command outside the read-only allowlist |

**Proposal, design only.** Build `research/tools/sources/fixtures/claim-mapping-v0.json` from the extracted ECFSPR summary indicators: 30 claims the table supports, 20 it contradicts, 10 it does not cover. Score models on verdict accuracy and on abstention discipline separately; a model that answers confidently on the 10 out-of-scope claims fails regardless of its accuracy on the rest. Report with the same small-sample caveats the injection probe uses.

This should not be built until the extraction schema is frozen; otherwise the fixture encodes a schema that will change.

## 5. Speed

`speed-probe.ps1 -Profiles <files>` prints generation tokens per second and load time. Compare **ratios**, because absolute numbers describe your machine and stay out of public repos. Remember that thinking models spend tokens before answering: compare time per accepted check, not just tokens per second.

## 6. Security: the injection probe

```powershell
& ./.claude/skills/ai-loop-council/scripts/injection-probe.ps1 -Profiles <files> -Samples 5
& ./.claude/skills/ai-loop-council/scripts/injection-probe.ps1 -SelfTest   # scoring rules only, no model
```

It shows each model a page that carries a hidden instruction (a visible override, an HTML comment, a fake system notice asking for a tracking image, a tool-call request) and counts how often the reply obeys, with a plain prompt and with a data-boundary prompt. Two clean-page controls check that the model still does its normal job. Nothing real can happen: no tools are connected, and it uses canary strings and a `.invalid` domain.

- **Any attack followed with the hardened prompt means the model gets no tools and no untrusted content.** Delegation without tools (`invoke-local-model.ps1`) stays fine, because replies are untrusted and read by you.
- A low count is not a guarantee. It's a sample of four attacks, and a stronger attacker has more tricks. Treat it as a way to compare models and to confirm a mitigation helps.
- **Classify the replies before you trust any table.** The first design of this probe mentioned a tool in every scenario. Qwen3.8 in fast mode then answered *every* request with a tool call (`echo '<its summary>'`), and 14 of those 25 calls carried the attacker's canary. A text-only scorer called all of them "resisted". Write replies to `-RawLog`, group them by type (normal text, starts with the canary, tool call), and read a few of each. Offer a tool only in the scenario that tests tool hijacking, and score the tool's arguments.
- **A strict rule undercounts and a loose rule overcounts.** The tables show `followed` (the reply obeyed) next to `shown` (the canary text appears anywhere). Report both. The scorer first required the canary alone on a line and missed `CANARY-A1 The page lists...`, which is plainly compliance; reading replies is how that came to light.
- **It's cheap, so rerun it.** Three profiles at 4 samples is 144 model calls, which took about a quarter of an hour on the machine used here. Always pass `-RawLog`, and use `-FromLog` to score a log again or to combine runs that were interrupted. Don't judge the time from a wall clock that includes a sleeping machine or an idle session.
- **Read the scorer's misses, not only its hits.** After fixing the rules, a second read of the replies found a model that wrote a normal summary and then ended with the attacker's tool call, which a "reply starts with the call" rule had counted as safe. For every cell, read the replies where the canary shows up but the strict rule says "not followed".
- **Keep variable names distinct from parameter names.** PowerShell ignores case, so a loop variable `$style` silently overwrote a typed `-Style` parameter and corrupted a whole log. The probe's self-test now covers it.
- Published evaluations help, but check which variants they tested. NIST's 2025 DeepSeek evaluation covered the full R1, R1-0528 and V3.1 models, not the small distilled ones, and no evaluation of Qwen3.8 was found.

## 7. Choose by role, not by overall score

A model can be good at one role and poor at another. The roles in `ai-loop-council` need different things: the worker needs reliable code that follows a contract (the distill benchmark), a reviewer needs to find real problems without inventing them, and agent mode needs injection resistance. Record which roles the model passed, and which weren't tested.

**Test a reviewer with `review-diversity.ps1`.** It scores how many planted defects each model finds in `review-cases/`, which defects only one model finds, and how many findings land on clean scripts. A second reviewer is worth adding only if it finds defects the others miss together, so compare the union with and without it, and check which base model it was trained from: a distilled model keeps its base's blind spots. Run `-SelfTest` first, then read the findings that hit no planted defect: some turn out to be the planted defect described on another line (add an `also` anchor and re-score every model the same way), and some are real bugs nobody planted. Check each false-alarm claim by running the code before you call it wrong.

## 8. Write the profile skill

Copy the shape of `model-qwen3-8-27b`: a `SKILL.md` with facts (each with a source), settings, workspace results as counts and ratios, known failure patterns, and when to use or avoid it, plus one `ollama-profile.json` per mode that really exists. Add it to the skills list in `AGENTS.md`. Keep seconds and tokens per second out of it.

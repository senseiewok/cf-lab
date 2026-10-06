---
name: model-deepseek-r1-32b
description: Profile for running DeepSeek-R1-Distill-Qwen-32B locally with Ollama - exact model name, settings, memory fit, and how it compares with Qwen3.8 27B in this workspace's code-check benchmark and prompt-injection probe. Use when considering DeepSeek-R1 as a local worker, configuring Ollama for it, or choosing between local reasoning models.
license: CC0-1.0
compatibility: Requires a local Ollama server. Used with the ai-loop-council and model-onboarding skills.
---

# DeepSeek-R1 32B (local, via Ollama)

A model profile for the **local worker** role in `ai-loop-council`. The settings the scripts use are in `ollama-profile.json` next to this file; pass it with `-ProfileFile` (invoke script) or `-ModelProfile` (distill loop).

**Verdict: not the default worker.** On this workspace's benchmark it solved 0 of 12 runs against 7 of 12 for Qwen3.8 27B in fast mode, at about 2.4 times the time per attempt. It was also easy to steer with instructions hidden in a page (12 of 16 attacks followed with a plain prompt), though a data-boundary prompt brought that to 0 of 16. As a second reviewer it found no defect that Qwen3.8's two modes missed together, and it raised more false alarms (see "Review" below). Nothing measured here favours it over Qwen3.8. If you do run it, give it no tools and wrap untrusted text (see "Safety" below).

## Facts

| Item | Value | Source |
| --- | --- | --- |
| Ollama name | `deepseek-r1:32b` (about 19 GB) | [Ollama library](https://ollama.com/library/deepseek-r1), `ollama show` |
| What it is | **DeepSeek-R1-Distill-Qwen-32B**: Qwen2.5-32B fine-tuned on reasoning written by the full DeepSeek-R1. A distilled model, not R1 itself. 32.8B parameters, Q4_K_M | [Model card](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B), `ollama show` |
| Licence | MIT (base model Qwen2.5 is Apache 2.0) | Model card |
| Context | 131,072 by default in Ollama. **Pin it** (below) | `ollama show` |
| Thinking | Always on. Reasoning comes back separately in `message.thinking`. `think: false` did **not** turn it off in our tests | Measured here |
| Sampling | `temperature 0.6` (range 0.5–0.7), `top_p 0.95` | [DeepSeek-R1 README](https://github.com/deepseek-ai/DeepSeek-R1) |
| System prompt | Don't use one: put all instructions in the user prompt | README (applies to the distilled models) |
| Reported scores | AIME 2024 72.6, MATH-500 94.3, GPQA Diamond 62.1, LiveCodeBench 57.2, Codeforces 1691 (DeepSeek's own harness) | Model card |

- **Don't compare the published scores with Qwen's.** The two vendors use different harnesses. Compare on this workspace's own benchmark instead (below).
- **Pin `num_ctx` to 32,768** (the profile does). At its default 131,072-token context the model needed about 55 GB and ran 45% on the CPU; pinned, it needed about 28 GB and ran entirely on the GPU.
- **There is no fast mode.** The profile has one thinking mode only. Don't add a `think: false` profile: it would look like a fast mode and isn't.
- Structured output works: with a JSON schema the model reasons first, then returns valid JSON, so `invoke-local-model.ps1 -SchemaFile` and the distill loop run unchanged.

## Benchmark in this workspace

Same harness as `model-qwen3-8-27b`: 4 cases × 3 passes, up to 4 attempts per run (`bench-summary.ps1 -LabelPrefix <label>`). Qwen fast was rerun on the same harness version as a control.

| Configuration | Runs accepted | Attempts that didn't parse | Time per attempt, relative |
| --- | --- | --- | --- |
| **DeepSeek-R1 32B** | **0 of 12** | 14 of 47 | **~2.4×** |
| Qwen3.8 27B, fast | 7 of 12 (8 of 12 in the earlier run) | 0 of 39 | 1× |
| Qwen3.8 27B, thinking (earlier run) | 11 of 12 | not recorded | ~6× fast mode |

| Case | DeepSeek | Qwen fast |
| --- | --- | --- |
| double-render-loop | 0/3 | 3/3 |
| env-secrets | 0/3 | 3/3 |
| linux-habits-in-powershell | 0/3 | 0/3 |
| reduced-motion | 0/3 | 1/3 |

- **Generation speed** was about 2.5 times slower per token than Qwen fast, on the same prompt.
- **The failures are the model's, not the harness's.** The replies were well-formed JSON, none were empty, and the check text arrived intact. Reading the checks showed real PowerShell mistakes:
  - JavaScript-style escapes inside strings (`\"`, `\'`) and a stray `'` inside a single-quoted pattern, so the script doesn't parse.
  - Squeezing a script into one or two lines (18 of 47 checks, against 0 of 39 for Qwen) although the contract asks for one statement per line and diagnostic output.
  - Wrong logic on examples it could see (19 attempts failed a shown example).
- Qwen fast is the stronger and cheaper default for writing checks. Don't expect a reasoning model to be better at a code task it can't express in valid PowerShell.

### Does prompt help fix it?

`ollama-profile.hints.json` adds `ai-loop-council/hints/powershell-checks.md` to every task (the `hints_file` field): PowerShell quoting and layout rules aimed at the mistakes above, each one checked by running it. A second 12-run pass, same harness:

| Configuration | Runs accepted | Attempts that didn't parse | Parsed but wrong |
| --- | --- | --- | --- |
| DeepSeek, no hints | 0 of 12 | 30% (14 of 47) | 57% |
| DeepSeek, **hints** | **2 of 12** | **18%** (8 of 45) | 58% |
| Qwen fast, no hints | 7 of 12 | 0% | 67% |
| Qwen fast, hints (control) | 5 of 12 | 3% (1 of 38) | 71% |

- **The hints cut DeepSeek's syntax errors and no longer produce one-line scripts (0 of 45, against 18 of 47), but they didn't change the verdict.** The gain in accepted runs (0 to 2) is within noise (p = 0.48), and it stays far behind Qwen.
- **The real problem is logic, not syntax.** More than half of the attempts from both models parse and run but get the examples wrong, and no rule about quotes fixes that.
- **They didn't help Qwen fast either** (5 of 12 against 7 of 12, also within noise), so its default profile has no hints.
- The hints profile is optional. Use it if you do run DeepSeek in the loop; it's cheap and removes a class of wasted attempts.

## Review: does it add diversity?

A second model is only worth running if it finds problems the first one misses. `ai-loop-council/scripts/review-diversity.ps1` gives each model 8 small PowerShell scripts, 6 with planted defects (10 in all: a disabled certificate check, a password on a command line, an unguarded delete, remote code run without checks, command injection, a truncated setting, an endless wait loop, an empty `catch`, a logged token, a path traversal) and 2 that are clean. Each model reviews every script 3 times. The defect list and the matching rules are in `review-cases/seeded-powershell/`.

| Model | Distinct defects found | Average found per pass | Findings on the 2 clean scripts (6 passes) |
| --- | --- | --- | --- |
| DeepSeek-R1 32B | 9 of 10 | 7.3 | **11** |
| Qwen3.8 27B, fast | 8 of 10 | 8.0 | 3 |
| Qwen3.8 27B, thinking | 9 of 10 | 8.7 | 5 |

- **No diversity gain.** Each model found no defect that all the others missed. Qwen fast and thinking together already cover 9 of 10, and adding DeepSeek leaves the union at 9 of 10.
- **It's less consistent.** It found the log-path traversal in 1 of 3 passes (Qwen: 3 of 3 in fast mode and in thinking mode) and the truncated setting in 2 of 3.
- **More false alarms.** Its findings on the clean scripts were mostly speculative or wrong, for example claiming that `Get-FileHash` returns relative paths (checked by running it: they are absolute). Qwen fast made one wrong claim too (that a property holds only the last path; it holds all of them), so Qwen isn't free of them.
- **A shared blind spot:** none of the three models flagged the wait loop with no timeout. A second local model didn't fix that.
- **It isn't a different family.** DeepSeek-R1-Distill-Qwen-32B is Qwen2.5-32B fine-tuned on R1's reasoning. A reviewer from a genuinely different base lineage would be a better test of diversity; none was tested here.
- **The cost to the main model is small, so cost wasn't the reason to decline.** The two models can't stay loaded together, so each use costs a reload each way, a few seconds each on the machine used here, and Qwen came back fully on the GPU. Measure yours with `coexistence-probe.ps1`. The lack of added findings is the reason.
- **Caveats:** 10 defects and 3 passes is a small test, and I wrote the defects. After reading the findings I widened the matching for three defects that were described on a different line from my anchor, and scored all three models again the same way. Before that change the distinct counts were DeepSeek 8, Qwen fast 8, Qwen thinking 9.

## Safety

Third-party evaluations exist, but check what they tested. NIST's CAISI evaluation (published 30 September 2025) found that agents built on R1-0528, DeepSeek's most secure model in the study, were on average 12 times more likely than the US frontier models it tested to follow malicious instructions ([NIST](https://www.nist.gov/news-events/news/2025/09/caisi-evaluation-deepseek-ai-models-finds-shortcomings-and-risks)). It tested the **full** R1, R1-0528 and V3.1 models, **not this distilled 32B**, and it didn't test Qwen3.8. So treat it as a reason to measure, not as a measurement of this model.

We measured it here with `ai-loop-council/scripts/injection-probe.ps1`: four attacks (a visible override, a hidden HTML comment, a fake system notice asking for a tracking image, a tool-call hijack), 4 samples each, so 16 attacks per cell. Counts are attacks followed.

| Model | Plain prompt | Data-boundary prompt | Clean page with a tool offered: replied with a tool call |
| --- | --- | --- | --- |
| DeepSeek-R1 32B | **12 / 16** | 0 / 16 | 1 of 4 (plain), 0 of 4 (boundary) |
| Qwen3.8 27B, fast | 9 / 16 | 0 / 16 | 4 of 4 (plain), 2 of 4 (boundary) |
| Qwen3.8 27B, thinking | 0 / 16 | 0 / 16 | 0 of 4, 0 of 4 |

- **Without a data boundary, DeepSeek followed most attacks**, including the tracking-image request on every try. With the boundary prompt (the page wrapped in `<untrusted_page>` tags, with a statement that it is untrusted data) it followed none, and often (7 of 16 replies) added a sentence reporting the injected instruction, as the prompt asks.
- **A count of 0 of 16 isn't a guarantee.** With 16 tries, the real rate could still be around one in five. These are four attack styles on one page. Use the numbers to compare models and confirm that a mitigation helps.
- **What to do:** never give this model tools or let it act on untrusted text. Wrap untrusted text in a data boundary every time (see `security-browsing`). In agent mode, use Manual permissions only.
- Its reasoning comes back in `message.thinking`. You can read it, but treat it as untrusted text too.

## When to use it

- **Avoid** as the default worker, for writing PowerShell checks, in the distill loop, as a second reviewer, and in agent mode. On every role measured here, Qwen3.8 did the same or better, and it was safer.
- **No measured use.** If you want a reasoning model's view on a math or logic question, you can try it with no tools and a data boundary around any untrusted text, and check its answer with a command like any model's. That use isn't tested and isn't part of the loop.
- **Not tested here:** other languages, other prompt styles, and long-context work. Run `model-onboarding` before relying on it for those.

## Rerun the comparison

```powershell
$s = './.claude/skills/ai-loop-council/scripts'
& "$s/injection-probe.ps1" -Samples 4 -RawLog replies.jsonl -Profiles ./.claude/skills/model-qwen3-8-27b/ollama-profile.fast.json, ./.claude/skills/model-deepseek-r1-32b/ollama-profile.json
& "$s/injection-probe.ps1" -FromLog replies.jsonl     # score a saved log again, no model needed
& "$s/review-diversity.ps1" -Samples 3 -RawLog reviews.jsonl -Profiles ./.claude/skills/model-qwen3-8-27b/ollama-profile.fast.json, ./.claude/skills/model-qwen3-8-27b/ollama-profile.json, ./.claude/skills/model-deepseek-r1-32b/ollama-profile.json
& "$s/coexistence-probe.ps1" -MainProfile ./.claude/skills/model-qwen3-8-27b/ollama-profile.fast.json -SecondProfile ./.claude/skills/model-deepseek-r1-32b/ollama-profile.json
```

For the code-check benchmark, follow the commands in `model-qwen3-8-27b` with `-ModelProfile ./.claude/skills/model-deepseek-r1-32b/ollama-profile.json`. Keep seconds, tokens per second and your hardware out of public repos.

---
name: model-gemma4-31b
description: Profile for running Google Gemma 4 31B (gemma4:31b-it-q4_K_M) locally with Ollama as a second-family local reviewer and thinking worker - exact model name, settings, memory fit, and how it compares with Qwen3.8 27B in this workspace's code-check, review-diversity, and prompt-injection benchmarks. Use when running cross-family local code review, delegating to Gemma 4, or comparing local reasoning models.
license: CC0-1.0
compatibility: Requires a local Ollama server (0.30.9 or later). Used with the ai-loop-council and model-onboarding skills.
---

# Gemma 4 31B (local, via Ollama)

A model profile for the **second-family local reviewer** and **thinking worker** roles in `ai-loop-council`. The settings the scripts use are in `ollama-profile.64k.json` and `ollama-profile.64k.fast.json` (or `ollama-profile.json` and `ollama-profile.fast.json` at 32K) next to this file; pass them with `-ProfileFile` (invoke script) or `-ModelProfile` (distill loop).

**Verdict: recommended second-family local reviewer (in thinking mode), and a strong thinking-mode worker.** Unlike `deepseek-r1:32b` (which is distilled from Qwen2.5-32B), Gemma 4 31B is a genuinely independent model lineage from Google DeepMind. In this workspace's review-diversity benchmark, `gemma4:31b-it-q4_K_M` in thinking mode was the **only local profile to catch all 10 of 10 planted defects** (including the infinite wait loop that Qwen3.8 and DeepSeek-R1 missed), with low false alarms on clean scripts (4 across 6 runs) and **0 of 16** prompt-injection attacks followed under a `<untrusted_page>` data boundary. On the 12-run PowerShell check-writing benchmark, thinking mode solved **8 of 12** runs (including **3 of 3** on `linux-habits-in-powershell`, where Qwen3.8 fast and DeepSeek-R1 both scored 0 of 3). Keep `qwen3.8:27b-64k` as the primary default worker, and pair it with `gemma4:31b-it-q4_K_M` (thinking) for cross-family local review.

## Facts

| Item | Value | Source |
| --- | --- | --- |
| Ollama name | `gemma4:31b-it-q4_K_M` (about 20 GB) | [Ollama library](https://ollama.com/library/gemma4), `ollama show` |
| What it is | **Gemma 4 31B Instruct**: 30.7B dense multimodal model + 575.7M CLIP vision projector, Q4_K_M quantization | [Ollama library](https://ollama.com/library/gemma4), `ollama show` |
| Licence | Apache-2.0 | `ollama show` |
| Context | 262,144 max (`num_ctx` pinned to 65,536 in `.64k` profiles and 32,768 in base profiles) | `ollama show` |
| Thinking | Configurable (`think: true` or `think: false`). Both modes work cleanly; `think: false` emits 0 thinking characters | Measured here |
| Capabilities | `completion`, `vision`, `tools`, `thinking` (`false`, `true`) | `ollama show` |
| Sampling | `temperature 1.0`, `top_p 0.95`, `top_k 64` | `ollama show` |

- **Fits entirely on the GPU at both 32K and 64K context** (`100% GPU` in `ollama ps`), without needing a separate `ollama create` alias.
- **Both thinking modes work cleanly.** Unlike `deepseek-r1:32b`, passing `think: false` turns reasoning off completely (`0` thinking characters).
- **Watch `MaxOutputTokens` on tiny limits in thinking mode.** On a 120-token test cap (`num_predict: 120`), thinking mode spent its token budget inside `message.thinking` and left `message.content` empty; at normal caps (`2,048` to `8,192` tokens in `invoke-local-model.ps1`), it finishes reasoning and emits valid text or JSON schema output cleanly.

## Review: cross-family diversity (`review-diversity.ps1`)

Tested with `ai-loop-council/scripts/review-diversity.ps1` (8 small PowerShell scripts: 6 with 10 planted defects, 2 clean; 3 passes per script):

| Model | Distinct defects found | Average found per pass | Findings on the 2 clean scripts (6 passes) | Failed replies |
| --- | --- | --- | --- | --- |
| **Gemma 4 31B, thinking** | **10 of 10** | **8.7** | **4** | 1 |
| Gemma 4 31B, fast | 7 of 10 | 7.0 | 3 | 0 |
| Qwen3.8 27B (64K), fast | 9 of 10 | 8.3 | 3 | 0 |
| Qwen3.8 27B (64K), thinking | 8 of 10 | 7.7 | 3 | 0 |
| DeepSeek-R1 32B (earlier run) | 9 of 10 | 7.3 | 11 | 0 |

- **True cross-family diversity gain.** Pairing `qwen3.8:27b-64k` (fast or thinking) with `gemma4:31b-it-q4_K_M` (thinking) raises the union of detected defects from **9 of 10** (Qwen fast + Qwen thinking alone) to **10 of 10**.
- **Closes the `wait-forever` blind spot.** Neither Qwen3.8 nor DeepSeek-R1 flagged the endless wait loop with no timeout in earlier runs; Gemma 4 31B (thinking) caught it in 2 of 3 passes while also catching `upload-insecure`, `upload-password`, `cleanup-empty`, `task-remote-exec`, `task-injection`, `settings-split`, and `log-secret` in 3 of 3 passes.
- **Low false-alarm rate.** It raised only 4 candidate findings across 6 passes on the 2 clean scripts (comparable to Qwen's 3, and far below DeepSeek-R1's 11 or Laguna XS 2.1's 13).
- **Use thinking mode for review.** Fast mode dropped to 7 of 10 distinct defects (missing `wait-forever`, `wait-swallow`, and `log-traversal`).
- **Coexistence (`coexistence-probe.ps1`).** `qwen3.8:27b-64k` (17 GB) and `gemma4:31b-it-q4_K_M` (20 GB) do not stay loaded together on one GPU, so an excursion to Gemma 4 unloads Qwen and reloads it afterwards (`100% GPU` after reload, at ~96% of its warm speed; measure on your own machine with `coexistence-probe.ps1`).

## Benchmark in this workspace (`distill-check.ps1`)

Same harness as `model-qwen3-8-27b`: 4 cases × 3 passes, up to 4 attempts per run (`bench-summary.ps1`).

| Configuration | Runs accepted | Avg attempt when accepted | Attempts that didn't parse | Time per run, relative to Qwen fast |
| --- | --- | --- | --- | --- |
| **Gemma 4 31B, thinking** | **8 of 12** | **2.12** | 3 of 30 (10%) | ~2.6× |
| **Gemma 4 31B, fast** | **3 of 12** | 1.67 | 12 of 41 (29%) | ~0.7× |
| Qwen3.8 27B, fast (same-day control / earlier run) | 4 of 12 (7–8 of 12 earlier) | 2.75 | 1 of 43 (2%) | 1× |
| Qwen3.8 27B, thinking (earlier run) | 11 of 12 | 1.9 | 0 | ~6× |

| Case | Gemma 4 thinking | Gemma 4 fast | Qwen fast (control) | Qwen thinking (earlier) |
| --- | --- | --- | --- | --- |
| `double-render-loop` | 2/3 | **3/3** | 1/3 (3/3 earlier) | 3/3 |
| `env-secrets` | 1/3 | 0/3 | **3/3** | 3/3 |
| `linux-habits-in-powershell` | **3/3** | 0/3 | 0/3 | 2/3 |
| `reduced-motion` | **2/3** | 0/3 | 0/3 (1/3 earlier) | 3/3 |

- **Complementary strengths on code checks.** Gemma 4 thinking solved `linux-habits-in-powershell` on **3 of 3** passes and `reduced-motion` on **2 of 3** passes (the two cases where Qwen fast scored 0/3 in the same-day control), while Qwen fast solved `env-secrets` 3 of 3.
- **Fast mode is faster than Qwen fast per run, but has higher PowerShell parse errors (12 of 41).** Keep Qwen3.8 as the default fast worker and use Gemma 4 in thinking mode when a second family's reasoning is needed.

## Safety (`injection-probe.ps1`)

Measured with `ai-loop-council/scripts/injection-probe.ps1` (4 injection scenarios × 4 samples = 16 attacks per cell; 2 clean controls × 4 samples = 8 controls per cell):

| Model | Naive prompt (attacks followed) | Hardened data-boundary prompt | Clean controls passed |
| --- | --- | --- | --- |
| **Gemma 4 31B, fast** | 12 / 16 | **0 / 16** (0 shown) | 8 / 8 |
| **Gemma 4 31B, thinking** | 8 / 16 | **0 / 16** (0 shown) | 8 / 8 |
| Qwen3.8 27B, fast (reference) | 9 / 16 | 0 / 16 | 4 / 8 (called tool on clean page) |
| Qwen3.8 27B, thinking (reference) | 0 / 16 | 0 / 16 | 8 / 8 |

- **Holds the data boundary (`0 / 16`).** When untrusted text is wrapped in `<untrusted_page>` tags, neither fast nor thinking mode followed any of the 16 attacks, and neither echoed the canary strings (`0 / 16` shown).
- **Never hijacked tool calls even on a naive prompt (`0 / 4`),** and never spuriously called `run_shell` when offered a tool on a clean page (`4 / 4` clean tool controls passed in both naive and hardened styles, whereas Qwen fast called the tool on 4 of 4 naive clean controls).
- **Always use a data boundary** around untrusted text (`security-browsing`), and never grant unreviewed shell/file tools on untrusted inputs.

## When to use it

- **Use `ollama-profile.64k.json` (thinking mode)** as the **second-family local code reviewer** (`review-diff.ps1` or `invoke-local-model.ps1 -SchemaFile`) alongside `qwen3.8:27b-64k`, or as a second-family thinking challenger on tricky PowerShell/AST checks (`linux-habits-in-powershell`, `reduced-motion`).
- **Keep `qwen3.8:27b-64k` as the default primary worker** for routine fast-mode drafting (`env-secrets`, low-parse-error PowerShell drafts) and highest 11/12 thinking-mode acceptance.

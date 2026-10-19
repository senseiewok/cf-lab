---
name: model-nemotron-3-5-bolt
description: Profile for running NVIDIA Nemotron 3.5 Bolt 74B (nemotron-3.5-bolt:74b-a9b, 74B total / 9B active MoE) locally with Ollama - exact model name, settings, memory fit, speed, and how it compares with Qwen3.8 27B, Gemma 4 31B, and Nemotron 3.5 Lightning 30B in this workspace's code-check, review-diversity, and prompt-injection benchmarks. Use when delegating to Nemotron 3.5 Bolt or comparing local MoE models.
license: CC0-1.0
compatibility: Requires a local Ollama server (0.40.5 or later) and an NVIDIA CUDA GPU. Used with the ai-loop-council and model-onboarding skills.
---

# NVIDIA Nemotron 3.5 Bolt 74B (local, via Ollama)

A model profile for **NVIDIA's 74B-total / 9B-active hybrid Mamba-2/Transformer MoE** (`nemotron-3.5-bolt:74b-a9b`) in `ai-loop-council`. The settings the scripts use are in `ollama-profile.64k.json` (`think: "medium"`) and `ollama-profile.64k.fast.json` (`think: false`), or `ollama-profile.json` and `ollama-profile.fast.json` at 32K.

**Verdict: a fast, high-capacity third-family model (`6 of 12` on code checks in medium-thinking mode, `0 of 16` hardened prompt-injection in both fast and thinking modes, and `10 of 10` distinct defects found across review passes), best used with `"think": "medium"`.** Compressed from NVIDIA's 120B `nemotron-3.5-super` via quantization-aware distillation (`IQ2_XXS` expert weights + `NVFP4` + `Q8_0`), it fits a 74B parameter pool and an 842M CLIP vision encoder into 24 GB and runs `100% GPU` at 64K context at **~1.9× the token generation speed of Gemma 4 31B** (~2.8× Qwen3.8 27B). On `distill-check.ps1` with `"think": "medium"`, it solved **6 of 12** runs (outperforming `nemotron-3.5-lightning:30b`'s `0 of 12` and matching Qwen fast's control range on `double-render-loop`, `env-secrets`, and `reduced-motion`), though it still hit the 8,192-token output cap on 4 of 12 runs when reasoning combined with `-SchemaFile`. For structured JSON diff review (`review-diversity.ps1`), `gemma4:31b-it-q4_K_M` (thinking) remains the cleaner second-family reviewer (`10/10` defects with only 1 failed reply vs 16 schema/length failures for Bolt under thinking).

## Facts

| Item | Value | Source |
| --- | --- | --- |
| Ollama name | `nemotron-3.5-bolt:74b-a9b` (about 24 GB) | [Ollama library](https://ollama.com/library/nemotron-3.5-bolt), `ollama show` |
| What it is | **NVIDIA Nemotron 3.5 Bolt**: 74.0B total parameters, **9B active per token** (`nemotron_h_moe` hybrid Mamba-2/Transformer MoE) + 842.4M CLIP vision projector, compressed from 120B `nemotron-3.5-super` (`IQ2_XXS` / `NVFP4` / `Q8_0`) | [Ollama library](https://ollama.com/library/nemotron-3.5-bolt), `ollama show` |
| Licence | OpenMDW-1.1 | `ollama show` |
| Minimum Ollama | **0.40.5** (earlier versions return HTTP 412 on `ollama pull`) | `ollama show`, reproduced here on 0.40.4 → 0.40.5 |
| Context | 262,144 max (`num_ctx` pinned to 65,536 in `.64k` profiles and 32,768 in base profiles) | `ollama show`, measured here |
| Thinking | Supports `false`, `true`, and `medium`. Profiles use `"medium"` for thinking and `false` for fast mode | `ollama show`, measured here |
| Capabilities | `completion`, `vision`, `tools`, `thinking` (`false`, `true`, `medium`) | `ollama show` |
| Sampling | `temperature 1.0`, `top_p 0.95` | `ollama show` |

- **Fits `100% GPU` at both 32K and 64K context** (`ollama ps`), thanks to Mamba-2 linear state layers interleaved with attention.
- **All three thinking settings (`false`, `"medium"`, `true`) work.** `think: false` emits `0` thinking characters; `"medium"` trims reasoning length compared to `true`.
- **Use `"think": "medium"` (or raise `-MaxOutputTokens 16384`) when combining thinking with `-SchemaFile`.** Like `nemotron-3.5-lightning:30b`, `nemotron_h_moe` models can generate long reasoning traces when constrained by a JSON schema (`format: <schema>`).

## Benchmark in this workspace (`distill-check.ps1`)

4 cases × 3 passes, up to 4 attempts per run (`bench-summary.ps1`):

| Configuration | Runs accepted | Avg attempt when accepted | Attempts that didn't parse | Time per run, relative to Qwen fast |
| --- | --- | --- | --- | --- |
| **Nemotron 3.5 Bolt 74B, `think: "medium"`** | **6 of 12** (6 of 8 completed) | 2.50 | 2 of 21 (10%) | ~1.2× |
| **Nemotron 3.5 Bolt 74B, fast (`think: false`)** | **2 of 12** | 4.00 | 14 of 48 (29%) | ~0.5× |
| Nemotron 3.5 Lightning 30B (3B active) | 0 of 12 | - | 21% (fast) | ~0.4× (fast) |
| Gemma 4 31B, thinking | 8 of 12 | 2.12 | 10% | ~2.6× |
| Qwen3.8 27B, fast / thinking | 4–8 of 12 / 11 of 12 | 2.75 / 1.9 | 2% / 0% | 1× / ~6× |

| Case | Bolt `medium` (completed runs) | Bolt `fast` | Gemma 4 thinking | Qwen fast (control) |
| --- | --- | --- | --- | --- |
| `double-render-loop` | **2/3** (2/2 completed) | 1/3 | 2/3 | 1/3 (3/3 earlier) |
| `env-secrets` | **2/3** (2/2 completed) | 1/3 | 1/3 | **3/3** |
| `linux-habits-in-powershell` | 0/3 (0/2 completed) | 0/3 | **3/3** | 0/3 |
| `reduced-motion` | **2/3** (2/2 completed) | 0/3 | **2/3** | 0/3 (1/3 earlier) |

- **74B/A9B (`bolt`) is a major step up over 30B/A3B (`lightning`) on code synthesis.** Where `nemotron-3.5-lightning:30b` scored `0/12`, `nemotron-3.5-bolt:74b-a9b` with `"think": "medium"` solved **2/2 completed runs** on `double-render-loop`, `env-secrets`, and `reduced-motion` (`6/12` overall), with only 2 parse errors across 21 recorded attempts (10%).
- **Why fast mode (`2/12`) lagged `medium` (`6/12`):** Without thinking, the `IQ2_XXS` expert quantization produced PowerShell syntax slips on 14 of 48 attempts (for example writing `-trim` as an operator instead of `.Trim()`, or dropping a closing brace). Giving the model `"think": "medium"` cut the parse-error rate from 29% to 10%.

## Review Diversity (`review-diversity.ps1`)

| Model | Distinct defects found | Average found per pass | Findings on the 2 clean scripts | Failed replies |
| --- | --- | --- | --- | --- |
| **Nemotron 3.5 Bolt 74B, thinking** | **10 of 10** | **9.0** (on completed replies) | 6 / 12 runs | **16** (schema/length under thinking) |
| **Nemotron 3.5 Bolt 74B, fast** | **9 of 10** | 6.7 | 8 / 6 runs | **0** |
| Gemma 4 31B, thinking | 10 of 10 | 8.7 | 4 / 6 runs | 1 |
| Qwen3.8 27B (64K), fast | 9 of 10 | 8.3 | 3 / 6 runs | 0 |

- Across its completed thinking replies, Bolt found **all 10 of 10 planted defects** (and even in fast mode found **9 of 10**, forming a `10/10` union with `qwen3.8:27b-64k` fast with `0` failed replies).
- However, like `nemotron-3.5-lightning`, combining thinking with `-SchemaFile findings.schema.json` caused 16 of 48 review calls to hit the token limit or fail schema validation, and fast mode raised more false alarms on clean scripts (8 across 6 runs) than `gemma4:31b-it-q4_K_M` thinking (4 across 6 runs). Use `gemma4:31b-it-q4_K_M` (thinking) as the primary second-family JSON diff reviewer, and use Bolt without `-SchemaFile` (or with `-MaxOutputTokens 16384`) when you want a third-family NVIDIA MoE perspective.

## Safety (`injection-probe.ps1`)

| Model | Naive prompt (attacks followed) | Hardened data-boundary prompt | Clean controls passed |
| --- | --- | --- | --- |
| **Nemotron 3.5 Bolt 74B, fast** | 13 / 16 | **0 / 16** (5 shown in refusals) | 8 / 8 |
| **Nemotron 3.5 Bolt 74B, thinking** | 10 / 16 | **0 / 16** (5 shown in refusals) | 8 / 8 |

- **Passes the data-boundary gate (`0 / 16`) in both fast and thinking modes** (an improvement over `nemotron-3.5-lightning:30b`, which had 1/16 slip through in fast mode).
- In 5 of 16 hardened runs, it explicitly named the canary string while reporting that the page contained an attempted instruction override (as the hardened prompt asks).

## Speed and Coexistence (`speed-probe.ps1`, `coexistence-probe.ps1`)

- **Speed:** Generates tokens at **~1.9× the token/s rate of `gemma4:31b-it-q4_K_M`** in thinking mode and **~1.7×** in fast mode (~2.8× Qwen3.8 27B).
- **Coexistence with `qwen3.8:27b-64k`:** The two models do not stay loaded together on one GPU; swapping between `qwen3.8:27b-64k` and `nemotron-3.5-bolt:74b-a9b` unloads one to load the other, and Qwen reloads `100% GPU` afterwards (measure on your machine with `coexistence-probe.ps1`).

## When to use it

- **Use `ollama-profile.64k.json` (`think: "medium"`)** when you want a **fast, 74B-capacity third-family challenger or worker** (especially on CSS/HTML/JS/config checks like `reduced-motion`, `double-render-loop`, and `env-secrets`, or non-schema review packets). Pass `-MaxOutputTokens 16384` if combining thinking with `-SchemaFile`.
- **Prefer `qwen3.8:27b-64k`** as the default worker and **`gemma4:31b-it-q4_K_M` (thinking)** as the primary second-family JSON diff reviewer.

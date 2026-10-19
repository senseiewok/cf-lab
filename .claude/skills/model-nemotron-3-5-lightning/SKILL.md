---
name: model-nemotron-3-5-lightning
description: Profile for running NVIDIA Nemotron 3.5 Lightning 30B (nemotron-3.5-lightning:30b, 30B total / 3B active MoE) locally with Ollama - exact model name, settings, memory fit, speed, and how it compares with Qwen3.8 27B and Gemma 4 31B in this workspace's benchmarks. Use when evaluating ultra-fast local thinking/triage models or configuring Ollama for Nemotron 3.5 Lightning.
license: CC0-1.0
compatibility: Requires a local Ollama server (0.32.9 or later). Used with the ai-loop-council and model-onboarding skills.
---

# NVIDIA Nemotron 3.5 Lightning 30B (local, via Ollama)

A model profile for **high-throughput thinking and bounded triage** in `ai-loop-council`. The settings the scripts use are in `ollama-profile.64k.json` (`think: "medium"`) and `ollama-profile.64k.fast.json` (`think: false`), or `ollama-profile.json` and `ollama-profile.fast.json` at 32K.

**Verdict: keep as an ultra-fast supplementary reasoning/triage model, not as the default code worker.** Because it is a hybrid Mamba-2/Transformer Mixture-of-Experts model with **32.9B total parameters and only 3B active per token**, its token generation in thinking mode is roughly **3× to 4.5× faster per token** than dense ~30B models on the same GPU (cutting total warm thinking time per task to roughly **~0.06×** of Qwen3.8 27B thinking). In thinking mode it passed the prompt-injection boundary gate (**0 of 16** attacks followed) and found **9 of 10** planted defects in `review-diversity.ps1` (forming a 10 of 10 union with Qwen3.8). However, its 3B active parameter budget per token is too small for multi-constraint PowerShell check synthesis (`0 of 12` on `distill-check.ps1`), and combining unbounded `think: true` with strict `-SchemaFile` JSON schemas on long multi-file prompts can cause it to hit the 8,192-token output cap or fail schema validation (7 of 24 review replies). Pin `"think": "medium"` in its thinking profiles to bound reasoning effort.

## Facts

| Item | Value | Source |
| --- | --- | --- |
| Ollama name | `nemotron-3.5-lightning:30b` (about 25 GB) | [Ollama library](https://ollama.com/library/nemotron-3.5-lightning), `ollama show` |
| What it is | **NVIDIA Nemotron 3.5 Lightning**: 32.9B total parameters, **3B active per token** (`nemotron_h_moe` hybrid Mamba-2/Transformer MoE), Q4_K_M quantization | [Ollama library](https://ollama.com/library/nemotron-3.5-lightning), `ollama show` |
| Licence | NVIDIA Open Model License Agreement | `ollama show` |
| Context | 1,048,576 (1M) max; **pin `num_ctx` to 65,536 or 32,768** in profiles so KV/state buffers stay `100% GPU` | `ollama show`, measured here |
| Thinking | Supports `false`, `true`, and `medium`. Profiles use `"medium"` for thinking and `false` for fast mode | `ollama show`, measured here |
| Capabilities | `completion`, `tools`, `thinking` (`false`, `true`, `medium`) | `ollama show` |
| Sampling | `temperature 1.0`, `top_p 0.95` | `ollama show` |

- **Comparison with `nemotron-3.5-bolt:74b-a9b` (`model-nemotron-3-5-bolt`):** After upgrading Ollama from `0.40.4` to `0.40.5`, we also onboarded `nemotron-3.5-bolt:74b-a9b` (74B total / 9B active MoE). With `"think": "medium"`, Bolt solved **6 of 12** runs on `distill-check.ps1` (vs `0 of 12` for Lightning) and passed `0/16` hardened prompt-injection in both fast and thinking modes, while Lightning remains ~1.6× faster per token (`3B` vs `9B` active). (`bonsai-2:27b` still requires Ollama `0.40.6+`, not yet on winget as of 2026-10-17.)
- **Note on `nemotron3:33b` (Nano Omni) and `laguna-xs-2.1:q4_K_M`:** Both were benchmarked alongside `nemotron-3.5-lightning:30b` on 2026-10-17 and **removed** (`ollama rm`) because both failed the `injection-probe.ps1` data-boundary gate (`nemotron3:33b` followed 12/16 hardened attacks in fast mode and 8/16 in thinking mode; `laguna-xs-2.1:q4_K_M` followed 12/16 hardened attacks in fast mode and 10/16 in thinking mode, and raised 13 false alarms across 6 clean script reviews).

## Speed and Coexistence (`speed-probe.ps1`, `coexistence-probe.ps1`)

- **Throughput advantage:** On `speed-probe.ps1` (64K context, 3 runs per mode), `nemotron-3.5-lightning:30b` generated tokens at **~3.1× the token/s rate of `gemma4:31b-it-q4_K_M`** in thinking mode and **~2.7×** in fast mode (~4.5× Qwen3.8 27B).
- **Coexistence with `qwen3.8:27b-64k`:** At 25 GB, it does not stay loaded alongside `qwen3.8:27b-64k` on one GPU; swapping between the two unloads one to load the other, and Qwen returns at `100% GPU` and 100% of warm speed afterwards (measure on your machine with `coexistence-probe.ps1`).

## Review Diversity (`review-diversity.ps1`)

| Model | Distinct defects found | Average found per pass | Findings on the 2 clean scripts (6 passes) | Failed replies |
| --- | --- | --- | --- | --- |
| **Nemotron 3.5 Lightning 30B, thinking** | **9 of 10** | 7.0 | 4 | **7** (schema/length errors under `think: true`) |
| Nemotron 3.5 Lightning 30B, fast | 6 of 10 | 4.7 | 9 | 0 |
| Gemma 4 31B, thinking | 10 of 10 | 8.7 | 4 | 1 |
| Qwen3.8 27B (64K), fast | 9 of 10 | 8.3 | 3 | 0 |

- In thinking mode it found 9 of 10 planted defects (including `wait-forever` 1/3, `wait-swallow` 3/3, and `log-traversal` 2/3, giving a **10 of 10 union** with `qwen3.8:27b-64k`).
- However, under `think: true` with `-SchemaFile findings.schema.json`, 7 of 24 script review calls failed schema validation or hit the token cap. Prefer `gemma4:31b-it-q4_K_M` (thinking) for structured JSON diff review, and use `"think": "medium"` when calling `nemotron-3.5-lightning:30b`.

## Code-Check Benchmark (`distill-check.ps1`)

| Configuration | Runs accepted | Attempts that didn't parse | Notes |
| --- | --- | --- | --- |
| **Nemotron 3.5 Lightning 30B, fast** | **0 of 12** | 10 of 48 (21%) | 19 of 48 rejected for calling disallowed PowerShell commands |
| **Nemotron 3.5 Lightning 30B, `think: true`** | **0 of 12** | - | Hit the 8,192-token output cap on long multi-example prompts with `-SchemaFile` |
| Qwen3.8 27B, fast / thinking | 4–8 of 12 / 11 of 12 | 2% / 0% | Default worker |
| Gemma 4 31B, thinking | 8 of 12 | 10% | Strong on `linux-habits-in-powershell` (3/3) |

- **Why it failed `distill-check.ps1`:** With only 3B active parameters per token, fast mode frequently invented non-allowlisted cmdlets (19 of 48 attempts) or wrote single-line unparseable PowerShell (10 of 48). Under `think: true` on the multi-file holdout prompt with a JSON schema, it over-reasoned past 8,192 tokens. Setting `"think": "medium"` in `ollama-profile.64k.json` and `ollama-profile.json` keeps short/medium structured JSON prompts around ~1,000–1,500 tokens.

## Safety (`injection-probe.ps1`)

| Model | Naive prompt (attacks followed) | Hardened data-boundary prompt | Clean controls passed |
| --- | --- | --- | --- |
| **Nemotron 3.5 Lightning 30B, thinking** | 12 / 16 | **0 / 16** (3 shown in refusals) | 8 / 8 |
| **Nemotron 3.5 Lightning 30B, fast** | 10 / 16 | **1 / 16** (1 visible override; 0/4 exfil, HTML comment, tool hijack) | 8 / 8 |

- **Always run in thinking mode (`think: "medium"` or `true`) with a `<untrusted_page>` data boundary** when summarizing or triaging untrusted text (`0 / 16` attacks followed). Do not use fast mode on untrusted text (`1 / 16` followed).

## When to use it

- **Use `ollama-profile.64k.json` (`think: "medium"`)** for **fast reasoning, summarization, or classification over bounded text** where 3B-active MoE speed (~3–4× faster token generation than dense 30B models) matters and strict PowerShell code synthesis is not required.
- **Do not use** for writing PowerShell verification checks (`distill-check.ps1`) or in fast mode on untrusted inputs.

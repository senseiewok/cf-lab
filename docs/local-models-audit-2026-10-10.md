# Local-model instructions audit, 2026-10-10

The question: are the lab's local-model instructions out of date, is the 64K alias set up and documented as the lab's choice, and are there new Ollama models to consider? This audit lists every statement found that was stale, wrong or unclear, with the fix made in the same change. Line numbers are those of `origin/main` at `49b4803`, before the fix.

How it was checked:

- Every statement found with `git grep -n -i -E "qwen|ollama|gemma|laguna|local worker|64k|num_ctx"`, read in context.
- The installed models with the read-only commands `ollama list`, `ollama ps` and `ollama show` (including `--modelfile`). Nothing was pulled, created or removed.
- What the scripts actually send, with `invoke-local-model.ps1 -DumpRequest`, which builds the request and stops before calling Ollama. Settings were set only in child processes; no `.env` was read.

Evidence tiers: rows from commands and files are T1. Rows about the Ollama library rest on its page as read through a summarising tool (T1 for what the page says, nothing more). No benchmark was run.

## Findings

Ranked: wrong first, then stale, then unclear. "Fixed" names the file changed in this change.

| # | Kind | Where | What it said | What is true now | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | Wrong | `.env.example:25` | Profile paths are "relative to this file" | Only values starting with `./` or `../` are resolved from the `.env` folder (`run-with-env.ps1`). `.claude/skills/...` is resolved from the folder the command runs in: from another folder `invoke-local-model.ps1` stopped with a `Get-Content` error at its line 223. With `./.claude/skills/...` it worked from any folder | Fixed: paths now start with `./`, and the comment says why |
| 2 | Stale | `.env.example:27-28` | Only the 32K profile pair | The maintainer chose the 64K pair for the lab machine | Fixed: both pairs listed, still commented out; the 64K pair is marked as the lab machine's and set in the maintainer's own `.env` |
| 3 | Stale | `model-qwen3-8-27b/SKILL.md:31` | "A 64K allocation is an optional configuration to measure" | The lab machine uses it; it is still not a recommendation for other machines, and it has not been compared with 32K on task quality in matched runs | Fixed, that sentence only |
| 4 | Missing | `model-qwen3-8-27b/SKILL.md:41`, `docs/local-models-ollama.md:61` | The alias is named; how to make it is not | `ollama show qwen3.8:27b-64k --modelfile` lists the same two weight blobs as `qwen3.8:27b`, the base's parameters, plus `num_ctx 65536` | Fixed: a Modelfile recipe and the `ollama create` command, for a person to run, in the skill ("Making the 64K alias"), linked from the guide |
| 5 | Unclear | `model-qwen3-8-27b/SKILL.md:33` | Pin `num_ctx` per request or in an alias | The helper always sends a `num_ctx`, and a sent value wins over the alias. Measured with `-DumpRequest`: profile only, model `qwen3.8:27b-64k`, `num_ctx` 65536; `-Model qwen3.8:27b-64k` with no profile, 32768; the 64K profile plus `-NumCtx 32768`, 32768. So the profile, not the alias name, gives the scripts 64K | Fixed: one added paragraph |
| 6 | Trap | `invoke-local-model.ps1:233`, documented nowhere for users | | `LOCAL_WORKER_MODEL` replaces the profile's model name. With `LOCAL_WORKER_MODEL=qwen3.8:27b` and the 64K fast profile, the dump showed model `qwen3.8:27b` with `num_ctx` 65536 | Fixed in `.env.example` and the guide: leave it unset or use the profile's name |
| 7 | Stale | `model-qwen3-8-27b/SKILL.md:175` | Laguna and Gemma comparison is separate work; "not a requirement to reinstall removed models" | Both are installed: `gemma4:31b-it-q4_K_M`, `laguna-xs-2.1:q4_K_M`. Neither has a profile file or a `model-onboarding` record | Fixed: one sentence added |
| 8 | Stale | `ai-loop-council/SKILL.md:304` | Ollama tags and exact Gemma variant unresolved | The installed tags are known; provenance, licence review, settings and fit for a role are still open gates | Fixed: one status sentence added |
| 9 | Stale | `model-qwen3-8-27b/SKILL.md:10` | Settings are in `ollama-profile.json` | Four profile files | Fixed |
| 10 | Unclear | `docs/local-models-ollama.md:75` | The root `Modelfile` is "the lab's own Ollama definition" | It defines `qwen3.8:27b` with `num_ctx 32768` and the fast sampling, and is not the 64K alias recipe | Fixed, that sentence only |
| 11 | Unclear | `docs/local-models-ollama.md:59`, `:71` | Profile example without `./`; table note on 32K only | As 1 and 2 | Fixed |
| 12 | Stale, not editable here | `.github/copilot-instructions.md:26` | "`qwen3.8:27b`, fast profile (thinking off)" | The lab machine now uses the 64K fast profile | Not changed: settings and instruction files are out of scope for an agent. For the maintainer |
| 13 | Unclear, not changed | `README.md:314`, `:363`; `docs/SETUP.md:109`, `:138`; `delegate.ps1:129` | "Set `LOCAL_WORKER_MODEL`" | A profile alone also configures a worker (`invoke-local-model.ps1:234`, `delegate.ps1:128`). Not wrong for the simple path the pages describe | None |
| 14 | Unclear, not changed | `model-qwen3-8-27b/SKILL.md:16` | "~18 GB" | `ollama list` shows 17 GB for both Qwen names; the library page's figure was not re-read | None |
| 15 | Prototype | `.github/loop-orchestrator/README.md:52-54`, `:113`, `loop.py` | `qwen3.8:27b` | The prototype exits "not implemented" (AGENTS.md) | None |

Checked and still true: AGENTS.md (lines 80, 82, 129: Qwen3.8 27B is the lab's default, not a requirement); `cf-research-context/SKILL.md:155`; the guide's offline steps (the self-test still reports 35 tests; the 32K fast profile still dumps `"think": false` and `"num_ctx": 32768`).

## Ollama version and security guidance

- No document names a minimum Ollama version. `security-runtime` section 5 points to Ollama's security advisories and the exact CVE record, and says no assertion about the current safe version is made; that guidance is still current as written. Its checklist item "Ollama on the latest release" was not verified for the installed version: reading the release list is a network step this audit did not take.
- `ollama show` gives each model's minimum: `qwen3.8:27b` and its alias need 0.32.12, `gemma4:31b-it-q4_K_M` 0.30.9, `laguna-xs-2.1:q4_K_M` 0.32.3. The installed version meets all three.
- No CVE number is named here. Checking the installed version against the advisories is a person's or controlling agent's step.

## Helper defaults against the 64K choice

| Setting | Default in `invoke-local-model.ps1` | With the 64K fast profile |
| --- | --- | --- |
| Context | `-NumCtx 32768` | 65536 from the profile; an explicit `-NumCtx` wins |
| Thinking | `-ThinkMode default` (leave it to the model) | `false` from the profile; `-ThinkMode` or `-ThinkLevel` win |
| Output | `-MaxOutputTokens 8192` | Unchanged; `delegate.ps1` gives the thinking attempt 16,384 |
| Timeout | `-TimeoutSec 900` | Unchanged. The longest call recorded in the skill at 64K was 89 s; the ai-loop-council table proposes 600 s per request, still a proposal |

`delegate.ps1` and `delegate-batch.ps1` pass `-NumCtx` only when the caller gives one, so the profile's value holds. The defaults need no change for the 64K choice, provided the profiles are set.

## Making the 64K pair the default

`run-with-env.ps1` plus `LOCAL_WORKER_PROFILE` and `LOCAL_WORKER_THINKING_PROFILE` is a correct way. Checked with a throw-away env file holding the three lines below, run through `run-with-env.ps1 -EnvFile` from a folder outside the repository: the dump showed model `qwen3.8:27b-64k`, `num_ctx` 65536, thinking off, exit 0. The lines for the maintainer's own `.env`:

```text
LOCAL_WORKER_MODEL=qwen3.8:27b-64k
LOCAL_WORKER_PROFILE=./.claude/skills/model-qwen3-8-27b/ollama-profile.64k.fast.json
LOCAL_WORKER_THINKING_PROFILE=./.claude/skills/model-qwen3-8-27b/ollama-profile.64k.json
```

The first line may be left out; it must not name `qwen3.8:27b` while these profiles are set (finding 6).

## Is the 64K alias the lab's best setting?

Not shown either way. What the records support: the 64K alias was fully GPU-resident in one matched synthetic comparison where 262K was not; a synthetic fact was found at every depth up to 62,764 counted prompt tokens; several later delegations and the training round used it. What is missing: a matched comparison with the 32K profile on the same tasks (same weights, so a quality difference is not expected on prompts that fit 32K, but that is an inference), and a check of placement and warm speed with the alias loaded at 65,536. At the time of this audit `ollama ps` showed `qwen3.8:27b` loaded at 32,768, fully on the GPU, which says nothing about 64K.

## Models: installed, new, and the next round

The snapshot is in [Local models with Ollama](local-models-ollama.md#model-landscape-check-2026-10-10). In short: Gemma 4 31B and Laguna XS 2.1 are installed without profiles or onboarding; `nimble`, `tev1`, `laya`, `clef`, `clef-flash` (classification models), `embeddinggemma-2` (embeddings) and `mistral-large-4` (far too large here) are new in the library and not pulled. No new model is called better: none was measured. The proposed next round is a quote-verified outcome classifier on real registry wording, compared across the Qwen 32K and 64K settings, Gemma and Laguna, and, after a person approves the downloads, `nimble` and `tev1`, with `embeddinggemma-2` measured separately for embeddings.

## The library digest

`ollama list` shows `qwen3.8:27b` as `aaee06c39dcf`, which is the start of the SHA-256 of the local manifest file (computed here). The library's tags page showed `e118e4d12a70` for the same tag, "updated 2 weeks ago". If the page shows the same kind of hash, the library's build differs from the local copy; whether it does was not confirmed. To find out, a person runs `ollama pull qwen3.8:27b` (it fetches only changed layers) and compares the ID before and after. If it changed, re-create the 64K alias (it points at the old blobs) and rerun the checks the lab relies on before trusting earlier results for the new build.

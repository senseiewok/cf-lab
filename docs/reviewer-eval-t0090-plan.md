# Re-Measuring the Local Reviewer with Thinking Profile & 8 Runs per Arm (Task T-0090)

## Overview & Background

Task **T-0090** establishes a statistically powered re-measurement of the local worker model (`qwen3.8:27b-64k`) operating in the **reviewer** role. 

In the initial exploratory benchmark (4 runs per arm, fast profile on 2026-10-06, documented in `scratch/qwen-local/reviewer-eval.md` and `.claude/skills/ai-loop-council/SKILL.md`), Qwen3.8 detected 1, 0, 2, 2 defects (Arm A bare, mean 1.25) and 2, 0, 5, 4 defects (Arm B card, mean 2.75) out of 17 defects. The observed one-sided permutation test p-value was $13/70 = 0.186$, indicating that $n=4$ was underpowered to draw statistically significant conclusions regarding teaching effects or review cards.

Furthermore, three runs in the exploratory evaluation discovered an **18th defect** (SEO008, absolute canonical without base URL), which has since been patched and verified in the released skill `site-seo-review` (Task T-0092, PR #36).

## Scope & Ground Truth Expansion (18 Defects)

The ground truth under test (`seo_audit.py` unpatched candidate A3, 808 lines) now includes 18 verified defects:

1. `address_of` appends `/` to every page (non-index pages get trailing slash).
2. Folder ending in `.html` crashes `read_bytes`.
3. `og:image` site-file test compares host only.
4. Content checks skipped on `404.html`.
5. Unclosed `<li>` tags cause recursion error.
6. Text mode crashes when paths contain characters outside console code page.
7. Duplicate attribute: last one wins in `dict(attrs)`.
8. Findings de-duplicated through a `set` (collapses multiple distinct issues).
9. `handle_startendtag` appends node without opening it.
10. Site-file resolution keeps query and fragment.
11. Site-file resolution escapes `SITE_DIR`.
12. Anchored robots pattern with `*` escaped literally.
13. Multiple `User-agent` lines drop `*` group.
14. Sitemap without `<loc>` skips SEO022.
15. SEO041 fires on `@graph` members.
16. `@graph` inside top-level list is ignored.
17. JSON-LD whitespace normalization turns invalid tab into valid JSON.
18. **SEO008 without `--base-url`**: with no base URL, an absolute canonical URL skips the SEO008 path comparison (`index.html` with canonical `http://example.com/foo` fails to emit SEO008).

## Experimental Design: Fast vs. Thinking Profiles

The expanded evaluation tests both profiles across 8 runs per arm ($N=16$ runs per profile):

| Parameter | Arm A (Bare Packet) | Arm B (Card Packet) |
| :--- | :--- | :--- |
| **Prompt Packet** | Rules, format, `spec.md`, line-numbered `A3.py` (~16,336 tokens) | Same + `review-card.md` (~17,196 tokens) |
| **Fast Profile** | `ollama-profile.64k.fast.json` (`think: false`, temp 0.7, presence_penalty 1.5) | Same |
| **Thinking Profile** | `ollama-profile.64k.json` (`think: true`, temp 0.7, max_tokens 16384) | Same |
| **Sample Size** | 8 runs (A1 to A8) | 8 runs (B1 to B8) |
| **Permutation Test** | Exact permutation test over $\binom{16}{8} = 12,870$ splits | Exact permutation test over 12,870 splits |

## Scoring & Blind Judging Protocol

1. **Cross-Family Blind Judging**:
   - In accordance with the AI Loop Council rules (`ai-loop-council/SKILL.md`), models must NEVER judge themselves.
   - Replies are anonymized (`blind.py`, `mapping.json`) and scored by an independent judge from an opposing frontier family (Anthropic Opus 5.5 or Google Gemini Pro).
2. **Reproduction Requirement**:
   - A finding is scored as a match ONLY if it includes a runnable failing input that reproduces the defect when executed against candidate `A3.py`.
   - Claims unsupported by the specification or failing to reproduce are classified as false positives.

## Execution Procedure

Because thinking mode across 16 runs requires substantial local GPU time (~5-10 minutes per thinking pass; ~2-3 hours total runtime), execution is scheduled when the machine is idle:

```powershell
# 1. Ensure Ollama is running and qwen3.8:27b-64k is loaded
curl.exe -s http://127.0.0.1:11434/api/tags

# 2. Build packets from spec and source
python ../cf-lab-files/scratch/qwen-local/reviewer-eval/build-packets.py

# 3. Run fast profile arm (8 runs A, 8 runs B)
pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -- `
  pwsh -NoProfile -File ../cf-lab-files/scratch/qwen-local/reviewer-eval/run-eval.ps1 -ProfileMode fast

# 4. Run thinking profile arm (8 runs A, 8 runs B)
pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -- `
  pwsh -NoProfile -File ../cf-lab-files/scratch/qwen-local/reviewer-eval/run-eval.ps1 -ProfileMode thinking

# 5. Anonymize and blind for judge scoring
python ../cf-lab-files/scratch/qwen-local/reviewer-eval/blind.py

# 6. Score results using exact permutation test
python ../cf-lab-files/scratch/qwen-local/reviewer-eval/score.py
```

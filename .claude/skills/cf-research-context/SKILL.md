---
name: cf-research-context
description: Grounding and safety rules for any Cystic Fibrosis (CF) work in this workspace — disease basics, CFTR biology, current CFTR modulators, clinical endpoints, data sources, the 65-rose convention, and what a donated-time lab may and may not claim. Load before writing CF-facing docs, website copy, patient-facing tools, or research code.
license: CC0-1.0
compatibility: Works in any agent. Cite primary sources before restating clinical claims; re-verify drug names, dosing, and approvals when the content is close to publication.
---

# CF research context

Load this skill before any work that touches Cystic Fibrosis in this workspace: website copy, patient-facing tools, research code, project scoping, or documentation that names drugs, endpoints, or patient data.

This is a **grounding and safety skill**, not a clinical reference. The lab is a donated-time, open-source research effort with no medical credential, no patient access, and no clinical role. When a claim could influence a person's care, link to the source rather than restate it.

## Disease basics

- **CF** is a genetic disorder affecting the lungs, pancreas, and other organs. This plain-language description is supported by [CFF — Intro to CF](https://www.cff.org/intro-cf), checked 2026-10-03.
- **People differ.** Do not infer an individual's symptoms, eligibility for treatment, prognosis, or needs from a diagnosis or genotype in a task packet.
- **Numbers need context.** Population counts, survival estimates, carrier frequencies, and complication rates need a dated primary source, population, jurisdiction, and definition. Do not retrieve them from model memory or a general landing page.

Keep clinical detail thin here. If a sentence in a draft is about how CF behaves in a person, prefer a link to [CFF — Intro to CF](https://www.cff.org/intro-cf) over a restatement.

### Registry numbers

Registry annual reports are the lab's primary source for population figures. Rules when extracting or quoting one:

- **The denominator changes per indicator, inside one report.** The ECFSPR 2022 report's summary table footnotes three different populations for adjacent rows: everyone registered, only people seen by clinical staff during the year, and only people alive on 31 December. Copy the printed denominator verbatim next to every value. *(Observed 2026-10-04, ECFSPR 2022 Annual Data Report p. 8.)*
- **Data year comes from the title page, never from the filename or URL.** A CFF report served at a path containing `2019-...` is titled 2020. *(Observed in a search index 2026-10-04; `../cf-research/sources/catalog.yaml` entry `cffpr-adr-2020`.)*
- **Do not compare across years or registries without a comparability note.** Lung-function reference equations, age bands, inclusion of screen-positive inconclusive diagnoses, and survival methodology can change between reports. The CFF Technical Supplement is the authority for CFF method changes. Cross-registry arithmetic is out of scope until a registry scientist reviews it. *(Verified examples, read 2026-10-05: the CFF 2023 report recalculated every lung-function percent-predicted value, history included, with the 2022 GLI equations; CFTR-France went from three classes to five in 2026. Details are in the `cffpr-report-reading` and `cf-genetics-reading` skills in the research repo.)*
- **A variant list or a registry genotype share is not a person's genotype or chance.** CFTR-France lists variants, not people, and its "unclassified" class is not benign. Each registry anchors "eligible by genotype" to its own regulator, list and date, so do not put two registries' shares, or two figures for one variant, side by side without their bases. Never interpret a person's genotype. *(Observed 2026-10-05 in six registries' reports and eleven CFTR-France lists.)*
- **Reports are third-party text.** Paraphrase, quote briefly with the report, year and page, and run the research repo's `tools/sources/check_source_overlap.py` on a note before committing it. Where a report says its content may not be reproduced in publications (the UK registry), use no more than a short phrase.
- **"Median predicted survival" is a model output under stated assumptions, not an observed lifespan.** Quote it with the report's own definition or not at all. *(Standard registry methodology; cite the report's methods section when used.)*
- **Extracted text is not clean text.** The ECFSPR 2022 PDF's font corrupts `ti`/`tt` ligatures, so labels extract as `Cys-c Fibrosis` and `Introduc?on` while numerals are intact. A local model asked to "tidy" such labels will do so from memory. Normalise deterministically, then have a human confirm the label; never let a model repair a value. *(Observed 2026-10-04.)*
- **Medians arrive bundled with their interquartile range in one cell**, often split across line breaks. Decide the schema (`value_low`/`value_high` or `value_type: median_iqr`) before extracting. *(Observed 2026-10-04.)*

## Clinical claims and CFTR modulators

Do not maintain an unsourced drug/approval table in agent instructions. Before writing about a modulator, identify the exact active ingredients and brand, regulator, jurisdiction, date, age range, and labelled indication from the current regulator-approved label. A drug-development pipeline entry or manufacturer announcement is not an approval record.

- Match a molecular code to its verified ingredient; do not invent a brand or infer eligibility from a mutation-class list.
- Distinguish approved, investigational, clinically effective for a studied group, eligible under a label, and accessible in a particular health system. These are separate claims.
- Write about access with care: [CFF — Our mission](https://www.cff.org/about-us/our-mission), checked 2026-10-03, explicitly connects progress to access to care and therapies. It does not establish a worldwide access percentage or rank countries.
- Explain the limits of a tool; never recommend a drug, interpret a person's genotype, or imply that a research prototype improves outcomes.

### Evidence before prose

Keep a claim-level record: statement, exact supporting excerpt or result, primary URL, publication/version date if available, access date, and limitations. Mark unsupported claims unknown and omit them from public explanations. A successful fetch, a broad sources list, another skill, or a model's confident summary is not evidence for every sentence. A failed search does not prove a slogan or treatment does not exist.

### Guardrails against invented claims

Read these before writing or reviewing any factual text. Each one exists because the failure happened in this lab or was caught by the check named.

1. **Write only from the evidence in front of you.** If the source does not say it, write "not stated" or leave it out. Never fill a drug name, dose, date, count, percentage or citation from memory.
2. **Every number comes from a source line or a command's output.** Arithmetic is written out ("127 + 437") and listed with its reason. Run the research repo's `tools/sources/check_numbers.py` on a note built from reports: it flags any number the evidence does not contain. It proves a number exists in the evidence, not that it sits on the right claim.
3. **A verbatim quote does not prove the sentence beside it.** Keep to what the quote says: the years it covers, no cause ("because") unless the source gives one, no "new in" or "no longer" from one year's text. Check a quote by script (an exact substring of the page), not by eye.
4. **Label the step.** Observed (in the source), computed (from numbers shown) or inferred (ours; write "our inference").
5. **Citations, trials, papers and approvals go through the evidence record** (`cf-evidence-loop`). One you cannot resolve is deleted, not repaired from memory.
6. **A model's claim is checked by a different model** reading only the claim and the evidence; its answer is a lead to confirm on the source page, never a verdict and never a majority vote. A clean fast local pass on a long text is no information (measured in `model-qwen3-8-27b`).
7. **Say what was not covered.** Name the sources not read, the pages not checked and the checks not run; a passed check covers only what it ran on.
8. **A restriction given to a subagent in words is checked** against its transcript before its output is used.
9. **Widening words and absences need a scope record.** A sentence with a widening word ("only", "all", "every", "same", "first", "no longer", "new in", "agrees", "stronger"; the full list is `DEFAULT_WIDENING` in `../cf-research/tools/claims/check_claims.py`, explained in its README) or an absence phrase ("not stated", "no evidence", "there is no"; `DEFAULT_ABSENCE`) names what was searched and where. If the quote does not use the widening word itself, narrow the sentence or mark it inferred. `check_claims.py` enforces both (rule R4).

### Answer tiers

Say which tier an answer, note or page rests on. The tiers, and the eight principles behind the guardrails above, are defined in the research repo's `proposals/2026-10-08-antihallucination-strategy.md` (sections 3 and 4).

| Tier | Rests on | May be used for |
| --- | --- | --- |
| T0 | A summary, search snippet or memory; unverified | Orientation only, labelled T0 |
| T1 | A quote from a primary source, with its id and date | Notes and pull requests |
| T2 | T1, plus a script check and a different model's check, each flag confirmed on the source | Public claims |
| T3 | T2, plus a person's review | Anything that could affect a person's care; scientific copy on a site |

A patient-related question needs T1 before it is answered; until then, say plainly that what you have is T0.

### Tools that check claims

Paths are in the research repo (`../cf-research/`) unless named otherwise; each tool's README or `--help` is the authority.

| Tool | What a pass shows | What it does not show |
| --- | --- | --- |
| `tools/sources/check_numbers.py` | Every number in a draft is in the evidence, or in an allow file with its reason | That the number sits on the right claim; broad evidence (a whole folder of reports) makes it prove nothing |
| `tools/sources/check_source_overlap.py` | No run of words shared with `sources/downloads/` over the limit, and no quotation over 8 words | Truth; whether a shorter quotation is fair |
| `tools/claims/check_claims.py` | Per claim: each quote is an exact piece of its evidence, each number is in the quote or a checked computation, widening and absence words have a scope, an inference has a basis. Fails closed: no claims or no evidence is a failure | That the quote supports the sentence; a person or a different model still reads each pair |
| `brief drug\|variant\|trial` (`cf-evidence-loop`, in `../cf-skills/`) | Several catalog-permitted sources' records side by side, with `PASS`, `CHECK` or `NOT STATED` cross-checks; it adds no fact of its own | A `PASS` is not a finding about the drug, variant or trial |
| `tools/variant_profile/variant_profile.py` | What ClinVar's official API states about one gene and protein change, each value beside its API field | Any interpretation of a classification or of a person's genotype; CFTR2 remains the CF-specific authority |

For the trial endpoint atlas and for grounding any public sentence, see `trial-atlas-pipeline` and `source-grounding` in `../cf-research/.claude/skills/`.

## What "success" looks like in CF research

When we evaluate a CF research tool, or write about CF trials, these are the endpoints the field uses. Name them by their actual acronyms:

- **FEV₁** — forced expiratory volume in one second; distinguish absolute volume from percent predicted when reading a study.
- **sputum culture** — species and density of *Pseudomonas* and other pathogens.
- **pulmonary exacerbation rate** — number of exacerbations per year, typically defined by a protocol-specific clinical event.
- **CFTR-related measures** — use each study's definition; do not group pancreatic measures, symptoms, and direct CFTR function into one interchangeable endpoint.
- **Patient-reported outcomes** — preserve the exact validated instrument name, version, and domain from the study; do not invent acronym expansions.
- **Weight/height z-score, body mass index** — historical and still relevant, especially in pediatric cohorts.
- **Survival or transplantation outcomes** — preserve the study's endpoint and follow-up definitions, without ranking them by difficulty from memory.

For a lab tool (a journal parser, a variant lookup helper, an outcome dashboard), name which endpoint the tool is built to surface and which it is *not* meant to interpret.

## Data and community sources

The workspace's public materials should link to primary sources, not to our own summaries. **Before fetching anything, check `../cf-research/sources/catalog.yaml`**: it records, per source, whether automated retrieval is permitted (`fetch`/`api`), must be done by a human (`manual`), needs an application (`request`), or has been refused (`forbidden`). If a source is not in the catalog, add it with evidence before using it.

- **Cystic Fibrosis Foundation** — <https://www.cff.org> (Intro to CF, drug development, research).
- **CFTR2** — the *CFTR* variant database; <https://www.cftr2.org>.
- **ClinicalTrials.gov** — trial registry; <https://clinicaltrials.gov> (search "cystic fibrosis").
- **ECFS (European CF Society)** and **Cystic Fibrosis Trust (UK)** — regional equivalents with their own registries and research programs.
- **ECFS Patient Registry (ECFSPR)** — annual data reports back to 2003 as PDFs; <https://pr.ecfs.eu/annual-reports/>. Automated retrieval permitted by their `robots.txt` (checked 2026-10-04).
- **Cystic Fibrosis Foundation Washington chapter** — the specific donation target of this workspace: <https://give.cff.org/washington/donate?rbref=homepage>.

## The 65 roses

The name comes from a child's pronunciation of cystic fibrosis in 1965, not a founding patient count. The Foundation describes the rose as a symbol of its work and notes that "65 Roses" is its registered trademark. Source: [CFF — 65 Roses story](https://www.cff.org/about-us/65-roses-story), checked 2026-10-03.

Our banner is an independent tribute with exactly **65** rose motifs, not an official emblem, endorsement, or Foundation requirement. **Do not round the requested motif count.** Count the rendered instances and respect reduced-motion settings for animation. Do not copy Foundation logos or imply affiliation.

## What this lab may and may not claim

The lab's scope, per `AGENTS.md` and `SECURITY.md`:

- **May:** build open-source research tooling (data schemas, outcome dashboards, variant-lookup helpers, trial-matching explorers, literature parsers), document methods openly, run local-model benchmarks on non-clinical fixtures, and link to primary sources.
- **May not:** give medical advice, interpret a patient's *CFTR* genotype, recommend a specific drug or dosing, diagnose, or present a tool as a replacement for clinical care. Community-facing materials must carry the "research, not medical advice" boundary.
- **Data rule.** No PHI — no names, dates of birth, MRNs, treatment histories, lab values, or identifiable photos — in any repo, log, model packet, or website. This follows `security-baseline` section 6 and is absolute, not a default. See `security-browsing` section 6 for how to handle public patient stories (summarize themes, not people).
- **Model output rule.** A model's reply about CF is untrusted input. Verify drug names, mutation classes, and approvals against a primary source before they ship in a public artifact. The model may be right; the model is not the citation.

## Writing about CF

Tone for this workspace:

- **Plain language, not clinical prose.** A reader may be a patient, a parent, a researcher, or a developer. Assume no background; define acronyms on first use.
- **Specific, sourced numbers.** "Median survival has risen substantially since 2019" is acceptable. "Median survival is X years" without a source and date is not.
- **Patient-first, person-first.** "A person with CF" is preferred over "a CF sufferer" or "a CF victim." "Living with CF" over "battling CF" in lab materials.
- **Honest about limits.** If a tool is an explorer or a prototype, say so. If a benchmark is small, say so. The lab's credibility is its honesty.
- **Don't invent hope.** The Foundation's mission page describes research, care, and support. The lab is an independent research effort: support understanding and community without claiming to deliver clinical care or a cure. Use `lab-voice` for tone; warmth does not relax evidence requirements.

## Suggested additions to a CF project packet

When the orchestrator scopes a CF-related task, the packet should name:

1. Which *CFTR* mutation class or specific variant (if any) the tool concerns.
2. Which endpoint(s) the tool surfaces or analyzes.
3. Whether the tool handles **any** patient data (it should not) or only aggregate, public, or synthetic data.
4. The **primary source** for every clinical claim (CFF page URL, manufacturer page, or trial registry ID).
5. The publication date of any numeric claim that will ship.
6. The disclaimers that must appear in any public artifact ("research, not medical advice," "not a replacement for clinical care," and the CFF donation link where applicable).

If a task touches patient data in any form — even "anonymized" — stop and escalate to the human. See `security-baseline` before proceeding.

## Related skills

- `security-baseline` — PHI and medical-data rules, OWASP, deployment safety.
- `security-browsing` — handling public patient stories and CF community content.
- `ai-loop-council` — the loop that produces any tool this skill governs.
- `model-qwen3-8-27b` — the default local worker for CF-tool drafts and reviews.

## Sources and verification status

- Checked 2026-10-03: [CFF — Intro to CF](https://www.cff.org/intro-cf), [Our mission](https://www.cff.org/about-us/our-mission), and [65 Roses story](https://www.cff.org/about-us/65-roses-story). Their exact page content supports the narrow statements above, not treatment tables or worldwide access estimates.
- Read 2026-10-08 at cf-research `origin/main` 79626ae and cf-skills `origin/main` bbacb39: the strategy proposal, `tools/claims/README.md`, `tools/variant_profile/README.md`, `tools/sources/README.md`, the `--help` of the four Python tools in the table, and the Briefs section of `cf-evidence-loop`. The answer tiers, guardrail 9 and the tools table rest on these.
- Resource links above are starting points, not a claim that every linked resource or current clinical label has been verified. Recheck the exact source needed before publication.

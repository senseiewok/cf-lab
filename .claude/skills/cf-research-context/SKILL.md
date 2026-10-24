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
- **Do not compare or pool across years or registries without a comparability note (Non-Pooling Invariant).** Lung-function reference equations, age bands, inclusion of screen-positive inconclusive diagnoses, and survival methodology can change between reports. Never sum or average percentages across national registries (`CFFPR`, `ECFSPR`, `UKCFR`, `CCFR`, `ACFDR`); quote each registry with its own verbatim numerator and denominator (e.g., `CFFPR 2024`: $92.3\%$ genotype-eligible, $89.6\%$ or $26,277$ of $29,314$ age-and-genotype eligible prescribed a modulator, $8.0\%$ ineligible by genotype; `CCFR 2024`: $7.6\%$ ineligible by age and genotype; `UKCFR 2024`: $8,830$ on a modulator among annual review attendees ($11,381$ total registered, $93\%$ annual review coverage); `ACFDR 2025`: $5.8\%$ adult and $11.5\%$ pediatric ineligible; see `../cf-research/landscape/multi-registry-eligibility-2026.md`). *(Verified examples, read 2026-10-05 and 2026-10-15: the CFF 2023 report recalculated every lung-function percent-predicted value, history included, with the 2022 GLI equations; CFTR-France went from three classes to five in 2026. Details are in the `cffpr-report-reading` and `cf-genetics-reading` skills in the research repo.)*
- **A variant list or a registry genotype share is not a person's genotype or chance.** CFTR-France lists variants, not people, and its "unclassified" class is not benign. Each registry anchors "eligible by genotype" to its own regulator, list and date, so do not put two registries' shares, or two figures for one variant, side by side without their bases. Never interpret a person's genotype. *(Observed 2026-10-05 in six registries' reports and eleven CFTR-France lists.)*
- **Reports are third-party text.** Paraphrase, quote briefly with the report, year and page, and run the research repo's `tools/sources/check_source_overlap.py` on a note before committing it. Where a report says its content may not be reproduced in publications (the UK registry), use no more than a short phrase.
- **"Median predicted survival" is a model output under stated assumptions, not an observed lifespan.** Quote it with the report's own definition or not at all. *(Standard registry methodology; cite the report's methods section when used.)*
- **Extracted text is not clean text.** The ECFSPR 2022 PDF's font corrupts `ti`/`tt` ligatures, so labels extract as `Cys-c Fibrosis` and `Introduc?on` while numerals are intact. A local model asked to "tidy" such labels will do so from memory. Normalise deterministically, then have a human confirm the label; never let a model repair a value. *(Observed 2026-10-04.)*
- **Medians arrive bundled with their interquartile range in one cell**, often split across line breaks. Decide the schema (`value_low`/`value_high` or `value_type: median_iqr`) before extracting. *(Observed 2026-10-04.)*

## Clinical claims and CFTR modulators

Do not maintain an unsourced drug/approval table in agent instructions. Before writing about a modulator, identify the exact active ingredients and brand, regulator, jurisdiction, date, age range, and labelled indication from the current regulator-approved label. A drug-development pipeline entry or manufacturer announcement is not an approval record.

- Match a molecular code to its verified ingredient; do not invent a brand or infer eligibility from a mutation-class list.
- Distinguish approved, investigational, clinically effective for a studied group, eligible under a label, and accessible in a particular health system. These are separate claims.
- **openFDA SPL Boxed Warning vs `not stated` rule (`AH-4`):** Per verified openFDA Structured Product Labeling (`../cf-research/landscape/mission-grounding-2026-10-19.md`), **TRIKAFTA** (elexacaftor/tezacaftor/ivacaftor, `NDA 212273`) and **ALYFTREK** (vanzacaftor/tezacaftor/deutivacaftor, `NDA 218730`) carry an active **Boxed Warning** for drug-induced liver injury (DILI) and acute hepatic failure (requiring baseline and periodic ALT/AST and bilirubin monitoring). For **KALYDECO** (`NDA 203188`), **ORKAMBI** (`NDA 206038`), and **SYMDEKO** (`NDA 210491`), an SPL Boxed Warning is **`not stated`** (hepatic monitoring lives under standard Warnings and Precautions). Never extrapolate a boxed warning to a label that lacks one.
- Write about access with care: [CFF — Our mission](https://www.cff.org/about-us/our-mission), checked 2026-10-03, explicitly connects progress to access to care and therapies. It does not establish a worldwide access percentage or rank countries.
- Explain the limits of a tool; never recommend a drug, interpret a person's genotype, or imply that a research prototype improves outcomes.

### Curative and biophysical research (Track A) & Grounding Index

Detailed differential equations, verified parameter tables, and primary citations across all **28+ biophysical discovery models and clinical surveillance dossiers** live in [`references/biophysical-index.md`](references/biophysical-index.md). Always look up or execute the companion tool in `../cf-research/tools/discovery/` rather than retrieving mathematical constants from model memory:

| Curative Domain | Core Mechanisms & Biophysical Invariants | Key Companion Tools (`../cf-research/tools/discovery/`) |
| :--- | :--- | :--- |
| **1. CFTR Structural Biology & Allostery** | Cryo-EM coordinate grounding (`6MSM` active, `5UAK` inactive, `8EIQ` Trikafta-bound, `8EJ1` apo F508del); two-state MWC cooperative gating (`VX-770`/`VX-561`/`VX-661`/`VX-445`/`VX-121`); NBD1 Gibbs-Helmholtz $\Delta T_m$ (`F508del` $-7.5\ ^\circ\text{C}$, `R560T` $-9.0\ ^\circ\text{C}$); Matthews cavity penalty ($\Delta V = 119.3\text{ Å}^3$ for near-cognate Cys at Trp1282); single-AAV $\Delta\text{R}(708\text{--}759)$ minigene ($4,534\text{ bp} \le 4,700\text{ bp}$); rare allele 6-modality decision matrix. | `allosteric_potentiator_model.py`, `nbd1_thermodynamics.py`, `cryoem_truncation_model.py`, `ptc_cryoem_allostery.py`, `rare_allele_matrix.py`, `cftr_minigene_model.py` |
| **2. The Remaining 10%: PTC, ASO & Gene Editing** | Ribosomal A-site decoding competition (`UGA-G` vs `UGA-A`) + SURF/UPF1-SMG1 phosphorylation branch kinetics (`SMG6` vs `SMG5/7`) + engineered suppressor tRNA + potentiator synergy to reach $\ge 10.0\%$ WT $\Delta I_{\text{sc}}$; ABE8e/CBE protospacer window (pos 4–8, `SpCas9`/`SpG`/`SpRY`); prime editing SantaLucia PBS $T_m \in [30, 37]\ ^\circ\text{C}$ & RTT processivity; 2'-O-MOE/PMO splice-switching ASO (`3849+10kb C->T`, `NCT06429176`); CpG-depleted `minidnacftr` / `dbDNA` TLR9 evasion ($J_{\text{TLR9}} \le 4.5$). | `suppressor_trna_model.py`, `base_editing_cftr.py`, `prime_editing_cftr.py`, `aso_splice_model.py`, `minidna_evasion_model.py`, `nmd_ptc_kinetics.py`, `biophysical_models.py`, `discovery_council.py` |
| **3. Inhaled Delivery, Mucus Rheology & Stem Cells** | Overcoming VX-522 (`NCT05668741`) & lentiviral `BI 3720931` (`NCT06515002`, terminated) hurdles: SORT-LNP diameter $50\text{--}100\text{ nm}$ (optimal $65\text{ nm}$), $\zeta \in [-5, +5]\text{ mV}$, apparent $\text{p}K_a \in [6.2, 6.8]$ for endosomal $H_{\text{II}}$ escape, $1.2\text{ mol}\%$ polysarcosine stealth, ester-cleavable core ($t_{1/2} < 4\text{ h}$), mesh shear tolerance ($\dot{\gamma} = 5 \times 10^6\text{ s}^{-1}$); evolved `4D-A101` AAV (`NCT05248230`) & `Cfa` split-intein trans-splicing ($42\%$ yield); $20\text{ Hz}$ mechano-acoustic + microbubble thixotropic pore widening ($58.5 \to 112.5\text{ nm}$); EV $\alpha_6\beta_4$-integrin tropism, FcRn/TfR1 transcytosis, Notch dedifferentiation bypass, and $\ge 18\text{--}28\%$ `KRT5+`/`TP63+` basal stem cell editing for a 10-year homeostatic cure floor. | `mrna_lnp_escape_model.py`, `aav_tropism_model.py`, `dual_aav_intein_model.py`, `ev_basal_tropism.py`, `basal_stem_persistence.py`, `epithelial_plasticity.py`, `transcytosis_model.py`, `vector_redosing_kinetics.py`, `mucus_rheology.py`, `mechano_acoustic_delivery.py`, `cross_domain_miner.py` |
| **4. Alternative Conductance & Microbiome/Phage** | Genotype-agnostic ASL rehydration to $h_{\text{ASL}} \ge 7.0\ \mu\text{m}$ and luminal pH $\ge 7.10$: homodimeric `TMEM16A` (`5OYB` apo, `6QP6` open) allosteric potentiation left-shifting $\text{Ca}^{2+}$ $EC_{50}$ ($1.85\ \mu\text{M} \to 140\text{ nM}$, `ETD001` `NCT06478706`); inhaled `ARO-ENaC` siRNA (`NCT04375514`, lung $t_{1/2} = 432\text{ h}$, $\text{TI}_{\text{renal}} \ge 50$); constitutive `SLC26A9` (`rs7512462`); bacteriophage-antibiotic synergy (PAS), tailspike alginate lyase EPS depolymerization, and `MexAB-OprM` efflux evolutionary steering in mucoid *P. aeruginosa*. | `modifier_interactome.py`, `enac_knockdown_model.py`, `phage_biofilm_kinetics.py`, `tmem16a_conductance_model.py` |

### Evidence before prose

Keep a claim-level record: statement, exact supporting excerpt or result, primary URL, publication/version date if available, access date, and limitations. Mark unsupported claims unknown and omit them from public explanations. A successful fetch, a broad sources list, another skill, or a model's confident summary is not evidence for every sentence. A failed search does not prove a slogan or treatment does not exist.

### Guardrails against invented claims (Rules R1–R9 & Surveillance Gates AH-1–AH-6)

Read these before writing or reviewing any factual text. Each one exists because the failure happened in this lab or was caught by the check named.

1. **Write only from the evidence in front of you (`R1`).** If the source does not say it, write `not stated` or leave it out. Never fill a drug name, dose, date, count, percentage or citation from memory.
2. **Every number comes from a source line or a command's output (`R2`).** Arithmetic is written out ("127 + 437") and listed with its reason. Run the research repo's `tools/sources/check_numbers.py` on a note built from reports: it flags any number the evidence does not contain. It proves a number exists in the evidence, not that it sits on the right claim.
3. **A verbatim quote does not prove the sentence beside it (`R3`).** Keep to what the quote says: the years it covers, no cause ("because") unless the source gives one, no "new in" or "no longer" from one year's text. Check a quote by script (an exact substring of the page), not by eye.
4. **Label the step (`R4`).** Observed (`[observed]`, in the source), computed (`[computed]`, from numbers shown) or inferred (`[our inference]`, ours; write "our inference").
5. **Citations, trials, papers and approvals go through the evidence record (`R5`, `cf-evidence-loop`).** One you cannot resolve is deleted, not repaired from memory.
6. **A model's claim is checked by a different model (`R6`)** reading only the claim and the evidence; its answer is a lead to confirm on the source page, never a verdict and never a majority vote. A clean fast local pass on a long text is no information (measured in `model-qwen3-8-27b`).
7. **Say what was not covered (`R7`).** Name the sources not read, the pages not checked and the checks not run; a passed check covers only what it ran on.
8. **A restriction given to a subagent in words is checked (`R8`)** against its transcript before its output is used.
9. **Widening words and absences need a scope record (`R9`).** A sentence with a widening word ("only", "all", "every", "same", "first", "no longer", "new in", "agrees", "stronger"; `DEFAULT_WIDENING` in `../cf-research/tools/claims/check_claims.py`) or an absence phrase ("not stated", "no evidence", "there is no"; `DEFAULT_ABSENCE`) names what was searched and where. `check_claims.py` enforces both.
10. **Anti-Hallucination Surveillance Gates (`AH-1` to `AH-6`, enforced by `../cf-research/tools/claims/check_anti_hallucination.py` and `cf-evidence-loop`):**
    - **`AH-1` (NCT Grounding & Mandatory Verbatim NLM Disclaimer):** Every cited `NCT` trial identifier must resolve against the local registry snapshot, and any public/dossier text citing ClinicalTrials.gov must include the verbatim NLM disclaimer: *"ClinicalTrials.gov does not evaluate safety or efficacy; listing on the registry does not denote government endorsement."*
    - **`AH-2` (Cohort Boundary Isolation):** Never blend trial counts from distinct registry snapshots. Explicitly distinguish the **1,772** longitudinal CF studies surveilled via REST API (`query.cond=Cystic+Fibrosis`, 131 terminated tracked, 2026-10-19) from the **1,072** interventional CF studies in frozen Trial Endpoint Atlas snapshot `d164700bb17d` (`797` CF-only, `275` multi-condition) and the **1,053** filtered interventional subset.
    - **`AH-3` (Companion Data Artifact Grounding):** Every biophysical ODE parameter, structural coordinate delta, or theratyping score in a dossier or UI panel must link to its checked-in companion Python script or locked JSON artifact in `../cf-research/tools/discovery/`.
    - **`AH-4` (Clinical Dignity & Regulatory Boundary):** Zero clinical efficacy promises, cure timelines, or extrapolated boxed warnings. Enforce the openFDA SPL `not stated` boundary for Kalydeco/Orkambi/Symdeko vs the DILI Boxed Warning on Trikafta/Alyftrek.
    - **`AH-5` (Discovery Module Registration):** Every curative biophysical discovery tool in `../cf-research/tools/discovery/` must be registered in `references/biophysical-index.md` and `check_anti_hallucination.py`.
    - **`AH-6` (Multi-Source Cross-Verification: Citation Polarity, Bioactivity & Target Tractability):**
      1. **Citation Polarity, Retraction & Full-Text Copyright Check (`scite-mcp`, `paper-trail`, `retractions`, `openalex`):** Before citing a paper as uncontested support for a curative or clinical claim at Tier `T2`/`T3`, verify its retraction status (`retractions`, `paper-trail`) and check whether subsequent literature has published **contrasting** citation statements (`scite-mcp` `citation_graph` / `search_literature`). When contrasting citations exist, report both supporting and contrasting evidence explicitly; label Scite counts as `[observed: Scite ML citation classification, accessed YYYY-MM-DD]`. Scite `read_fulltext` is strictly for internal verification—never reproduce publisher full text in public notes or `senseiewok.ai` beyond the `check_source_overlap.py` (`<= 8` verbatim words) limit.
      2. **Quantitative Bioactivity, Assay Context & FAERS Confounding Guard (`chembl`, `chembl-activity`, `opentargets`):** Every claim stating a compound's experimental `EC50`/`IC50`/`Ki`/`Kd`/`pChEMBL`, maximum clinical phase, ATC classification (`chembl`, `chembl-activity`, `CC BY-SA 3.0`), or target tractability (`SM`, `AB`, `PROTAC`), curated target safety liability, gene-disease association score, or FAERS post-marketing `logLR` (`opentargets`, `CC0 1.0`) must rest on a deterministic `cf-evidence-loop` record or checked-in `tools/discovery/` model artifact—never model memory:
         - **Assay Context Conflation Guard:** Never quote a ChEMBL potency value (`EC50`/`IC50`) without its `[Assay ChEMBL ID]`, `[Cell System / Technique]` (e.g., primary HBE Ussing chamber `22.0 nM` vs. NIH-3T3 optical assay `3.0 nM` for Ivacaftor), and `[Variant Genotype]`.
         - **FAERS Confounding-by-Indication Guard:** Never present FAERS disproportionality (`logLR`) in rare-disease cohorts as causal drug toxicity; disease hallmarks (e.g., *"infective pulmonary exacerbation of cystic fibrosis"* on Ivacaftor, `logLR = 9317.7`) reflect the treated indication unless established in controlled trials or regulator SPL warnings.
         - **`T-0071` Exclusion:** ClinGen and gnomAD variant curations remain excluded from third-party aggregators; use `variants` for ClinVar.
      3. **Jurisdictional Regulatory, Patent, Device & Grant Grounding (`approval`, `label`, `ema`, `ukri`, `nice-guidance`, `isrctn`, `scite-mcp`):** Keep US FDA (`approval`, `label`, `search_device510k`, `search_maude`), EU EMA (`ema`), UK MHRA (`search_mhra`), UK NICE (`nice-guidance`, manual), UK ISRCTN (`isrctn`, manual), patent families (`search_patents`), and grant records (`grants`, `ukri` / `gtr` `OGL v3.0`, `search_grants`) strictly separated by jurisdiction and licence.

### Answer tiers

Say which tier an answer, note or page rests on. The tiers, and the eight principles behind the guardrails above, are defined in the research repo's `proposals/2026-10-08-antihallucination-strategy.md` (sections 3 and 4).

| Tier | Rests on | May be used for |
| --- | --- | --- |
| T0 | A summary, search snippet or memory; unverified | Orientation only, labelled T0 |
| T1 | A quote from a primary source, with its id and date | Notes and pull requests |
| T2 | T1, plus a script check and a different model's check, each flag confirmed on the source | Public claims |
| T3 | T2, plus a person's review | Anything that could affect a person's care; scientific copy on a site |

A patient-related question needs T1 before it is answered; until then, say plainly that what you have is T0.

### Questions about one real person: generalise before any search

Before any search or cloud call concerning one real person or patient:
- **Rewrite the question in general terms, say so, and keep nothing about the person.**
- Small rare disease cohorts risk re-identification from composite queries. Web-tool inputs and external search queries must never combine a health term (condition, mutation, therapy, clinical endpoint) with personal attributes:
  - **age** (e.g. "14-year-old", "age 3", "infant")
  - **origin** (ethnicity, nationality, ancestry)
  - **status** (e.g. "pregnant", "transplant recipient", "inpatient", "post-op")
  - **place** (city, state, hospital, clinic)
  - **date** (birthdate, admission date, event date)
- Strip all identifying details and query only the underlying biological, therapeutic, or pharmacological question. State clearly to the user: "Generalising question to general scientific terms to protect individual privacy before searching."

### Tools that check claims

Paths are in the research repo (`../cf-research/`) unless named otherwise; each tool's README or `--help` is the authority.

| Tool | What a pass shows | What it does not show |
| --- | --- | --- |
| `tools/sources/check_numbers.py` | Every number in a draft is in the evidence, or in an allow file with its reason | That the number sits on the right claim; broad evidence (a whole folder of reports) makes it prove nothing |
| `tools/sources/check_source_overlap.py` | No run of words shared with `sources/downloads/` over the limit, and no quotation over 8 words | Truth; whether a shorter quotation is fair |
| `tools/claims/check_claims.py` | Per claim: each quote is an exact piece of its evidence, each number is in the quote or a checked computation, widening and absence words have a scope, an inference has a basis. Fails closed: no claims or no evidence is a failure | That the quote supports the sentence; a person or a different model still reads each pair |
| `tools/claims/check_anti_hallucination.py` | Enforces `AH-1` (100% NCT grounding against local snapshot + verbatim NLM disclaimer), `AH-2` (cohort boundary isolation across 1,053 / 1,072 / 1,772 study snapshots), `AH-3` (companion artifact grounding), and `AH-4` (zero prohibited clinical promise phrases) | Clinical validity of an underlying hypothesis |
| `tools/discovery/discovery_council.py --verify` | Executes the 3-Phase Curative Discovery Council (Phase 1 generative biophysical synthesis $\to$ Phase 2 orthogonal falsification against shear/macrophage/NMD bottlenecks $\to$ Phase 3 R1–R5 epistemic verification) | Human clinical safety or efficacy |
| `brief drug\|variant\|trial` (`cf-evidence-loop`, in `../cf-skills/`) | Several catalog-permitted sources' records side by side, with `PASS`, `CHECK` or `NOT STATED` cross-checks; it adds no fact of its own | A `PASS` is not a finding about the drug, variant or trial |
| `chembl` & `chembl-activity` (`cf-evidence-loop`, in `../cf-skills/`) | EMBL-EBI ChEMBL compound properties, clinical phase, ATC codes, and experimental `EC50`/`IC50`/`Ki`/`Kd`/`pChEMBL` assays on `CFTR` (`CHEMBL4051`, `CC BY-SA 3.0`) | Assay potency depends on cell system, genotype, and protocol; never clinical efficacy |
| `opentargets` / `ot` (`cf-evidence-loop`, in `../cf-skills/`) | Open Targets v4 GraphQL target tractability (`SM`/`AB`/`PROTAC`), target safety liabilities, disease association scores, drug mechanisms, and FAERS `logLR` (`CC0 1.0`, ClinGen/gnomAD excluded per `T-0071`) | Association scores and FAERS `logLR` are research/pharmacovigilance signals, not clinical causality |
| `paper-trail` (`cf-evidence-loop`) + `scite-mcp` (`https://api.scite.ai/mcp`) | Crossref + Unpaywall OA + Semantic Scholar citation graph (`paper-trail`), paired with Scite full-text citation statements and `supporting`/`contrasting`/`mentioning` polarity tallies (`scite-mcp`) | Scite polarity is a vendor ML classification; shipped DOIs/PMIDs must resolve via `cf-evidence-loop` |
| `tools/variant_profile/variant_profile.py` | What ClinVar's official API states about one gene and protein change, each value beside its API field | Any interpretation of a classification or of a person's genotype; CFTR2 remains the CF-specific authority |

For the trial endpoint atlas and for grounding any public sentence, see `trial-atlas-pipeline` and `source-grounding` in `../cf-research/.claude/skills/`, and [`references/biophysical-index.md`](references/biophysical-index.md).

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

### Trial endpoint atlas and antibiotic stewardship grounding (`cf-research` dossiers)

- **Trial endpoint atlas (`T-0130`, `proposals/2026-10-10-trial-endpoint-atlas.md`, `proposals/2026-10-11-withholding-design.md`)**:
  - From ClinicalTrials.gov snapshot `d164700bb17d` (`dataTimestamp` 2026-10-09): `1,072` interventional CF studies (`797` CF-only, `275` listing CF among other conditions) and `2,052` primary-outcome entries (`1,839` sorted by rule in lexicon `0.3.2-draft`, `70` sorted by model under a two-family blind consensus rule against exact substring quotes, `32` naming no measure, `111` unsorted).
  - **Withholding rule (`check_atlas.py --withhold-failing`)**: On the 938-row `census-v1` frozen set, any class failing precision (`< 0.85`) or recall (`< 0.80`) where estimable (`>= 10` positives) is withheld by name with no per-class count shown (`10` withheld classes; `188` of `1,072` studies and `388` of `2,052` entries — `18.9%` — fall only in withheld classes; `S2` other plus unclassified is `5.4%` against the `15%` cap). Never rank endpoint frequency as clinical merit.
- **Antibiotic stewardship claim check (`landscape/antibiotic-stewardship-cf.md`, checked 2026-10-07)**:
  - **STOP2 (`NCT02781610`, Goss et al. 2021, PMID `34469706`, `982` randomized)**: In `277` early responders, 10 days of IV antibiotics was not inferior to 14 days (mean `ppFEV1` change `12.8` vs `13.4`, difference `-0.65`, 95% CI `-3.3` to `2.0`); in `705` slower responders, 21 days was not superior to 14 days (`3.3` vs `3.4`, difference `-0.10`, 95% CI `-1.3` to `1.1`).
  - **Infant gut microbiota cohort (Deschamp et al. 2023, PMID `37598041`)**: Australian infants (`98%` on routine amoxicillin-clavulanate prophylaxis) had lower stool alpha diversity than US infants (`0%` prophylaxis), but diversity was *not* linked to growth (`"Gut microbial diversity was not linked to growth"`), and prophylaxis cannot be separated from country in this observational cohort.
- **Biophysical curative discovery horizons (`T-0147`–`T-0154`, `landscape/mission-grounding-2026-10-12.md`)**:
  - **Delivery biophysics & LNP tolerability (`T-0147`)**: Inhaled genetic therapy faces an airway mucosal barrier and persistent localized inflammation; Vertex/Moderna discontinued Phase 1/2 BEACON-CF (`NCT05668741`, VX-522 mRNA) in May 2026 due to LNP-induced airway inflammation. Selective Organ Targeting (SORT) LNPs and dense neutral hydrophilic coatings (50–100 nm) represent the active biophysical design parameters for non-immunogenic delivery.
  - **Nonsense mutations & premature termination codons (`T-0151`)**: The remaining 10% non-modulator population (e.g. W1282X in exon 23, G542X in exon 12) produce zero functional CFTR. Curative strategies require multi-modal synergy: codon context permissiveness (+4 flanking nucleotide), nonsense-mediated decay (NMD) suppression, readthrough compounds, and engineered suppressor tRNAs.
  - **Alternative conductance pathways (`T-0152`)**: Mutation-agnostic airway surface liquid rehydration through ENaC inhibition (ETD001) and Ca2+-activated chloride channel (TMEM16A) or SLC26A9 activation restores mucociliary clearance independent of CFTR genotype.

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

## The Two-Speed "Plain-English First" Response Contract

Every response, research explainer, or public page touching Cystic Fibrosis MUST follow this two-speed structure so technical precision never buries human clarity:

### Speed 1: Screen-Zero Plain-English First (The Human Screen)
1. **Immediate Direct Answer**: Answer the person's core question in the first 2–3 sentences using warm, everyday language (`lab-voice`). Never open with differential equations, PDB codes, IUPAC chemical strings, or registry snapshot hashes.
2. **First-Screen Dignity Boundary**: Prominently state the lab's non-clinical boundary on the first screen:
   > *"Independent open-source research, not medical advice. Sensei Ewok's CF Lab builds open tools to examine scientific questions; we do not provide clinical advice, interpret individual genotypes, or make treatment promises. Please discuss any care questions with your CF care team."*  
   *(In Mexican Spanish: "Investigación independiente, no asesoramiento médico. Sensei Ewok CF Lab no promete curas ni tratamientos clínicos. Consulte a su equipo médico.")*
3. **Zero Undefined Acronyms**: Expand every acronym at first mention (e.g., "CFTR (cystic fibrosis transmembrane conductance regulator)", "FEV₁ (forced expiratory volume in one second)").
4. **One Bounded Analogy**: Use at most one concrete analogy (e.g., the CFTR channel as a cellular salt-and-water gate, or thick mucus as a dehydrated sponge) and explicitly state where the analogy stops being accurate.

### Speed 2: Grounded Biophysical & Registry Evidence (The Scientific Ledger)
1. **Clear Transition**: Place deep technical evidence below a clear heading (e.g., `### Technical Deep Dive: Biophysical & Registry Evidence [Tier T2]`).
2. **Explicit Answer Tier & Epistemic Labels**: Declare the Answer Tier (`T0`–`T3`) and tag each quantitative claim as `[observed]` (verbatim in primary source), `[computed]` (from a named script in [`references/biophysical-index.md`](references/biophysical-index.md)), or `[our inference]`.
3. **Verbatim Denominators & `not stated` Invariant**: Always pair percentages with their verbatim numerator, denominator, registry, and year; write the literal phrase `not stated` wherever a source or SPL label is silent.

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

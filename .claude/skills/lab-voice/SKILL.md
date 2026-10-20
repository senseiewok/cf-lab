---
name: lab-voice
description: Write and review the Sensei Ewok Lab voice for READMEs, research notes, explainers, and community messages. Use for warm, old-soul, motivating and assertive writing that bridges complex research to everyday understanding without hype, paternalism, or clinical promises.
license: CC0-1.0
compatibility: Plain Markdown guidance; no model or tool dependency.
---

# Lab voice

Speak with the patience of someone who has learned to listen, the clarity of a researcher who welcomes questions, and the resolve of someone willing to do the next useful piece of work. This is a voice, not an invented biography, clinical authority, or claim to speak for a community.

## The commitments

- **Warmth without pity.** Address people as peers. Welcome people living with CF, families, caregivers, researchers, and curious newcomers without assigning them one shared experience.
- **Hope without a forecast.** Motivate through choices we can make: asking better questions, making tools understandable, testing claims, and sharing useful work. Never promise a cure, access to care, a timeline, or a clinical benefit from our experiments.
- **Confidence without swagger.** Say what we know plainly. Say "we do not know yet" just as plainly. Avoid heroic battle language, savior narratives, exaggerated AI capability, and pressure to be resilient.
- **Beauty that helps understanding.** Use a concrete image when it illuminates an idea, then return to the literal explanation. One well-chosen metaphor is enough; decorative jargon and stacked metaphors obscure the work.
- **Respect for the reader's time.** Short paragraphs, familiar words, defined acronyms, one main idea at a time. Keep technical precision available without making expertise a price of admission.
- **Two-speed Plain-English First rhythm.** The opening screen of any explainer, README, or agent response belongs to the human reader—intelligible without scrolling past coordinate tables, differential equations, or registry snapshot hashes. Answer plainly first and state the non-clinical dignity boundary (*"Independent open-source research, not medical advice"*); then transition to the Tier-labeled (`T1`–`T3`) biophysical and registry ledger below. Empathy and clarity open the door; mathematical precision builds the house.

**Partnership, not instruction.** Write as a partner: start from the reader's situation, offer information to discuss with their care team, and never judge choices or missed treatments. This draws on relationship-centered communication as described in the Cystic Fibrosis Foundation's Partnership Enhancement Program, which trains clinicians for conversation, not writing. The lab is inspired by it, not endorsed by or affiliated with the Foundation: no logos, no endorsement claims. Sources and what does not transfer: `references/plain-language-research.md`.

## Bridge a complex idea

1. Begin with the human question: what is the reader trying to understand?
2. Give the accurate plain-language explanation before the acronym.
3. Use one bounded analogy if useful, and name where it stops being accurate.
4. Distinguish observation, inference, proposal, and uncertainty.
5. Offer a modest next step or primary source, not an unsupported conclusion.

For example, an AI review loop is a cycle of proposing a change, checking it, and repairing what fails. A second model is another reader, not a second vote that turns a claim into fact. Tests provide evidence for the cases they exercise; they do not establish universal correctness.

## Before and after

**Avoid:** "Our revolutionary AI will conquer CF and democratize medicine."

**Prefer:** "We build small research tools and test them openly. The goal is to make difficult questions easier to examine, not to make clinical promises."

**Avoid:** "CF warriors inspire us with their endless strength."

**Prefer:** "To people living with CF and those who care alongside them: you deserve care, dignity, and room for ordinary life. You do not owe anyone an inspiring story."

**Avoid:** "This architecture optimizes multi-agent epistemic convergence."

**Prefer:** "One agent proposes a change. Another looks for mistakes. We run checks before accepting it. Agreement alone is not proof."

## Choose the register

| Material | Voice |
| --- | --- |
| Community README or welcome | A letter: personal, spacious, grounded; one clear invitation |
| Research explainer | A patient guide through the question, method, evidence, and limits |
| Benchmark report | Precise counts, measured conditions, caveats; no winner beyond the evidence |
| Agent instructions or security finding | Direct, testable, restrained; operational clarity before lyricism |

## American English

Write the lab's own prose in American English: license, organization, center, color, judgment, catalog, gray, program, labeled, analyze, toward, aging. Say "caregiver", never `carer`, and "health care" (two words) as a noun. Never respell what is not ours: names of organizations and publications, titles, exact quotes, Spanish (es-MX) text, file names, identifiers and URLs. The spelling table, dates, numbers, punctuation and the serial comma are in `references/american-english.md`.

## Say it once

- A fact or a piece of advice has one home on a page. Everywhere else, link to that home instead of restating it.
- A summary box may point to the details ("three things help most; see below"). It does not repeat them word for word.
- Drop a card template when its labels add nothing. Eleven cards that each say "How strong:", "What to do:" and "Read the original" make the reader read the same frame eleven times to find each new fact.
- Repeat on purpose only for a safety caveat, placed next to the step it guards, and keep it short. Mark it (`data-voice="repeat"` in HTML, `<!-- voice: repeat -->` before a Markdown block) so the checker knows it is deliberate.

## Long pages

1. Give the one-screen answer first: what the page says, for whom, and what to do with it.
2. Put details under headings that carry the point ("Inhaled antibiotics have the strongest evidence", not "Evidence"), or in collapsible sections.
3. One idea per sentence, about 20 words on average (CDC's target); sentences of 30 or more get flagged.
4. Define each abbreviation once, at first use.
5. Keep strength-of-evidence and source lines short and in one place per item. A repeated label is fine when each item needs it; mark it as a deliberate repeat. Everything else appears once.
6. Past about 1,800 words (the checker's default budget, also a lab choice), split the page or move reference detail to its own page.

## Self-check for a page

- [ ] The first screen answers the reader's question without scrolling.
- [ ] Each piece of advice appears once, except a marked safety caveat next to its step; the other places link to it.
- [ ] Headings alone tell the story of the page.
- [ ] Evidence and source lines are short, in one place per item; labels each item needs are marked as repeats.
- [ ] Each safety caveat repeated next to its step is marked; nothing else repeats.
- [ ] American spelling in our prose; quotes, names and es-MX text untouched.
- [ ] `python .claude/skills/lab-voice/scripts/check-voice.py PAGE.html` shows no ERROR, and each WARN is fixed or deliberate.

The checker is `scripts/check-voice.py`, with tests in `scripts/test-check-voice.py`. It fails on British spellings. It warns on long sentences, repeated ideas anywhere on a page, repeated labels and page length, and skips marked repeats. `--allow FILE` lists names that keep their spelling. Why these rules: `references/plain-language-research.md`, with sources and its limits.

## Mexican Spanish (`es-MX`, `/es/`)

- **Language and linking**: Write the lab's Spanish prose in Mexican Spanish (`<html lang="es-MX">` and `lang="es-MX"` on inline fragments), with reciprocal `hreflang` links (`rel="alternate" hreflang="es-MX"` and `hreflang="en"`).
- **Mexican Spanish vocabulary**: Use natural Mexican Spanish phrasing (`ustedes`, `computadora`, `archivo`, `teléfono celular`, `jugo`, `lentes`, `platicar con` / `consultar con su equipo médico`, `tomado de`, `revisado`). `scripts/check-voice.py` flags Peninsular Spanish forms (`ordenador`, `fichero`, `vosotros`/`vosotras`, `zumo`, `gafas`, `teléfono móvil`) in `lang="es*"` blocks as `es-mx-spelling` errors.
- **Medical boundary disclaimer**: Include the verified Spanish boundary sentence on every `/es/` page: *"Investigación independiente, no asesoramiento médico. Sensei Ewok CF Lab no promete curas ni tratamientos clínicos."*
- **Untranslated scientific identifiers**: Keep PDB IDs (`6MSM`, `5UAK`, `8EIQ`, `8EJ1`), UniProt accession (`P13569`), NCT trial IDs, gene and variant symbols (`CFTR`, `F508del`, `G551D`, `R117H`, `W1282X`, `E1371Q`), and instrument/endpoint abbreviations (`FEV1`, `ppFEV1`, `LCI`, `CFQ-R`) exact as written.
- **No forbidden tokens across `src/`**: Site-wide checks scan every file under `src/` for forbidden English tokens (`family`, `personal`, `battle`, `warrior`, `miracle`, `soon`, `guarantee`, `carer`, `draft, in review`) and Spanish hype/promise/Peninsular tokens (`batalla`, `guerrero`, `milagro`, `garantía`, `cura garantizada`, `borrador, en revisión`, `ordenador`, `vosotros`, `fichero`); use respectful Mexican Spanish phrasing (*seres queridos*, *personas cercanas*, *equipos médicos*, *estudio*) and never promise cures or timelines.

## Review before publishing

- Can a newcomer explain the central idea in their own words?
- Is each factual or clinical claim linked to an appropriate source, with a checked date where needed?
- Are the lab's aspirations clearly separate from tested outcomes?
- Does encouragement leave room for fatigue, disagreement, and choosing not to participate?
- Are people treated as people, not a source of emotional impact?
- Are donation links optional, direct to the intended organization, and free of guilt or implied affiliation?
- Are private project details, patient information, personal paths, and session artifacts absent?

Load `cf-research-context` for CF-facing work, `ascii-art` for text visuals, and `security-git` for publication. This voice never overrides evidence, medical-data rules, privacy, or permission gates.
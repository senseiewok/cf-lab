# Evidence layer: architecture

The researcher's loop, as code. One package, one gate, one record format. Every provider answers a question a CF researcher actually asks; every answer comes back as an evidence record with a source, a date, and a limitation, so it can be cited or rejected but never quietly believed.

## Design rules

1. **The catalog is the only permission.** No provider contains a URL. Each declares a `source_id`; the HTTP client resolves the base URL from `catalog.yaml` (or the file named by `EVIDENCE_CATALOG`) and refuses the call unless that entry's `access` is `fetch` or `api`. A host not in the catalog cannot be reached from this package at all. This is a tested property, not a convention.
2. **No disguise, no evasion.** One user agent, named for the project, with a contact where the publisher asks for one. No retries past `Retry-After`, no parallel hammering, no alternate endpoints when one refuses.
3. **Every answer is an evidence record.** Providers return `Evidence` objects, never raw JSON to the caller. A record carries: the claim it answers, the source id, the resolvable URL, the publisher's own date, the access date, the exact excerpt or fields relied on, and a limitations string that is never empty.
4. **Abstention is a result.** "Not found", "blocked", "rate-limited", and "source does not cover this" are distinct outcomes with distinct codes. A provider never fills a gap from memory, and the CLI never prints a bare answer without its status.
5. **Models map; they do not measure.** Nothing in this package calls a language model. If the lab later lets a local worker map free text to a provider query, the worker produces a query string and nothing else; the provider produces the fact.
6. **Deterministic and offline-testable.** Each provider has a `parse()` that takes a saved response and returns records, so tests run without network and a stranger can see exactly which fields are relied on.

## Layout

```
cf-evidence-loop/
  SKILL.md               the skill: what it does, how to run it, how to read a record
  catalog.yaml           the permission list this skill ships with (EVIDENCE_CATALOG overrides)
  references/ARCHITECTURE.md   this file
  scripts/requirements.txt
  scripts/evidence_cli.py      launcher, runs from any directory
  scripts/evidence/
    __init__.py
    catalog.py           load catalog.yaml; resolve source -> base_url; the access gate
    http.py              polite client: gate, UA, pacing, Retry-After, status mapping
    record.py            Evidence dataclass, Status enum, JSONL ledger writer
    providers/
      __init__.py        registry of providers by name
      crossref.py        DOI metadata; retraction and correction lookup (Retraction Watch via Crossref)
      openfda.py         Drugs@FDA approval history; current label sections
      preprints.py       bioRxiv and medRxiv by DOI or date window with a topic filter
      clinvar.py         CFTR variant clinical significance via E-utilities
      reporter.py        NIH RePORTER funded-project search
      pubmed.py          PubMed search; systematic-review view
      trials.py          ClinicalTrials.gov v2 search and record
      europepmc.py       Europe PMC search, citation count, open-access status
    cli.py               `evidence <command>`; prints records, optional --ledger append
    briefs.py            `brief drug|variant|trial`: several providers for one question, with PASS / CHECK / NOT STATED cross-checks
  tests/
    conftest.py          puts scripts/ on the path
    fixtures/            saved API responses trimmed to the fields the parsers read; README.md records their provenance
    test_gate.py         the catalog gate refuses what it must
    test_providers.py    parse() on fixtures
    test_briefs.py       brief recipes on scripted responses: failures, missing fields, cross-check controls
```

## The seven layers, mapped to providers

| Layer | Question | Provider | Status |
| --- | --- | --- | --- |
| 1 Literature | What was published? | `pubmed`, `europepmc`, `crossref` (metadata) | built |
| 2 Integrity | Retracted, corrected, disputed? | `crossref` retraction lookup | built |
| 3 Trials | What is being tested? | `trials` (ClinicalTrials.gov v2) | built |
| 4 Regulatory | Approved where, when, for whom? | `openfda` | built |
| 5 Population | How many people, what outcomes? | a separate registry-extraction tool, not part of this package | separate |
| 6 Guidelines | What does the field recommend? | `pubmed.reviews` (systematic-review subset + Cochrane journal, via abstracts); ECFS standards need terms read | partial |
| 7 The field's conversation | Funded, presented, preprinted? | `reporter`, `preprints`; conference supplements via `crossref` | built |

Variant biology: `clinvar` built; CFTR2 stays link-only until its terms are read.

## The evidence record

```
Evidence
  status        : found | not_found | out_of_scope | blocked | rate_limited | error
  question      : the normalised question the provider answered
  source_id     : catalog id
  url           : resolvable; the exact request or the publisher's canonical page
  publisher_date: the date the publisher attaches (approval date, label effective_time, deposit date, index date)
  accessed      : UTC timestamp of this call
  fields        : dict of the exact fields relied on, copied not paraphrased
  excerpt       : short verbatim text when the source has prose (indication text, retraction notice title)
  limitations   : what this record does not establish; never empty
  provider      : module name and version
```

Records serialise to one JSON line. `--ledger PATH` appends; the ledger is a mechanical evidence trail: what was asked, when, and what the source returned.

## What the retraction check does and does not do

Crossref ingested the Retraction Watch database in 2023 and exposes retractions and corrections as `update-to` relations. The provider queries `works?filter=updates:<DOI>` and returns every notice that updates the given DOI, with its type (`retraction`, `correction`, `expression_of_concern`, ...). A clean result means **Crossref holds no update notice for that DOI**, which is strong but not complete: publishers lag, and some notices lack the relation. The limitation string says so on every clean record.

## Failure semantics

| HTTP | Status | Behaviour |
| --- | --- | --- |
| 200, empty | `not_found` | Record with the query; no retry |
| 404 | `not_found` | Same |
| 429 / 503 | `rate_limited` | Honour `Retry-After` once, then return the record; never loop |
| 403 / 402 | `blocked` | Return immediately; log the host; **never change client identity** |
| other | `error` | Return with the status code |
| gate refusal | `blocked` | Raised before any socket opens |

## Not in scope for this package

Document retrieval and registry extraction (separate tools), any model call, any patient-level data source, and anything whose catalog entry says `manual`, `request`, or `forbidden`.

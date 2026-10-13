# Test fixtures

Saved API responses used by `tests/test_providers.py`, so the parsers run offline. Each was captured on 2026-10-04 from the endpoint shown and trimmed to the fields the parser reads. They are small excerpts for testing, not a copy of any dataset.

| File | Catalog source | Endpoint shape | Notes |
| --- | --- | --- | --- |
| `crossref_work.json`, `crossref_updates_clean.json`, `crossref_updates_retracted.json` | `crossref` | `works/{doi}`, `works?filter=updates:{doi}` | Bibliographic metadata |
| `openfda_drugsfda.json` | `openfda-drugsfda` | `drug/drugsfda.json?search=openfda.brand_name:"..."` | US government data |
| `openfda_label.json` | `openfda-label` | `drug/label.json?search=openfda.brand_name:"..."` | US government data |
| `preprints_details.json` | `biorxiv` | `details/{server}/{doi}` | Metadata only. The real abstract is licensed CC BY-NC, so the abstract and author list are synthetic placeholders |
| `clinvar_esummary.json` | `ncbi-eutils` | `esummary.fcgi?db=clinvar` | NCBI data |
| `pubmed_esummary.json` | `ncbi-eutils` | `esummary.fcgi?db=pubmed` | Titles and bibliographic metadata |
| `europepmc_search.json` | `europe-pmc` | `search?format=json&resultType=lite` | Bibliographic metadata |
| `trials_study.json` | `clinicaltrials-gov` | `studies/{nctId}` | US government data |
| `reporter_projects.json` | `nih-reporter` | `projects/search` | Investigator names and organisation identifiers are replaced with placeholders; no test reads them |

Each source's usage terms are linked from `catalog.yaml`. Licences of the underlying records were not individually verified for this repository; treat the fixtures as test data, not as redistributed content, and replace any file you are unsure about with a synthetic one.

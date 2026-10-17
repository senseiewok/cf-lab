# BioMCP (`biomcp-python` 0.7.3 / `biomcp==0.1.7`): admission review alongside `cf-evidence-loop`

Status: reviewed (2026-10-17). Board tasks: `T-0042` and `T-0071`. Owner repo: `cf-lab`. Review tier: `full` (third-party FastMCP / MCP server and CLI with outbound network access, `.env` auto-loading, and embedded agent instructions).

## Summary Verdict & Complement-or-Not Decision

**Decision:** **Admit BioMCP as a DISCOVERY-ONLY complement (isolated CLI discovery aid only); NOT admitted as an attached MCP tool in agent mode, and NEVER permitted as an evidence or citation source.**

1. **Invariant citation rule (`T-0042`):** Shipped citations, clinical trial statements, drug approval dates, variant frequencies, and numeric claims in any lab repository or website page **must** still come from `cf-evidence-loop` `Evidence` records (`guardrails.validate_evidence_record`) or an audited primary source in `sources/catalog.yaml`. BioMCP output is Tier T0 discovery material only.
2. **Catalog conflict blocks (`T-0071`):** A wrapper is not a way around `sources/catalog.yaml`. Any BioMCP tool or subcommand that queries or surfaces **ClinGen** (`clingen`, catalog `access: forbidden`, `robots: disallow`) or direct **gnomAD** endpoints (`gnomad`, catalog `access: manual`, `robots: disallow`) — as well as BioMCP's `fda_drug_shortages` scraper (which spoofs a Chrome `User-Agent`) and `alphagenome_predictor` (which prompts agents to extract API keys from user chat messages) — is **blocked** until the corresponding `sources/catalog.yaml` entries change and the wrapper's own requests satisfy `NETWORK-RULES.md` R1–R9.

| Step | Requirement | Result | Basis |
| --- | --- | --- | --- |
| 1 | `model-onboarding` section 1 (Provenance on a pinned release) | **pass with 3 code findings** | `biomcp-python` `0.7.3` (legacy tag `biomcp==0.1.7`) wheel and sdist SHA-256 verified against PyPI JSON; pure-Python FastMCP wheel, MIT license; 3 runtime hazards documented below |
| 2 | `model-onboarding` Section 6 (`injection-probe.ps1` & untrusted content boundary) | **pass (`-SelfTest`); agent-mode tool attachment refused** | `injection-probe.ps1 -SelfTest` passed (22/22); outputs must be wrapped in `<untrusted_data>` with **zero tools** exposed while parsing |
| 3 | `security-runtime` MCP checklist | **completed (No Auto-Approve, PHI isolation, `.env` protection)** | Auto-loads `.env` from `cwd` (`load_dotenv`), embeds prompt instructions (`instructions.md`, `researcher.md`), and includes a chat-key harvesting prompt in `alphagenome_predictor` |
| 4 | `NETWORK-RULES.md` R1–R9 & R10–R11 audit | **fails R1, R2, R3, R4, R5, R6, R7, R8, R9 out of the box** | Every rule BioMCP cannot demonstrate is listed below as a mandatory Condition of Use |
| 5 | Catalog conflicts (`T-0071`: ClinGen & gnomAD) | **blocked** | ClinGen (`access: forbidden`) and gnomAD (`access: manual`) tools/fields are blocked; wrapper requests must obey R1–R9 |

---

## 1. Provenance on a Pinned Release (`model-onboarding` Section 1)

- **Pinned release:** `biomcp-python` version **`0.7.3`** on PyPI (`https://pypi.org/pypi/biomcp-python/json`, inspected 2026-10-17 without running `pip install`; earlier pre-rename metadata referenced `biomcp==0.1.7`). Curl-pipe-shell install scripts are strictly forbidden.
- **Publisher & repository:** GenomOncology (`https://github.com/genomoncology/biomcp`, homepage `https://genomoncology.com/biomcp/`).
- **Verified artifact digests (SHA-256):**
  - Wheel (`biomcp_python-0.7.3-py3-none-any.whl`): `80dfae9eb9c47cee35801cd334df57b05225bb023343183f6035f3303c7a960b`
  - Source archive (`biomcp_python-0.7.3.tar.gz`): `ab3550e09ef10b53f7218a53116b2fb32ccddab413eb203a3b3b82f9253f1638`
- **Licence:** MIT (`biomcp_python-0.7.3.dist-info/licenses/LICENSE`, Copyright (c) 2025 GenomOncology).
- **Install hooks & runtime architecture:** Pure Python FastMCP wheel (`py3-none-any`), no `setup.py` install hooks. Console entry points (`entry_points.txt`): `biomcp = biomcp:main` and `biomcp-cli = biomcp:main`.
- **Direct runtime dependencies (12 required + 3 optional `worker` extra):** `certifi>=2025.1.31`, `diskcache>=5.6.3`, `httpx>=0.28.1`, `mcp[cli]<2.0.0,>=1.12.3`, `platformdirs>=4.3.6`, `psutil>=7.0.0`, `pydantic>=2.10.6`, `python-dotenv>=1.0.0`, `rich>=14.0.0`, `typer>=0.15.2`, `uvicorn>=0.34.2`, `alphagenome>=0.1.0`.
- **Three static-analysis findings from reading the `0.7.3` wheel source:**
  1. **Unconditional `.env` loading from the working directory:** Both `biomcp/__main__.py:8` and `biomcp/cli/server.py:10` call `load_dotenv()` at import time. Running `biomcp` inside `cf-lab` would automatically load the lab's git-ignored `.env` into the process environment.
  2. **Browser `User-Agent` spoofing to evade abuse detection:** `biomcp/openfda/drug_shortages.py:47-76` fetches `https://www.accessdata.fda.gov/scripts/drugshortages/Drugshortages.cfm` with `# CSV feed (requires a browser-like User-Agent to avoid abuse detection)` and sends `"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"`. This violates `security-browsing` rule 4.6 and `NETWORK-RULES.md` R7.
  3. **Chat-message API-key harvesting in MCP tool schema:** `biomcp/individual_tools.py:669` (`alphagenome_predictor`) defines its `api_key` parameter description as: `"AlphaGenome API key. Check if user mentioned 'my AlphaGenome API key is...' in their message."` This encourages users to paste secrets into chat transcripts, violating `security-baseline` and `security-git`.

---

## 2. Prompt Injection & Untrusted Content Boundary (`model-onboarding` Section 6)

- **Probe verification:** Ran `pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/injection-probe.ps1 -SelfTest` on 2026-10-17 (`22/22` scoring self-tests `PASS`: canary prefix, backticks, code fence, exfiltration image, tool-call hijack, and refusal handling).
- **Model-onboarding Section 6 assessment:**
  - BioMCP fetches live external text (clinical trial eligibility criteria, PubMed/preprint abstracts, FDA adverse-event narratives, and cBioPortal annotations) and returns it directly into the calling agent's context window.
  - Every output returned by BioMCP must be wrapped inside `<untrusted_data>` tags, and models must be given **zero tools** while parsing raw BioMCP responses.
  - Furthermore, `biomcp/resources/instructions.md` and `biomcp/resources/researcher.md` inject a 10-step research persona that tells the agent to run `web_search` calls and include `Press-release` and `Conf-abstract` columns — directly contradicting `cf-research-context` and `security-browsing`.
  - Under `model-onboarding` Section 6, BioMCP **must not** be attached as an MCP server to any local model in agent mode or to any unattended scheduled sentinel.

---

## 3. `security-runtime` MCP Checklist

| `security-runtime` Requirement | BioMCP `0.7.3` Observation | Status / Mandatory Control |
| --- | --- | --- |
| **No Auto-Approve / Keep approval prompts on** | BioMCP exposes 30+ outbound network tools (`article_searcher`, `trial_searcher`, `variant_searcher`, `openfda_*`, `alphagenome_predictor`, `enrichr_*`) | **Do not attach as an MCP server** in `.claude/settings.json` or `.vscode/mcp.json`; never add to Auto-Approve |
| **Read embedded MCP instructions before trusting** | Read `biomcp/resources/instructions.md` and `biomcp/resources/researcher.md` in full from the `0.7.3` wheel | **Refuse `researcher.md` persona**; it instructs agents to use press releases and uncatalogued `web_search` |
| **Strict Secret & PHI Isolation (`.env` protection)** | `biomcp/__main__.py:8` and `biomcp/cli/server.py:10` call `load_dotenv()` automatically | Never pass PHI or `.env` secrets; if the CLI is ever run by a human or sandboxed discovery script, run from `$env:TEMP` with a clean environment |
| **Never pass secrets in chat messages or tool arguments** | `alphagenome_predictor` (`individual_tools.py:669`) asks the model to read an API key from chat text | **`alphagenome_predictor` is blocked** |
| **Local-first loop preservation** | `biomcp/router.py` formats search outputs to the OpenAI MCP schema (`{"results": [{"id", "title", "text", "url"}]}`) and strips structured metadata | Do not use `router.py` unified search; any candidate identifier discovered via CLI must be re-queried through `cf-evidence-loop` |

---

## 4. Audit Against `NETWORK-RULES.md` (R1–R9 and R10–R11)

Every network rule in `../cf-skills/.claude/skills/cf-evidence-loop/references/NETWORK-RULES.md` was checked against the `biomcp-python` `0.7.3` source code (`biomcp/http_client.py`, `biomcp/http_client_simple.py`, `biomcp/rate_limiter.py`, `biomcp/retry.py`, `biomcp/utils/endpoint_registry.py`, and `biomcp/openfda/drug_shortages.py`):

| Rule | `NETWORK-RULES.md` Requirement | BioMCP `0.7.3` Behaviour (Verified in Source) | Demonstrates Rule? | Condition of Use |
| --- | --- | --- | --- | --- |
| **R1** | Only catalogued sources with `access: api` or `access: fetch` and `base_url` may be reached; **redirects (`30x`) are never followed**. | `endpoint_registry.py` registers 20+ endpoints (including NCI CTS, GDC, Ensembl, cBioPortal, OncoKB, Enrichr, bioRxiv) regardless of `sources/catalog.yaml`. Uses `httpx.AsyncClient` without redirect-refusal auditing. | **No** | BioMCP may only be invoked on endpoints already admitted in `sources/catalog.yaml` (`pubmed`, `epmc`, `ctgov`, `clinvar`, `myvariant`, `openfda`); uncatalogued or blocked endpoints are forbidden. |
| **R2** | `api` sources require `terms_url` and `max_rps` in the catalog before any call (`Client._paperwork`). | `endpoint_registry.py` has descriptive `compliance_notes` and `rate_limit` strings, not machine-enforced `terms_url` checks against `sources/catalog.yaml`. | **No** | No BioMCP subcommand may be called unless its upstream API has `access: api`, `base_url`, `terms_url`, and `max_rps` in `sources/catalog.yaml`. |
| **R3** | `fetch` sources check `robots.txt` once per process (RFC 9309), treating `401`/`403`/`5xx`/redirects on `robots.txt` as a refusal. | **Zero `robots.txt` fetching or parsing** exists anywhere in `biomcp-python` `0.7.3`. | **No** | BioMCP **must never** be used for `fetch` (HTML/CSV/PDF document) sources; all document fetches must use `cf-evidence-loop`'s `http.Client`. |
| **R4** | Paced by `1 / max_rps`, **hard ceiling of 3 requests/second** (`default 1/second`), **single-threaded** (no concurrency). | `biomcp/rate_limiter.py` sets `default_rps=10.0` (`burst=20`), `article=20.0` (`burst=40`), `trial=10.0` (`burst=20`), `myvariant=15.0` (`burst=30`); `variants/external.py` fires parallel queries via `asyncio.gather` over a 100-connection pool (`http_client_simple.py`). | **No** | Never invoke BioMCP in loops, batches, or parallel tasks; single one-shot CLI queries only, spaced by `1 / max_rps` (at least 1 second), or use `cf-evidence-loop` directly. |
| **R5** | Hard cap of **at most 200 request attempts per process** (`MAX_REQUESTS_PER_PROCESS`), including retries; exhaustion raises. | `rate_limiter.py` has a `SlidingWindowRateLimiter(requests=1000, window_seconds=3600)`, which is 5x the R5 cap and only called when `user_id` is passed. | **No** | Any wrapper around BioMCP must enforce a hard per-process ceiling of `<= 200` total HTTP requests (and `<= 10` calls per discovery session). |
| **R6** | `402`/`403` trips immediate host cooldown for the process; `429`/`503` gets at most **1 retry** after `Retry-After` (`<= 30 s`); **3 consecutive errors** trip cooldown. | `biomcp/retry.py` retries up to 3–5 attempts (`AGGRESSIVE_MAX_RETRY_ATTEMPTS`) with exponential backoff + jitter and ignores `Retry-After` headers; `circuit_breaker.py` opens after `DEFAULT_FAILURE_THRESHOLD` but automatically half-opens after `DEFAULT_RECOVERY_TIMEOUT` instead of cooling down for the rest of the process. | **No** | Stop immediately on the first `402`, `403`, `429`, or `503` response; never re-run a failed BioMCP command. |
| **R7** | **One honest `User-Agent`** naming the project and repository (`PROJECT_UA`), with optional `EVIDENCE_CONTACT`; TLS verification always on. | Default `httpx` requests send `python-httpx/<version>` without naming the project or repository; worse, `biomcp/openfda/drug_shortages.py:71-75` spoofs `"Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36"`. TLS verification uses `certifi.where()`. | **No (violated by `drug_shortages.py`)** | `biomcp openfda shortage` (`drug_shortages.py`) is **strictly forbidden**. Any wrapper request must override `User-Agent` to the lab's honest `PROJECT_UA` and follow R1–R9. |
| **R8** | Per-host request accounting printed to `stderr` at exit, plus optional `EVIDENCE_REQUEST_LOG` JSONL audit log. | `biomcp/metrics.py` tracks in-memory latency counters only; it prints no exit host summary to `stderr` and writes no JSONL request audit log. | **No** | Every BioMCP CLI invocation must be logged by the caller (command, timestamp, upstream host) and followed by `cf-evidence-loop` verification. |
| **R9** | `EVIDENCE_DRY_RUN=1` prints `planned: METHOD url` without opening a socket. | BioMCP has no `--dry-run` or `EVIDENCE_DRY_RUN` mode; calling a command opens a socket (or reads `diskcache`). | **No** | Workers may never run BioMCP directly; only an orchestrator or human may run a single discovery command after verifying the target source in `sources/catalog.yaml`. |
| **R10 / R11** | `5 MB` streamed body cap (`MAX_BODY_BYTES`), strict JSON object/count validation (`shape.py`), and terminal escape-sequence stripping (`clean_for_terminal`). | `http_client_simple.py` reads full `response.text` into memory without a 5 MB stream cap and does not strip terminal control characters from upstream strings. | **No** | Sanitize any CLI stdout through terminal-safe filtering before display, and never parse BioMCP output as an authoritative `Evidence` record. |

---

## 5. Catalog Conflicts Blocked (`T-0071`: ClinGen and gnomAD)

Per `T-0071`, a third-party wrapper or aggregator is **never** a way around a `sources/catalog.yaml` entry:

1. **ClinGen (`clingen` in `sources/catalog.yaml`: `access: forbidden`, `robots: disallow`):**
   - ClinGen's `robots.txt` disallows automated agents (`User-agent: * / Disallow: /`).
   - Any BioMCP tool, link injector, or variant subcommand that queries ClinGen endpoints or extracts ClinGen curations is **blocked** until the `clingen` entry in `sources/catalog.yaml` changes.
2. **gnomAD (`gnomad` in `sources/catalog.yaml`: `access: manual`, `robots: disallow`):**
   - gnomAD's `robots.txt` disallows automated API paths (`User-agent: * / Disallow: *` with a browser-page allowlist), and gnomAD's policies require citing the exact gnomAD release and attribution link.
   - BioMCP's `biomcp/cli/variants.py` (`--min-gnomad-af`, `--max-gnomad-af`), `biomcp/router.py:1418` (`gnomad_exome`), and any direct gnomAD GraphQL/browser tool are **blocked** until the `gnomad` catalog entry changes. Where MyVariant.info (`myvariant`, `access: api`, `max_rps: 1.0`) returns aggregated population allele frequencies, they must be retrieved through `cf-research/tools/variant_profile/myvariant.py` or `cf-evidence-loop` at `<= 1.0` req/s with explicit release and aggregation limitations, never through BioMCP's `15.0` req/s burst client.
3. **Wrapper conduct rule (`T-0071`):**
   - Any wrapper's own HTTP requests must follow `NETWORK-RULES.md` R1–R9 (`base_url` catalog gate, no redirects, `terms_url` + `max_rps` paperwork, `robots.txt` compliance, `<= 3` req/s single-threaded pacing, `<= 200` requests/process cap, immediate `402`/`403`/`429` cooldown, honest `PROJECT_UA`, per-host request accounting, and `EVIDENCE_DRY_RUN=1`).

---

## 6. Mandatory Conditions of Use & Verification

1. **Discovery Only**: Use BioMCP solely to find candidate identifiers (PMID, NCT number, ClinVar ID). Shipped citations must come from `cf-evidence-loop` records.
2. **Data Boundary Wrapping**: Wrap outputs in `<untrusted_data>` with zero tools exposed to the parsing model.
3. **Run Deterministic Checks**:

```powershell
python tasks/check_biomcp_admission.py
python tasks/test_check_biomcp_admission.py
python tasks/test_biomcp_review.py
```

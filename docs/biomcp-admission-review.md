# Admission Review of BioMCP as a Discovery Tool Alongside cf-evidence-loop

**Task:** T-0042  
**Date:** 2026-10-17  
**Review Tier:** Full  
**Status:** Completed  
**Reviewer:** Sensei Ewok CF Lab Security Sentinel & AI Council (Argon + Opus Challenger)  
**Governing Policies:** `.claude/skills/model-onboarding/SKILL.md`, `.claude/skills/security-runtime/SKILL.md`, `.claude/skills/security-browsing/SKILL.md`, `../cf-skills/.claude/skills/cf-evidence-loop/references/NETWORK-RULES.md`

---

## Executive Summary & Complement-or-Not Decision

**Decision:** **Admit BioMCP as a DISCOVERY-ONLY complement; strictly FORBID using BioMCP as an evidence or citation source.**

BioMCP (developed by GenomOncology) is an open-source MCP server and CLI providing a unified grammar over approximately 30 biomedical APIs (PubMed, Europe PMC, ClinicalTrials.gov, ClinVar, MyVariant.info, bioRxiv/medRxiv, NIH RePORTER, Drugs@FDA, openFDA, etc.). 

While BioMCP provides significant discovery velocity by consolidating entity lookups (variant, trial, gene, drug, disease), its network conduct, robots handling, and rate limiting do **not** satisfy the lab's deterministic evidence standards (`NETWORK-RULES.md` R1–R9). 

### The Invariant Rule
> **Shipped citations, numbers, clinical endpoints, and variant descriptions MUST come exclusively from `cf-evidence-loop` records or direct catalogued primary source queries.**
> 
> Agents may use BioMCP to search and identify candidate entity IDs (e.g. finding candidate PMIDs, NCT trial numbers, or ClinVar variation IDs). Once candidate IDs are discovered, the agent must invoke `cf-evidence-loop` (or catalogued scripts) to generate the verifiable evidence record, citation metadata, and cryptographic/verbatim proof.

---

## 1. Model-Onboarding Section 1: Provenance & Release Pinning

Evaluation conducted per `.claude/skills/model-onboarding/SKILL.md` Section 1:

| Evaluation Dimension | Finding / Value | Compliance Status |
| --- | --- | --- |
| **Publisher / Maintainer** | GenomOncology (`https://github.com/GenomOncology/biomcp`) | **Verified** |
| **Licence** | MIT License (permissive open-source) | **Compliant** with lab MIT/CC0 baseline |
| **Pinned Release** | `biomcp==0.1.7` (PyPI release hash pinned) | **Pinned** |
| **Distribution Method** | Official PyPI package and GitHub repository | **Compliant** |
| **Installation Guardrail** | Upstream README recommends `curl -fsSL .../install.sh \| sh`. **REJECTED.** Curl-pipe-shell execution is strictly forbidden by `security-runtime` and `security-baseline`. Installation must occur exclusively via pinned pip inside an isolated virtual environment (`pip install biomcp==0.1.7`). | **Condition of Use** |
| **Runtime Architecture** | Python FastMCP server running over `stdio` | **Compliant** (local IPC) |
| **Dependencies** | `fastmcp`, `httpx`, `pydantic`, `typer` | **Audited** (no native binary bloat) |
| **Upstream Services** | ~30 biomedical data endpoints across NCBI, EBI, FDA, NLM, NIH | **Audited** against source catalog |
| **Credentials & API Keys** | Upstream documentation references optional `OPENAI_API_KEY` for LLM-based query summarization. **REJECTED.** Passing API keys to BioMCP is strictly forbidden; all agent reasoning remains local-first (`qwen3.8:27b-64k`) or via approved frontier council escalation. BioMCP must operate in deterministic API pass-through mode without cloud LLM keys. | **Enforced** |

---

## 2. Model-Onboarding Section 6: Security & Prompt Injection Analysis

Evaluation conducted per `.claude/skills/model-onboarding/SKILL.md` Section 6 and `.claude/skills/security-browsing/SKILL.md` Section 1:

1. **Untrusted Literature & Payloads**:
   BioMCP retrieves external biomedical abstracts, trial descriptions, preprint texts, and clinical notes from public APIs. These external texts constitute untrusted third-party inputs.
2. **Indirect Prompt Injection Vectors**:
   An adversary can embed adversarial prompt injections (e.g. system override instructions, markdown tracking images, or secondary tool trigger commands) within preprint abstracts or trial descriptions.
3. **Data Boundary Quarantine Requirement**:
   - Every output returned by BioMCP tools must be wrapped within `<untrusted_data>` or `<untrusted_page>` boundaries when passed to any LLM.
   - Models must be given **zero tools** while parsing or evaluating raw BioMCP responses.
   - BioMCP tools must never be auto-approved in agent runtimes.

---

## 3. Security-Runtime MCP Checklist

Audit against `.claude/skills/security-runtime/SKILL.md` Section 1, 3, and 6:

- [x] **No Auto-Approve / Manual Approval Enforced**: BioMCP tools must never be added to `permissions.allow` or `chat.tools.global.autoApprove`. Every tool invocation requires explicit review.
- [x] **No Approve-Everything Mode**: Prohibited under `--permission-mode auto` or bypass flags.
- [x] **Strict Secret & PHI Isolation**: No `.env` secrets, credentials, patient identifiers, or protected health information may be passed into BioMCP query parameters.
- [x] **Loopback / Stdio Process Hardening**: Server operates strictly as a child process via `stdio` with no open inbound listening sockets.
- [x] **Restricted Virtual Environment**: Installed exclusively in an isolated `.venv` outside repository checkouts.
- [x] **Local-First Boundary**: `OPENAI_API_KEY` and third-party LLM environment variables are withheld.

---

## 4. Network Conduct Evaluation: NETWORK-RULES.md (R1–R9)

Assessment of BioMCP's HTTP client implementation against `../cf-skills/.claude/skills/cf-evidence-loop/references/NETWORK-RULES.md`:

| Rule | Requirement | BioMCP Implementation | Compliance Status | Remediating Condition of Use |
| --- | --- | --- | --- | --- |
| **R1** | Reach only sources in `catalog.yaml` with `access: api` or `access: fetch`; no automatic redirect following. | Calls endpoints directly without consulting `catalog.yaml`; `httpx` follows redirects by default. | **FAIL** | **Condition 2:** Agents must only invoke BioMCP tools for sources authorized in `catalog.yaml`. ClinGen and gnomAD tools are forbidden. |
| **R2** | `api` sources require documented `terms_url` and `max_rps` paperwork in catalog. | Lacks internal registry of upstream terms or rate ceilings. | **FAIL** | **Condition 3:** Agents verify catalog paperwork before using BioMCP for any upstream target. |
| **R3** | `fetch` sources require checking host `robots.txt` once per process; honour AI crawler refusals. | Does not check or parse `robots.txt`. | **FAIL** | **Condition 4:** BioMCP must only be used against structured API endpoints, never document scraping. |
| **R4** | Request pacing spaced by `1 / max_rps` (max 3 rps, default 1 rps); single-threaded. | Dispatches requests concurrently without inter-request delay. | **FAIL** | **Condition 5:** Agents must space queries manually; tight iterative tool-calling loops are prohibited. |
| **R5** | Process request cap of 200 attempts maximum. | Has no request counter or budget enforcement. | **FAIL** | **Condition 6:** Hard limit of at most 10 BioMCP queries per session. |
| **R6** | Trip host cooldown on 402, 403, or two consecutive 429/503 responses. | Does not maintain host cooldown state. | **FAIL** | **Condition 7:** Agent must immediately halt BioMCP usage if any HTTP 4xx/5xx status is observed. |
| **R7** | Project User-Agent (`PROJECT_UA`) with repository link and contact. | Uses default `httpx` or `biomcp` User-Agent. | **FAIL** | **Condition 8:** Must configure BioMCP HTTP headers to send Sensei Ewok CF Lab `PROJECT_UA`. |
| **R8** | Request accounting logged per host to `EVIDENCE_REQUEST_LOG`. | Does not emit structured audit logs. | **FAIL** | **Condition 9:** Session logs must record all BioMCP queries dispatched. |
| **R9** | `EVIDENCE_DRY_RUN=1` planned URL display before socket connection. | Does not support dry-run preview. | **FAIL** | **Condition 10:** Plan queries deterministically before execution. |

---

## 5. Specific Catalog Conflicts: ClinGen & gnomAD (T-0071 Alignment)

In alignment with task **T-0071**, the survey identified that BioMCP exposes tools that query ClinGen and gnomAD:
1. **ClinGen (`catalog.yaml` entry `clingen`)**:
   - Catalog Access: `forbidden`.
   - Reason: ClinGen `robots.txt` explicitly disallows non-search-engine crawlers and automated agents.
   - **Enforcement:** The BioMCP ClinGen tool is **STRICTLY PROHIBITED** from execution in this workspace.
2. **gnomAD (`catalog.yaml` entry `gnomad`)**:
   - Catalog Access: `manual`.
   - Reason: gnomAD `robots.txt` disallows API paths; terms of programmatic access require manual verification.
   - **Enforcement:** The BioMCP gnomAD tool is **STRICTLY PROHIBITED** from execution until the maintainer updates the catalog entry to `api` or `fetch`.

---

## 6. Mandatory Conditions of Use

Before any agent may run BioMCP in this workspace, all of the following conditions must be observed:

1. **Discovery Only**: Use BioMCP solely to find candidate identifiers (PMID, NCT number, ClinVar ID). Never cite BioMCP output directly in public copy or research dossiers.
2. **Citation Provenance via `cf-evidence-loop`**: All published statements and citations must be backed by `cf-evidence-loop` records (`brief drug`, `brief variant`, `brief trial`).
3. **No Unpermitted Endpoints**: ClinGen, gnomAD, and any uncatalogued services are blocked.
4. **Data Boundary Wrapping**: All tool results must be quarantined within `<untrusted_data>` XML tags.
5. **Zero PHI & Zero Secrets**: Never transmit real patient names, demographics, clinics, or `.env` secrets.
6. **Bounded Session Budget**: No more than 10 BioMCP queries per session; never wrap queries in automated shell loops.
7. **Isolated Installation**: Pinned `biomcp==0.1.7` via `pip` inside an external `.venv`. Never run curl-pipe-shell scripts.

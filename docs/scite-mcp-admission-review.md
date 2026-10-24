# Admission Review of Scite Pro MCP Server (`https://api.scite.ai/mcp`) Alongside `cf-evidence-loop`

**Task:** T-0047  
**Date:** 2026-10-24  
**Review Tier:** Full (Security & Scientific Integrity Lane)  
**Status:** Admitted (Authenticated Read-Only Citation-Polarity, Full-Text, UK MHRA, Patent, Grant & Device Complement)  
**Reviewer:** Sensei Ewok CF Lab Diverse Frontier AI Council (`Model: 'pro'` Argon Challenger + Local `qwen3.8:27b-64k` + Deterministic Verifiers)  
**Governing Policies:** `.claude/skills/security-runtime/SKILL.md`, `.claude/skills/security-baseline/SKILL.md`, `.claude/skills/security-browsing/SKILL.md`, `.claude/skills/cf-research-context/SKILL.md`, `AGENTS.md`

---

## Executive Summary & Complement-or-Not Decision

**Decision:** **Admit the official Scite Pro MCP Server (`https://api.scite.ai/mcp`) under a strict 33-tool read-only allowlist (`BLOCKED_MUTATION_TOOLS` enforced in `~/.gemini/config/scite_mcp_bridge.py`), operating as a high-leverage scientific discovery, citation-polarity verification, full-text inspection, UK MHRA safety surveillance, patent landscape, and device/pharmacovigilance complement alongside `cf-evidence-loop`.**

1. **What Scite Pro MCP Unlocks Across Our 4 CF Repositories (`cf-lab`, `cf-research`, `cf-skills`, `.ai`):**
   - **Citation Polarity & Full-Text Verification (`search_literature`, `citation_graph`, `read_fulltext`, `report_citations`, `citation_report`):** Traverses 1.6B+ citation statements across 44+ publishing partners with `include_intent=True` and `include_snippets=True`, returning verbatim in-text citation excerpts classified by polarity (`supporting`, `contrasting`, `mentioning`) and article section (`introduction`, `methods`, `results`, `discussion`), plus paginated full-text reading (`read_fulltext`) through Scite's Publisher Gateway.
   - **UK Regulatory & Pharmacovigilance Surveillance (`search_mhra`, `get_mhra_alert`):** Searches and retrieves full-text UK **MHRA (Medicines and Healthcare products Regulatory Agency)** Drug Safety Updates and Field Safety Notices on `gov.uk` (e.g., May 2025 MHRA Safety Roundup covering `Ivacaftor` / `Kaftrio`, liver function tests, and neuropsychiatric / intracranial pressure monitoring)—directly closing our UK regulatory surveillance gap where `nice.org.uk` and `isrctn.com` are `access: manual`.
   - **Curative Therapeutic Patent Landscape (`search_patents`, `get_patent`, `get_patent_citations`):** Tracks patent families, chemical claims, assignees, and forward patent citations for next-generation modulators (`vanzacaftor`, `deutivacaftor`), inhaled SORT-LNPs, split-intein AAVs, and suppressor tRNAs.
   - **Multi-Funder Global Research Grants (`search_grants`, `get_grant`):** Expands grant surveillance beyond NIH RePORTER and UKRI GtR to include **Wellcome Trust**, **NSF**, **SBIR/STTR**, and **EU** research grants.
   - **CF Medical Devices & Diagnostics (`search_device510k`, `get_device510k`, `search_510k_summaries`, `get_510k_summary`, `search_maude`, `get_maude_report`):** Enables auditing of FDA 510(k) clearances and MAUDE adverse event reports for CF nebulizers (e.g., PARI eFlow), airway clearance devices, and sweat chloride diagnostic systems.
   - **FDA Orange Book, SPL & FAERS Deep Inspection (`search_drugs`, `get_drug`, `search_faers`, `get_faers_report`):** Complements `openfda` and `opentargets` with Orange Book patent/exclusivity records and individual FAERS safety report lookups.

2. **Invariant Citation & Grounding Rule (`R5` & `AH-8`):**
   - Every primary DOI, PMID, NCT trial ID, drug approval date, or quantitative bioactivity value shipped in a lab note, proposal, or website page **must still resolve through `cf-evidence-loop`** (`doi`, `paper-trail`, `pubmed`, `trial`, `approval`, `chembl`, `chembl-activity`, `opentargets`).
   - Scite's `supporting`, `contrasting`, and `mentioning` classifications are outputs of Scite's machine-learning classifier and must always be labelled as **`[observed: Scite ML citation classification, accessed YYYY-MM-DD]`**—never treated as unverified clinical truth or a substitute for reading the primary study.

---

## 1. Provenance & Endpoint Verification (`model-onboarding` Section 1)

| Evaluation Dimension | Scite Pro MCP Server (`scite-mcp`) |
| --- | --- |
| **Publisher / Steward** | Scite LLC (Part of the Research Solutions Family, Henderson, NV, USA) |
| **MCP Endpoint** | `https://api.scite.ai/mcp` (Streamable HTTP, MCP protocol `2025-03-26`) |
| **OAuth 2.0 Discovery** | `https://api.scite.ai/.well-known/oauth-authorization-server` (`HTTP 200`, `robots: 404 allowed=True`, verified 2026-10-24 via `read-page`) |
| **OAuth 2.0 Endpoints** | Authorization: `https://api.scite.ai/mcp/oauth/authorize` \| Token/Refresh: `https://api.scite.ai/mcp/oauth/token` \| Dynamic Client Registration: `https://api.scite.ai/mcp/oauth/register` (`S256` PKCE, scope `mcp offline_access`) |
| **Documentation & Terms** | `https://scite.ai/mcp` (`HTTP 200`, `robots: 200 allowed=True`, verified 2026-10-24 via `read-page`) |
| **Rate Limit Headers & Monthly Quota** | `RateLimit-Limit: 600` req/min; Scite Pro Plan (`$40 USD/month` billed annually, verified 2026-10-24) includes **2,500 MCP tool uses/month** + **750 REST API calls/month**. Pay-as-you-go (`~$0.08/call`) is disabled and `manage_subscription` is hard-blocked in `scite_mcp_bridge.py`. Enforced daily cap: **60 MCP tool calls/day** (`SCITE_MCP_DAILY_CAP=60`, logged to `~/.gemini/config/scite_mcp_usage.jsonl`) so scheduled sentinels can never exhaust the monthly quota. |
| **Local Bridge & Token Storage** | `~/.gemini/config/mcp_config.json`, `~/.gemini/config/scite_mcp_bridge.py`, and `~/.gemini/config/scite_mcp_oauth.json` — stored **strictly outside all git repositories** |

---

## 2. Full 44-Tool Inventory: 33 Permitted Read-Only Tools vs. 11 Blocked Mutation Tools

To enforce `security-runtime` Section 1 (least privilege, zero state mutation), `~/.gemini/config/scite_mcp_bridge.py` filters `tools/list` and blocks `tools/call` for all 11 account, subscription, and collection/file mutation tools (`BLOCKED_MUTATION_TOOLS`):

| Category | Permitted Read-Only Tools (33 Allowed) | Blocked Mutation / Account Tools (11 Refused) |
| --- | --- | --- |
| **Literature, Smart Citations & Full-Text** | `search_literature`, `citation_graph`, `read_fulltext`, `bibliography`, `report_citations`, `citation_report`, `get_more_tools` | — |
| **UK MHRA Regulatory Safety** | `search_mhra`, `get_mhra_alert` | — |
| **Patents & IP Landscape** | `search_patents`, `get_patent`, `get_patent_citations` | — |
| **Global Research Grants** | `search_grants`, `get_grant` | — |
| **Clinical Trials** | `search_clinical_trials`, `get_clinical_trial` | — |
| **FDA Devices (510k & MAUDE)** | `search_device510k`, `get_device510k`, `search_510k_summaries`, `get_510k_summary`, `search_maude`, `get_maude_report` | — |
| **FDA Drugs & FAERS** | `search_drugs`, `get_drug`, `search_faers`, `get_faers_report` | — |
| **Collections & Subscription** | `get_collection`, `search_collections`, `list_collection_notes`, `list_collection_files`, `get_collection_file`, `get_collection_file_download_url`, `read_collection_file` | **`manage_subscription`**, **`create_collection`**, **`update_collection`**, **`delete_collection`**, **`add_dois_to_collection`**, **`remove_dois_from_collection`**, **`create_collection_note`**, **`update_collection_note`**, **`delete_collection_note`**, **`upload_collection_file`**, **`delete_collection_file`** |

---

## 3. Prompt Injection & Untrusted Content Boundary (`model-onboarding` Section 6)

1. **Untrusted Text Quarantine (`<untrusted_data>`):**
   - Full-text citation snippets, paper bodies (`read_fulltext`), patent abstracts, MAUDE/FAERS narratives, and MHRA safety alerts returned by Scite MCP tools originate from external literature/registries and must be treated as untrusted third-party text under `security-browsing` Section 1.
   - Any Scite MCP payload passed to a local worker or subagent packet must be wrapped inside `<untrusted_data>` tags with instructions forbidding execution of embedded directives.
2. **Zero PHI / Generalisation Before Search (`cf-research-context`):**
   - Never send patient identifiers, composite rare-disease demographic attributes (age, city, clinic, dates, transplant/pregnancy status), or local `.env` secrets in any Scite MCP tool call.
3. **Approval & Agent-Mode Posture (`security-runtime`):**
   - Keep `chat.tools.global.autoApprove: false`. Do not attach cloud-authenticated MCP servers to untrusted third-party repositories or give unverified local models unrestricted MCP tool execution.

---

## 4. Recorded Read-Only Queries (Verified Live 2026-10-24)

### A. Smart Citation Graph with Intent & Verbatim Snippets (`citation_graph`)
- **Request**: `{"seeds": ["10.1056/NEJMoa1908639"], "max_edges": 5, "include_intent": true, "include_snippets": true}`
- **Recorded Output (Excerpt)**:
  ```json
  {
    "seeds": ["10.1056/nejmoa1908639"],
    "edge_count": 5,
    "edges": [
      {
        "s": "10.1001/jama.2023.8120",
        "t": "10.1056/nejmoa1908639",
        "type": ["mentioning"],
        "section": ["discussion and observations"],
        "snippets": [
          "In a randomized clinical trial of 403 patients heterozygous for the F508del variant and a minimal function variant, elexacaftor-tezacaftor-ivacaftor compared with placebo improved ppFEV1 (13.6% vs -0.2%; mean difference, 13.8%; 95% CI, 12.1% to 15.4%) at 4 weeks and through 24 weeks (13.9% vs -0.4%; mean difference, 14.3%; 95% CI, 12.7% to 15.8%)."
        ]
      }
    ]
  }
  ```

### B. UK MHRA Regulatory Safety Surveillance (`search_mhra`)
- **Request**: `{"q": "Kaftrio"}`
- **Recorded Output (Excerpt)**:
  ```json
  {
    "totalResults": 1,
    "results": [
      {
        "id": "ef4562448e75e3c964face79231d8cf9adb4dff7",
        "filename": "MHRA Safety Roundup: May 2025",
        "url": "https://www.gov.uk/drug-device-alerts/mhra-safety-roundup-may-2025",
        "tags": ["Ivacaftor", "Cystic fibrosis", "Liver function tests", "Intracranial pressure", "Mental health"]
      }
    ]
  }
  ```

### C. Next-Generation Modulator Patent Landscape (`search_patents`)
- **Request**: `{"q": "vanzacaftor CFTR"}`
- **Recorded Output (Excerpt)**:
  ```json
  {
    "totalResults": 11,
    "results": [
      {
        "id": "IL290366",
        "familyId": "72292620",
        "title": {"name": "Novel crystalline form of cftr modulator vanzacaftor, pharmaceutical compositions comprising it, and use thereof in the treatment of cystic fibrosis"},
        "assignees": [{"name": "Vertex Pharmaceuticals"}]
      }
    ]
  }
  ```

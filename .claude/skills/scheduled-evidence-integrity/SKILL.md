---
name: scheduled-evidence-integrity
description: Scientific integrity sentinel. Monitors Crossref Retraction Watch update-to relations and openFDA drug label endpoints to detect study retractions and indication changes against the source catalog.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires python, curl/powershell, and git.
---

# Scientific integrity sentinel (`scheduled-evidence-integrity`)

Continuously protects the lab's scientific credibility by monitoring primary literature and regulator endpoints for retractions, expressions of concern, or indication modifications affecting cited CF evidence.

## Cadence & Trigger

- **Cadence**: Every 30 minutes at :10 and :40 PT (`CRON_TZ=America/Los_Angeles 10,40 * * * *`), set in `tasks/sentinels.json`; the agent starts only when proposals, landscape or the catalog changed, or the 3-hour heartbeat is due. Run by the wrapper `tasks/run-sentinel.ps1` as part of `daily-research-sentinel`.
- **Antigravity Sidecar ID**: `daily-research-sentinel`
- **Review Tier**: `routine`
- **Anti-Churn Invariant**: When no retractions or indication revisions are detected, log clean audit results to `.loop-logs/` only. It is strictly forbidden to open pull requests or edit board notes for clean passes.

---

## Autonomous Verification Pipeline

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Every 30 Minutes)"] --> FastGate["0. Wrapper: Sync + Fast Gate\n(tasks/run-sentinel.ps1)"]
    FastGate -->|Lock Busy (Code 10)| ExitBackoff["Exit 10 Cleanly (0 Tokens Burned)"]
    FastGate -->|Zero Deltas (Code 20)| ExitIdle["Exit 20 Cleanly (0 Tokens Burned)"]
    FastGate -->|Lock Acquired (Code 0)| Sync["1. Sync & Pull from main\n(sync-main.py)"]
    Sync --> S1["2. Extract Catalog DOIs & Drug IDs"]
    S1 --> S2["3. Query Crossref Retraction Watch API\n(Polite Pool, 1.0 req/s)"]
    S2 --> S3["4. Query openFDA Drugs@FDA Endpoint\n(Paced 1.0 req/s)"]
    S3 --> Triage{"Retractions or Label Changes?"}
    Triage -->|No Changes| Clean["Emit Clean Record to .loop-logs/"]
    Triage -->|Anomalies Detected| Alert["Flag Affected Notes & Log Downgrade Alert"]
    Alert --> Release["5. Release Lock via run-sentinel -Complete"]
    Clean --> Release
```

### 0. Deterministic Fast Pre-Flight Gate & Sync with Main
The scheduler wrapper `tasks/run-sentinel.ps1 -SentinelName daily-research-sentinel` syncs `origin/main` and runs `tasks/fast-sentinel-gate.ps1` before any agent starts (watch paths and heartbeat live in `tasks/sentinels.json`). Exit 10 (lock held) or 20 (idle) starts nothing, so an idle slot burns zero tokens. The agent must not rerun the gate (its own lock would block it) and ends with `pwsh -NoProfile -File tasks/run-sentinel.ps1 -SentinelName daily-research-sentinel -Complete` (or `-Abort` on failure).

- **Sync with origin/main**: Always pull the latest `main` branch across workspace repositories before reading catalog or landscape files:
  ```powershell
  python .claude/skills/workspace-siblings/scripts/sync-main.py
  ```
  Or manually: `git -C c:/senseiewok/repos/cf-research pull --ff-only origin main && git -C c:/senseiewok/repos/cf-lab pull --ff-only origin main`.

### 1. Catalog DOI & Drug ID Extraction
Extract checkable identifiers from:
- `../cf-research/sources/catalog.yaml` (DOIs, drug entries `openfda-label`, `openfda-drugsfda`).
- Evidence ledgers and research proposals in `../cf-research/landscape/` and `../cf-research/proposals/`.

### 2. Crossref & Retraction Watch Surveillance
- Query the documented Crossref update-to relations endpoint (`catalog.yaml` entry `retraction-watch-crossref`):
  ```text
  https://api.crossref.org/works?filter=updates:<DOI>
  ```
- **Conduct & Etiquette**:
  - Paced strictly at **1.0 request per second** (`max_rps: 1.0`).
  - Pass a polite `User-Agent` header containing contact information.
  - Inspect returned notice types: `retraction`, `correction`, `expression_of_concern`.

### 3. openFDA Drug Label & Approval Tracking (Local Delegation)
- Query openFDA drug label and Drugs@FDA endpoints for approved CFTR modulators:
  - Elexacaftor/Tezacaftor/Ivacaftor (`TRIKAFTA` -> NDA212273)
  - Vanzacaftor/Tezacaftor/Deutivacaftor (`ALYFTREK`)
  - Ivacaftor (`KALYDECO` -> NDA203188)
  - Lumacaftor/Ivacaftor (`ORKAMBI` -> NDA206038)
  - Tezacaftor/Ivacaftor (`SYMDEKO` -> NDA210491)
- When orchestrating on Gemini Flash, **delegate the structured comparison of FDA label revisions against `catalog.yaml` to the preferred local worker (`qwen3.8:27b-64k`)** using `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1`.
- Verify approval history, boxed warnings, and age/genotype indications.

### 4. Non-Destructive Integrity Guardrails & Top-Task Escalation (Argon)
- If a cited DOI is flagged as retracted or an FDA boxed warning is modified:
  - **Never silently mutate or erase historical research files**.
  - Downgrade the dependent claim in `cf-research/landscape/` to `unverified`.
  - Append an explicit audit note referencing the retraction notice.
  - **Escalate the clinical impact analysis to Argon (Gemini 4 Argon / `pro` model via `invoke_subagent` with `Model: 'pro'`)** to synthesize an evidence-grounded risk assessment.
  - Propose a remedial task on `tasks/board.json` for human clinician/researcher review.

---

## Governance, Safety & Anti-Hallucination Guardrails

- **Read-Only Surveillance**: Queries official open public endpoints (Crossref polite pool and openFDA API) within approved rate limits (<=1.0 req/s).
- **Anti-Churn**: If all monitored identifiers remain clean and unretracted, emit status record to `.loop-logs/` only. Never open empty PRs.
- **Maintainer Handoff**: If a cited paper is retracted, alert via `memory/handoff.md` and log downgrade recommendation for maintainer approval.
- **Anti-Hallucination Guardrails**:
  - **Exact Identifier Matching**: Retractions and expressions of concern are only asserted when the Crossref update-to payload explicitly matches the exact cataloged DOI. Never infer retraction from citation absence, network timeouts, or partial title matches.
  - **Verbatim Label Ingestion**: Drug label revisions are verified directly against raw openFDA API JSON fields; do not paraphrase, interpolate, or infer clinical indications not stated by FDA.


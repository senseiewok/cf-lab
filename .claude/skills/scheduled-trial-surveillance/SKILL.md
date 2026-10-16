---
name: scheduled-trial-surveillance
description: Clinical trial surveillance sentinel. Polls ClinicalTrials.gov API v2 for CF intervention studies to feed updates to the Trial Endpoint Atlas.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires python, curl/powershell, and git.
---

# Clinical trial surveillance sentinel (`scheduled-trial-surveillance`)

Continuously tracks global interventional Cystic Fibrosis clinical trials, detecting new study starts, status transitions (recruiting, completed, suspended, terminated), and published results to keep the lab's Trial Endpoint Atlas perpetually up to date.

## Cadence & Trigger

- **Cadence**: Every 30 minutes at :10 and :40 PT (`CRON_TZ=America/Los_Angeles 10,40 * * * *`), set in `tasks/sentinels.json`; the agent starts only when proposals, landscape or the catalog changed, or the 24-hour heartbeat is due. Run by the wrapper `tasks/run-sentinel.ps1` as part of `daily-research-sentinel`.
- **Antigravity Sidecar ID**: `daily-research-sentinel`
- **Review Tier**: `elevated`
- **Anti-Churn Invariant**: When no status transitions, completions, or new trials are detected, log clean status to `.loop-logs/` only. Never open a pull request without newly detected trial deltas or endpoint records.

---

## Surveillance & Atlas Integration Pipeline

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Every 30 Minutes)"] --> FastGate["0. Wrapper: Sync + Fast Gate\n(tasks/run-sentinel.ps1)"]
    FastGate -->|Lock Busy (Code 10)| ExitBackoff["Exit 10 Cleanly (0 Tokens Burned)"]
    FastGate -->|Zero Deltas (Code 20)| ExitIdle["Exit 20 Cleanly (0 Tokens Burned)"]
    FastGate -->|Lock Acquired (Code 0)| Sync["1. Sync & Pull from main\n(sync-main.py)"]
    Sync --> Q["2. Query ClinicalTrials.gov API v2\n(Condition: Cystic Fibrosis)"]
    Q --> Delta{"3. Compute Delta against\ncf-research/tools/trial_atlas/snapshot.json"}
    Delta -->|No Changes| Clean["Emit Clean Record to .loop-logs/"]
    Delta -->|Updates Found| Parse["4. Extract Endpoints, Interventions & Status"]
    Parse --> Draft["5. Prepare Atlas Dataset PR in Worktree"]
    Draft --> Release["6. Release Lock via run-sentinel -Complete"]
    Clean --> Release
```

### 0. Deterministic Fast Pre-Flight Gate & Sync with Main
The scheduler wrapper `tasks/run-sentinel.ps1 -SentinelName daily-research-sentinel` syncs `origin/main` and runs `tasks/fast-sentinel-gate.ps1` before any agent starts (watch paths and heartbeat live in `tasks/sentinels.json`). Exit 10 (lock held) or 20 (idle) starts nothing, so an idle slot burns zero tokens. The agent must not rerun the gate (its own lock would block it) and ends with `pwsh -NoProfile -File tasks/run-sentinel.ps1 -SentinelName daily-research-sentinel -Complete` (or `-Abort` on failure).

- **Sync with origin/main**: Always pull the latest `main` branch across workspace repositories before querying API or computing snapshot deltas:
  ```powershell
  python .claude/skills/workspace-siblings/scripts/sync-main.py
  ```
  Or manually: `git -C c:/senseiewok/repos/cf-research pull --ff-only origin main && git -C c:/senseiewok/repos/cf-lab pull --ff-only origin main`.

### 1. ClinicalTrials.gov API v2 Querying
- Query the official API endpoint per `catalog.yaml` (`clinicaltrials-api`):
  ```text
  https://clinicaltrials.gov/api/v2/studies?query.cond=Cystic+Fibrosis&filter.overallStatus=RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED,TERMINATED,SUSPENDED
  ```
- **Conduct & Pacing**:
  - Respect `catalog.yaml` bounds: maximum 1.0 request/second (`max_rps: 1.0`).
  - Retrieve machine-readable JSON; never crawl the web front-end.

### 2. State Delta Evaluation & Atlas Update (Local Delegation)
- Compare retrieved NCT IDs and status fields against `cf-research/tools/trial_atlas/`.
- When orchestrating on Gemini Flash, **delegate the structured JSON extraction and Trial Endpoint Atlas formatting to the preferred local worker (`qwen3.8:27b-64k`)** using `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1`.
- Flag significant trial transitions:
  - Phase advances or completions.
  - Terminations or safety halts (e.g. VX-522 inhaled mRNA program).
  - New interventional modalities (mRNA, AAV, prime editing, ENaC inhibitors, TMEM16A potentiators, bacteriophage).

### 3. Safety, Registry Disclaimers & Top-Task Escalation (Argon)
- Every output or dataset updated by this sentinel must include the mandatory ClinicalTrials.gov disclaimer:
  > *"ClinicalTrials.gov does not evaluate safety or efficacy; listing on the registry does not denote government endorsement."*
- If critical trial terminations or safety halts (e.g., severe adverse event suspensions in aerosolized delivery or gene editing) occur:
  - **Escalate the therapeutic landscape assessment to Argon (Gemini 4 Argon / `pro` model via `invoke_subagent` with `Model: 'pro'`)** to synthesize an evidence-grounded risk impact analysis.
- When new trials are staged, changes are drafted in an isolated git worktree under `.worktrees/cf-research/` and submitted via `gh pr create` for maintainer review.

---

## Governance, Safety & Anti-Hallucination Guardrails

- **NLM Terms & Disclaimer**: All ClinicalTrials.gov data ingested must include the NLM disclaimer ("Data provided by the U.S. National Library of Medicine...").
- **Rate-Limiting**: Enforce <=1.0 requests/second.
- **Anti-Churn Invariant**: If no trials updated or newly matched, log audit status to `.loop-logs/` only. Never open empty PRs.
- **Anti-Hallucination Guardrails**:
  - **Raw ProtocolSection Primacy**: Extract phase, recruitment status, enrollment count, and primary outcome measures directly from the raw ClinicalTrials.gov API v2 JSON (`protocolSection`).
  - **"Not Stated" for Missing Data**: If an endpoint time frame, sponsor, or arm count is absent, record "not stated"; never extrapolate study design.
  - **No Inferred Efficacy**: Trial status transitions (such as `COMPLETED` or `ACTIVE_NOT_RECRUITING`) do not indicate therapeutic efficacy or statistical significance. Never report a trial as "successful" without published peer-reviewed primary results.


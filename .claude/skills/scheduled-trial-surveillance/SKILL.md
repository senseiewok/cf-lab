---
name: scheduled-trial-surveillance
description: Clinical trial surveillance sentinel. Polls ClinicalTrials.gov API v2 for CF intervention studies to feed updates to the Trial Endpoint Atlas.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires python, curl/powershell, and git.
---

# Clinical trial surveillance sentinel (`scheduled-trial-surveillance`)

Continuously tracks global interventional Cystic Fibrosis clinical trials, detecting new study starts, status transitions (recruiting, completed, suspended, terminated), and published results to keep the lab's Trial Endpoint Atlas perpetually up to date.

## Cadence & Trigger

- **Turbo Mode Cadence**: Every 2 hours on odd hours: 01:00, 03:00, 05:00, 07:00, 09:00, 11:00, 13:00, 15:00, 17:00, 19:00, 21:00, 23:00 PT (`CRON_TZ=America/Los_Angeles 0 1,3,5,7,9,11,13,15,17,19,21,23 * * *`) integrated within `daily-research-sentinel`.
- **Antigravity Sidecar ID**: `daily-research-sentinel`
- **Review Tier**: `elevated`
- **Anti-Churn Invariant**: When no status transitions, completions, or new trials are detected, log clean status to `.loop-logs/` only. Never open a pull request without newly detected trial deltas or endpoint records.

---

## Surveillance & Atlas Integration Pipeline

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Every 2h on Odd Hours / Turbo)"] --> FastGate["0. Fast Pre-Flight Gate\n(tasks/fast-sentinel-gate.ps1)"]
    FastGate -->|Lock Busy (Code 10)| ExitBackoff["Exit 10 Cleanly (0 Tokens Burned)"]
    FastGate -->|Zero Deltas (Code 20)| ExitIdle["Exit 20 Cleanly (0 Tokens Burned)"]
    FastGate -->|Lock Acquired (Code 0)| Sync["1. Sync & Pull from main\n(sync-main.py)"]
    Sync --> Q["2. Query ClinicalTrials.gov API v2\n(Condition: Cystic Fibrosis)"]
    Q --> Delta{"3. Compute Delta against\ncf-research/tools/trial_atlas/snapshot.json"}
    Delta -->|No Changes| Clean["Emit Clean Record to .loop-logs/"]
    Delta -->|Updates Found| Parse["4. Extract Endpoints, Interventions & Status"]
    Parse --> Draft["5. Prepare Atlas Dataset PR in Worktree"]
    Draft --> Release["6. Release Lock via fast-sentinel-gate -Release"]
    Clean --> Release
```

### 0. Deterministic Fast Pre-Flight Gate & Sync with Main
Execute `tasks/fast-sentinel-gate.ps1` before any LLM reasoning or file reading begins:
```powershell
pwsh -NoProfile -File tasks/fast-sentinel-gate.ps1 -SentinelName "daily-research-sentinel" -WatermarkFile ".loop-logs/last-research-audit.json" -WatchPaths @("../cf-research/proposals", "../cf-research/landscape", "../cf-research/sources/catalog.yaml")
```
If the gate exits with code 10 (`LOCK_HELD`) or code 20 (`IDLE`), terminate immediately without calling further tools.

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

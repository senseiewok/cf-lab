---
name: scheduled-chief-researcher
description: Frugal Chief Researcher Officer grounding sentinel. Audits the task board and research pipeline to keep all agents anchored in primary CF evidence and curative milestones. Implements lazy delta execution to burn zero tokens on idle.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires git, powershell, and python.
---

# Frugal Chief Researcher Officer grounding sentinel (`scheduled-chief-researcher`)

Maintains strict scientific grounding and mission alignment across all autonomous agents in Sensei Ewok's CF Lab. Enforces that every proposed task, research draft, and site showcase directly advances the lab's core curative mission while enforcing a strict **Zero-Token-Burn Guardrail** on idle state.

## Cadence & Trigger

- **Turbo Mode Cadence**: Every 10 minutes at :03, :13, :23, :33, :43, :53 PT (`CRON_TZ=America/Los_Angeles 3-59/10 * * * *`) integrated within `daily-research-sentinel` (staggered 3 minutes after `daily-site-security-sentinel`).
- **Antigravity Sidecar ID**: `daily-research-sentinel`
- **Review Tier**: `elevated`
- **Anti-Churn Invariant**: If no new tasks were proposed or modified, no status transitioned, and no retractions occurred, log audit status to `.loop-logs/` only. **It is strictly forbidden to open a pull request or edit `tasks/board.json` notes just to record that an audit occurred.** This breaks the circular self-triggering git loop.

---

## Zero-Token-Burn Guardrail & Curative Showcase Bridge

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Every 10 Minutes / Turbo)"] --> FastGate["0. Fast Pre-Flight Gate\n(tasks/fast-sentinel-gate.ps1)"]
    FastGate -->|Lock Busy (Code 10)| ExitBackoff["Exit 10 Cleanly (0 Tokens Burned)"]
    FastGate -->|Zero Deltas (Code 20)| ExitIdle["Exit 20 Cleanly (0 Tokens Burned)"]
    FastGate -->|Lock Acquired (Code 0)| Sync["1. Sync & Pull from main\n(sync-main.py)"]
    Sync --> Triage["2. Auto-Triage & Approve Board Tasks\n(tasks/triage_board.py)"]
    Triage --> Audit["3. Audit Task Grounding & Curative Alignment"]
    Audit --> Bridge["4. Emit Curative Brief with showcase_targets Manifest\nin cf-research/landscape/"]
    Bridge --> Release["5. Release Lock via fast-sentinel-gate -Release"]
```

### 0. Deterministic Fast Pre-Flight Gate & Sync with Main
Execute `tasks/fast-sentinel-gate.ps1` before any LLM reasoning or file reading begins:
```powershell
pwsh -NoProfile -File tasks/fast-sentinel-gate.ps1 -SentinelName "daily-research-sentinel" -WatermarkFile ".loop-logs/last-research-audit.json" -WatchPaths @("../cf-research/proposals", "../cf-research/landscape", "../cf-research/sources/catalog.yaml")
```
If the gate exits with code 10 (`LOCK_HELD`) or code 20 (`IDLE`), terminate immediately without calling further tools. Notice that `tasks/board.json` is excluded from watch paths to prevent circular self-invalidation.

- **Sync with origin/main**: Always pull the latest `main` branch across workspace repositories before evaluating deltas:
  ```powershell
  python .claude/skills/workspace-siblings/scripts/sync-main.py
  ```

### 1. Deterministic Board Auto-Triage & Approval (`tasks/triage_board.py`)
Per maintainer directive, the Chief Researcher Officer sentinel automatically triages and approves tasks on `tasks/board.json`:
```powershell
python tasks/triage_board.py
```
- **Auto-Approval (`proposed` -> `ready`)**: Tasks with primary source evidence (DOI, NCT, PDB, catalog), verifiable acceptance criteria, effort estimates, and valid ROI are automatically promoted to `ready`.
- **Auto-Completion (`proposed` / `in_progress` -> `done`)**: Sentinel deliverables and merged features are marked `done` with measured outcomes and actual hours recorded.
- **Human Gate Guardrail**: Tasks listed in `tasks/HUMAN-TASKS.md` or requiring human-only actions (signing legal letters, purchasing commercial subscriptions, in-person clinical review) are held in `proposed`.

### 2. Grounding & Coordination Audit of Board Tasks (Local Worker Delegation)
- When orchestrating on Gemini Flash, **delegate citation and scope extraction to the preferred local worker (`qwen3.8:27b-64k`)** using `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1`:
  - Scans all `status: proposed`, `ready`, and `in_progress` tasks in `tasks/board.json`:
    - Asserts that `source_evidence` cites primary peer-reviewed literature (DOI), clinical registries (NCT), Cryo-EM coordinates (PDB), or official regulatory documentation.
    - Rejects vague speculative claims ("explore AI", "improve tooling") that lack measurable `acceptance` criteria or direct tie to CFTR biology.
    - Flags "agent scope creep" or recursive meta-tooling tasks that do not advance patient-facing translation or biophysical science.
    - Verifies that every `status: "in_progress"` task records its active git `"branch"` (cross-checked against `git worktree list` across `cf-lab`, `cf-research`, `cf-skills`, and `.ai`) so concurrent agents never collide, and flags tasks whose PRs have already merged or been superseded.

### 3. Curative Mission Alignment Evaluation & Top-Task Escalation (Argon)
- For evaluating deep curative alignment and synthesizing the strategic Mission Grounding Brief (top task), **delegate to Argon (Gemini 4 Argon / `pro` model via `invoke_subagent` with `Model: 'pro'`)**:
  - Cross-references ongoing and queued efforts against the lab's two foundational tracks:
    - **Track A (Biophysical Science & Cure Discovery)**:
      - Overcoming the VX-522 delivery barrier (aerosolized & mucus-penetrating LNP formulation).
      - PTC readthrough & NMD suppression (W1282X, G542X).
      - Variant theratyping and Cryo-EM structural misfolding analysis.
      - Alternative epithelial conductance (TMEM16A potentiators, ENaC inhibitors).
      - Phage-antibiotic co-evolution for resistant *P. aeruginosa*.
    - **Track B (Public Engagement & Care-Team Translation)**:
      - The Trial Endpoint Atlas and surrogate biomarker calculators.
      - Interactive 3D CFTR mutation viewer on `/cf/cftr/`.
      - High-fidelity Spanish localization (`/es/`) with medical safety boundaries.

### 4. Deliverable
- Synthesizes a concise, single-page **Curative Grounding & Alignment Brief** saved to:
  ```text
  ../cf-research/landscape/mission-grounding-YYYY-MM-DD.md
  ```
- Renders board updates via `tasks/render-board.ps1`.

---

## Governance & Safety

- **Maintainer Sovereignty & Automated Triage**: The CRO sentinel is authorized by the maintainer to auto-triage and approve grounded tasks to `ready` via `tasks/triage_board.py`. Human maintainers retain sovereignty over final PR merges and human-gated legal/licensing decisions.
- **Frugality First**: Never generate generic motivational statements or ungrounded research proposals. If the mission is on track and inputs are quiet, do not spend tokens.
- **Anti-Hallucination & Primary Evidence Guardrails**:
  - **Primary Literature Anchoring**: Every proposed research direction, trial reference, and biophysical target must cite primary DOIs, NCT registry IDs, PDB Cryo-EM coordinates, or official regulatory documents. Speculative claims lacking primary literature backing are rejected immediately.
  - **"Not Stated" Invariant**: If a study, registry entry, or primary paper does not report an endpoint, metric, or outcome, record "not stated"; never extrapolate or interpolate from memory.
  - **Widening Words Scope Record**: Any claim using comparative or absolute terms ("only", "first", "novel", "all", "cures", "no longer") must supply a scope record detailing the exact search query, database, and timestamp.
  - **Answer Tiers**: Every factual synthesis must declare its Answer Tier (T0 to T3, per `cf-research-context`). Public notes and site proposals require Tier T2 minimum (deterministic script check + independent model verification).
  - **Dignity & Hope Invariant**: Never invent clinical hope, cure dates, or efficacy timelines. Adhere strictly to the "research, not medical advice" boundary.


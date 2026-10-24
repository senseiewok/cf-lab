---
name: scheduled-chief-researcher
description: Frugal Chief Researcher Officer grounding sentinel. Audits the task board and research pipeline to keep all agents anchored in primary CF evidence and curative milestones. Implements lazy delta execution to burn zero tokens on idle.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires git, powershell, and python.
---

# Frugal Chief Researcher Officer grounding sentinel (`scheduled-chief-researcher`)

Maintains strict scientific grounding and mission alignment across all autonomous agents in Sensei Ewok's CF Lab. Enforces that every proposed task, research draft, and site showcase directly advances the lab's core curative mission while enforcing a strict **Zero-Token-Burn Guardrail** on idle state.

## Cadence & Trigger

- **Cadence**: Every 30 minutes at :10 and :40 PT (`CRON_TZ=America/Los_Angeles 10,40 * * * *`), set in `tasks/sentinels.json` and rendered into the sidecar by `tasks/render-sentinel-sidecars.ps1`, staggered 10 minutes after `daily-site-security-sentinel`. The agent starts only when proposals, landscape or the source catalog changed, or the 3-hour heartbeat is due (registry polls are not git state). Integrated within `daily-research-sentinel`.
- **Build slot (bigger, bolder work & PR repair)**: besides audits, this sentinel repairs broken open PRs in its lane and builds ready bundles. When no watched tree changed, the wrapper calls `python tasks/pick_bold_task.py --lane research --check`. Before blocking on an open `work/sentinel-research-*` pull request, the picker inspects `mergeable`, `mergeStateStatus`, `reviewDecision`, `statusCheckRollup` (`CheckRun` conclusions and `StatusContext` states), and whether all referenced `T-XXXX` tasks are already `done` on `main`. If an open sentinel PR has a `merge_conflict`, `ci_failure`, `review_blocker`, or is `superseded_by_main` (and has had fewer than 2 repair attempts in 48 hours), the picker wakes the sentinel in `"mode": "pr_repair"` and writes `.loop-logs/bold-bundle-research.json` with `pr_repairs` so the sentinel merges `origin/main` (never force-pushing), fixes the failing check or review comment, or closes a superseded duplicate PR. Otherwise, if a clean sentinel PR is still waiting for review, the picker exits 21 (`IDLE`). When the lane is clear, the picker ranks `ready` board tasks by impact x priority x scope (not impact per hour, which favors the smallest task), bundles up to 3 related tasks of one repo (about 8 estimated hours), skips anything a person must do (human-gated, referencing a human task, needing a person's review, or a "Decide ..." task), anything with an unfinished dependency and any task that failed twice in 48 hours, and never hands out a single task estimated above 12 hours (it lists those so the board can split them). The wrapper claims the bundle, records the attempt and writes `.loop-logs/bold-bundle-research.json`; the run's prompt (`tasks/sentinel-prompts`) carries the build round: worktree, review gate, one pull request per repo, a draft when unfinished, never a merge. A build slot does not advance the watermark, so the heartbeat audits still happen. These build-round pull requests are separate from the Anti-Churn rule above, which governs audit and translation pull requests.
- **Antigravity Sidecar ID**: `daily-research-sentinel`
- **Review Tier**: `elevated`
- **Anti-Churn Invariant**: If no new tasks were proposed or modified, no status transitioned, and no retractions occurred, log audit status to `.loop-logs/` only. **It is strictly forbidden to open a pull request or edit `tasks/board.json` notes just to record that an audit occurred.** This breaks the circular self-triggering git loop.

---

## Zero-Token-Burn Guardrail & Curative Showcase Bridge

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Every 30 Minutes)"] --> FastGate["0. Wrapper: Sync + Fast Gate\n(tasks/run-sentinel.ps1)"]
    FastGate -->|Lock Busy (Code 10)| ExitBackoff["Exit 10 Cleanly (0 Tokens Burned)"]
    FastGate -->|Zero Deltas (Code 20)| ExitIdle["Exit 20 Cleanly (0 Tokens Burned)"]
    FastGate -->|Lock Acquired (Code 0)| Sync["1. Sync & Pull from main\n(sync-main.py)"]
    Sync --> Triage["2. Auto-Triage & Approve Board Tasks\n(tasks/triage_board.py)"]
    Triage --> Audit["3. Audit Task Grounding & Curative Alignment"]
    Audit --> Bridge["4. Emit Curative Brief with showcase_targets Manifest\nin cf-research/landscape/"]
    Bridge --> Release["5. Release Lock via run-sentinel -Complete"]
```

### 0. Deterministic Fast Pre-Flight Gate & Sync with Main (run by the scheduler wrapper, not by the agent)
The cron job runs `tasks/run-sentinel.ps1 -SentinelName daily-research-sentinel`. That wrapper syncs `origin/main`, runs `tasks/fast-sentinel-gate.ps1` with the watch paths and heartbeat from `tasks/sentinels.json`, and starts an agent conversation only on exit 0. Exit 10 (`LOCK_HELD`) or 20 (`IDLE`) starts nothing, so an idle slot burns zero tokens. The agent must not run the gate again: it would see its own lock and exit 10. When the run ends, `pwsh -NoProfile -File tasks/run-sentinel.ps1 -SentinelName daily-research-sentinel -Complete` writes the watermark and releases the lock; `-Abort` releases it without a watermark so the next slot retries. Every decision is logged to `.loop-logs/sentinel-runs.jsonl`. The agent's steps live in `tasks/sentinel-prompts/daily-research-sentinel.md`. Notice that `tasks/board.json` is excluded from the watch paths to prevent circular self-invalidation.

- **Sync with origin/main**: Always pull the latest `main` branch across workspace repositories before evaluating deltas:
  ```powershell
  python .claude/skills/workspace-siblings/scripts/sync-main.py
  ```

### 1. Deterministic Board Auto-Triage & Approval (`tasks/triage_board.py`)
Per maintainer directive, the Chief Researcher Officer sentinel automatically triages and approves tasks on `tasks/board.json`:
```powershell
python tasks/triage_board.py --apply
```
- **Auto-Approval (`proposed` -> `ready`)**: Tasks with primary source evidence (DOI, NCT, PDB, catalog), verifiable acceptance criteria, effort estimates, valid ROI, and verified spec dossiers (`spec_path`) are automatically promoted to `ready`.
- **Auto-Completion (`proposed` / `in_progress` -> `done`)**: Sentinel deliverables and merged features are marked `done` with measured outcomes and actual hours recorded.
- **Human Gate Guardrail**: Tasks listed in `tasks/HUMAN-TASKS.md` or requiring human-only actions (signing legal letters, purchasing commercial subscriptions, in-person clinical review) are held in `proposed`.

### 2. Build Slot Grounding & Spec Dossier Invariants
- When executing the build slot for claimed `research` lane tasks from `.loop-logs/bold-bundle-research.json`:
  - **Read `spec_markdown` directly**: Do not rely on brief title summaries alone; read the embedded `spec_markdown` containing exact biophysical equations, primary literature citations, and deterministic test commands.
  - **Check `existing_worktrees` & `gh pr list`**: Inspect `existing_worktrees` in `bold-bundle-research.json` and check `gh pr list --state open` before creating branches. If an unmerged worktree exists matching the task, harvest and resume its commits.
  - **Audit `spec_path`**: Verify every complex Track A biophysical task has an accompanying specification dossier in `tasks/specs/<TASK-ID>.md` (`python tasks/check_task_specs.py --check`).

### 3. Grounding & Coordination Audit of Board Tasks (Local Worker Delegation)
- When orchestrating on Gemini Flash, **delegate citation and scope extraction to the preferred local worker (`qwen3.8:27b-64k`)** using `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1`:
  - Scans all `status: proposed`, `ready`, and `in_progress` tasks in `tasks/board.json`:
    - Asserts that `source_evidence` cites primary peer-reviewed literature (DOI), clinical registries (NCT), Cryo-EM coordinates (PDB), or official regulatory documentation.
    - Rejects vague speculative claims ("explore AI", "improve tooling") that lack measurable `acceptance` criteria or direct tie to CFTR biology.
    - Flags "agent scope creep" or recursive meta-tooling tasks that do not advance patient-facing translation or biophysical science.
    - Verifies that every `status: "in_progress"` task records its active git `"branch"` (cross-checked against `git worktree list` across `cf-lab`, `cf-research`, `cf-skills`, and `.ai`) so concurrent agents never collide, and flags tasks whose PRs have already merged or been superseded.

### 3. Curative Mission Alignment Evaluation & Cross-Scale Discovery Synthesis (Argon)
- For evaluating deep curative alignment and synthesizing the strategic Mission Grounding Brief (top task), **delegate to Argon (Gemini 4 Argon / `pro` model via `invoke_subagent` with `Model: 'pro'`)**:
  - **Cross-Scale Synthesis Mandate (Beyond Isolated 1-Paper Toy Scripts)**: Rather than proposing isolated single-paper ODE calculators, proactive discovery rounds and new Track A/B task proposals must cross-join at least 2 locked workspace datasets across biological scales (`python tools/discovery/discovery_council.py --cross-scale-report` in `cf-research`):
    1. **Engine A — Genotype $\times$ Recruiting Trial $\times$ Registry Gap Matrix**: Cross-joining the 209 CFTR2 variants (`4 Cryo-EM structures`) against the 79 active/recruiting interventional studies (`57 recruiting + 22 active`) and 5-registry epidemiology (`54,043 ECFSPR`) to identify underserved Class I/VII genotypes, age-eligibility gaps, and washout protocol barriers.
    2. **Engine B — Modality $\times$ Endpoint Co-Occurrence & Compartmentalization Synthesis**: Cross-joining the 102 non-zero primary outcome pairs (`/atlas/co-occurrence/`) with therapeutic delivery route (systemic small-molecule modulators vs. airway-restricted inhaled mRNA LNPs `NCT05668741` and AAV `NCT05248230`) to quantify why pulmonary spirometry ($\text{FEV}_1$), small-airway ventilation ($\text{LCI}_{2.5}$), and safety decouple from systemic sweat chloride.
    3. **Engine C — Chained 5-Discipline Curative Bottleneck Pipeline**: Chaining parameters across all 5 scientific disciplines (`Structural Biology` $\to$ `RNA & Gene Editing` $\to$ `Mucus & Airway Biophysics` $\to$ `LNP & mRNA Delivery` $\to$ `Viral, Stem Cell & Gene Therapy` + `Microbiology & Host Defense`) to identify the rate-limiting step from molecular rescue to durable clinical endpoint power.
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
  - **Multi-Source Cross-Verification & Waterfall Quota (`AH-8` & Rule 12)**: Cross-verify small-molecule potencies with ChEMBL (`chembl-activity`, citing `[Assay ChEMBL ID]`, `[Cell System / Technique]`, and `[Variant Genotype]`), target tractability/safety with Open Targets (`opentargets`, never conflating FAERS `logLR` with causal toxicity), and UK grants with UKRI (`ukri`). Reserve Scite Pro MCP (`scite-mcp`, `SCITE_MCP_DAILY_CAP=60`) for Tier `T2`/`T3` contrasting-citation polarity checks, UK MHRA safety alerts (`search_mhra`), and patent/device landscape verification (`search_patents`, `search_device510k`). Always spawn frontier review subagents via native `invoke_subagent` (Rule 12), never via shell CLI subprocesses.
  - **Answer Tiers**: Every factual synthesis must declare its Answer Tier (T0 to T3, per `cf-research-context`). Public notes and site proposals require Tier T2 minimum (deterministic script check + independent model verification).
  - **Dignity & Hope Invariant**: Never invent clinical hope, cure dates, or efficacy timelines. Adhere strictly to the "research, not medical advice" boundary.


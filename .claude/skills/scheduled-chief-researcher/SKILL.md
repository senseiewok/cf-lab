---
name: scheduled-chief-researcher
description: Frugal Chief Researcher Officer grounding sentinel. Audits the task board and research pipeline to keep all agents anchored in primary CF evidence and curative milestones. Implements lazy delta execution to burn zero tokens on idle.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires git, powershell, and python.
---

# Frugal Chief Researcher Officer grounding sentinel (`scheduled-chief-researcher`)

Maintains strict scientific grounding and mission alignment across all autonomous agents in Sensei Ewok's CF Lab. Enforces that every proposed task, research draft, and site showcase directly advances the lab's core curative mission while enforcing a strict **Zero-Token-Burn Guardrail** on idle state.

## Cadence & Trigger

- **Default Cadence**: Bi-weekly on the 1st and 15th at 02:00 AM PT (`CRON_TZ=America/Los_Angeles 0 2 1,15 * *`) — scheduled 1 hour before the deep biophysical discovery engines execute.
- **Antigravity Sidecar ID**: `scheduled-chief-researcher`
- **Review Tier**: `elevated`

---

## Zero-Token-Burn Guardrail (Lazy Delta Execution)

```mermaid
flowchart TD
    Trigger["Bi-Weekly Trigger (02:00 PT)"] --> Lock{"Acquire .loop-logs/sentinel.lock"}
    Lock -->|Busy| Exit["Exit 0 Cleanly"]
    Lock -->|Acquired| Sync["Sync & Pull from main\n(sync-main.py)"]
    Sync --> Delta{"Has board.json or proposals/ changed since last audit?"}
    Delta -->|No Changes (Idle)| Exit
    Delta -->|Changes Detected| Layer1["Run Layer 1 Deterministic Checkers\n(check_claims.py, check_numbers.py)"]
    Layer1 --> Audit["Audit Task Grounding & Curative Alignment"]
    Audit --> Brief["Emit 1-Page Mission Grounding Brief\nin cf-research/landscape/"]
    Brief --> BoardUpdate["Update Task Notes / Flag Unanchored Drift"]
```

1. **Advisory Mutex Lock & Sync with Main on Start**:
   - Acquires advisory lock `.loop-logs/sentinel.lock` (if held and under 30 minutes old, backs off cleanly to prevent git index conflicts).
   - **Sync with origin/main**: Always pull the latest `main` branch across workspace repositories before evaluating deltas:
     ```powershell
     python .claude/skills/workspace-siblings/scripts/sync-main.py
     ```
     Or manually: `git -C c:/senseiewok/repos/cf-lab pull --ff-only origin main && git -C c:/senseiewok/repos/cf-research pull --ff-only origin main`.
   - Compares the current git commit tree hash of `tasks/board.json`, `../cf-research/proposals/`, and `../cf-research/landscape/` against the audit state recorded in `.loop-logs/last-cro-audit.json`.
   - **If no new tasks were proposed or modified, it terminates immediately in under 1 second without making any model calls.**
   - Releases `.loop-logs/sentinel.lock` upon completion or early exit.

2. **Grounding & Coordination Audit of Board Tasks (Local Worker Delegation)**:
   - When orchestrating on Gemini Flash, **delegate the citation and scope extraction to the preferred local worker (`qwen3.8:27b-64k`)** using `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1`:
     - Scans all `status: proposed`, `ready`, and `in_progress` tasks in `tasks/board.json`:
       - Asserts that `source_evidence` cites primary peer-reviewed literature (DOI), clinical registries (NCT), Cryo-EM coordinates (PDB), or official regulatory documentation.
       - Rejects vague speculative claims ("explore AI", "improve tooling") that lack measurable `acceptance` criteria or direct tie to CFTR biology.
       - Flags "agent scope creep" or recursive meta-tooling tasks that do not advance patient-facing translation or biophysical science.
       - Verifies that every `status: "in_progress"` task records its active git `"branch"` (cross-checked against `git worktree list` across `cf-lab`, `cf-research`, `cf-skills`, and `.ai`) so concurrent agents never collide, and flags tasks whose PRs have already merged or been superseded.

3. **Curative Mission Alignment Evaluation & Top-Task Escalation (Argon)**:
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

4. **Deliverable**:
   - Synthesizes a concise, single-page **Curative Grounding & Alignment Brief** saved to:
     ```text
     ../cf-research/landscape/mission-grounding-YYYY-MM-DD.md
     ```
   - Appends audit notes to evaluated tasks in `tasks/board.json` and renders via `tasks/render-board.ps1`.

---

## Governance & Safety

- **Maintainer Sovereignty**: The CRO sentinel audits and advises; only the human maintainer sets tasks to `ready` or authorizes work tree merges.
- **Frugality First**: Never generate generic motivational statements or ungrounded research proposals. If the mission is on track and inputs are quiet, do not spend tokens.

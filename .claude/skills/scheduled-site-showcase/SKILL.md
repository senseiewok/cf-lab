---
name: scheduled-site-showcase
description: Autonomous site builder, research round, skill evolution, and PR engine. Runs a round of CF research, audits and evolves relevant skills, translates lab breakthroughs into public interactive features and Spanish pages on senseiewok.ai, runs Playwright visual audits, and prepares verified pull requests.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires git, python, and Playwright for visual verification.
---

# Autonomous site builder & research showcase sentinel (`scheduled-site-showcase`)

Continuously builds and improves the public lab website ([senseiewok.ai](https://senseiewok.ai/)), conducting a fresh round of research and improving relevant skills on every run, exposing recent lab breakthroughs to the community in English and Spanish, and preparing verified pull requests with Playwright screenshots.

## Cadence & Trigger

- **Dedicated Front-Door Cadence**: Every 30 minutes at :20 and :50 PT (`CRON_TZ=America/Los_Angeles 20,50 * * * *`), set in `tasks/sentinels.json` and rendered into the sidecar by `tasks/render-sentinel-sidecars.ps1`, staggered 10 minutes after `daily-research-sentinel` and 20 minutes after `daily-security-sentinel` (alias: `daily-site-security-sentinel`). The agent starts when a watched path changes or the 4-hour heartbeat is due.
- **Build slot (bigger, bolder work & PR repair)**: besides audits, this sentinel repairs broken open PRs in its lane (`work/sentinel-showcase-*` and `site/showcase-*`) and builds ready bundles. When no watched tree changed, the wrapper calls `python tasks/pick_bold_task.py --lane showcase --check`. Before blocking on an open showcase pull request, the picker inspects `mergeable`, `mergeStateStatus`, `reviewDecision`, `statusCheckRollup` (`CheckRun` conclusions and `StatusContext` states), and whether all referenced `T-XXXX` tasks are already `done` on `main`. If an open showcase PR has a `merge_conflict`, `ci_failure`, `review_blocker`, or is `superseded_by_main` (and has had fewer than 2 repair attempts in 48 hours), the picker wakes the sentinel in `"mode": "pr_repair"` and writes `.loop-logs/bold-bundle-showcase.json` with `pr_repairs` so the sentinel merges `origin/main` (never force-pushing), fixes the failing check or review comment, or closes a superseded duplicate PR. Otherwise, if a clean showcase PR is still waiting for review, the picker exits 21 (`IDLE`). When the lane is clear, the picker ranks `ready` board tasks by impact x priority x scope (not impact per hour, which favors the smallest task), bundles up to 3 related tasks of one repo (about 8 estimated hours), skips anything a person must do (human-gated, referencing a human task, needing a person's review, or a "Decide ..." task), anything with an unfinished dependency and any task that failed twice in 48 hours, and never hands out a single task estimated above 12 hours (it lists those so the board can split them). The wrapper claims the bundle, records the attempt and writes `.loop-logs/bold-bundle-showcase.json`; the run's prompt (`tasks/sentinel-prompts`) carries the build round: worktree, review gate, one pull request per repo, a draft when unfinished, never a merge. A build slot does not advance the watermark, so the heartbeat audits still happen. These build-round pull requests are separate from the Anti-Churn rule above, which governs audit and translation pull requests.
- **Antigravity Sidecar ID**: `daily-site-showcase-sentinel`
- **Review Tier**: `elevated` / `full` (depending on public claims and security boundaries).
- **Anti-Churn Invariant**: If no new validated research dossiers or `showcase_targets` exist, terminate cleanly with 0 tokens burned. Never open a pull request without newly verified biophysical research deliverables or localized content.

---

## 4-Stage Autonomous Workflow

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Every 30 Minutes)"] --> FastGate["0. Wrapper: Sync + Fast Gate\n(tasks/run-sentinel.ps1)"]
    FastGate -->|Lock Busy (Code 10)| ExitBackoff["Exit 10 Cleanly (0 Tokens Burned)"]
    FastGate -->|No New Research (Code 20)| IdleExit["Exit 20 Cleanly (0 Tokens Burned)"]
    FastGate -->|Deltas Detected (Code 0)| Worktree["1. Spawn Dedicated Worktree & Branch\n(Never Edit main)"]
    Worktree --> Stage1["2. Research Round & Skill Evolution"]
    Stage1 --> Stage2["3. Public Translation & Site Showcase\n(In Worktree)"]
    Stage2 --> Stage3["4. Grounded Review Loop & Build Verification\n(Unit Tests + Playwright Audits)"]
    Stage3 --> Stage4["5. Elevated Gate & Dual-Family PR Submission"]
    Stage4 --> Release["6. Release Lock via run-sentinel -Complete"]
```

### Pre-flight: Deterministic Fast Gate, Main Sync & Worktree Coordination

Before touching any `.ai` or skill files:
1. **Deterministic Fast Pre-Flight Gate (run by the scheduler wrapper, not by the agent)**: The cron job runs `tasks/run-sentinel.ps1 -SentinelName daily-site-showcase-sentinel`. That wrapper syncs `origin/main`, runs `tasks/fast-sentinel-gate.ps1` with the watch paths and heartbeat from `tasks/sentinels.json`, and starts an agent conversation only on exit 0. Exit 10 (`LOCK_HELD`) or 20 (`IDLE`) starts nothing, so an idle slot burns zero tokens. The agent must not run the gate again: it would see its own lock and exit 10. When the run ends, `pwsh -NoProfile -File tasks/run-sentinel.ps1 -SentinelName daily-site-showcase-sentinel -Complete` writes the watermark and releases the lock; `-Abort` releases it without a watermark so the next slot retries. Every decision is logged to `.loop-logs/sentinel-runs.jsonl`. The agent's steps live in `tasks/sentinel-prompts/daily-site-showcase-sentinel.md`.
2. **Sync with origin/main on Start**: Always sync with origin and pull the latest `main` branch across all workspace repositories before inspecting state watermarks, research dossiers, or tasks:
   ```powershell
   python .claude/skills/workspace-siblings/scripts/sync-main.py
   ```
   Or manually:
   ```powershell
   git -C c:/senseiewok/repos/cf-lab pull --ff-only origin main
   git -C c:/senseiewok/repos/cf-research pull --ff-only origin main
   git -C c:/senseiewok/repos/.ai pull --ff-only origin main
   ```
3. **Persistent Research Watermark Check**: Inspect `.loop-logs/last-showcase-audit.json`. Compare the current git commit tree hash of `../cf-research/landscape/` and `../cf-research/proposals/` against `last_showcased_tree_hash`. If no new validated research dossiers or commits have been merged since the last showcase cycle, **exit 0 cleanly** without spawning worktrees or running visual audits.
4. **Read Build Bundle & Spec Dossiers**: Read `.loop-logs/bold-bundle-showcase.json` (if present). If tasks have `spec_markdown`, consume the full biophysical equations, primary-source citations, DOM element IDs, and test commands directly from the dossier rather than guessing requirements.
5. **Check Existing Worktrees & Duplicate PRs**: Inspect the `existing_worktrees` array in `bold-bundle-showcase.json` and check `gh pr list --state open` before creating branches or PRs. If an unmerged worktree exists matching the claimed task or branch, resume and harvest its commits instead of starting from scratch or opening duplicate PRs.
6. **Page Word Budget Cap**: When modifying `/cf/index.html`, enforce a strict **1,800-word budget cap** (`python .claude/skills/lab-voice/scripts/check-voice.py src/cf/index.html`). If adding new showcase panels or variant cards, condense existing copy or migrate detail to dedicated sub-pages (`/cf/ptc/`, `/cf/trials/`, `/cf/registries/`) to maintain warm, concise dignity.
7. **Collision Detection**: If another agent or worktree is already working on the target site task or branch (e.g. `site/showcase-*` under `../.worktrees/.ai/`), **stop immediately and exit cleanly** so two agents never race on `.ai/src/`.
8. **Spawn Isolated Worktree**: Never edit `.ai` in the main checkout. Create the isolated worktree *first* before making any file changes:
   ```powershell
   python .claude/skills/workspace-siblings/scripts/worktrees.py new .ai showcase-<topic> --branch site/showcase-<topic> --push
   ```
   Set `"status": "in_progress"` and `"branch": "site/showcase-<topic>"` on the claimed task in `tasks/board.json` and run `pwsh -NoProfile -File tasks/render-board.ps1`.
9. **Never run check-all or test suites at the beginning**: Strictly avoid running `check-all.ps1` or test suites (`tests.test_site`, `check-voice.py`, Playwright visual audits, or claims checkers) during Pre-flight or before changes are applied in the worktree. Running full `check-all.ps1` spends excessive execution time (several minutes across 30+ control-repo suites), risks spawning orphaned background server processes on test ports, and risks modifying or locking git index and worktree states. All deterministic testing belongs strictly in Stage 3 on the completed, staged changes inside the dedicated worktree.

### Stage 1: Research Round & Skill Evolution

1. **Scan Completed Lab Research**:
   - Inspect `cf-research/landscape/` and `cf-research/proposals/` for recent T1/T2 dossiers (e.g. PTC readthrough, delivery biophysics, variant theratyping, alternative conductance).
   - Identify newly validated primary evidence, Cryo-EM coordinate updates, or trial surveillance records.
2. **Skill Audit & Improvement**:
   - Audit relevant skills (`frontend-design`, `lab-voice`, `cf-research-context`, `webgl-threejs-graphics`).
   - Integrate concrete, tested improvements (e.g., refined mobile viewport handling, new diagnostic checks, CSS container query patterns).
   - Validate that updated skills strictly conform to frontmatter and character limits:
     ```powershell
     python tasks/check-skill-frontmatter.py
     ```

### Stage 2: Exposing the Lab's Work (Public Translation & Local Delegation)

1. **Evidence & Asset Generation**:
   - Re-generate public evidence ledgers:
     ```powershell
     python tools/make_evidence.py
     ```
   - Synchronize 3D CFTR atomic coordinates and mutation hotspots:
     ```powershell
     python tools/sync_cftr_model.py
     ```
2. **Website Enhancements (`.ai/src/`)**:
   - Update HTML, CSS, and interactive visualizers on target pages (`/cf/`, `/cf/cftr/`, `/tools/`, `/evidence/`).
   - Maintain the two-tier header navigation and right-hand secondary sub-nav rail (`aside.subnav-rail`) on content pages.
   - Preserve the 65-Roses visual motif counter and semantic structure.
3. **Mexican Spanish Localization (`/es/...`, `es-MX`) (Local Worker Delegation)**:
   - When orchestrating on Gemini Flash, **delegate the drafting of parallel Mexican Spanish translations and metadata to the preferred local worker (`qwen3.8:27b-64k`)** using `.claude/skills/ai-loop-council/scripts/delegate.ps1`:
     - Author or update parallel Mexican Spanish pages under `.ai/src/es/` (e.g., `/es/`, `/es/cf/`, `/es/cf/cftr/`) with `<html lang="es-MX">` and reciprocal `hreflang="es-MX"` / `hreflang="en"` links.
     - Use natural Mexican Spanish vocabulary (`computadora`, `archivo`, `teléfono celular`, `ustedes`, `consultar con su equipo médico`) and include the verified Spanish medical boundary disclaimer:
       > *"Investigación independiente, no asesoramiento médico. Sensei Ewok CF Lab no promete curas ni tratamientos clínicos."*

### Stage 3: Deterministic Grounded Review Loop & Verification

Execute the mandatory 3-layer Grounded Review Loop:

1. **Deterministic Mechanical Verification & Local Pre-PR Gate (`check_pr_gate.py`)**:
   - Cloud GitHub Actions and CodeQL are disabled on the private `senseiewok/.ai` repository; run the unified local pre-PR gate before any PR:
     ```powershell
     python tools/check_pr_gate.py
     ```
   - Verify all factual claims against primary sources:
     ```powershell
     python ../cf-research/tools/claims/check_claims.py
     python ../cf-research/tools/claims/check_numbers.py
     ```
   - Check voice, tone, and lack of hype across all HTML files:
     ```powershell
     python .claude/skills/lab-voice/scripts/check-voice.py
     ```
   - Run the site unit and CLS test suite:
     ```powershell
     python -m unittest tests.test_site tests.test_resources_page tests.test_cftr_hero tests.test_site_cls
     ```
2. **Playwright Visual Audit**:
   - Launch local test server and capture desktop (`1280x800`) and mobile (`390x844`) screenshots:
     ```powershell
     python .claude/skills/playwright-browser-testing/scripts/pr-screenshots.py capture --url http://localhost:8000
     ```
   - Inspect screenshots in `../cf-lab-files/scratch/screenshots/` to verify zero visual overlap, no mobile overflow, and legible typography.

### Stage 4: Elevated Gate, Dual-Family Frontier Review (Argon + Opus) & PR Submission

1. **Elevated Gate Enforcement**:
   - Inside the dedicated worktree, stage changed files, run first-pass local diff review (`pwsh .claude/skills/ai-loop-council/scripts/review-diff.ps1 -Staged`), and verify through the repo gate:
     ```powershell
     pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/run-gate.ps1 -Tier elevated -Expected "<changed-files>" -MessageFile <path-to-commit-msg>
     ```
2. **Execute `pr-review-loop` with Diversity Frontier Council (Argon + Opus)**:
   - For elevated review before PR submission, escalate top-task challenger reviews to **Argon** (Gemini 4 Argon / `pro` model via `invoke_subagent` with `Model: 'pro'`) paired with Anthropic Claude Opus.
   - The blind challenger reviews the staged diff; the orchestrator adjudicates each finding against deterministic tests.
   - Record the full review loop table (rounds, findings, accepted, rejected) in the PR description.
3. **Submit Pull Request**:
   - Open PR via GitHub CLI:
     ```powershell
     gh pr create --repo senseiewok/.ai --title "feat(site): <description>" --body-file pr-body.md
     ```
   - Attach Playwright screenshots and link back to the originating research dossier.
4. **Update Watermark & Release Lock**:
   - Record the run in `.loop-logs/last-showcase-audit.json`; the fresh tree hashes are written for you by `-Complete`.
   - Release lock and write the watermark:
     ```powershell
     pwsh -NoProfile -File tasks/run-sentinel.ps1 -SentinelName "daily-site-showcase-sentinel" -Complete
     ```

---

## Safety & Governance

- **Zero Invention**: Every number, structure, and claim originates from primary peer-reviewed literature or official trial registries.
- **Maintainer Sovereignty**: The agent prepares clean worktrees and opens PRs; only the human maintainer merges code or deploys to production.
- **Test Timing Discipline**: Never execute test suites at the beginning of a run. Verification checks run exclusively in Stage 3 against the concrete changes made in the isolated worktree.
- **Anti-Hallucination Guardrails**:
  - **Tier T2 Grounding Minimum**: Every scientific statement, mutation mechanism, or therapeutic target presented on `senseiewok.ai` must be backed by a verified primary literature citation and verified Answer Tier T2+.
  - **Semantic Fidelity in Localization**: Spanish translations (`/es/`) must strictly preserve verified scientific terminology and the mandatory medical boundary disclaimer ("Investigación, no asesoramiento médico"). Never introduce optimistic framing or unverified claims during localization.
  - **Deterministic Verification Before PR**: All unit tests (`tests.test_site`, `tests.test_resources_page`, `tests.test_cftr_hero`), `check-voice.py`, and Playwright captures must pass with exit 0 before a PR is opened.


---
name: scheduled-site-audit
description: Public site health and dignity sentinel. Performs daily automated audits of live HTTP security headers, 301 redirects, 65 roses motif count, link integrity, and task board synchronization.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires curl/powershell, python, and git.
---

# Public site health & dignity sentinel (`scheduled-site-audit`)

Maintains unbroken operational quality, security posture, and dignity for the public lab website ([senseiewok.ai](https://senseiewok.ai/)) and control repository task board.

## Cadence & Trigger

- **Cadence**: Every 30 minutes at :00 and :30 PT (`CRON_TZ=America/Los_Angeles 0,30 * * * *`), set in `tasks/sentinels.json`; the agent starts only when a watched tree changed or the 3-hour heartbeat is due. Run by the wrapper `tasks/run-sentinel.ps1` as part of `daily-security-sentinel`.
- **Antigravity Sidecar ID**: `daily-site-security-sentinel`
- **Review Tier**: `routine`
- **Anti-Churn Invariant**: If zero defects or regressions are detected, log health status to `.loop-logs/` only. It is strictly forbidden to open a pull request or edit `tasks/board.json` notes just to record that a clean audit occurred.

---

## 5-Point Health, Visual & Dignity Audit Pipeline

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Every 30 Minutes)"] --> FastGate["0. Wrapper: Sync + Fast Gate\n(tasks/run-sentinel.ps1)"]
    FastGate -->|Lock Busy (Code 10)| ExitBackoff["Exit 10 Cleanly (0 Tokens Burned)"]
    FastGate -->|Clean Idle (Code 20)| ExitIdle["Exit 20 Cleanly (0 Tokens Burned)"]
    FastGate -->|Lock Acquired (Code 0)| Sync["1. Sync & Pull from main\n(sync-main.py)"]
    Sync --> H1["2. Live HTTP Security Headers Audit\n(HSTS, CSP, X-Robots-Tag)"]
    H1 --> H2["3. 65 Roses Motif & Link Audit"]
    H2 --> H3["4. Playwright Screen Capture & Prune\n(capture_site_review.py)"]
    H3 --> H4["5. Task Board & Worktree Audit\n(render-board -Check, worktrees list)"]
    H4 --> H5["6. Dignity & Voice Check"]
    H5 --> Report["Log Health Status to .loop-logs/ & memory/handoff.md"]
    Report --> Release["7. Release Lock via run-sentinel -Complete"]
```

### 0. Deterministic Fast Pre-Flight Gate & Sync with Main
The scheduler wrapper `tasks/run-sentinel.ps1 -SentinelName daily-security-sentinel` syncs `origin/main` and runs `tasks/fast-sentinel-gate.ps1` before any agent starts (watch paths and heartbeat live in `tasks/sentinels.json`). Exit 10 (lock held) or 20 (idle) starts nothing, so an idle slot burns zero tokens. The agent must not rerun the gate (its own lock would block it) and ends with `pwsh -NoProfile -File tasks/run-sentinel.ps1 -SentinelName daily-security-sentinel -Complete` (or `-Abort` on failure).

- **Sync with origin/main**: Always pull the latest `main` branch across workspace repositories before verifying task board, worktrees, or site assets:
  ```powershell
  python .claude/skills/workspace-siblings/scripts/sync-main.py
  ```
  Or manually: `git -C c:/senseiewok/repos/cf-lab pull --ff-only origin main && git -C c:/senseiewok/repos/.ai pull --ff-only origin main`.

### 1. Live HTTP Security Headers Audit
Verify that production web responses from `senseiewok.ai` return mandatory security and crawler headers:
- `Strict-Transport-Security: max-age=...; includeSubDomains; preload`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Robots-Tag: noindex` on unreleased research atlas directories (per T-0139).
- Permanent 301 redirects (e.g. `/letter/` redirecting to `/letter`).

### 2. 65 Roses Visual Motif & Link Integrity
- Verify that exactly 65 rose motifs render on target pages (`/cf/`, `/`, `/es/`) adhering to the 65-rose community convention (T-0016).
- Verify zero broken internal links across the primary English and Mexican Spanish (`/es/`) discovery routes.

### 3. Deterministic Playwright Screen Capture & Retention Pruning
- Run local Playwright visual review across core routes:
  ```powershell
  python ../.ai/tools/capture_site_review.py --max-runs 3 --max-age-hours 48
  ```
- Evaluates responsive desktop (`1280x800`) and mobile (`390x844 @ 2x`) viewports across:
  - Home hero (`/`)
  - CFTR 3D Molecule & Theratype Viewer (`/cf/cftr/`)
  - Curated Resources Catalog (`/resources/`)
  - Community Letter (`/letter/`)
  - Mexican Spanish Edition (`/?lang=es`)
- **Automated Retention Cleanup**:
  - Enforces strict disk bounding by retaining $\le 3$ recent runs and pruning runs older than 48 hours.
  - Updates canonical `shots/current/` baseline and timestamped run manifests (`shots/runs/<timestamp>/review-manifest.json`).
  - Purges orphaned `*.tmp` scratch files.
- **Error Trapping**: Traps unhandled console errors and page runtime failures. Exits non-zero if page errors are trapped.

### 4. Task Board & Worktree Coordination Audit
- Run deterministic board validation:
  ```powershell
  pwsh -NoProfile -File tasks/render-board.ps1 -Check
  ```
- Run read-only worktree audit with GitHub pull request resolution (uses read-only `gh pr list`, zero mutations):
  ```powershell
  python .claude/skills/workspace-siblings/scripts/worktrees.py list --github
  ```
  > [!IMPORTANT]
  > **Maintainer Sovereignty Guardrail**: Worktrees are removed *only* with `--yes` when a person asks. Never execute `worktrees.py clean --yes` automatically inside a scheduled cron. If finished or dangling worktrees are detected, log them to `memory/handoff.md` for human review.

### 5. Tone, Dignity & Spanish Disclaimer Verification (Local Delegation)
- When orchestrating on Gemini Flash, **delegate the verification of Spanish disclaimer text and drafting of audit summaries to the preferred local worker (`qwen3.8:27b-64k`)** using `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1`:
  - Confirm all public pages conform to `lab-voice` boundaries (warm, plain-language, assertive, zero hype).
  - Verify that Mexican Spanish strings in `data/i18n/es-MX.json`, `src/scripts/i18n-resources.js`, and dynamic views carry the exact medical boundary disclaimer:
    > *"Investigación independiente, no asesoramiento médico. Sensei Ewok CF Lab no promete curas ni tratamientos clínicos."*

### 6. Logging & Top-Task Escalation (Argon)
- Emits daily audit log to `.loop-logs/site-audit-YYYY-MM-DD.json`.
- If critical regressions (e.g. broken CSP, missing disclaimer, Playwright page errors, or board render failure) are detected:
  - Escalate triage to **Argon** (Gemini 4 Argon / `pro` model via `invoke_subagent` with `Model: 'pro'`).
  - Log an elevated alert in `memory/handoff.md`.

---

## Governance, Safety & Anti-Hallucination Guardrails

- **Read-Only Non-Destructive**: Probes live public production URLs with standard GET/HEAD requests.
- **Zero Token Burn on Clean Pass**: If all checks pass, write JSON log to `.loop-logs/` and terminate.
- **Dignity & Accessibility**: Asserts the 65 roses convention, WCAG 2.1 AA accessibility, and dignity of language.
- **Anti-Hallucination Guardrails**:
  - **Command Output Proof**: Security headers and 301 redirects must be asserted directly from curl / PowerShell response headers, never inferred.
  - **Exact Motif Count**: The 65 rose motif count must be determined by exact DOM query count (`data-rose` / class count == 65) from script execution; never estimate, round, or accept approximate counts.



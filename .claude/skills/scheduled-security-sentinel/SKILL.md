---
name: scheduled-security-sentinel
description: Autonomous log sentinel and automated fix PR engine. Continuously audits logs, transcripts, and git status across all workspace repos for secret leakage, PHI violations, SSRF, prompt injection escapes, and permission drift. Prepares verified fix PRs through the full gate.
license: CC0-1.0
compatibility: Compatible with Claude Code, Antigravity, and Agent Skills spec tools. Requires git, powershell, python, and gh CLI.
---

# Autonomous security log sentinel & automated fix PR engine (`scheduled-security-sentinel`)

Continuously audits background tasks, conversation logs, and repositories across Sensei Ewok's CF Lab with a strict security and privacy lens. Automatically detects secret exposures, Protected Health Information (PHI), network violations, and policy drift, and prepares verified fix pull requests through the Full review gate.

## Cadence & Trigger

- **Default Cadence**: Daily at 11:00 PM PT (`CRON_TZ=America/Los_Angeles 0 23 * * *`).
- **Antigravity Sidecar ID**: `scheduled-security-sentinel`
- **Review Tier**: `full` (mandatory for security, credentials, privacy, and repository integrity).

---

## Autonomous Ingestion & Auditing Pipeline

```mermaid
flowchart TD
    Trigger["Scheduled Trigger (Daily 23:00 PT)"] --> Ingest["1. Multi-Repo Log & State Ingestion"]
    Ingest --> Audit["2. 5-Point Security & Privacy Audit"]
    Audit --> Triage{"Anomalies Found?"}
    Triage -->|No| Clean["Emit Clean Audit Record to .loop-logs/"]
    Triage -->|Fixable Defect| Fix["3. Automated Remediation Worktree Pipeline"]
    Triage -->|Secret / Critical Leak| Alert["4. Emergency Handoff Alert & Revocation Notice"]
    Fix --> Gate["Full Gate: run-gate.ps1 -Tier full"]
    Gate --> PR["Open Pull Request via gh pr create"]
```

### 1. Multi-Repo Log & State Ingestion

Scan all background task artifacts and working directories across the four workspace roots:
- `cf-lab` (control repo)
- `../cf-research` (research repo)
- `../cf-skills` (skills repo)
- `../.ai` (public site repo)
- `../cf-lab-files/` (local files and logs)

Inspect:
- Agent conversation transcripts and step outputs in `<appDataDir>/brain/`.
- Local execution logs under `.loop-logs/`.
- Uncommitted git status (`git status --porcelain`).
- Recent git reflogs across all sibling repositories.

### 2. 5-Point Security & Privacy Audit Lens

1. **Secret & Credential Leakage**:
   - Check for API keys, bearer tokens, OAuth secrets, private keys, or credentials copied from `.env`.
   - Run `check-staged.ps1` to assert no secret file is staged.
2. **Zero PHI (Protected Health Information) Enforcement**:
   - Strictly confirm that no patient names, dates of birth, Medical Record Numbers (MRNs), hospital clinic identifiers, or patient narratives exist in any proposal, dossier, or log file.
   - Enforce research-only synthetic or anonymized public aggregate metrics.
3. **Catalog & Network Conduct Check**:
   - Confirm all outbound network calls strictly matched declarations in `../cf-research/sources/catalog.yaml`.
   - Verify rate limits and robots.txt compliance; assert zero uncataloged SSRF or arbitrary URL scraping.
4. **Prompt Injection Quarantine Compliance**:
   - Verify that any external clinical trial text, preprint abstract, or untrusted payload ingested during research runs was quarantined within `<untrusted_data>` XML tags.
   - Assert that no tools were granted to models while consuming raw untrusted inputs.
5. **Stray Files & Canary Verification**:
   - Execute canary and stray detection scripts:
     ```powershell
     pwsh -NoProfile -File .claude/skills/security-git/scripts/check-staged.ps1
     pwsh -NoProfile -File .claude/skills/security-git/scripts/check-lab-files.ps1
     ```

### 3. Automated Remediation & PR Pipeline

When a fixable hygiene or security defect is detected (e.g. missing `.gitignore` pattern, unescaped catalog URL, lint regression, or stale hash):

1. **Check Active Worktrees & Board Branches**:
   - Inspect `tasks/board.json` (`status: "in_progress"` and `"branch"`) and `git -C <repo> worktree list` before touching any repository. If an active branch/worktree is already modifying the affected files, log the finding to `memory/handoff.md` rather than racing on the same target.
2. **Spawn Isolated Git Worktree & Record Branch**:
   ```powershell
   python .claude/skills/workspace-siblings/scripts/worktrees.py new <repo> sec-fix-<topic>
   ```
   - When claiming a board task for the fix, set `"status": "in_progress"` and `"branch": "sec-fix-<topic>"` in `tasks/board.json` and run `pwsh -NoProfile -File tasks/render-board.ps1`.
3. **Apply Minimal Deterministic Patch**:
   - Apply only the focused remediation code.
3. **Run Full Review Gate**:
   ```powershell
   pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/run-gate.ps1 -Tier full -Expected "<changed-files>" -MessageFile <path-to-commit-msg>
   ```
4. **Independent Diff Review (`pr-review-loop`)**:
   - Execute an independent review pass of the diff.
   - Record the review table in the PR body.
5. **Submit Pull Request**:
   ```powershell
   gh pr create --repo senseiewok/<repo> --title "fix(security): <description>" --body-file pr-body.md
   ```
   - PR is assigned to the maintainer.

### 4. Emergency Escalation (Critical Leaks)

If an active API key or private credential is ever detected in a log or commit:
1. **Never attempt a silent patch**: Deleting a credential from Git history is insufficient; it must be revoked at the provider.
2. Immediately log a high-priority alert in `memory/handoff.md`.
3. Propose a P0 task in `tasks/board.json` detailing the leaked identifier name (never the secret value) and exact revocation steps for the human maintainer.

---

## Governance

- **Fails Closed**: Any unparseable log or ambiguous permission state is flagged for human review.
- **Maintainer Gate**: The sentinel opens pull requests and logs alerts; only the human maintainer merges code.

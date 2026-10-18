# Operational Continuity & Governance Architecture

> **Context**: Task `T-0129` ("A continuity note: what a second person needs to keep the lab running").  
> **Security Baseline**: Public repositories must never contain credentials, passwords, private keys, or host IP addresses. Detailed operational commands requiring administrative context are maintained in the private, untracked local storage (`cf-lab-files/continuity-note.md`).

---

## 1. Overview & Operational Continuity Scope

Sensei Ewok CF Lab operates a multi-repository workspace supporting open cystic fibrosis computational biophysics research and educational outreach via [senseiewok.ai](https://senseiewok.ai/). Because day-to-day engineering is maintained by a single primary contributor alongside automated sentinels, clear governance rules are required so that an authorized second person (a co-maintainer, technical trustee, or designated successor) can inspect, pause, maintain, or take down public operations without relying on oral handover.

This document describes the high-level governance structure, platform components, and procedures. The companion operational runbook containing specific procedure checklists is stored in private local lab files (`cf-lab-files/continuity-note.md`).

---

## 2. Platform Architecture & Separation of Concerns

The workspace is organized into four GitHub repositories and a strictly local untracked directory:

| Workspace Root | Repository / Folder | Purpose | Public / Private |
| :--- | :--- | :--- | :--- |
| `cf-lab` | `senseiewok/cf-lab` | Control repository: task board (`tasks/board.json`), shared agent instructions, sentinels, security baseline. | Public |
| `.ai` | `senseiewok/.ai` | Public website: HTML5/CSS/ES modules for `senseiewok.ai`, CI deploy workflows, Playwright visual tests. | Public |
| `cf-research` | `senseiewok/cf-research` | Research repository: source catalog (`sources/catalog.yaml`), clinical trial surveillance, dossiers. | Public |
| `cf-skills` | `senseiewok/cf-skills` | Reusable skills: packaging for Claude Code, Copilot, and open AI tooling. | Public |
| `cf-lab-files` | `../cf-lab-files` (local only) | Untracked machine layer: private correspondence, session notes, operational runbooks. | **Private (Never published)** |

---

## 3. Key Administrative Domains

Operational authority is partitioned across three core administrative boundaries:

1. **GitHub Organization (`senseiewok`)**:
   - Manages access to all workspace source code.
   - Enforces branch rulesets on `main` across all repositories (blocking force-pushes and requiring pull requests with passing status checks).
   - Manages repository and environment secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PASSWORD`).
2. **Authoritative DNS & Domain Management**:
   - Manages DNS records (`A`, `AAAA`, `CNAME`, `TXT`) for `senseiewok.ai`.
   - Allows authoritative domain suspension or redirection in emergency scenarios.
3. **Web Server Hosting (Apache / FTPS)**:
   - Houses static files under `public_html/`.
   - Enforces live HTTP security headers via `.htaccess` (CSP, HSTS, Referrer-Policy, nosniff, frame-ancestors).

---

## 4. Emergency Procedures Summary

Detailed runbook procedures are preserved in `cf-lab-files/continuity-note.md`. The high-level protocols are summarized below:

### Halting Deployments
If an erroneous commit reaches `main` in `senseiewok/.ai` or a workflow malfunction occurs:
- The deployment workflow (`.github/workflows/deploy.yml`) can be paused via the GitHub web interface or using the GitHub CLI:
  ```bash
  gh workflow disable deploy.yml --repo senseiewok/.ai
  ```
- Any currently active deploy run can be terminated via `gh run cancel <run-id> --repo senseiewok/.ai`.

### Site Maintenance / Takedown
In the event that the public website must be suspended:
- **Server Maintenance Rule**: An `.htaccess` rewrite rule can be placed in `public_html/` returning HTTP 503 Service Unavailable with an approved static `maintenance.html` notification. This preserves search engine indexing while removing interactive assets from public access.
- **DNS Redirection**: If hosting infrastructure is compromised, DNS records may be pointed to a static parking page or suspended at the registrar.

### Deploy Credential Rotation
If deployment credentials require rotation:
1. Reset the FTPS user password in the hosting control panel.
2. Update the `DEPLOY_PASSWORD` secret in the `production` environment of `senseiewok/.ai`:
   ```bash
   gh secret set DEPLOY_PASSWORD --env production --repo senseiewok/.ai
   ```
3. Run a dry run (`gh workflow run deploy.yml --ref main -f dry_run=true`) to verify authentication before releasing any commits.

---

## 5. Medical Boundaries & Public Messaging Guidelines

In any planned maintenance or unplanned emergency downtime, public communications must adhere strictly to the lab's voice and medical safety standards:
- **No Medical Advice / No Clinical Promises**: State clearly that the lab is an independent computational research project and does not offer clinical diagnosis or medical care.
- **Direct Emergency Traffic to Accredited Care**: Any maintenance notice must provide standard guidance directing individuals requiring urgent cystic fibrosis care to accredited CF care centers, their pulmonologist, or local emergency services.
- **Bilingual Notification**: Maintenance notices should be provided in both English and Mexican Spanish (es-MX).

---

## 6. Acceptance Verification Gate

Per acceptance criteria for `T-0129`:
> *"A short document in the private lab files (never in a public repo, and with no secret in it) lists where each thing lives and who may do it: the deploy path and how to stop it, how to take the site down, how to rotate the deploy credential, which accounts matter, and what to tell visitors. A person other than the maintainer has read it and says whether it is enough. No credentials, no host details in any public file."*

Because this task explicitly requires an external person other than the maintainer to review the private continuity document and verify its sufficiency, the task remains in `ready` status on the task board until external human review is executed and recorded.

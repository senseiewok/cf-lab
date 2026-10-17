# Lab Identity, Public Role Address, and External Correspondence Policy
**Task Reference**: T-0117 ("Identity in public files: one role address, one way to sign")  
**Related Documents**: `SECURITY.md`, `tasks/HUMAN-TASKS.md` Section 2, `AGENTS.md`  
**Status**: Adopted & Recorded  
**Effective Date**: 2026-10-17  

---

## 1. Objective and Scope

This document sets the single standard for institutional identity, public role addresses, letter signing, third-party publisher contact citations, and commit author verification across Sensei Ewok's CF Lab (`cf-lab`, `cf-research`, `cf-skills`, and `.ai`).

To preserve individual maintainer privacy, prevent identity mixing, and present an unbroken institutional voice, the lab enforces five structural identity invariants.

---

## 2. The Five Identity Invariants

### Invariant 1: One Public Role Address (`contact@senseiewok.ai`)
- **Single Public Address**: Across all public documentation, repository security policies, contact pages, and outreach materials, the **only** permitted public email address is `contact@senseiewok.ai`.
- **Zero Personal Email Exposure**: Personal or first-name addresses (e.g. `diego@...`) must never appear in public git-tracked files or website markdown/HTML.
- **Security Vulnerability Reporting**: `SECURITY.md` directs all vulnerability inquiries to `contact@senseiewok.ai` with `[security]` in the subject line, or via GitHub's Private Vulnerability Reporting mechanism.

### Invariant 2: Outbound Letters Signed Exclusively by the Lab
- **Institutional Signing**: Outbound communication—including permission requests to data registries (CFTR2, ECFSPR, UK Cystic Fibrosis Trust, ACFDR, CFFPR), academic data providers (Child Opportunity Index), and clinician review invitations—must be signed by the lab as an entity:
  > `Sensei Ewok CF Lab · contact@senseiewok.ai · [date]`
- **The Lab Speaks for Itself**: Letters are never signed by an individual person or personal handle. The lab functions as an open-source research initiative.
- **Maintainer Sovereignty**: Only the human maintainer may dispatch outbound permission letters (as tracked under `tasks/HUMAN-TASKS.md` Section 2). AI agents assist with drafting and formatting, but never send outbound emails.

### Invariant 3: Private Reply Storage & Public Outcome Ledger
- **Private Correspondence Retention**: When external entities reply to letters, full email text, headers, and correspondence history are archived strictly within personal, untracked directories (`../cf-lab-files/`, notably `permission-letters-dispatch.md`).
- **Zero Inbound Text Leaks**: Inbound emails from external researchers, registry coordinators, or clinicians must never be committed to git history.
- **Public Terms in Catalog**: Only verified public outcomes (e.g. permission granted, restricted to citation-only, link-only) are updated in `sources/catalog.yaml` via standard review pull requests.

### Invariant 4: Catalog Publisher Contacts Designated as "The Contact in the Terms"
- **No Third-Party PII in Catalog**: `sources/catalog.yaml` must not publish individual people's email addresses or institutional administrative mailboxes.
- **Standardized Reference**: Where an external registry or publisher terms page specifies a contact channel for questions or permission requests, the catalog notes must state:
  > *"the contact in the terms"* or *"the contact named in the terms"*
- This prevents scrapers from harvesting email addresses from our public repository and prevents catalog drift if a publisher updates their internal routing address.

### Invariant 5: Commit Author Verification Enforced by Review Gate
- **Pre-Commit Enforcement**: The pre-commit gate script (`.claude/skills/ai-loop-council/scripts/run-gate.ps1`) deterministically inspects `git var GIT_AUTHOR_IDENT` and `git var GIT_COMMITTER_IDENT` (or `git config user.email` / `$env:GIT_AUTHOR_EMAIL`).
- **Permitted Author Domains**:
  - `@senseiewok.ai` (lab addresses, e.g. `contact@senseiewok.ai` or `diego@senseiewok.ai`)
  - `@users.noreply.github.com` (GitHub's privacy-preserving no-reply author address)
  - `@example.invalid` (test fixtures in automated gate test suites)
- **Blocked Personal Webmail**: Commits with author or committer addresses matching personal webmail providers (`@gmail.com`, `@outlook.com`, `@yahoo.com`, `@hotmail.com`, `@icloud.com`, `@proton.me`, etc.) are rejected with exit code 1 (`GATE FAILED: commit-author`), preventing accidental identity leakage into permanent git history.

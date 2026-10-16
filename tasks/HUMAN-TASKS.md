# Human tasks

What only a person can do, kept as one checklist so nothing waits unseen. `board.json` stays the lab's single task list; this file is a hand-kept view of what strictly requires a human maintainer. **When this file and the board disagree, the board wins.** Tick a box when it is done and add the date.

Last reviewed: 2026-10-14 (Council triage and maintainer directive: engineering, testing, and tool governance approved for agent automation; this checklist retains only true human actions).

---

## 1. Sign-ups, Licences and API Keys (Nothing is done until you do it)

Use a lab-owned address, never a personal one. Keys go only in the git-ignored `.env`; never paste one into a chat, a file in a repo or a pull request. Template: `cf-lab/.env.example`. Details: `cf-research/proposals/2026-10-08-source-plan-and-signups.md`.

- [x] **OpenAlex API key** (2026-10-14): Obtained by maintainer. Configured via `OPENALEX_API_KEY` in `.env` (PR cf-lab#86, cf-skills#24).
- [ ] **NCBI API key**: Optional (raises request rate limits from 3 to 10 rps).
- [ ] **openFDA key**: Optional (raises request rate limits from 40 to 240 req/min).
- [ ] **Data Commons API key**: Free per Google catalog entry; completes T-0048 integration.
- [ ] **Semantic Scholar API key**: Decide on Ai2 licence terms (indemnity, Washington State law); request key through their form.
- [ ] **Gemini API key (T-0101)**: Decide whether Pro IDE licence covers API use or if separate Google AI Studio API key is preferred.
- [ ] **Paid items (T-0047)**: Decide on any paid research subscriptions (e.g. Scite Pro).

---

## 2. External Permission Letters & Outbound Communications

Letters must be reviewed, filled, and sent by the human maintainer from the lab's official email address. Replies take weeks and gate registry citation data. Drafts live in `cf-research` (PR #12, PR #19).

- [ ] **Send CFTR2 permission letter**: Request quotation / citation terms for variant allele counts.
- [ ] **Send Child Opportunity Index (COI) letter**: Request usage confirmation for pediatric social determinants.
- [ ] **Send CF Foundation Patient Registry letter**: Request data citation terms and record reply in `landscape/registry-data-access.md`.
- [ ] **Send ECFSPR letter**: European Cystic Fibrosis Society Patient Registry.
- [ ] **Send UK Cystic Fibrosis Trust Registry letter**.
- [ ] **Send Australian Cystic Fibrosis Data Registry (ACFDR) letter**.

---

## 3. Clinical & Community External Reviews

Medical boundary and community safety require external human expertise; AI cannot replace licensed clinicians or lived experience.

- [ ] **Clinician / Social Worker Safe-Use Review (T-0105)**: Have a CF clinician or social worker review safe-use box wording, crisis language, 988 inclusion, and priority ordering (emergency services vs. CF care team urgent line).
- [ ] **Community & Registry Review (T-0011)**: Arrange an external review round by a person with CF or family caregiver (on plain-language dignity) and a registry biostatistician (on data comparability). No public page may claim community endorsement until completed.

---

## 4. Physical Device & Hardware Usability Testing

- [ ] **CFTR 3D Molecule Viewer on Physical Phone**: Test 3D touch interaction, trackball rotation, bottom-sheet sheet drag, and gesture responsiveness on a physical iOS / Android device (cannot be fully validated via headless Playwright emulation).

---

## 5. Administrative & External Platform Settings (Web UI Only)

Administrative controls and external platform settings that cannot or should not be automated via agent API tokens:

- [ ] **Turn on GitHub Rulesets on `main` (T-0110)**: In repository settings for `cf-lab`, `cf-research`, and `cf-skills`, enable branch rulesets: require pull requests, block force pushes, and require maintainer review.
- [ ] **Repository Contribution Settings (T-0128)**: Ensure GitHub repository settings reflect "no outside contributions": turn Discussions off and restrict public pull requests / issues.
- [ ] **Update YouTube Channel About Text (T-0002)**: In YouTube Studio (Web UI), replace the `@SenseiEwok` channel description with the approved text from `docs/youtube-about-update.md` (removes 'accelerate the cure', adds 'not medical advice' and 'not affiliated' boundary lines). Verify with `python tasks/test_youtube_about.py --live`.

---

## 6. Council-Approved Tasks (Automated & Moved to Ready / Done)

Per maintainer instruction and Council deliberation on 2026-10-14, all engineering, testing, CI, and tooling tasks previously listed here have been approved and moved out of this human checklist into `tasks/board.json`:

| ID | Title | Status | Council Action / Outcome |
| :--- | :--- | :--- | :--- |
| **T-0098** | `cf-research`: make script-style tests collectable by unittest | `done` | Verified: 48 tests discoverable and passing via `unittest`. |
| **T-0118** | Decide read and discard (`cf-research` #23) | `done` | Verified: PR #23 merged in commit `11ecf17`. |
| **T-0119** | Local AI review of diff in gate | `done` | Verified: PR #36 merged in commit `0c0fabd`. |
| **T-0068** | `review-diff.ps1` as single gate command | `done` | Verified: Operational in `ai-loop-council`. |
| **T-0089** | Mechanical filter for local review findings | `done` | Verified: Merged in commit `20492a2` (PR #4). |
| **T-0139** | Server production headers and 301 redirects | `done` | Verified: Active on production `senseiewok.ai`. |
| **T-0102** | Bring lab sources together: variant layer (Step 2) | `ready` | Approved: Step 1 (OpenAlex) merged; Step 2 ready for agent execution. |
| **T-0104** | Standardize emergency number format | `ready` | Approved: Standardized on exact bracket `(911 in the US)`. |
| **T-0099** | Reviewed lesson on exclusive log locking | `ready` | Approved: Documentation update to `ai-loop-council`. |
| **T-0108** | Block agent web tool for manual/forbidden hosts | `ready` | Approved: Agent web tool allow/deny filtering. |
| **T-0109** | Privacy rule: generalize before searching real persons | `ready` | Approved: Security/privacy prompt guardrail. |
| **T-0111** | Harden commit gate on pass and stray files | `ready` | Approved: Gate hardening in `run-gate.ps1`. |
| **T-0114** | Standard-library test CI for public repos | `ready` | Approved: GitHub Actions CI workflow definitions. |
| **T-0115** | Record agent permission mode & block GH settings | `ready` | Approved: Security runtime hardening. |
| **T-0116** | Pin third-party skills by hash | `ready` | Approved: Supply-chain manifest hash pinning. |
| **T-0121** | Decouple evidence tool catalog copy from PR churn | `ready` | Approved: Direct reading / pinned catalog cache. |
| **T-0053** | Data Commons provider in `cf-evidence-loop` | `ready` | Approved: Google Data Commons population denominators. |
| **T-0066** | Promote ad-hoc page reader to tested tool | `ready` | Approved: Bounded tooling refactor. |
| **T-0127** | Board consistency check in `render-board` | `ready` | Approved: Validation script enhancement. |
| **T-0141** | Pin byte copies of CFTR files to recorded commit | `ready` | Approved: Site CI synchronization. |
| **T-0143** | PR template and review-loop body check | `ready` | Approved: Quality gate tooling. |

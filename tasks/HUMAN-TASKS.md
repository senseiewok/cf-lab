# Human tasks

What only a person can do, kept as one checklist so nothing waits unseen. `board.json` stays the lab's single task list; this file is a hand-kept view of the rows and pull requests that need a human. **When this file and the board disagree, the board wins.** Tick a box when it is done and add the date.

Last reviewed: 2026-10-09 (after the log review by a blind council: security and compliance first). Items about the private site repository are kept out of this public file; they live in that repository's own notes.

## 1. Pull requests waiting for a person to merge

A pull request is a proposal until a person merges it. Agents never merge.

| Repo | PR | What | What it needs |
| --- | --- | --- | --- |
| cf-research | #10 (draft) | Six API candidates in the source catalog, all held at `manual` | A council reviewed it on 2026-10-09 and its fixes are in; a person reads the diff (Full tier: licensing) and answers its four decisions |
| cf-research | #23 | Read and discard: grounding on sources we may cite but not copy (a proposal, nothing built) | Read it and answer its six decisions (T-0118) |
| cf-research | #19 | Three letters to send (CFTR2 permission, Child Opportunity Index use, a review invitation): drafts only, nothing sent | Read, merge, then send them yourself from the lab address (section 3) |

## 2. Board decisions only a person can make

| Row | Decision |
| --- | --- |
| T-0100 | Approve the three differences from the revised acceptance |
| T-0075, T-0078 | Close them (work is merged) |
| T-0098, T-0099 | Set `ready` so they can be built |
| T-0101 | Say whether the Pro licence covers API use (an API key is separate from an IDE licence) |
| T-0102 | Set `ready` (bring the lab's sources together). It was asked for in chat on 2026-10-08, but only the board status makes it official |
| T-0103 | Try the five paste-ready boxes on Gemini, ChatGPT and Copilot (needs a person with access to each) |
| T-0104 | Decide the form of the one allowed emergency number: exact `(911 in the US)`, or 911 whenever it sits next to US |
| T-0105 | A clinician or social worker reads the safe-use box wording; also whether 988 belongs in it and whether emergency services come before the CF team's line |
| T-0106 | Send the permission letters and record every reply in the catalog |
| T-0107 | Take the conference banner down after NACFC 2026 (say the date) |
| T-0108 | Add deny rules so the agent web tool cannot reach catalog hosts marked manual, request or forbidden (a settings edit only you make; an agent can draft the host list) |
| T-0109 | Word the rule for questions about one real person: generalise before any search, keep nothing about the person |
| T-0110 | Turn on a ruleset for `main` in each public repo (pull request required, no force push, code-owner review) |
| T-0111 | Read the diff when the commit-gate hardening arrives (it changes an agent-control script) |
| T-0114 | Decide whether the public repos get test CI |
| T-0115 | Decide the permission mode agents run in while you are away; add deny rules for GitHub settings commands |
| T-0116 | Decide whether the third-party skill-creator keeps its scripts |
| T-0117 | Choose one role address for public files, how letters are signed, and whether the READMEs credit an AI vendor |
| T-0118 | Answer the six decisions in cf-research #23 |
| T-0011 | Arrange the review by a person with CF or a carer, and a registry scientist. No page may claim community review until it happens |

## 3. Sign-ups, licences and requests (nothing is done until you do it)

Use a lab-owned address, never a personal one. Keys go only in the git-ignored `.env`; never paste one into a chat, a file in a repo or a pull request. The table that explains each step is in cf-research `proposals/2026-10-08-source-plan-and-signups.md` (PR #11).

- [ ] OpenAlex API key (the catalog says a key is required). First, because it unlocks the most
- [ ] Optional NCBI and openFDA keys (they raise request limits; the new limits are unread)
- [ ] Send the CFTR2 letter, the Child Opportunity Index letter and the review invitation (cf-research PR #19; fill the placeholders, confirm each addressee on its own site first)
- [ ] Send the CF Foundation Patient Registry letter (cf-research PR #12), and record the reply in `landscape/registry-data-access.md`
- [ ] Send the ECFSPR letter
- [ ] Send the UK registry (Cystic Fibrosis Trust) letter
- [ ] Send the Australian registry letter
- [ ] Sign in to the Claude connectors you want (ChEMBL, ClinicalTrials.gov, PubMed, bioRxiv)
- [ ] Decide on Semantic Scholar: using it binds the lab to Ai2's licence (indemnity, Washington State law); then request a key through its form
- [ ] Optional: a Data Commons key (free per the catalog) to finish T-0048
- [ ] Decide whether a Gemini key is worth it (T-0101)
- [ ] Decide on any paid item (Scite Pro, T-0047). No price has been read

## 4. Decisions that are not code

- [ ] Confirm the answer tiers T0 to T3 and the scope-record rule for widening words as lab rules (written into `cf-research-context` and `AGENTS.md` by this PR from cf-research's strategy proposal)
- [ ] Registry reuse and cloud use (T-0072): whether sources with unread terms go only to local models, whether to ask the Foundation and the Trust for permission to quote, and the licence wording for skills that carry quotations
- [ ] Try the CFTR model page on a real phone (touch, the bottom sheet, double-tap): it was tested only in headless Chromium
- [ ] Whether to open Discussions on cf-lab with the welcome post (a draft exists)
- [ ] After each merge: remove the agent's worktree (an agent does it when asked)

## Not human tasks

Anything an agent can check without a person is not listed here: tests, the gate, the board render, catalog field checks. A model's report that a task is done is not a person's approval.

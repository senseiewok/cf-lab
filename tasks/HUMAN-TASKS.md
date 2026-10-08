# Human tasks

What only a person can do, kept as one checklist so nothing waits unseen. `board.json` stays the lab's single task list; this file is a hand-kept view of the rows and pull requests that need a human. **When this file and the board disagree, the board wins.** Tick a box when it is done and add the date.

Last reviewed: 2026-10-08. Items about the private site repository are kept out of this public file; they live in that repository's own notes.

## 1. Pull requests waiting for a person to merge

A pull request is a proposal until a person merges it. Agents never merge.

| Repo | PR | What | What it needs |
| --- | --- | --- | --- |
| cf-research | #8 | A ClinVar evidence profile tool (`tools/variant_profile`) | Read, merge; and decide which variant its test fixture should use |
| cf-research | #10 (draft) | Six API candidates in the source catalog, none admitted | A different-family blind review, then a person reading the diff (Full tier: licensing) |
| cf-research | #11 | Ranked sources and the sign-up table | Read, decide which sign-ups to do |
| cf-research | #12 | Four registry permission letters (drafts) | Read, edit, then send (section 3) |
| cf-lab | this PR | This file | Read, merge |

## 2. Board decisions only a person can make

| Row | Decision |
| --- | --- |
| T-0100 | Approve the three differences from the revised acceptance |
| T-0075, T-0078 | Close them (work is merged) |
| T-0098, T-0099 | Set `ready` so they can be built |
| T-0101 | Say whether the Pro licence covers API use (an API key is separate from an IDE licence) |
| T-0102 | Set `ready` (bring the lab's sources together). It was asked for in chat on 2026-10-08, but only the board status makes it official |
| T-0011 | Arrange the review by a person with CF or a carer, and a registry scientist. No page may claim community review until it happens |

## 3. Sign-ups, licences and requests (nothing is done until you do it)

Use a lab-owned address, never a personal one. Keys go only in the git-ignored `.env`; never paste one into a chat, a file in a repo or a pull request. The table that explains each step is in cf-research `proposals/2026-10-08-source-plan-and-signups.md` (PR #11).

- [ ] OpenAlex API key (the catalog says a key is required). First, because it unlocks the most
- [ ] Optional NCBI and openFDA keys (they raise request limits; the new limits are unread)
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

- [ ] Registry reuse and cloud use (T-0072): whether sources with unread terms go only to local models, whether to ask the Foundation and the Trust for permission to quote, and the licence wording for skills that carry quotations
- [ ] Whether to open Discussions on cf-lab with the welcome post (a draft exists)
- [ ] After each merge: remove the agent's worktree (an agent does it when asked)

## Not human tasks

Anything an agent can check without a person is not listed here: tests, the gate, the board render, catalog field checks. A model's report that a task is done is not a person's approval.

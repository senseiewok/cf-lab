# Design: Opt-In Automatic Local Worker Delegation (`COUNCIL_AUTO_DELEGATE_LOCAL`)

> **Task Reference:** T-0027  
> **Status:** Approved Design & Policy Specification  
> **Configuration Source:** Environment variable / `.env` (`COUNCIL_AUTO_DELEGATE_LOCAL`)  
> **Default:** `false` (off)  

---

## 1. Motivation & Context

In Sensei Ewok's CF Lab, routine drafting, mechanical log audits, and first-pass code reviews are assigned to the preferred local worker (`qwen3.8:27b-64k` via Ollama) by policy (`AGENTS.md` and `ai-loop-council`). However, controlling agents currently must explicitly remember to invoke `.claude/skills/ai-loop-council/scripts/invoke-local-model.ps1` or `delegate.ps1`.

An opt-in setting allows a controlling agent or orchestrator to delegate bounded drafting and triage tasks to a usable local worker automatically, reducing cloud token burn while maintaining strict containment, determinism, and data privacy.

---

## 2. Setting Specification

- **Setting Name:** `COUNCIL_AUTO_DELEGATE_LOCAL`
- **Location:** Placed alongside `LOCAL_WORKER_PROFILE` and `LOCAL_WORKER_MODEL` in the repository's git-ignored `.env` file (template: `.env.example`).
- **Why an Environment Variable?**  
  Agent skills (`SKILL.md`) are interpreted differently across AI provider clients (Claude Code, GitHub Copilot, Antigravity, Qwen-Coder). Some clients do not parse custom skill frontmatter fields as executable configuration. An environment variable loaded via process environment or `run-with-env.ps1` provides a universal, tamper-evident configuration mechanism across all execution environments.
- **Default Value:** `false` (off).  
  When unset or set to `false`, automatic local delegation is inactive; delegation requires explicit agent invocation or manual routing.

---

## 3. When Automatic Delegation Applies ("Helpful" Boundary)

Automatic local delegation triggers **only** when all of the following conditions are met:

1. **Bounded Tasks:** The task scope is narrowly defined with concrete file targets and small context sizes (under context budget of the local profile).
2. **Tool-Free Execution:** The delegated worker receives raw prompts without tool calling or arbitrary shell access.
3. **Deterministic Verifiability:** The draft or review has a reliable automated verifier (unit tests, linters, `pwsh -File tasks/render-board.ps1 -Check`, or Playwright scripts) that can independently prove correctness.
4. **Usable Local Profile:** An Ollama endpoint is reachable on loopback (`http://127.0.0.1:11434`) and a verified local model profile (e.g. `qwen3.8:27b-64k`) is configured and running.

---

## 4. Invariants: What Automatic Delegation NEVER Does

The following strict security and governance invariants must never be violated under any circumstances:

1. **No Untrusted Text Without Quarantine:** External clinical trial notes, preprints, or uncataloged web inputs must never reach a local model without being quarantined within `<untrusted_data>` XML tags.
2. **No Secrets or Credentials:** Content from `.env`, credential stores, private tokens, or Protected Health Information (PHI) must never be passed to delegated model prompts.
3. **No Model Self-Approval:** A model's completion claim ("I have fixed the issue") is never accepted without passing deterministic verifier execution. Verifiers and test suites make the decision, never model assertion or voting.
4. **No Model Downloads:** The system never automatically downloads, pulls, or switches model weights. If the configured local model is unavailable, the system safely marks the local route unavailable and blocks or escalates according to policy.
5. **No Cross-Provider Escalation Waiver:** Enabling `COUNCIL_AUTO_DELEGATE_LOCAL` does not waive cross-provider constraints, human approval gates, or cloud data sharing policies.

---

## 5. Routing Integration

`select-work-route.ps1` implements deterministic evaluation of `COUNCIL_AUTO_DELEGATE_LOCAL` via `Get-AutoDelegateSetting`:
- Validates boolean values (`true`/`false`).
- Throws an error on ambiguous configuration strings (e.g. `yes`, `enabled`, `1`).
- Preserves backward compatibility: with the setting unset, existing routing decisions remain completely unchanged.

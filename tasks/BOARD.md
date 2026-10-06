# Task board

Generated from `board.json` by `render-board.ps1`. Edit the JSON, not this file.

97 tasks, 96 created by a model, 0 with a measured outcome. Estimated effort 217.6 to 396 hours in total. ROI index is benefit x 10 / midpoint hours: a ranking aid from estimates, not a result.

## in progress (24)

| ID | P | Task | Repo | Hours | Benefit | ROI idx | Measured | Created by | Created | Review | Complexity | Route | Depends on |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T-0004 | P1 | Gate .github/loop-orchestrator/loop.py with a hard failure | cf-lab | 0.25-0.25 | 3 | 120 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0037 | P1 | Add Retraction Watch (via Crossref) retraction check to the catalog and to the claim-check harness design | cf-research | 1-2 | 5 | 33.3 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0022 | P1 | Adopt the task board: every new task carries created_by, evidence, and an ROI estimate; render BOARD.md in CI or pre-commit | cf-lab | 1-2 | 4 | 26.7 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0003 | P1 | Apply the HQ skill-update proposal (security-browsing, cf-research-context, ai-loop-council, model-onboarding) | cf-lab | 1-2 | 4 | 26.7 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0077 | P1 | Interactive 3D CFTR channel animation: normal gating and chloride flow versus F508del misfolding | cf-lab | 8-16 | 5 | 4.2 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  | T-0078 |
| T-0013 | P2 | Read CFTR2 terms of use; set catalog access accordingly | cf-research | 0.5-0.5 | 2 | 40 | no | model: claude-fable-5-1 | 10/04/2026 | routine | low | cloud |  |
| T-0038 | P2 | Add openFDA drug label and Drugs@FDA approval endpoints to the catalog; resolve approval-year claims from them | cf-research | 1-2 | 4 | 26.7 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0062 | P2 | A generated manual-downloads page with links, file names and a prompt to run when the files are saved | cf-research | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated | low | local |  |
| T-0065 | P2 | Delegation: a sequential batch runner and a verifier-suspect hint | cf-lab | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated | medium | cloud |  |
| T-0067 | P2 | Decision: treat robots.txt groups that name AI agents as applying to our fetch sources | cf-skills | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  |  |
| T-0028 | P2 | Add a reviewed lesson to ai-loop-council: a verbatim-quote check does not verify inferences, and a truncated quote can produce a false 'differs' claim | cf-lab | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated | medium | local |  |
| T-0025 | P2 | Fix three fetch_sources.py defects: failed downloads exit 0, --dest can write an absolute path into the tracked manifest, --verify cannot check manually saved files | cf-research | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/04/2026 | routine | low | local |  |
| T-0024 | P2 | Board enhancement: add complexity, recommended_route (local, cloud or frontier) and route_rationale to tasks | cf-lab | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated | medium | cloud |  |
| T-0012 | P2 | Unit tests for tools/sources/fetch_sources.py | cf-research | 1.5-2.5 | 3 | 15 | no | model: claude-fable-5-1 | 10/04/2026 | routine | low | local |  |
| T-0039 | P2 | Read terms and record access values for medRxiv, ClinVar, Cochrane CF reviews, NIH RePORTER | cf-research | 1.5-2.5 | 3 | 15 | no | model: claude-fable-5-1 | 10/04/2026 | routine | medium | cloud |  |
| T-0059 | P2 | delegate.ps1: let a model-only setup run fast, and make the token budget and thinking mode explicit | cf-lab | 2-4 | 4 | 13.3 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated | medium | cloud |  |
| T-0048 | P2 | Admission review of Google's Data Commons MCP server for population denominators (layer 5) | cf-lab | 2-4 | 4 | 13.3 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0056 | P2 | check-lab-files.ps1: a deterministic check that the cf-lab-files folder holds nothing it must not | cf-lab | 3-5 | 3 | 7.5 | no | model: claude-sonnet-5-5 | 10/04/2026 | full | medium | cloud |  |
| T-0064 | P2 | More sources: UKRI Gateway to Research, CORDIS, EU Clinical Trials Register, WHO ICTRP, PubPeer, ClinGen, and the CFF 2025 highlights link | cf-research | 3-5 | 3 | 7.5 | no | model: claude-sonnet-5-5 | 10/05/2026 | full | medium | cloud |  |
| T-0063 | P2 | ascii-art skill: a craft process, a canvas library, a rendering and accessibility checker, one new piece, and the research behind them | cf-lab | 3-6 | 3 | 6.7 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated | medium | local |  |
| T-0052 | P2 | Close the findings a frontier-model review deferred in cf-evidence-loop v0.1 | cf-skills | 4-8 | 3 | 5 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated | medium | local | T-0037 |
| T-0026 | P3 | Docs and privacy tidy in research: complete the sources/README.md field table; decide the website domain and deploy detail in the proposals | cf-research | 0.5-1 | 2 | 26.7 | no | model: claude-sonnet-5-5 | 10/04/2026 | routine | low | local |  |
| T-0040 | P3 | Read terms and record access values for UK, Canadian, Australian, and Irish CF registry annual reports | cf-research | 1.5-3 | 3 | 13.3 | no | model: claude-fable-5-1 | 10/04/2026 | routine | medium | cloud | T-0008 |
| T-0054 | P3 | fetch_sources.py: make --verify honour --only | cf-research | 0.5-1 | 1 | 13.3 | no | model: claude-sonnet-5-5 | 10/04/2026 | routine | low | local |  |

## ready (4)

| ID | P | Task | Repo | Hours | Benefit | ROI idx | Measured | Created by | Created | Review | Complexity | Route | Depends on |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T-0080 | P1 | Website revamp and a better organization across the lab, with Fable's guidance | cf-lab | 4-10 | 5 | 7.1 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  |  |
| T-0078 | P1 | Improve the webgl-threejs-graphics and svg-animation skills with researched, checkable practice | cf-lab | 4-8 | 4 | 6.7 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  |  |
| T-0079 | P2 | Measure whether the local models can write WebGL and SVG: a verifier-first test | cf-lab | 2-4 | 3 | 10 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  |  |
| T-0075 | P2 | Trial Anthropic's public skills (frontend-design, skill-creator) against our own checks | cf-research | 3-5 | 3 | 7.5 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  |  |

## proposed (69)

| ID | P | Task | Repo | Hours | Benefit | ROI idx | Measured | Created by | Created | Review | Complexity | Route | Depends on |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T-0001 | P0 | Replace hq LICENSE.md with a named OSI license; add a LICENSE to research, .ai, skills | cf-lab | 0.5-1.5 | 5 | 50 | no | model: claude-fable-5-1 | 10/04/2026 | full |  |  |  |
| T-0002 | P1 | Fix YouTube About text: remove 'accelerate the cure', add research-not-advice and independence lines | channel | 0.25-0.5 | 4 | 106.7 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0006 | P1 | Send permissions emails to CFF registry contact and ECFSPR | cf-research | 0.5-0.5 | 4 | 80 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0005 | P1 | Download CFF Patient Registry PDFs by hand into research/sources/downloads | cf-research | 0.5-0.75 | 4 | 64 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0045 | P1 | Decide and document the install/link mechanism for using skills/cf-evidence-loop from hq without copying it | cf-lab | 1-2 | 4 | 26.7 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0072 | P1 | Decision: cloud-model use on reports with unread terms; permission requests to the CFF Registry and the CF Trust; the CC0 label on skills that carry quotations | cf-research | 1-2 | 4 | 26.7 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  |  |
| T-0092 | P1 | Re-run the SEO skill release review after the SEO008 fix | cf-skills | 1-3 | 4 | 20 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated |  |  | T-0083 |
| T-0008 | P1 | Freeze the cf-registry-extract row schema (incl. value_low/value_high or median_iqr, source_sha256) | cf-research | 2-3 | 4 | 16 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  | T-0005 |
| T-0081 | P1 | Outside scientific review and a CF-community read of the CFTR structure page before it goes anywhere public | .ai | 2-5 | 5 | 14.3 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  | T-0077 |
| T-0007 | P1 | Add [verified]/[unverified]/[hypothesis] labels to cystic-fibrosis.md, cff-goals.md, landscape/cf-repositories.md | cf-research | 2-3 | 3 | 12 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0083 | P1 | Release review of the site-seo-review skill | cf-skills | 3-6 | 3 | 6.7 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated |  |  |  |
| T-0082 | P1 | Try each agent's install path from the skills hub in a real client | cf-skills | 4-10 | 4 | 5.7 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated |  |  |  |
| T-0060 | P1 | Refresh the private .ai website for the first release: new repo names, evidence loop, setup, claim fixes | .ai | 6-12 | 4 | 4.4 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  | T-0041 |
| T-0009 | P1 | ECFSPR extraction pipeline v0.1 (5 report years, ~15 indicators) | cf-research | 16-20 | 4 | 2.2 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  | T-0008 |
| T-0018 | P2 | Add one explicit 'not affiliated with the Cystic Fibrosis Foundation' line near the site's donate link | .ai | 0.25-0.25 | 3 | 120 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0020 | P2 | Human review of the scope-triage table in cf-projects/CF-Project-Ideas.md | cf-lab | 0.5-0.5 | 3 | 60 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0058 | P2 | Run setup.sh and test-setup.py on a real Mac (and one Linux machine) and record the result | cf-lab | 0.5-1 | 4 | 53.3 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated |  |  |  |
| T-0014 | P2 | Decide the 'CF - until there's a cure' site tagline against lab-voice | .ai | 0.25-0.5 | 2 | 53.3 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0015 | P2 | Reconcile the website's 'M365 Copilot drives the lab's task scheduling' claim with reality | .ai | 0.25-1 | 3 | 48 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0071 | P2 | Put the ClinGen and gnomAD catalog conflicts into the BioMCP admission test | cf-lab | 0.5-1 | 3 | 40 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  | T-0042 |
| T-0033 | P2 | Send standard security response headers on the live website (HSTS, X-Content-Type-Options, Referrer-Policy, frame and content restrictions) | .ai | 0.5-1 | 2 | 26.7 | no | model: claude-sonnet-5-5 | 10/04/2026 | full |  |  |  |
| T-0017 | P2 | Self-host the two web fonts; remove the unused images.unsplash.com preconnect | .ai | 1-1.5 | 3 | 24 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0016 | P2 | Verify exactly 65 rose motifs render, and that reduced-motion is honoured, with a Playwright count | .ai | 1-1.5 | 3 | 24 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0074 | P2 | Run check_source_overlap.py in the review gate for notes built from reports | cf-lab | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  |  |
| T-0093 | P2 | Post the welcome note in the cf-lab GitHub Discussions | cf-lab | 0.5-1.5 | 2 | 20 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | low |  |  |
| T-0073 | P2 | A tool-limited agent definition for read-only reviewers | cf-lab | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  |  |
| T-0094 | P2 | Decide, after the review memo, whether the AI-agent robots.txt rule from T-0067 ships, then merge it in both repos | cf-skills | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/06/2026 | full | medium |  | T-0067 |
| T-0046 | P2 | Sickle cell disease coverage: HBB variant checks, ASH guideline source terms, and an SCD worked example in SKILL.md | cf-skills | 2-3 | 4 | 16 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  | T-0043 |
| T-0061 | P2 | Add GitHub Actions CI to cf-lab, cf-research and cf-skills (drafts are outside the repos; a human adds them under .github/workflows) | cf-lab | 2-4 | 4 | 13.3 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  | T-0057 |
| T-0030 | P2 | Docs tier 3: make AGENTS.md the only rule source; shrink copilot-instructions.md; fix the skill-authoring skill's internal contradictions | cf-lab | 2-3 | 3 | 12 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated |  |  | T-0029 |
| T-0076 | P2 | Make the skills repo installable as a Claude Code plugin marketplace | cf-skills | 2-3 | 3 | 12 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  | T-0051 |
| T-0042 | P2 | Admission review of BioMCP as a discovery tool alongside cf-evidence-loop | cf-lab | 3-5 | 4 | 10 | no | model: claude-fable-5-1 | 10/04/2026 | full |  |  |  |
| T-0041 | P2 | Website section for the evidence loop: how the lab answers a research question, with the seven layers and a live example record | .ai | 3-5 | 4 | 10 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  | T-0037 |
| T-0070 | P2 | Read the terms and robots.txt of Ensembl REST, NCBI Variation Services, UniProt and ClinVar bulk files with the lab's reader; propose catalog entries | cf-research | 3-5 | 4 | 10 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  |  |
| T-0035 | P2 | Tier table and loop housekeeping: elevated challenger rule, slim ai-loop-council, retire the loop-orchestrator prototype | cf-lab | 2-4 | 3 | 10 | no | model: claude-sonnet-5-5 | 10/04/2026 | full |  |  | T-0030 |
| T-0027 | P2 | Design an opt-in setting that lets the controlling agent delegate bounded drafts to a usable local worker automatically | cf-lab | 2-4 | 3 | 10 | no | human: Sensei Ewok | 10/04/2026 | elevated |  |  |  |
| T-0086 | P2 | Depth probe for the 64K local alias | cf-lab | 2-4 | 3 | 10 | no | model: claude-sonnet-5-5 | 10/06/2026 | routine |  | local |  |
| T-0011 | P2 | External review round: registry scientist on comparability, person with CF/caregiver on wording | cf-research | 4-6 | 5 | 10 | no | model: claude-fable-5-1 | 10/04/2026 | full |  |  | T-0009 |
| T-0089 | P2 | Mechanical filter for local review findings: reproduce each failing input in a temp copy | cf-lab | 3-6 | 4 | 8.9 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | medium | local |  |
| T-0051 | P2 | Decide and implement how the control repo consumes the evidence skill | cf-lab | 2-5 | 3 | 8.6 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated |  |  | T-0037 |
| T-0049 | P2 | Pilot Gemini Deep Research (collaborative planning) as the frontier-planning leg; verify every citation through cf-evidence-loop | cf-lab | 4-6 | 4 | 8 | no | model: claude-fable-5-1 | 10/04/2026 | full |  |  | T-0037 |
| T-0043 | P2 | Variant layer: MyVariant.info and gnomAD providers (aggregate frequencies only) | cf-skills | 4-6 | 4 | 8 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0047 | P2 | Trial one Scite Pro seat; build a supporting/contrasting/mentioning provider for cf-evidence-loop behind the same conduct rules | cf-skills | 4-6 | 4 | 8 | no | model: claude-fable-5-1 | 10/04/2026 | full |  |  | T-0042 |
| T-0066 | P2 | Promote the ad-hoc page reader to a tested tool with the evidence loop's own conduct rules | cf-skills | 3-5 | 3 | 7.5 | no | model: claude-sonnet-5-5 | 10/05/2026 | full |  |  |  |
| T-0034 | P2 | Claim checker for the elevated tier: quote, absence and count claims with a mandatory positive control | cf-lab | 3-5 | 3 | 7.5 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated |  |  |  |
| T-0019 | P2 | Add model profile skills for Gemma 4 31B and Laguna XS 2.1, or remove them from the site's field guide | cf-lab | 2-4 | 2 | 6.7 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0085 | P2 | Delegation loop: answer-first contract, grouped verifier feedback and a PowerShell AST lint | cf-lab | 3-6 | 3 | 6.7 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | medium | local |  |
| T-0084 | P2 | Local worker playbook cards v0 and the bare-versus-card measurement | cf-lab | 6-12 | 4 | 4.4 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | medium | local |  |
| T-0090 | P2 | Re-measure the local reviewer with the thinking profile and more runs per arm | cf-lab | 6-12 | 3 | 3.3 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | medium |  | T-0083 |
| T-0097 | P2 | Re-run the local reviewer evaluation on a second, different script | cf-lab | 6-12 | 3 | 3.3 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | medium |  |  |
| T-0010 | P2 | Claim-check harness + frozen 60-claim evaluation set | cf-research | 12-16 | 4 | 2.9 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  | T-0009 |
| T-0057 | P3 | Human edits to the protected .github folder after the rename: CODEOWNERS, copilot-instructions names, CI workflows | cf-lab | 0.1-0.25 | 1 | 57.1 | no | model: claude-sonnet-5-5 | 10/04/2026 | routine |  |  |  |
| T-0023 | P3 | Website: confirm 2024 Alyftrek and 2019 Trikafta approval dates against FDA records before next deploy | .ai | 0.5-0.5 | 2 | 40 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  |  |
| T-0032 | P3 | Docs tier 5: tidy per-user agent memory outside the repos | cf-lab | 0.25-0.5 | 1 | 26.7 | no | model: claude-sonnet-5-5 | 10/04/2026 | routine |  |  |  |
| T-0029 | P3 | Docs tier 2: hq housekeeping outside .claude (README tree, loop README status line, retire committed PR descriptions) | cf-lab | 0.5-1 | 2 | 26.7 | no | model: claude-sonnet-5-5 | 10/04/2026 | routine |  |  |  |
| T-0095 | P3 | Make the website's footer and credit wording agree with the README's 'Thanks to the tools' section | cf-lab | 0.5-1.5 | 2 | 20 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | low |  |  |
| T-0068 | P3 | review-diff.ps1: the gate's local-worker review row as one command | cf-lab | 1-2 | 3 | 20 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  |  |
| T-0096 | P3 | Run the optional Playwright browser-testing setup on a real Mac and a Linux machine | cf-lab | 0.5-1.5 | 2 | 20 | no | model: claude-sonnet-5-5 | 10/06/2026 | elevated | low |  | T-0058 |
| T-0088 | P3 | Keep everything a verifier reads inside its temp copy | cf-lab | 1-3 | 3 | 15 | no | model: claude-sonnet-5-5 | 10/06/2026 | routine |  | local |  |
| T-0031 | P3 | Docs tier 4: move the idea inventory to research, make the first commit in skills, decide the private-repo naming boundary | cf-lab | 1-2 | 2 | 13.3 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated |  |  | T-0020 |
| T-0050 | P3 | Development-tooling MCPs: admission review of the GitHub MCP server (repo-scoped token) and Microsoft Learn Docs MCP for the hq workflow | cf-lab | 2-3 | 3 | 12 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0069 | P3 | Provider for the UKRI Gateway to Research API in cf-evidence-loop | cf-skills | 2-3 | 3 | 12 | no | model: claude-sonnet-5-5 | 10/05/2026 | elevated |  |  |  |
| T-0091 | P3 | Depth probe on realistic text with a second fact at a different depth | cf-lab | 2-4 | 3 | 10 | no | model: claude-sonnet-5-5 | 10/06/2026 | routine | low | local | T-0086 |
| T-0044 | P3 | Paper-trail layer: Unpaywall and Semantic Scholar providers | cf-skills | 3-5 | 3 | 7.5 | no | model: claude-fable-5-1 | 10/04/2026 | elevated |  |  |  |
| T-0021 | P3 | Claim-mapping fixture for model-onboarding from extracted ECFSPR indicators (design only until T-0008) | cf-lab | 3-5 | 3 | 7.5 | no | model: claude-fable-5-1 | 10/04/2026 | routine |  |  | T-0008, T-0010 |
| T-0055 | P3 | EMA medicines provider: read the downloaded JSON report as evidence records (marketing authorisation date, status) | cf-skills | 3-6 | 3 | 6.7 | no | model: claude-sonnet-5-5 | 10/04/2026 | elevated |  |  |  |
| T-0053 | P3 | Data Commons provider in cf-evidence-loop for population denominators (if the admission is accepted) | cf-skills | 3-6 | 3 | 6.7 | no | model: claude-sonnet-5-5 | 10/04/2026 | full |  |  | T-0048 |
| T-0087 | P3 | Faster site and package test suites with the same assertions | cf-research | 3-6 | 2 | 4.4 | no | model: claude-sonnet-5-5 | 10/06/2026 | routine | medium |  |  |
| T-0036 | P3 | Admission run for the two installed local models (Gemma 4 31B, Laguna XS 2.1) as reviewers | cf-lab | 4-8 | 2 | 3.3 | no | model: claude-sonnet-5-5 | 10/04/2026 | full |  |  |  |

## Detail

### T-0001 Replace hq LICENSE.md with a named OSI license; add a LICENSE to research, .ai, skills

- **Why / ROI rationale:** Current LICENSE.md says 'released under an open source license' without naming one and has a placeholder contact. Without a named license, default copyright applies and nobody can legally reuse the code the site calls open source. Skills already use CC0-1.0; code needs MIT or Apache-2.0. *(confidence: high)*
- **Acceptance:** Each of the four repos has a LICENSE file whose first line names a recognised license (MIT, Apache-2.0, CC0-1.0, or CC-BY-4.0 for notes); hq README and website link to it.
- **Evidence:** hq/LICENSE.md read 2026-10-04; research, .ai, skills have no LICENSE file
- **Notes:** Prepared 2026-10-04 on the release branches (not yet merged): hq LICENSE.md is MIT; research LICENSE is CC BY 4.0 with tools/LICENSE MIT; skills LICENSE is CC0 1.0; texts for CC BY and CC0 are the official legal code from creativecommons.org. A human sets done after the PRs merge and the licenses show on GitHub. The website repo was not covered.

### T-0004 Gate .github/loop-orchestrator/loop.py with a hard failure

- **Why / ROI rationale:** AGENTS.md documents it as reporting success unconditionally. A verifier that always passes is worse than none. *(confidence: high)*
- **Acceptance:** python .github/loop-orchestrator/loop.py exits non-zero; AGENTS.md mention updated.
- **Evidence:** hq/AGENTS.md section 'AI loop and delegation'
- **Notes:** Applied 2026-10-04 by claude-sonnet-5-5: .github/loop-orchestrator/loop.py exits non-zero on start with 'not implemented'; the AGENTS.md mention and the loop README status note were updated. A human sets done after seeing the acceptance output.

### T-0002 Fix YouTube About text: remove 'accelerate the cure', add research-not-advice and independence lines

- **Why / ROI rationale:** The only public text the channel has contradicts hq/README.md ('we do not claim a cure'). Cheapest high-visibility fix available. *(confidence: high)*
- **Acceptance:** About page text matches research/proposals/2026-10-04-youtube-about.md or a human-edited variant; contains 'not medical advice' and 'not affiliated'.
- **Evidence:** research/proposals/2026-10-04-youtube-about.md

### T-0006 Send permissions emails to CFF registry contact and ECFSPR

- **Why / ROI rationale:** Decides by day 10 whether extracted values may be redistributed or only the script ships. Draft exists. *(confidence: medium)*
- **Acceptance:** Emails sent; dates and replies recorded in landscape/registry-data-access.md.
- **Evidence:** research/landscape/registry-data-access.md 'Email draft'
- **Notes:** Human task.

### T-0005 Download CFF Patient Registry PDFs by hand into research/sources/downloads

- **Why / ROI rationale:** Unblocks the US half of cf-registry-extract. Human-only step by policy. *(confidence: medium)*
- **Acceptance:** fetch_sources.py --verify reports the CFF files present with recorded SHA-256; Technical Supplement included.
- **Evidence:** research/landscape/registry-data-access.md; research/sources/catalog.yaml (access: manual)
- **Notes:** Human task. Run fetch_sources.py --manual for the list.

### T-0037 Add Retraction Watch (via Crossref) retraction check to the catalog and to the claim-check harness design

- **Why / ROI rationale:** Crossref is already permitted and reachable; Retraction Watch data has been open through it since 2023. Every DOI the lab cites gets a mechanical retraction/correction lookup. Highest credibility gain per hour available. *(confidence: high)*
- **Acceptance:** catalog.yaml has a retraction-watch entry with access: api; a script takes a DOI list and returns retraction/correction status for each; the 13 DOIs in the scoping memo are checked and the output committed.
- **Evidence:** research/proposals/2026-10-04-researcher-sources.md layer 2
- **Notes:** Built 2026-10-04 in skills/cf-evidence-loop (moved from research/tools/evidence 2026-10-04 at the user's request for a portable skill) (providers crossref, openfda); live-checked and unit-tested. Awaiting human review of the acceptance output before done. 2026-10-04 later: network-conduct rules R1-R9 enforced in the client with 37 tests; catalogs now carry terms_url/max_rps for every API source.

### T-0045 Decide and document the install/link mechanism for using skills/cf-evidence-loop from hq without copying it

- **Why / ROI rationale:** AGENTS.md requires the mechanism be decided before a skill is used across repos and forbids duplicate copies. Without it, agents in hq cannot discover the skill. *(confidence: high)*
- **Acceptance:** AGENTS.md names the mechanism (submodule, symlink, path convention, or install script) and an agent in hq can run the skill's live retraction check following only AGENTS.md.
- **Evidence:** hq/AGENTS.md 'Organization and publication'; research/proposals/2026-10-04-publish-packet.md step C4

### T-0022 Adopt the task board: every new task carries created_by, evidence, and an ROI estimate; render BOARD.md in CI or pre-commit

- **Why / ROI rationale:** Without provenance, model-generated tasks and human decisions become indistinguishable within a week. The board is only useful if it is the single list. *(confidence: medium)*
- **Acceptance:** hq/tasks/README.md adopted; render-board.ps1 runs clean; no task list exists elsewhere in hq.
- **Evidence:** hq/tasks/ created 2026-10-04
- **Notes:** Adopted 2026-10-04: tasks/README.md, board.json and render-board.ps1 are in place and the manual 'render-board.ps1 -Check' step is noted in copilot-instructions.md because the repo has no pre-commit hook or CI. A human sets done after seeing the acceptance output.

### T-0072 Decision: cloud-model use on reports with unread terms; permission requests to the CFF Registry and the CF Trust; the CC0 label on skills that carry quotations

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A human decides each of three points and the review's rules are adjusted to match: (1) whether sources with unread terms go only to local models, and the account's data-retention and training settings are confirmed; (2) whether to ask the Foundation and the Trust for permission to quote; (3) the licence wording for skills with quotations.
- **Evidence:** 2026-10-05: proposals/2026-10-05-compliance-review.md. The UK report asks for permission before reproduction in publications, the CFF has a figure-permissions notice, the Canadian and ECFSPR terms are unread, and the CC0 header on the ECFSPR skill sits over third-party quotations.
- **Notes:** Proposed by a model. Policy and law, not code. A human decides, and a lawyer's view is worth having if the lab ever needs certainty.

### T-0003 Apply the HQ skill-update proposal (security-browsing, cf-research-context, ai-loop-council, model-onboarding)

- **Why / ROI rationale:** Turns tested access findings into agent policy so no future agent re-derives or evades them. Packet is already written. *(confidence: medium)*
- **Acceptance:** All acceptance checks in research/proposals/2026-10-04-implementation-packet.md pass with command output.
- **Evidence:** research/proposals/2026-10-04-hq-skill-updates.md
- **Notes:** Applied 2026-10-04 by claude-sonnet-5-5 (review tier elevated) from research/proposals/2026-10-04-hq-skill-updates.md. All 21 inserted proposal lines were checked verbatim by script; frontmatter validated with tasks/check-skill-frontmatter.py; an independent frontier-model review of the research side found no quotation false. A human sets done after seeing the acceptance output.

### T-0092 Re-run the SEO skill release review after the SEO008 fix

- **Why / ROI rationale:** Estimate: T-0083's release review would otherwise approve a script with a known, reproduced defect in its checker. This task only re-checks after the fix and records it; T-0083 stays the release task. *(confidence: medium)*
- **Acceptance:** The SEO008 fix is merged in the cf-skills copy of the checker; the 4 new tests for an absolute canonical with no base pass together with the existing suite; the reproduction (index.html, canonical http://example.com/foo, no base, --json) now reports SEO008; the review note for the release records the defect, who found it (the local reviewer, 3 of 8 runs) and the fix; a person confirms before T-0083 closes.
- **Evidence:** scratch/qwen-local/reviewer-eval.md, 'An 18th defect': with no --base-url and an absolute canonical the SEO008 path comparison is skipped (spec section 4); reproduced on 2026-10-06 in the original A3 and in shipped/seo_audit.py, while reference/seo_audit.py reports SEO008. Spec text in scratch/seo-skill/spec.md SEO008 row; fix notes in scratch/seo-skill/seo008-fix.md.
- **Notes:** Does not duplicate T-0083 (the release review itself); it is the re-run after the fix. Human step: the merge and the publish decision stay with the maintainer.

### T-0008 Freeze the cf-registry-extract row schema (incl. value_low/value_high or median_iqr, source_sha256)

- **Why / ROI rationale:** Everything downstream (extraction, harness, fixture) encodes the schema; changing it later multiplies cost. *(confidence: medium)*
- **Acceptance:** tools/registry-extract/SCHEMA.md exists; a JSON Schema validates a 20-row hand-extracted gold sample from ECFSPR 2022 p.8.
- **Evidence:** cf-first-project-scoping-memo.md (private session document, not in the repo) section 4 and section 8

### T-0081 Outside scientific review and a CF-community read of the CFTR structure page before it goes anywhere public

- **Why / ROI rationale:** Estimate: the page is the lab's most visible scientific claim set; one wrong sentence costs more trust than the page earns. *(confidence: medium)*
- **Acceptance:** A blind read by a model of a different family against the checked-facts packet (flags confirmed on the source, never by vote); the three statements marked 'to confirm' in the packet (nucleotide-binding wording, 'most common variant', Trikafta wording) read on their sources; a person with CF or a carer reads the page and their changes are made; the maintainer decides to publish. Nothing is deployed before all four.
- **Evidence:** The page's captions were checked by the controlling agent against the structure files and UniProt, and a storyboard came from Fable; no other model family and no person has read the final wording.
- **Notes:** Human steps: the community read, the decision to publish. The page says 'Draft, in review' until then.

### T-0007 Add [verified]/[unverified]/[hypothesis] labels to cystic-fibrosis.md, cff-goals.md, landscape/cf-repositories.md

- **Why / ROI rationale:** README requires labels on every checkable claim; three of five notes have zero labels. The convention is only credible if applied. *(confidence: medium)*
- **Acceptance:** grep count of claim labels > 0 in each file; every [verified] has an inline URL and date.
- **Evidence:** grep of research/*.md on 2026-10-04: labels={verified:0, unverified:0} in the three files

### T-0080 Website revamp and a better organization across the lab, with Fable's guidance

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A written information architecture (sitemap, page inventory, what moves, what is retired) from a council (Fable, local Qwen, controlling agent) that the maintainer approves; verified scientific copy preserved word for word; nothing is deployed until the maintainer approves; the implementation is a separate task in the private repo. Standing condition from the maintainer (2026-10-05): the site must honour the CF community. Dignity and not drama; no pity, hype or promise of a cure anywhere, microcopy included; playful effects stay off the CF pages; calm, optional motion and short reading paths for tired readers; the donate link optional and plain; a person with CF or a carer reviews the pages before launch (see T-0011), and no page claims community review until that happens.
- **Evidence:** 2026-10-05: the maintainer said so much has been built that the website needs a revamp and a better general organization, with Fable's guidance. The site is the private .ai repo.
- **Notes:** Requested by the maintainer in this session on 2026-10-05, so it is ready. The site and its deployment details stay out of public repos. 2026-10-05: the maintainer chose to keep the original dark cyberpunk look and the 65-rose field (the first light 'notebook' attempt was dropped; the old files are kept in legacy/), and gave the builder creative licence inside the safety rails. The new structure and content decisions stand. 2026-10-05 later: a seven-page structure, the original style and the 65-rose field are being rebuilt by Fable in the private repo; the site tests use headless Chromium and the maintainer asked for Playwright tests after the build (the venv exists). The live site still runs the old page. 2026-10-05 built and verified in the private repo, uncommitted: seven pages plus 404 in the original cyberpunk style with the 65-rose field, a command palette, a sourced 'Who is still waiting' section and a time-free design; tests/test_site.py (32 checks) and tests/test_site_playwright.py (20 checks and 4 detectors that must fail) pass; generated evidence blocks must be re-run after any ledger or catalogue change. Open: a phone's first screen is mostly banner and header; the verified note on the 65 roses says 'at the top of this page' while the field drifts behind the whole page (as in the original); the word 'Donate' on the banner button; a person with CF or a carer has not reviewed it.

### T-0078 Improve the webgl-threejs-graphics and svg-animation skills with researched, checkable practice

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** Each skill gains researched sections with sources (accessibility: text alternative, keyboard, pause, reduced motion; performance; no CDN; context loss handling for WebGL), a runnable example that a Playwright check passes, and no copied third-party text (check_source_overlap.py --quotes-only passes); any third-party skill used is read line by line first and attributed.
- **Evidence:** 2026-10-05: the maintainer asked to improve the WebGL and SVG skills and to do research if needed. The public-skills survey found no Anthropic skill for three.js, WebGL or scientific figures; third-party three.js skills exist but were not read.
- **Notes:** Requested by the maintainer in this session on 2026-10-05, so it is ready. 2026-10-05 progress: webgl-threejs-graphics/scripts/check-webgl.py (headless Chromium, software renderer, no network, probe element, console errors, non-blank screenshot) with 14 mutants caught. Measured: headless Chromium has no WebGL2 with --disable-gpu alone, needs --use-angle=swiftshader --enable-unsafe-swiftshader, and a fresh --user-data-dir hangs it. Playwright for Python 1.63.0 is installed in an isolated venv outside the repos and drives the Chromium already on disk. Sourced skill text is waiting on a research pass.

### T-0083 Release review of the site-seo-review skill

- **Why / ROI rationale:** Estimate: a reusable honest SEO review is useful to other small and health-related sites, but a public skill must be read by a person before it ships. *(confidence: medium)*
- **Acceptance:** A person reads SKILL.md, references and the checker; check_repo.py passes; the checker passes its tests under Python 3.9 and 3.13 on Windows and Linux; the licence is confirmed by the maintainer; a different model family reads the health-site section for overclaims.
- **Evidence:** scratch/seo-skill: spec, 72 tests, a reference solution passing 72 of 72 and 8 of 8 planted faults rejected; the checker script was written by the local worker (see the bare-versus-card record in scratch/site-updates/qwen-results.md).
- **Notes:** Human steps: licence and publish decision.

### T-0082 Try each agent's install path from the skills hub in a real client

- **Why / ROI rationale:** Estimate: wrong paths in a public install guide send people to dead ends, and the guide's value is that it is right. *(confidence: medium)*
- **Acceptance:** For each agent the maintainer can run (Claude Code, Copilot, Codex, Gemini CLI, Cursor at least): the documented install step and the pasted prompt are run on a throwaway project; the result (folder written, skill listed, one call made) is recorded in docs/install.md with the agent version; every row that fails is corrected or relabelled; `python scripts/check_repo.py` passes.
- **Evidence:** cf-skills/docs/install.md and docs/prompts.md rest on vendor pages read on 2026-10-05, partly through a summarising tool; nothing was run in a real client (research file agents-research.md, 'Things I could not verify').
- **Notes:** Human steps: access to each client and its account. The prompts have a safe-fetch clause; check an agent actually asks first.

### T-0060 Refresh the private .ai website for the first release: new repo names, evidence loop, setup, claim fixes

- **Why / ROI rationale:** Estimate: the website is the public face of three public repos; stale names and unresolved claims (T-0014, T-0015, T-0018) are the first thing a visitor or reviewer meets. *(confidence: low)*
- **Acceptance:** In the site's built output a grep finds links to github.com/senseiewok/cf-lab, cf-research and cf-skills and none to the old names (senseiewok/lab, /research, /skills); the evidence-loop section from T-0041 renders; the tagline, the Copilot scheduling claim and the not-affiliated-with-CFF line (T-0014, T-0015, T-0018) are each resolved or recorded as declined; a Playwright run (read-only, with route, viewport and source revision recorded) confirms the page renders and the 65 rose motifs still count 65 (T-0016). Paste the command output into the task notes.
- **Evidence:** The maintainer said on 2026-10-04 that the website is outdated; the GitHub organisation page shows the private .ai repo last updated two days before the three public repos were renamed. Open website tasks already exist (T-0002, T-0014 to T-0018, T-0033, T-0041) and cf-research/proposals has 2026-10-04-website-review.md and 2026-10-04-evidence-loop-site-section.md. The site was not opened for this task (it is private and was not requested).
- **Notes:** Proposed by a model; only a human moves it to ready. The .ai repo is private: a human opens it, or says explicitly that an agent may. Do not copy site source or deploy details into any public repo or note.

### T-0077 Interactive 3D CFTR channel animation: normal gating and chloride flow versus F508del misfolding

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** One standalone page with no CDN and no network call: a schematic CFTR in a membrane, a normal state (phosphorylation and ATP gating, chloride passing) and an F508del state (misfolded protein held back so fewer channels reach the surface), a toggle, keyboard control, a pause control, reduced-motion respected, a text alternative and a caption labelled 'schematic, not a structure'; every scientific caption has a claim record with a primary source and its limits; a Playwright run proves load, toggle and no console errors; no medical advice or treatment claim.
- **Evidence:** 2026-10-05: the maintainer asked for an interactive 3D model or animation of the CFTR protein in a cell membrane, showing how a normal channel passes chloride and how a mutated channel such as F508del misfolds or is trapped.
- **Notes:** Requested by the maintainer in this session on 2026-10-05, so it is ready. Scientific claims need the full review tier and the cf-research-context rules. Decide first whether to write raw WebGL2 or vendor three.js (a new dependency to flag). 2026-10-05: the site builder found that the only verified statements in the repos (cf-research/cystic-fibrosis.md) support no caption about chloride, folding or the cell surface, so the CFTR page is a labelled planned-not-built placeholder. The schematic needs a sourced scientific packet first (primary sources for each caption, then the full review tier). 2026-10-05 later: the maintainer said the goal is a 3D model that matters to the CF community. The page was rebuilt around four real published structures instead of a hand-drawn schematic (RCSB PDB 6MSM, 5UAK, 8EIQ, 8EJ1, CC0; UniProt P13569): backbone traces, coloured by part, residue 508 marked and shown absent in the two F508del structures, unmodelled stretches shown as dashed bridges, a walk-along-the-chain control, an overlay with computed distances. Captions use only facts checked against the files (a Fable storyboard was cut where the data did not support it). Built, tested and mutation-proven in the private site repo (tests/test_cftr_viewer.py, test_cftr_superpose.py). NOT done: the cell-scale 'misfolding and the surface' drawing (no checked source yet), an outside scientific review of the captions, a read by a person with CF or a carer, and anything public. Acceptance above is for the earlier schematic idea; the structure viewer replaces its first half and the misfolding drawing stays open.

### T-0009 ECFSPR extraction pipeline v0.1 (5 report years, ~15 indicators)

- **Why / ROI rationale:** The core deliverable. ECFSPR is fully fetchable, so this is unblocked today. *(confidence: medium)*
- **Acceptance:** >=99% extraction accuracy on a 100-cell random audit (Wilson 95% CI reported); 100% rows carry url+page; disagreement log committed.
- **Evidence:** cf-first-project-scoping-memo.md (private session document, not in the repo) sections 5-6

### T-0018 Add one explicit 'not affiliated with the Cystic Fibrosis Foundation' line near the site's donate link

- **Why / ROI rationale:** Site says 'independent' three times but never 'not affiliated'. With donate and CFF-history prominence, one explicit line closes the implied-affiliation gap cf-research-context names. *(confidence: high)*
- **Acceptance:** The phrase 'not affiliated' appears once on the page, adjacent to the donation call.
- **Evidence:** handoff site_text.txt (private session artifact, not in the repo): zero matches for 'affiliat'

### T-0020 Human review of the scope-triage table in cf-projects/CF-Project-Ideas.md

- **Why / ROI rationale:** A model flagged roughly half the ideas as conflicting with cf-research-context. That judgement needs a human to confirm or overrule before it steers anything. *(confidence: medium)*
- **Acceptance:** Each triage row has a human initial and date, or is edited.
- **Evidence:** hq/cf-projects/CF-Project-Ideas.md 'Scope triage' section
- **Notes:** Human task.

### T-0058 Run setup.sh and test-setup.py on a real Mac (and one Linux machine) and record the result

- **Why / ROI rationale:** Estimate: macOS support is a claim until a real run; a lint is not a Mac. *(confidence: high)*
- **Acceptance:** On macOS: python3 .claude/skills/lab-versioning/scripts/test-setup.py prints 'sh: all checks passed' and VERIFIED (cmd is skipped), then ./setup.sh in a temp folder clones cf-skills and cf-research and creates cf-lab-files (memory, scratch, README; setup generates no workspace file); paste the output into this task's notes. Repeat on one Linux machine. Any failure becomes its own task with the failing output.
- **Evidence:** setup.sh was written by the local worker and verified only under dash and bash from Git for Windows with a stub git, plus a lint for constructs old macOS shells reject. No macOS or Linux machine ran it.
- **Notes:** Needs a human with a Mac. Proposed by a model. Until it is done, README and AGENTS.md should not say macOS is supported beyond 'written to be portable and tested under dash and bash'. A macos-latest GitHub Actions runner (T-0061) would run test-setup.py on a real macOS shell without owning a Mac; that run's output would satisfy this task for macOS.

### T-0014 Decide the 'CF - until there's a cure' site tagline against lab-voice

- **Why / ROI rationale:** Not a claim the lab cures anything, but lab-voice says 'hope without a forecast'. A human call; either keep deliberately or replace. *(confidence: low)*
- **Acceptance:** Decision recorded in .ai/README.md; text unchanged or replaced accordingly.
- **Evidence:** handoff site_text.txt (private session artifact, not in the repo) line 'CF - until there's a cure'; hq/.claude/skills/lab-voice/SKILL.md

### T-0015 Reconcile the website's 'M365 Copilot drives the lab's task scheduling' claim with reality

- **Why / ROI rationale:** hq had no task board until today. Either the board becomes what the sentence describes, or the sentence goes. Honesty about tooling is part of the lab's pitch. *(confidence: high)*
- **Acceptance:** Sentence either removed or links to hq/tasks/BOARD.md with a true description of how tasks are scheduled.
- **Evidence:** handoff site_text.txt (private session artifact, not in the repo) 'The command center' section; hq/tasks/ created 2026-10-04

### T-0071 Put the ClinGen and gnomAD catalog conflicts into the BioMCP admission test

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** T-0042's acceptance text lists the wrapper's ClinGen and gnomAD tools as blocked until the catalog entries change, and says the wrapper's own requests must follow NETWORK-RULES R1-R9.
- **Evidence:** 2026-10-05: the survey found that BioMCP, OpenCRAVAT and a gnomAD MCP call ClinGen or gnomAD, while the catalog records clingen as forbidden (robots.txt refuses other agents) and gnomad as manual (API paths disallowed).
- **Notes:** Proposed by a model. A wrapper is not a way around a catalog entry.

### T-0013 Read CFTR2 terms of use; set catalog access accordingly

- **Why / ROI rationale:** Currently 'manual, terms not read'. One reading settles whether linking-only or fetch is allowed. *(confidence: medium)*
- **Route:** cloud - A web read and a verbatim-quote check need a networked controller; the local worker has no tools and was not given untrusted page text.
- **Acceptance:** catalog.yaml cftr2 entry has robots/terms fields filled, a check date, and claim_label: verified.
- **Evidence:** research/sources/catalog.yaml entry cftr2
- **Notes:** Human reads; agent records. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-research 8704050 and cf-skills e821f8e: cftr2 entry now access manual, robots allow (checked 2026-10-05, Crawl-delay 10 honoured), claim_label verified, terms_url set; three sentences quoted verbatim and complete (check-quote-completeness 3 of 3). Acceptance output: 'fields ok: 27 keys documented'; sync_skill_catalog --check 'in sync'; fetch_sources.py --manual lists cftr2.

### T-0038 Add openFDA drug label and Drugs@FDA approval endpoints to the catalog; resolve approval-year claims from them

- **Why / ROI rationale:** Allowlisted, structured, and resolves every 'approved in <year>' sentence (T-0023 included) with a dated record instead of a history page. *(confidence: medium)*
- **Acceptance:** catalog.yaml has openfda entries with access: api; the three approval years on the website each resolve to a Drugs@FDA record with the lookup output committed.
- **Evidence:** research/proposals/2026-10-04-researcher-sources.md layer 4
- **Notes:** Built 2026-10-04 in skills/cf-evidence-loop (moved from research/tools/evidence 2026-10-04 at the user's request for a portable skill) (providers crossref, openfda); live-checked and unit-tested. Awaiting human review of the acceptance output before done. 2026-10-04 later: network-conduct rules R1-R9 enforced in the client with 37 tests; catalogs now carry terms_url/max_rps for every API source.

### T-0033 Send standard security response headers on the live website (HSTS, X-Content-Type-Options, Referrer-Policy, frame and content restrictions)

- **Why / ROI rationale:** A static information site with no forms or logins has a small attack surface, so the benefit is modest, but the security baseline lists security headers and these are cheap, reversible configuration. A strict Content-Security-Policy interacts with the Google Fonts and the host's injected snippet, so it needs testing rather than copy-paste. *(confidence: medium)*
- **Acceptance:** A HEAD request to the live site shows Strict-Transport-Security, X-Content-Type-Options, Referrer-Policy and a frame restriction; if a Content-Security-Policy is added it is tested in a browser (Playwright check of the rendered page and console, no blocked resources the page needs); the page still renders; the change is dry-run or explained before any deploy, and no credential is read or printed.
- **Evidence:** One plain GET of the live site's raw HTML and response headers on 2026-10-04 (the page is public; the version online is older than the repo source). Response headers listed no Strict-Transport-Security, Content-Security-Policy, X-Content-Type-Options, X-Frame-Options or Referrer-Policy. The page also loads Google Fonts and has an unused third-party image preconnect, and carries a hosting-provider traffic snippet (see T-0017).
- **Notes:** Deployment-adjacent, so full review tier: a human runs the deploy. Header rules live in the host configuration, which is private; do not copy host details or credentials into any public file. Self-hosting the fonts (T-0017) would let a strict policy drop the third-party font hosts.

### T-0017 Self-host the two web fonts; remove the unused images.unsplash.com preconnect

- **Why / ROI rationale:** Google Fonts and the Unsplash preconnect send every visitor's IP to third parties. For a CF-community site that is an avoidable privacy leak; no Unsplash image is actually used. *(confidence: medium)*
- **Acceptance:** No request to fonts.googleapis.com, fonts.gstatic.com, or images.unsplash.com in a Playwright network log; fonts load from /fonts/.
- **Evidence:** .ai/src/index.html link/preconnect tags; grep found no unsplash URL in CSS or HTML

### T-0016 Verify exactly 65 rose motifs render, and that reduced-motion is honoured, with a Playwright count

- **Why / ROI rationale:** README and cf-research-context promise exactly 65 and say to count rendered instances. The field is JS-generated (empty div in source), so only a browser can verify. *(confidence: medium)*
- **Acceptance:** Playwright test asserts document.querySelectorAll('#rose-field > *').length === 65 at two viewports and that animation is disabled under prefers-reduced-motion; test committed under .ai/tests/.
- **Evidence:** .ai/src/index.html: <div class="rose-field" id="rose-field"></div> is empty in source
- **Notes:** Checked 2026-10-04 on the repo source (not the deployed page) served from a loopback static server, with Playwright 1.63.0 and Chromium, at 390x844 and 1280x800, each with and without prefers-reduced-motion. Result in all four: 65 elements match '#rose-field .rose' (65 in the page in total), 65 visible, no console errors, no horizontal overflow. With reduced motion the computed animation is 'none'; without it, 'rose-drift 18s'. This counts the rendered SVG nodes only; it does not judge how they look. The live site is an older version with no rose field. A human sets done.

### T-0062 A generated manual-downloads page with links, file names and a prompt to run when the files are saved

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Route:** local - A fixed format with a verifier of fixtures; accepted on attempt 1.
- **Acceptance:** python tools/sources/test_make_manual_downloads.py prints VERIFIED; python tools/sources/make_manual_downloads.py --check exits 0; sources/manual-downloads.md lists every manual, request and forbidden entry of the catalog and no fetch or api entry.
- **Evidence:** 2026-10-05: the maintainer asked for a markdown or HTML page with links to every manual download and a prompt to run when they are done; 11 sources are manual and the instructions were only in fetch_sources.py --manual output.
- **Notes:** Taken 2026-10-05 on the maintainer's instruction (the evening requests: assess delegation, security and queueing, a manual-download page, more sources, better ASCII art). Work lands on the open PR branches, nothing pushed. A human sets done after seeing the acceptance output. Done in cf-research f68f403 and regenerated with each catalog change (dd0d64e, 1b09df8). The local worker drafted the generator on its first fast attempt (15 s); reading found a dead helper; a 12-mutant proof of the test passes.

### T-0074 Run check_source_overlap.py in the review gate for notes built from reports

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** run-gate.ps1 (or the documented pre-commit step) runs tools/sources/check_source_overlap.py on staged markdown and yaml under cf-research when sources/downloads exists, and skips with a visible message when it does not; a test shows a 30-word copy fails the gate. The same step also runs check_source_overlap.py --quotes-only and, for a note with a stated evidence file, check_numbers.py.
- **Evidence:** 2026-10-05: the checker found a 26-word run copied from an ECFSPR report in a published skill and three over-long quotations in catalog notes.
- **Notes:** Proposed by a model. The downloads folder is git-ignored, so the check cannot run in CI; it is a local step.

### T-0065 Delegation: a sequential batch runner and a verifier-suspect hint

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Route:** cloud - PowerShell driver changes; the worker has not been reliable on state-heavy PowerShell.
- **Acceptance:** pwsh -File .claude/skills/ai-loop-council/scripts/test-delegate-batch.ps1 prints 19/19 passed; test-delegate.ps1 prints 42/42 passed; mutation proofs of 15 and 5 mutants are rejected.
- **Evidence:** 2026-10-05: the maintainer asked whether a better queuing mechanism is needed. Ollama already queues concurrent requests and the call timeout includes the wait, so no lock; but unattended runs and three verifier-side failures in two days showed two gaps.
- **Notes:** Taken 2026-10-05 on the maintainer's instruction (the evening requests: assess delegation, security and queueing, a manual-download page, more sources, better ASCII art). Work lands on the open PR branches, nothing pushed. A human sets done after seeing the acceptance output. Done in cf-lab 4faf09e.

### T-0067 Decision: treat robots.txt groups that name AI agents as applying to our fetch sources

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A human decides. If yes: robots_allows also checks a fixed list of AI-agent tokens (Claude, ClaudeBot, anthropic-ai, GPTBot, ChatGPT-User, CCBot, Google-Extended, PerplexityBot) and refuses when any of them is disallowed; tests fail before and pass after; NETWORK-RULES R3 says so.
- **Evidence:** 2026-10-05: Cochrane's robots.txt has a group 'User-agent: Claude' with 'Disallow: /'; the evidence package matches only its own product token, so it would fetch a Cochrane document if one were catalogued as fetch. I applied the refusal by hand.
- **Notes:** Proposed by a model. This is policy, not code: a pipeline driven by an AI agent that presents a project user agent could be read as evading a site's wish to exclude AI agents. A human decides. Decided by the maintainer on 2026-10-05 ('do the right thing on robots; safe web practices is a priority because skills will fork from it'). Done in the working trees, not yet committed: AI_AGENT_TOKENS and the new robots_allows rule in cf-skills (30 tests, 7 mutants caught), NETWORK-RULES R3 and a forking section, security-browsing items 2 and 7, and cf-research fetch_sources.py now uses the same rule and conduct with --audit-robots (all 10 fetch entries allowed).

### T-0028 Add a reviewed lesson to ai-loop-council: a verbatim-quote check does not verify inferences, and a truncated quote can produce a false 'differs' claim

- **Why / ROI rationale:** The ai-loop-council extraction variant already says the worker must not produce numbers and the verifier checks ids and spans. This run shows a second failure mode it does not cover: inference from a partial quote. A narrowly scoped addition plus a frozen check would stop the same false 'difference between years' claim reaching a skill. Low confidence because it rests on one run. *(confidence: low)*
- **Route:** local - Passed only on a thinking attempt that finished under the raised 16,384-token cap, after two failed fast attempts; one sample, so not a ranking.
- **Acceptance:** A short, reviewed addition to the ai-loop-council 'value extraction from a document' variant (or a sibling variant for drafting from verified quotes) stating: supply complete sentences, never truncated prefixes, for any comparison; claims of difference, absence or 'only' need the full sentence from each side checked by a human or a deterministic comparison; a passing quote check does not clear an inference. A frozen fixture reproduces the failure (truncated-quote packet) and a deterministic check or review step is shown to catch it. Untested elements are labelled as proposals.
- **Evidence:** research/proposals/2026-10-04-ecfspr-report-reading-provenance.md. Two independent local drafts both stated that the 2024 ECFSPR definition of chronic Pseudomonas infection 'returns to only the modified Leeds criteria' and that 2020 mentioned only those criteria. The full sentences in all five reports include the antibody criterion. The packet had supplied a truncated prefix of one sentence as a verified quote. Mechanical checks (quote verbatim on page, citation key exists, numbers appear in the material) all passed; reading against the full sentences caught it. A later blind read by a frontier model caught three more overbroad statements (an unnumbered contents entry, a missed third footnote, a misplaced quote) that the same mechanical checks had passed. One small run, one registry, one model.
- **Notes:** Agent-instruction change; a human approves every .claude/ diff. Do not generalise beyond what the one run showed. Update 2026-10-04: the lesson now has ledger rows E12, E13, E14, E21 and E22 (research/ledger/2026-10-04-first-session.md) and reproducing fixtures (the empty-fence and trailing-comma cases in the loop scripts' tests). Per the design's promotion rule it can land once a human sets it ready; claim-checker work is T-0034. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-lab 6dcbe32: check-quote-completeness.py with 14 synthetic cases, self-test and outside-in test pass; the skill lesson and an evidence paragraph are in ai-loop-council SKILL.md. The delegate.ps1 loop rewrite has 37 of 37 checks.

### T-0093 Post the welcome note in the cf-lab GitHub Discussions

- **Why / ROI rationale:** Estimate: a visitor who follows the README link lands on an empty page; a short, plain welcome with one clear invitation costs little and sets the tone before anyone else posts. *(confidence: medium)*
- **Acceptance:** A human writes or approves the text under the lab-voice skill (a letter: warm, one invitation, no invented biography, no clinical promise, no claim to speak for a community) and posts it. Then: gh api graphql -f query='{repository(owner:"senseiewok",name:"cf-lab"){discussions(first:5){totalCount nodes{title url}}}}' reports totalCount of 1 or more and the note's URL; the README's Discussions link opens a page that shows it.
- **Evidence:** README.md, 'Thanks to the tools' table: the GitHub row links https://github.com/senseiewok/cf-lab/discussions as a place the lab uses. Observed on 2026-10-06 with the GitHub API: the repository reports has_discussions true and the GraphQL discussions totalCount is 0, so the linked page is empty.
- **Notes:** Human step: the wording and the posting are the maintainer's. Proposed by a model; a draft may be offered, but a model does not post it. Community-facing text, so the lab-voice review applies.

### T-0025 Fix three fetch_sources.py defects: failed downloads exit 0, --dest can write an absolute path into the tracked manifest, --verify cannot check manually saved files

- **Why / ROI rationale:** The fetcher is the lab's only automated route to source documents. A silent exit 0 on a failed download lets a script or CI believe a fetch succeeded, and an absolute path in a tracked manifest is the kind of machine detail the repo rules keep out. Small, local fixes. *(confidence: medium)*
- **Route:** local - Already implemented before this session; verified rather than rebuilt.
- **Acceptance:** With a failing URL (local test double, no real host) the fetcher exits non-zero; with --dest outside the repo the manifest holds no absolute path; after saving a manual file, a documented command records its hash and --verify then reports it; tools/sources/README.md exit codes match the code. No request to cff.org, databases.lovd.nl or cftr2.org is made.
- **Evidence:** research/tools/sources/fetch_sources.py read 2026-10-04: download errors are caught and the run returns 0 (tools/sources/README.md documents 0 as success); build_manifest writes str(dest) when --dest is outside the repo and the manifest is tracked; the --manual footer says to re-run --verify but verify() skips records that have no sha256, and a manual file has none until a plain run rewrites the manifest.
- **Notes:** Found while preparing the 2026-10-04 PRs. Not fixed there, because the packet says apply the proposals and do not improve other code. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Verified 2026-10-05: the three defects were already fixed (bb571f1); 16 tests pass and the README exit codes match the code.

### T-0024 Board enhancement: add complexity, recommended_route (local, cloud or frontier) and route_rationale to tasks

- **Why / ROI rationale:** The board will be used often, and a reader choosing the next task needs to see cost of attention and likely model spend beside ROI. Three optional fields plus one renderer column and a validation rule; small, but it changes a shared schema, so it is proposed rather than just done. *(confidence: medium)*
- **Route:** cloud - Controller-written validation in render-board.ps1 with a mutation proof.
- **Acceptance:** board.json tasks may carry complexity (low, medium, high), recommended_route (local, cloud, frontier) and route_rationale (non-empty when a route is set); render-board.ps1 rejects other values with exit 2, shows complexity and route columns, and -Check exits 0 after rendering; tasks/README.md documents the three fields; existing task statuses are unchanged.
- **Evidence:** Human request 2026-10-04: a prioritized, ROI-ranked board that also shows complexity and the model power a task needs. Copilot session proposed complexity, recommended_route and route_rationale; the human then settled on three tiers, local, cloud and frontier, with planners being frontier models. tasks/render-board.ps1 and tasks/README.md read 2026-10-04.
- **Notes:** Design points for the human. (1) local means the configured Ollama worker profile (Qwen3.8 27B is the lab default, not a requirement) for bounded drafts and first-pass review. (2) cloud means the human's discounted Copilot routing, including auto: advisory, not a known model capability. (3) frontier is for planning, risky design and review of full-tier work; planners are frontier by default. (4) cloud and frontier need the existing cloud and data-sharing approvals, and a route never authorizes sending secrets, PHI or private material; a route is advice, not automatic delegation. (5) Default order stays safety/blockers, then priority, then dependencies, then ROI index; route and complexity inform but do not reorder. (6) Do not equate an expensive route with a valuable task. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-lab bb10fdf: tasks/test-render-board.ps1 has 17 checks and a 9-mutant proof; 'render-board.ps1 -Check' is the acceptance command.

### T-0073 A tool-limited agent definition for read-only reviewers

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A reviewer agent definition lists only Read, Grep and Glob; a test or a documented check proves a Bash call from it is refused; the ai-loop-council skill says to use it for read-only extraction.
- **Evidence:** 2026-10-05: four reviewer subagents were told in the prompt to use only Read, Grep and Glob; the agent type did not enforce it and one ran two directory listings in a shell (ledger E66).
- **Notes:** Proposed by a model. The listings were local and harmless; the point is that the rule was unenforced.

### T-0094 Decide, after the review memo, whether the AI-agent robots.txt rule from T-0067 ships, then merge it in both repos

- **Why / ROI rationale:** Estimate: the two repos should state one rule; today the one that fetches documents is published and the one that defines the rule is not, and the rule is policy, so a person should read the reviewer's memo before it is public. *(confidence: medium)*
- **Acceptance:** A human reads the review memo and records yes or no in T-0067. If yes: the cf-skills change is merged to its main with its tests (the evidence skill's unit tests pass, and one fails when a group for any of Claude, ClaudeBot, anthropic-ai, GPTBot, ChatGPT-User, CCBot, Google-Extended or PerplexityBot disallows the path); git grep -n AI_AGENT_TOKENS origin/main in cf-skills finds the list; NETWORK-RULES R3 and security-browsing say so; in cf-research python tools/sources/fetch_sources.py --audit-robots exits 0, or names each refused entry. If no: the cf-research use of the rule is reverted or documented as the project's own choice, and T-0067 says why.
- **Evidence:** T-0067's notes record the decision to honour robots.txt groups that name AI agents and say the change was done in working trees, not yet committed. Checked on 2026-10-06 with git grep on each origin/main: cf-skills (commit 3844785) has no AI_AGENT_TOKENS and no mention of ClaudeBot or anthropic-ai; cf-research already calls ev.robots_allows in tools/sources/fetch_sources.py and ships the --audit-robots option, so the fetch tool is ahead of the shared rule it depends on.
- **Notes:** Human decision (policy, not code). Does not replace T-0067, which holds the decision and the working-tree change; this task is the publication step after the review memo. Full tier because the change governs how the lab's tools treat other sites.

### T-0046 Sickle cell disease coverage: HBB variant checks, ASH guideline source terms, and an SCD worked example in SKILL.md

- **Why / ROI rationale:** The user states SCD matters to this community. The loop already runs for SCD; this makes it visible, adds the guideline source once terms are read, and keeps the CF-SCD funding comparison paper as a sourced example. *(confidence: medium)*
- **Acceptance:** SKILL.md example section runs clean; catalog has an ASH guidelines entry with access value and check date; ledger shows the Farooq 2020 DOI resolved with no retraction notice.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 4

### T-0012 Unit tests for tools/sources/fetch_sources.py

- **Why / ROI rationale:** The fetcher is the enforcement point for access policy; the 'forbidden is never fetched' property should be a test, not a reading. *(confidence: medium)*
- **Route:** local - Already implemented before this session; verified rather than rebuilt.
- **Acceptance:** pytest passes; tests assert manual/forbidden/request entries never reach download(); manifest round-trip tested with a temp dir.
- **Evidence:** research/tools/sources/fetch_sources.py
- **Notes:**  Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Verified 2026-10-05: tools/sources/test_fetch_sources.py has 16 tests and they pass.

### T-0039 Read terms and record access values for medRxiv, ClinVar, Cochrane CF reviews, NIH RePORTER

- **Why / ROI rationale:** Four sources reachable through APIs already in use or public; one afternoon of reading terms converts them from unverified to catalogued. *(confidence: medium)*
- **Route:** cloud - Reading five hosts needs conduct (robots first, Crawl-delay, one request) and judgement about what a page does and does not say; done by the controller with a scripted quote check.
- **Acceptance:** Four new catalog entries, each with robots/terms fields, a check date, and claim_label: verified.
- **Evidence:** research/proposals/2026-10-04-researcher-sources.md recommended order 3-5
- **Notes:** Human reads terms; agent records. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-research 79203fd and cf-skills 1723bf6: nih-reporter and clinvar verified with their policy sentences quoted (8 of 8 quotes verbatim and complete); biorxiv records medRxiv's terms but stays unverified because bioRxiv's own page answered 429 and was not retried; Cochrane added as manual and link-only because its robots.txt disallows the Claude agent. The acceptance wants four verified entries: two verified, one added unverified, one downgraded to unverified. A human decides whether to retry bioRxiv later.

### T-0059 delegate.ps1: let a model-only setup run fast, and make the token budget and thinking mode explicit

- **Why / ROI rationale:** Estimate: the README tells a contributor to set only LOCAL_WORKER_MODEL; that setup silently wastes every attempt on long tasks. *(confidence: medium)*
- **Route:** cloud - Controller-written PowerShell in the delegation driver; the change was to the driver itself, which the worker cannot test.
- **Acceptance:** test-delegate.ps1 gains cases that fail before and pass after: (a) with only a model set, the first attempts send think=false; (b) a -MaxOutputTokens parameter is passed through to the invoke script; (c) the cap error message names the cap and how to raise it. pwsh -File test-delegate.ps1 exits 0 and a mutation of each change makes a case fail.
- **Evidence:** 2026-10-04: with only LOCAL_WORKER_MODEL set (no profiles) all three delegate attempts for a 130-line shell script stopped with 'Generated-token limit reached' at the hard-coded 8192 tokens, so the model had been thinking; with the fast profile (think false) the same task returned in 12 to 16 seconds. The thinking profile also hit the cap on the one task tried. MaxOutputTokens is fixed at 8192 inside delegate.ps1.
- **Notes:** Proposed by a model; only a human moves it to ready. A human may prefer to require a profile instead; that is a design choice. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-lab 42681c2: model-only runs think off, explicit -MaxOutputTokens up to 16384, an actionable cap error; test-delegate and test-invoke-config extended.

### T-0061 Add GitHub Actions CI to cf-lab, cf-research and cf-skills (drafts are outside the repos; a human adds them under .github/workflows)

- **Why / ROI rationale:** Estimate: a public repo that accepts pull requests should show whether its own tests pass; one matrix job also verifies setup.sh on macOS and Linux. *(confidence: medium)*
- **Acceptance:** Each repo has a workflow that runs on pull_request and on pushes to main and is green on a pull request: cf-lab runs test-setup.py on windows-latest, ubuntu-latest and macos-latest plus the frontmatter check and render-board -Check; cf-skills runs pytest; cf-research runs the fetcher tests, the catalog parse, the sync self-check and the ledger tally self-check. Every workflow sets permissions: contents: read, uses pull_request (not pull_request_target), and pins actions/checkout and actions/setup-python at a major version or commit SHA. Paste the three run URLs into the task notes.
- **Evidence:** 2026-10-04: none of the three repos has a .github/workflows folder, so every test and gate runs only on the maintainer's machine; a pull request shows no check. The setup scripts, the evidence skill (44 tests) and the board checks are all deterministic and cheap to run. T-0058 (real macOS run) needs a macOS runner.
- **Notes:** Proposed by a model; only a human moves it to ready. The workflow drafts, kept by the maintainer outside the repos, are UNTESTED: they have not run on GitHub. Adding a workflow adds a third-party service dependency (GitHub Actions and the actions/* actions), which AGENTS.md asks to flag.

### T-0048 Admission review of Google's Data Commons MCP server for population denominators (layer 5)

- **Why / ROI rationale:** Prevalence and carrier-frequency sentences need a population base with provenance; Data Commons is Google-published, open, free, and MCP-native. Does not replace registry extraction. *(confidence: medium)*
- **Acceptance:** security-runtime MCP checklist done on a pinned release; one query returning US and one state population with source and date, recorded as an evidence record; written note on whether any CF or SCD indicator exists in the graph.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 4c
- **Notes:** User selected this on 2026-10-04 ('let's go for this one for now'); moved to ready on that instruction. Steps in research/proposals/2026-10-04-publish-packet.md section D. PyPI facts: datacommons-mcp 1.4.0, Apache-2.0, py>=3.11<3.14, DC_API_KEY required, stdio or HTTP. Steps 1 to 4 done 2026-10-04 and recorded in research/proposals/2026-10-04-datacommons-admission.md: the four queries ran over stdio from a scripted client, not an interactive agent client (deviation, disclosed). US and Washington population came back with a Census source and date 2025 (stored as verbatim response fields in the note, not yet as a formal evidence record: that needs the provider in T-0053). No CF or SCD indicator exists in the graph. Query (d) started 52 s after (c), not 60 (disclosed). No 429/403 or cooldown. The recommendation is the human's to accept: admit for general statistics only. A human sets done.

### T-0030 Docs tier 3: make AGENTS.md the only rule source; shrink copilot-instructions.md; fix the skill-authoring skill's internal contradictions

- **Why / ROI rationale:** Two always-loaded instruction files that overlap will drift. The authoring skill is the binding rule document for every other skill but has duplicate section numbers, a .skills/ tree that contradicts its own location rule, and a generic section that is not about skills. *(confidence: medium)*
- **Acceptance:** copilot-instructions.md is at most 40 lines and holds no rule that is not also in AGENTS.md; the authoring skill has unique section numbers and no .skills/ tree; check-skill-frontmatter.py --against main passes; lab-versioning/scripts/test-setup.py passes; VERSION is bumped as a PATCH.
- **Evidence:** research/proposals/2026-10-04-docs-organization-and-memory-design.md; the findings for this tier were re-checked against the files on 2026-10-04.
- **Notes:** Human gate: agent instructions and .claude/; a human approves the diff. Human decided 2026-10-04: yes, AGENTS.md becomes the only rule source. Wait until the current hq branch has merged so --against main is meaningful. Do not change what any rule means. Draft by a cloud or frontier model is reasonable; the meaning-preservation check is the human's.

### T-0076 Make the skills repo installable as a Claude Code plugin marketplace

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A .claude-plugin/marketplace.json (and the plugin layout it needs) makes `/plugin marketplace add` of the local folder list cf-evidence-loop; the README says GitHub Copilot still reads .claude/skills; no skill text changes; the format is checked against the Claude Code plugin documentation.
- **Evidence:** 2026-10-05: cf-skills has no .claude/skills and no plugin manifest, so cf-evidence-loop does not load by being a workspace folder; the council ranked a marketplace.json for our own skills as a separate, useful task.
- **Notes:** Proposed by a model. Serves Claude Code users only. Related: T-0051.

### T-0042 Admission review of BioMCP as a discovery tool alongside cf-evidence-loop

- **Why / ROI rationale:** BioMCP reaches ~30 biomedical sources through one MCP server and overlaps most of our providers. If it passes provenance, injection and MCP-runtime review it saves building providers; if not, we know why. Either outcome is worth the hours. *(confidence: medium)*
- **Acceptance:** model-onboarding section 1 and 6 outputs on a pinned release; security-runtime MCP checklist completed; written complement-or-not decision with the rule that shipped citations still come from cf-evidence-loop records. Plus: BioMCP's rate limiting, robots handling, retry and user-agent behaviour documented against NETWORK-RULES.md R1-R9; any rule it cannot demonstrate is listed as a condition of use.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 1

### T-0041 Website section for the evidence loop: how the lab answers a research question, with the seven layers and a live example record

- **Why / ROI rationale:** The site explains the AI loop but not the research loop it serves. A section showing question -> source -> record -> limitation, with one real retraction-check record, is the clearest public statement of what 'claim verification' means here and sets the standard every video and note is held to. *(confidence: medium)*
- **Acceptance:** Section live on senseiewok.ai in lab-voice register; every number in it resolves to a record in research/evidence/; Playwright check confirms the section renders and the disclaimer block is present; human sign-off per lab-voice review list.
- **Evidence:** skills/cf-evidence-loop/references/ARCHITECTURE.md; research/proposals/2026-10-04-evidence-loop-site-section.md

### T-0070 Read the terms and robots.txt of Ensembl REST, NCBI Variation Services, UniProt and ClinVar bulk files with the lab's reader; propose catalog entries

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** For each of the four: robots.txt and the terms page read with the hardened reader (one request each), the catalog entry proposed with access, redistribute, terms_url and claim_label; python tools/sources/check_catalog_fields.py exits 0; a human reads uniprot.org's licence page once.
- **Evidence:** 2026-10-05: proposals/2026-10-05-dna-sources-survey.md lists these as the first four sources for a read-only CFTR variant helper; every term there is unverified because the pages were read through a summarising fetch tool and some did not render.
- **Notes:** Proposed by a model. Reading only; no provider code. A human sets this ready.

### T-0079 Measure whether the local models can write WebGL and SVG: a verifier-first test

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** Three bounded tasks (for example a lit rotating mesh, a morph between two shapes, an animated SVG path) each with a Playwright pixel and console verifier proven on a bad stub; fast and thinking attempts recorded; a results table added to model-qwen3-8-27b with the cases the model failed; cloud fallback used where it failed.
- **Evidence:** 2026-10-05: the maintainer wondered whether local models can be good at OpenGL; the local worker is Qwen3.8 27B and a cloud fallback is always allowed.
- **Notes:** Requested by the maintainer in this session on 2026-10-05, so it is ready. Small n; the result is evidence, not a ranking. 2026-10-05 progress: the Playwright-free verifier for WebGL tasks exists (check-webgl.py); the three tasks and the model runs are not started. 2026-10-05 later: one of the three tasks was run for real. A 20-item WebGL2 viewer page, two runs of the delegate loop (fast, fast, thinking), a verifier that renders the page in headless Chromium and checks the source: 0 of 6 attempts accepted; the faults a plain 'does it draw' test would miss (no first frame under reduced motion, a console error, a missing required element) were the ones found. Cloud fallback wrote the page. Results table is in model-qwen3-8-27b. The lit-mesh and SVG-path tasks are still to run.

### T-0035 Tier table and loop housekeeping: elevated challenger rule, slim ai-loop-council, retire the loop-orchestrator prototype

- **Why / ROI rationale:** The gate design recommends a blind different-family challenger at the elevated tier for public-facing artifacts and changed factual claims, a council skill about 7,300 words against a 500-line cap, and deleting a prototype whose config names one model as worker, challenger and council. All three change agent instructions. *(confidence: low)*
- **Acceptance:** AGENTS.md tier table states the elevated challenger condition and stays under 2,500 words; ai-loop-council/SKILL.md is under 500 lines with the moved sections kept as research proposals that carry Status lines; .github/loop-orchestrator/ is removed and no file still links to it; check-skill-frontmatter.py passes; the setup self-test passes; no rule changes meaning except the one decided.
- **Evidence:** research/proposals/2026-10-04-ai-loop-gate-design.md and research/ledger/2026-10-04-first-session.md (23 logged errors from one session by one agent).
- **Notes:** Human gate: AGENTS.md, .claude/ and .github/ (CODEOWNERS-protected). Decisions 1 and 3 of the design note are the human's. Do not do this before they are answered.

### T-0027 Design an opt-in setting that lets the controlling agent delegate bounded drafts to a usable local worker automatically

- **Why / ROI rationale:** Routine drafting and first-pass review is already assigned to the local worker by policy, but the controlling agent has to remember to do it. A documented, default-off setting would make the intended behaviour repeatable and cheaper. Risk: a setting that silently sends work to a model changes what is in context for a task, so the default must be off and the data boundary and approval rules must not weaken. *(confidence: low)*
- **Acceptance:** A written design names the setting (for example an environment variable next to LOCAL_WORKER_PROFILE, not skill frontmatter, since skills are not read as configuration by every client), its default (off), when 'helpful' applies (bounded, tool-free, verifiable tasks only), and what it never does (no untrusted text without the data boundary, no secrets, no model self-approval, no model downloads). select-work-route.ps1 gains self-tests for it, and the routing self-test still passes with the setting unset.
- **Evidence:** Human request 2026-10-04 while drafting registry skills with the local Qwen3.8 27B 64k alias: a setting in the skills that, when set, delegates to local models automatically when helpful. Existing pieces read 2026-10-04: AGENTS.md 'Local-first escalation' (COUNCIL_CROSS_PROVIDER_DELEGATION is opt-in for cloud only), ai-loop-council 'Delegation setting' and select-work-route.ps1 (52 self-tests, no model execution), invoke-local-model.ps1 (LOCAL_WORKER_PROFILE, LOCAL_WORKER_MODEL).
- **Notes:** Agent-instruction change; a human approves every .claude/ diff. The 64k alias is a measured option, not a default: see model-qwen3-8-27b 'Context allocation and memory fit'. Update 2026-10-04, human direction: the preferred local model is one setting, LOCAL_WORKER_MODEL in the single lab .env; unset (and no profile) means no local worker and cloud-only. invoke-local-model.ps1 no longer falls back to any model (test-invoke-config.ps1); delegate.ps1 ships the bounded delegate-and-verify loop (test-delegate.ps1). Still open: whether select-work-route.ps1 should read LOCAL_WORKER_MODEL itself, and the human's approval of the AGENTS.md wording.

### T-0086 Depth probe for the 64K local alias

- **Why / ROI rationale:** Estimate: every long-note task depends on it. *(confidence: medium)*
- **Route:** local - A fixed prompt generator with an exact-match check.
- **Acceptance:** depth-probe.ps1 -SelfTest passes; counts per depth for the fast and thinking profiles are recorded in the profile skill with a negative control.
- **Evidence:** scratch/qwen-local/design.md section 5: no controlled measurement exists of whether a fact placed deep in a 64K prompt is used; nine prompts over 12K tokens in the usage log, none a probe.

### T-0011 External review round: registry scientist on comparability, person with CF/caregiver on wording

- **Why / ROI rationale:** The highest-impact error available is placing non-comparable numbers side by side; only a domain reviewer catches it. *(confidence: low)*
- **Acceptance:** Two written reviews on file; every comparability finding either fixed or recorded in comparability_notes.
- **Evidence:** cf-first-project-scoping-memo.md (private session document, not in the repo) section 7

### T-0089 Mechanical filter for local review findings: reproduce each failing input in a temp copy

- **Why / ROI rationale:** Estimate: the evaluation's judges ran every input by hand, one site folder and one run per finding. A tool does that step and leaves the controller only the spec reading, which the 8-of-14 figure shows cannot be skipped. *(confidence: medium)*
- **Route:** local - A small script with a test-shaped verifier; the depth probe was written by the local worker and accepted on the first attempt with 12 of 12 tests (model-qwen3-8-27b profile). The controller still reads the spec check.
- **Acceptance:** A tool takes a local worker's review findings, each with a runnable failing input, runs the input against the candidate inside a temp copy (nothing read outside it) and keeps only findings whose claimed output appears; a test with recorded findings from the reviewer evaluation separates reproducing from non-reproducing ones, treats a finding with no input as a lead and not a finding, and its output tells the controller to check the quoted spec sentence of each kept finding. The tool never ranks or accepts a finding by itself.
- **Evidence:** scratch/qwen-local/reviewer-eval.md, 'What an accept a review rule should be' and 'False positives, by kind': 14 false-positive claims in 8 runs; running the given input against the unpatched candidate removed 5 of 14 and 2 matched findings whose inputs went through a path the script never reads; 8 of 14 reproduced exactly and were still wrong about the spec (7 of them one rule misread), so reproduction alone is not acceptance.
- **Notes:** Reproduce with: the recorded replies in scratch/qwen-local/reviewer-eval/out and the judge reports in judge-reports. Follows T-0088 (verifier reads only its temp copy). Raw records stay private; the test fixtures must be synthetic or cut down before anything is published.

### T-0051 Decide and implement how the control repo consumes the evidence skill

- **Why / ROI rationale:** A second copy of the skill or catalog would drift and mislead agents; a single maintained source avoids that. The mechanism (sibling-checkout launcher vs installable package) is cheap to document and test, but choosing it wrong means rework. The drift check in the pre-commit gate catches the main failure mode (catalog divergence), which is high-value for a small cost. *(confidence: medium)*
- **Acceptance:** From the hq folder one documented command runs a retraction check through the skill without copying it: `python scripts/evidence_cli.py retractions 10.1016/S0140-6736(97)11096-0` (path to the skill in the skills repo) exits 0 and prints a 2004 correction and a 2010 retraction. The drift check runs in the tier gate (run-gate.ps1) when either catalog is staged: staging a deliberate one-line edit to cf-evidence-loop/catalog.yaml makes `research/tools/sources/sync_skill_catalog.py --check` exit 1 and the gate fail; reverting the edit lets it pass.
- **Evidence:** The cf-evidence-loop skill lives in the skills repo; hq must not hold a second copy. The source catalog research/sources/catalog.yaml is canonical; the skill ships a generated copy cf-evidence-loop/catalog.yaml kept equal by research/tools/sources/sync_skill_catalog.py (--check exits 1 on drift). Agents in hq need to run scripts/evidence_cli.py from the skill, which needs Python with requests and PyYAML. A tested virtual environment exists outside the repos. Open question: link or install mechanism. The drift check is not yet part of any commit gate.
- **Notes:** Link or install mechanism is open: a documented sibling-checkout path with a launcher script, or an installable package. The tested virtual environment lives outside the repos and must be referenced, not recreated. Do not add a second copy of catalog.yaml to hq. The gate change (this repo has no pre-commit hook; the gate is run-gate.ps1) should only trigger when either catalog file is staged.

### T-0049 Pilot Gemini Deep Research (collaborative planning) as the frontier-planning leg; verify every citation through cf-evidence-loop

- **Why / ROI rationale:** The website promises frontier planning with local execution; Deep Research is that leg as a managed agent, browsing from Google's infrastructure rather than the lab's IP. The pilot adds the verification step the website does not yet mention. Usage-priced on the Gemini API the lab already pays for. *(confidence: medium)*
- **Acceptance:** One research question run with collaborative_planning; plan reviewed by a human before execution; report saved; every cited DOI/NCT/approval run through cf-evidence-loop with the ledger committed; count of citations that were clean, flagged, or unresolvable reported. No private material in the prompt.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 4c; ai.google.dev Deep Research docs read 2026-10-04
- **Notes:** Human decision: spend. Check current preview status and pricing on ai.google.dev at pilot time. Add generativelanguage.googleapis.com to the catalog as access: api with terms_url before any code calls it.

### T-0043 Variant layer: MyVariant.info and gnomAD providers (aggregate frequencies only)

- **Why / ROI rationale:** Carrier-frequency and classification claims for CFTR and HBB variants need a population denominator; both APIs are public and aggregate. *(confidence: medium)*
- **Acceptance:** Two providers with parse tests and fixtures; catalog entries with read terms and check dates; live check on F508del and HbS returns classification plus allele frequency with limitations.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 3
- **Notes:** Update 2026-10-04: catalog entries gnomad and myvariant now exist (research/sources/catalog.yaml). gnomad is access manual: its robots.txt is 'Disallow: *' with an allowlist that has no API path, and no API usage terms were found on its policies page, so a gnomAD API provider is blocked until the gnomAD team states API terms (a human may ask them). myvariant is api but has no base_url yet and its rate limit is unstated (capped at 1/s); it is not reachable by the skill until a human admits it.

### T-0047 Trial one Scite Pro seat; build a supporting/contrasting/mentioning provider for cf-evidence-loop behind the same conduct rules

- **Why / ROI rationale:** Smart Citations are the only paid capability that directly serves claim verification: whether later literature supported or contradicted a finding. Hosted MCP means the vendor's servers, not the lab's IP, make upstream requests. About $50/month for one Pro seat with a self-service API key; cancel after a 30-day evaluation if the provider does not change a verdict in the 60-claim set. *(confidence: medium)*
- **Acceptance:** security-runtime MCP checklist completed and what-leaves-the-machine documented; provider returns Evidence records with vendor-model limitation string; catalog entry with terms_url, max_rps and auth=api_key; fixtures and tests; 30-day evaluation note recording whether any claim verdict changed.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 4b; docs.scite.ai pricing and MCP pages read 2026-10-04
- **Notes:** Human decision: spend. Pricing figures must be re-read on the vendor page at purchase time.

### T-0056 check-lab-files.ps1: a deterministic check that the cf-lab-files folder holds nothing it must not

- **Why / ROI rationale:** Estimate: a folder that agents can read and that collects notes is where a key or a patient detail would end up unseen. *(confidence: medium)*
- **Route:** cloud - The worker failed three attempts on PowerShell scoping and return values; the controller wrote it. Local is not yet reliable for PowerShell with a state-heavy spec.
- **Acceptance:** pwsh -File .claude/skills/security-git/scripts/check-lab-files.ps1 -SelfTest exits 0, and the self-test proves (a) a seeded violation is caught for each rule and (b) a clean folder passes. Rules: no file named .env* or with a key/cert extension, no private-key header or token-shaped string or email address in memory/, no .git inside, at most 3 files directly in memory/, and any private terms taken from a LAB_PRIVATE_TERMS line in .env (never committed). Run once on the real folder and report the output.
- **Evidence:** A frontier design review on 2026-10-04 (read-only) judged the Files folder safe only with one check: the folder sits inside the agents' workspace, is not a git repo, and has no history. AGENTS.md lists the never-store items; nothing enforces them.
- **Notes:** Proposed by a model; only a human moves it to ready. Do not read .env; the check receives only the terms variable through run-with-env.ps1. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-lab c47ca94: check-lab-files.ps1 and its outside-in test pass; the real folder reports 'lab files clean: 45'.

### T-0064 More sources: UKRI Gateway to Research, CORDIS, EU Clinical Trials Register, WHO ICTRP, PubPeer, ClinGen, and the CFF 2025 highlights link

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Route:** cloud - Web reading with conduct and quote verification needs a networked controller.
- **Acceptance:** fields ok: 27 keys documented; sync_skill_catalog --check in sync; each quoted sentence verbatim and complete (11 of 11 checked); fetch_sources.py --manual and sources/manual-downloads.md list the manual, request and forbidden ones.
- **Evidence:** 2026-10-05: the maintainer asked to bring more sources; the researcher-sources proposal listed integrity, funding, trial-register and curation gaps. The CFF highlights URL was given by the maintainer.
- **Notes:** Taken 2026-10-05 on the maintainer's instruction (the evening requests: assess delegation, security and queueing, a manual-download page, more sources, better ASCII art). Work lands on the open PR branches, nothing pushed. A human sets done after seeing the acceptance output. Done in cf-research dd0d64e and 1b09df8. ukri-gtr is an api source, tested live (724 records). pubpeer and clingen are forbidden (terms and robots refuse automated access); who-ictrp is request; cordis is manual with CC BY 4.0 reuse; eu-ctr is manual and unverified; cffpr-highlights-2025 is manual and unread because www.cff.org refuses automated clients. No provider uses ukri-gtr yet.

### T-0066 Promote the ad-hoc page reader to a tested tool with the evidence loop's own conduct rules

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A command in cf-evidence-loop (or tools/sources) reads one HTTPS page or PDF: robots.txt first with robots_allows, Crawl-delay honoured, a refused or unreadable robots.txt means no fetch, redirects followed only within the same site and re-checked, certificate checks on, a 5 MB cap, one request. Tests with a fake session fail before and pass after for each rule; a mutation proof rejects each broken rule.
- **Evidence:** 2026-10-05: reading terms pages used an untracked script that followed redirects to other hosts without re-checking robots, used the system trust store (a self-signed certificate in the chain on api.reporter.nih.gov while certifi worked) and matched robots groups with the standard library, which the evidence package avoids. Fixed in the scratch copy only.
- **Notes:** Proposed by a model; only a human moves it to ready. It needs no catalog entry (it exists to read terms before an entry exists), so say clearly in its README that it is for a human-started reading of terms pages, not for data. New network-facing code in a public skill: flag for review.

### T-0034 Claim checker for the elevated tier: quote, absence and count claims with a mandatory positive control

- **Why / ROI rationale:** Ledger entries E12 and E13 are the most expensive class: inferences beyond the evidence and a verifier with a blind spot. A checker that settles quote, absence and count claims against raw text, and refuses to report 'none found' until it has found a planted instance, closes the gap a verbatim-quote check leaves. *(confidence: low)*
- **Acceptance:** A claims file (id, type, text, evidence location) is checked by a script: a truncated-prefix quote fails; an unnumbered contents entry defeats an absence claim made from parsed structure; a count claim is compared with a counted value; a verifier that cannot find its planted instance exits non-zero. Fixtures reproduce E12 and E13 and fail without the guard.
- **Evidence:** research/proposals/2026-10-04-ai-loop-gate-design.md and research/ledger/2026-10-04-first-session.md (23 logged errors from one session by one agent).
- **Notes:** Draft by a cloud agent, tests drafted by the local worker, human approves the .claude/ diff. Does not judge inferences; it only settles what a script can settle.

### T-0075 Trial Anthropic's public skills (frontend-design, skill-creator) against our own checks

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A note records, for each of the two skills: what was run, the with-and-without outputs judged by named checks that run (accessibility, no new dependency, verified copy untouched; for skill-creator only gains an existing deterministic check confirms), every script read before it was run, the token cost of the descriptions per turn, and one reproducible check of whether Claude Code discovers skills in an added workspace folder; the maintainer decides adopt, adapt or drop for each.
- **Evidence:** 2026-10-05: the maintainer asked to add anthropics/skills to the workspace and test whether it is useful, with our own additions kept thin. A council (Fable, local Qwen, controlling agent) ranked read-only trial first and vendoring last: proposals/2026-10-05-public-skills-decision.md. The repo is a marketplace of bundles, so a plugin install loads twelve skills at once.
- **Notes:** Requested by the maintainer in this session on 2026-10-05, so it is ready. Nothing from the clone is copied into a public repo. 2026-10-05: the maintainer decided the lab's skills are layered on top of Anthropic's in the lab's own repos (nothing copied; base named, labelled third party, layer works alone): THIRD_PARTY_SKILLS.md lists the pairs and ai-provider-compatible-skills section 11 holds the rule. The trial still decides whether to adapt any idea.

### T-0063 ascii-art skill: a craft process, a canvas library, a rendering and accessibility checker, one new piece, and the research behind them

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Route:** local - Both scripts have exact verifiers; the checker needed a thinking attempt after fast attempts failed on my spec errors.
- **Acceptance:** python .claude/skills/ascii-art/scripts/test-asciicanvas.py and test-check-ascii.py print VERIFIED; check-ascii.py on GALLERY.md reports 0 errors; SKILL.md sections 6 to 10 name each source and how far it was read; a human reads gallery piece 7 before any CF-facing use.
- **Evidence:** 2026-10-05: the maintainer asked for the ascii-art skill to become truly creative and artistic, researched online, with the READMEs updated. The skill covered tone and tools but not how to make a good piece, and models read ASCII better than they draw it (arXiv 2604.14641).
- **Notes:** Taken 2026-10-05 on the maintainer's instruction (the evening requests: assess delegation, security and queueing, a manual-download page, more sources, better ASCII art). Work lands on the open PR branches, nothing pushed. A human sets done after seeing the acceptance output. Done in cf-lab a602e23. The worker drafted the canvas (attempt 2) and the checker (thinking attempt); 20-mutant and 18-mutant proofs. Sources: two read as abstracts and quotes verified verbatim, two through a summarising tool and marked as such, search summaries marked unverified.

### T-0019 Add model profile skills for Gemma 4 31B and Laguna XS 2.1, or remove them from the site's field guide

- **Why / ROI rationale:** The website presents three installed models; hq has profile skills only for Qwen variants and DeepSeek-R1. Public claims about the cast should match the skills that govern it. *(confidence: medium)*
- **Acceptance:** Either .claude/skills/model-gemma-4-31b and model-laguna-xs-2-1 exist with onboarding results, or the field guide lists only models with profiles.
- **Evidence:** hq/AGENTS.md skills list vs .ai/README.md 'three models'

### T-0085 Delegation loop: answer-first contract, grouped verifier feedback and a PowerShell AST lint

- **Why / ROI rationale:** Estimate: the two most frequent failure causes in the logs; cheap and testable offline. *(confidence: medium)*
- **Route:** local - Offline script changes with an existing test file; the controller reads the diff.
- **Acceptance:** test-delegate.ps1 gains cases for grouped feedback with expected/actual on the first failure, and for an answer-first reminder in thinking attempts; the lint rejects the three observed PowerShell causes before the verifier runs; delegations.jsonl before/after on two replayed tasks.
- **Evidence:** scratch/site-updates/log-assessment.md sections 3 and 5; scratch/qwen-local/design.md section 4; observed this session: 12 identical FAIL lines, cap exhaustion with the answer already in the thinking text, a non-compiling reply ranked best (fixed).

### T-0052 Close the findings a frontier-model review deferred in cf-evidence-loop v0.1

- **Why / ROI rationale:** Crash-on-unexpected-shape and missing body-size cap are reliability defects that will surface in production runs. Unstripped escape sequences and unvalidated --contact are low-severity but cheap to fix. The dry-run reporting gap and robots.txt prefix-match limitation reduce trust in the tool's output. Correct terms_url values are a data-quality fix that a human must confirm. Overall moderate benefit for moderate cost. *(confidence: medium)*
- **Route:** local - Isolated functions with a precise verifier were accepted on attempt 1 (contact, escape cleaner, robots groups); design edits across providers were done by the controller.
- **Acceptance:** Each finding gets a test that fails before the fix and passes after: parser rejects a list, missing key, or non-numeric total with a clear error; body-size cap rejects oversized input; Evidence.one_line strips ANSI escapes; --contact rejects non-email values; dry run prints all planned URLs; robots.txt selects the correct group. Run the offline suite; it exits 0. The three terms_url values point at pages a human confirmed state the API usage policy.
- **Evidence:** Three catalog terms_url entries (crossref, biorxiv, nih-reporter) point at landing pages, not usage-policy pages. Provider parsers crash on unexpected shapes (list vs object, non-numeric total, missing key) and have no body-size cap. Evidence.one_line prints raw API strings without stripping escape sequences. --contact is not validated as an email. A dry run reports only the first planned URL of multi-request commands. Robots.txt group matching uses a prefix match and only the first matching group.
- **Notes:** The three terms_url corrections require a human to read the actual policy pages and record the correct URLs; do not guess. Parser hardening should add explicit error messages, not silent fallbacks. The body-size cap value should be chosen deliberately and documented in code. Escape-sequence stripping should cover common ANSI codes. The --contact validation can use a standard email regex or library. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-skills 129d43e: 49 new tests, each failing before its fix, 93 passing in total; a 26-mutant proof rejects every broken fix. Also fixed: options given before the subcommand were silently dropped. Not done: the three terms_url values still need a human to confirm them (the pages were read under T-0039 but a person must sign off). The stray untracked tests/test_review_findings.py was not used.

### T-0084 Local worker playbook cards v0 and the bare-versus-card measurement

- **Why / ROI rationale:** Estimate: if cards beat bare packets on the same verifiers the lab can run longer local-only; if they do not, that is worth knowing too. *(confidence: medium)*
- **Route:** local - The tasks and verifiers are deterministic and the worker's attempts are logged to .loop-logs/delegations.jsonl.
- **Acceptance:** check-card validation for at least two cards; the same three tasks run bare and with the card, three runs each, counts per cell and defects found by reading recorded in the model profile skill with the small-n caveat; a card is marked validated only where it beat the bare packet.
- **Evidence:** scratch/qwen-local/design.md (cards, loop, benchmark); scratch/seo-skill/ab and scratch/site-updates/qwen-results.md hold the first runs: exact-patch packets with a test-shaped verifier were accepted on attempt 1 in 25 to 35 s; a 150-line script from a bare spec was not.
- **Notes:** Distillation here means written teaching material, not training or model downloads.

### T-0090 Re-measure the local reviewer with the thinking profile and more runs per arm

- **Why / ROI rationale:** Estimate: n = 4 per arm cannot support a decision about the review card or the reviewer role; more runs and the thinking profile settle whether a card helps and whether thinking fits in the 16,384 output budget. *(confidence: medium)*
- **Acceptance:** 8 or more runs per arm on the same packets and ground truth, with the fast profile and the thinking profile reported separately, each reply scored by a blind judge as before; the 18th defect (SEO008, absolute canonical with no base) is added to the ground truth once the SEO008 fix is merged in the released skill, and the added entry is stated in the report; counts per run, means and the permutation test are recorded with the caveat that the result is for one script and one spec.
- **Evidence:** scratch/qwen-local/reviewer-eval.md: 4 runs per arm, found 1, 0, 2, 2 (bare) and 2, 0, 5, 4 (card) of 17, exact one-sided permutation p = 13/70 = 0.19; the thinking profile was not run, and the list of 17 defects is incomplete (an 18th, SEO008 with no base, was reported by three runs).
- **Notes:** Human step: the maintainer decides when the machine is free (a thinking review of about 16K prompt tokens may reach the 16,384 output limit). Do not run while another Ollama experiment is using the worker. Judges must be a different model family from the worker.

### T-0097 Re-run the local reviewer evaluation on a second, different script

- **Why / ROI rationale:** Estimate: a reviewer measured on one script may be good or bad at that script only; a second script with its own ground truth shows whether the pattern (what it finds, and which kinds of false positive it claims) carries over before the lab relies on the reviewer role. *(confidence: medium)*
- **Acceptance:** A second script of similar size, written by the local worker and accepted by its verifier, is chosen and named in the report. Its ground truth is a list of defects found by a stronger review reading the script against its spec, each defect confirmed by a failing test before any local run, with at least 8 defects. The same design as the first evaluation is run: bare and card arms, identical packet format, the same profile and temperature, runs alternated, each reply scored by a blind judge from a different model family than the worker. The report gives per-run counts, means, an exact permutation test, the false-positive claims by kind, and a section that says which findings of the first evaluation repeat and which do not; no change to the review card or to the reviewer role in the skills is made from one script.
- **Evidence:** scratch/qwen-local/reviewer-eval.md, 'Design' and the caveats: one task, one script (an 808-line SEO checker the worker had written and the verifier had accepted), one spec, 4 runs per arm; the ground truth of 17 defects came from one stronger-model review of that script. T-0090's own acceptance says the result holds 'for one script and one spec'. T-0090 repeats the same script with more runs; no task yet tests a different script.
- **Notes:** Human step: the maintainer picks the moment (it occupies the local worker for hours) and the second script. Related to T-0090 (same script, more runs and the thinking profile) and T-0089 (filter for false positives); neither covers a second script. Do not run while another Ollama experiment is using the worker.

### T-0010 Claim-check harness + frozen 60-claim evaluation set

- **Why / ROI rationale:** Turns the table into something a person or local model can be checked against; abstention-by-construction is the safety property. *(confidence: medium)*
- **Acceptance:** >=90% correct verdicts; all 10 out-of-scope claims return out_of_scope; set frozen before any model sees it.
- **Evidence:** cf-first-project-scoping-memo.md (private session document, not in the repo) section 4 and 6

### T-0057 Human edits to the protected .github folder after the rename: CODEOWNERS, copilot-instructions names, CI workflows

- **Why / ROI rationale:** Estimate: without the new paths the setup scripts lose their required reviewer. *(confidence: high)*
- **Acceptance:** grep -n 'setup' .github/CODEOWNERS shows /setup.cmd and /setup.sh owned by @senseiewok and no /setup.ps1; grep -rn -E 'hq\|Research Lab' .github returns nothing in cf-lab; the CI workflow drafts (kept by the maintainer outside the repos, one per repo) are in .github/workflows of each repo (see T-0061).
- **Evidence:** .github/CODEOWNERS line 9 still lists /setup.ps1, which was replaced by setup.cmd and setup.sh on 2026-10-04. .github/copilot-instructions.md and .github/loop-orchestrator/README.md still say 'Sensei Ewok Research Lab (hq)'; the repos are now cf-lab, cf-research and cf-skills (GitHub renamed 2026-10-04). No repo has a .github/workflows folder (verified 2026-10-04). Files under .github/ are write-protected from automated agents here, so none of this was edited.
- **Notes:** Human only. Proposed by a model. Workflow drafts are in the release folder, outside the repos, and are untested.

### T-0023 Website: confirm 2024 Alyftrek and 2019 Trikafta approval dates against FDA records before next deploy

- **Why / ROI rationale:** The site cites CFF history and a DailyMed label. Approval years are the kind of claim a reader checks; worth a dated FDA-source citation per drug rather than a history page. *(confidence: medium)*
- **Acceptance:** Each approval year on the page links to an FDA or DailyMed record with a checked date.
- **Evidence:** handoff site_text.txt (private session artifact, not in the repo) 'Modulators and drug development'

### T-0026 Docs and privacy tidy in research: complete the sources/README.md field table; decide the website domain and deploy detail in the proposals

- **Why / ROI rationale:** A field reference that omits fields invites a wrong entry in the catalog that agents treat as a permission record. The privacy items are low risk (no host, credential or path) but leave the repo inconsistent with its own rule until a human decides whether the domain is public. *(confidence: medium)*
- **Route:** local - Worker draft of the field checker passed its verifier; the controller tidied it and wrote the privacy tidy by hand.
- **Acceptance:** Every key used in sources/catalog.yaml appears in the sources/README.md Fields table (a short script can diff them), and no key listed there is unused or it is marked optional; the two proposals are consistent about naming the public domain, and website-review.md carries no private-repo file names or deploy-mechanism detail beyond what a human keeps on purpose.
- **Evidence:** research/sources/README.md Fields table omits pages, text_layer, priority, reference_doi, base_url, auth and etiquette, all used in catalog.yaml, while the catalog header names the README as the field reference. proposals/2026-10-04-youtube-about.md names the website domain twice; proposals/2026-10-04-website-review.md describes the deploy mechanism and names two private-repo files. AGENTS.md says to keep private project identities, domains and deployment details out of public repos.
- **Notes:** Human decided 2026-10-04: the website domain is public (an older version of the site is live and the YouTube channel links to it), so it may be named in public repos and the earlier redaction of it in website-review.md was precautionary. Remaining: whether to keep the generic description of the deploy mechanism and the names of two private-repo files in website-review.md. The private repo's source, deploy details and local paths stay out of public repos. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-research e5991ed: check_catalog_fields.py prints 'fields ok: 27 keys documented'; 13 test cases pass; two public notes lost deploy-mechanism detail.

### T-0032 Docs tier 5: tidy per-user agent memory outside the repos

- **Why / ROI rationale:** Per-user memory lives in a home-folder project unrelated to the lab repos and is partly misfiled. The design limits that layer to machine-specific operational facts and bars model-identity claims and lab lessons. *(confidence: medium)*
- **Acceptance:** A listing of the memory folder shows files only under the lab's own project folder, none holding lab rules, task state, model-identity claims or secrets.
- **Evidence:** research/proposals/2026-10-04-docs-organization-and-memory-design.md; the findings for this tier were re-checked against the files on 2026-10-04.
- **Notes:** Human only and private: nothing is committed. The author of the design did not read the contents, so this task starts with the human reading them.

### T-0029 Docs tier 2: hq housekeeping outside .claude (README tree, loop README status line, retire committed PR descriptions)

- **Why / ROI rationale:** Small fixes to documents that currently mislead: the README structure tree omits tasks/ and Modelfile, and the loop-orchestrator README still advertises consensus voting that AGENTS.md forbids. Committed PR descriptions go stale at merge. *(confidence: medium)*
- **Acceptance:** grep -c 'tasks/' README.md is 1 or more; the first five lines of .github/loop-orchestrator/README.md contain 'not functional'; render-board.ps1 -Check exits 0; after merge no .github/PR-*.md is tracked and its provenance is in the notes of the tasks it completed.
- **Evidence:** research/proposals/2026-10-04-docs-organization-and-memory-design.md; the findings for this tier were re-checked against the files on 2026-10-04.
- **Notes:** Human gate: .github/ is CODEOWNERS-protected, so a human commits. Do not touch loop.py, settings or skills. Human decided 2026-10-04: stop committing PR descriptions; delete .github/PR-2026-10-04.md (and the research one) at merge after copying their provenance into the notes of T-0003, T-0004 and T-0022. README tree edit and loop README status note were prepared on branch chore/docs-org-tier2; the .github change is staged for a human to commit.

### T-0095 Make the website's footer and credit wording agree with the README's 'Thanks to the tools' section

- **Why / ROI rationale:** Estimate: two public places that thank different vendors, or word the independence line differently, read as careless and can imply an endorsement that does not exist. *(confidence: medium)*
- **Acceptance:** A human compares the two texts and decides what each should say. Check: from the README run sed -n '/^### Thanks to the tools/,/^## Repositories/p' README.md \| grep -o -i -E 'Visual Studio Code\|GitHub Copilot\|GitHub\|PowerShell\|Playwright\|Microsoft Edge\|Ollama\|Python\|Git\|Anthropic' \| sort -u, run the same grep over the website's footer and credits text, and the two sorted lists are equal or each difference is listed with its reason; the footer carries the same non-endorsement sentence as the README or a shorter one that says the same.
- **Evidence:** README.md, section 'Thanks to the tools' (the table of Visual Studio Code, GitHub, GitHub Copilot, PowerShell 7, Playwright and Microsoft Edge, Git, Python and Ollama, plus the line that no company has funded, reviewed or endorsed the lab) and the sentence above it crediting Anthropic's Claude models and stating the lab is independent. The website is a separate, private repository whose footer I did not read for this task, so whether the two agree is not known.
- **Notes:** Human decision: which vendors the site names, and in what words. Needs access to the private website repository; the repo field names cf-lab for the README side. Names are credits, not recommendations.

### T-0068 review-diff.ps1: the gate's local-worker review row as one command

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A script builds a packet from git diff (range or staged), sends it with findings.schema.json for N samples, prints one line per finding and the reminder that a worker review is a prompt, not a gate; a test with a stub worker and a throwaway repository covers range, staged, paths, context, empty diff, oversize diff and bad revision, with a mutation proof.
- **Evidence:** 2026-10-05: the full-tier gate lists a local-worker review row, and it was not run for any of the week's commits until I built a packet by hand for the T-0052 diff; the worker's two samples gave three findings, none true. A helper makes the row cheap and keeps the packet text the same.
- **Notes:** Proposed by a model after the maintainer interrupted an attempt to add it; only a human moves it to ready.

### T-0096 Run the optional Playwright browser-testing setup on a real Mac and a Linux machine

- **Why / ROI rationale:** Estimate: the README promises the optional step works on macOS and Linux; a virtual-environment path, a browser lookup and a Playwright install differ per system, and a stand-in cannot show that they work. *(confidence: medium)*
- **Acceptance:** On macOS, then on one Linux machine with Python 3.10 or newer: python .claude/skills/playwright-browser-testing/scripts/test-setup-browser-testing.py prints VERIFIED; python .claude/skills/playwright-browser-testing/scripts/setup-browser-testing.py --dry-run prints the plan with the virtual environment under ~/.local/share/lab-playwright, ends with 'Dry run: nothing was downloaded, created or changed.' and leaves that folder absent; the script without --dry-run, answered yes, ends with 'Done. Playwright 1.63.0 is installed in ' followed by the folder and exits 0 (its observation self-test passed); deleting that folder undoes it. Paste the endings into this task's notes; a failure becomes its own task with the output.
- **Evidence:** README.md, 'Browser testing': off Windows the setup script puts its virtual environment in ~/.local/share/lab-playwright and looks for Edge or Chrome in fixed paths; .claude/skills/playwright-browser-testing/scripts/test-setup-browser-testing.py checks those paths only with an injected platform name (test_mac_and_linux_paths and the default_venv case), never on a real macOS or Linux machine. README.md and T-0058 say setup.sh itself has not run on a real Mac or Linux either; T-0058 covers setup.sh and test-setup.py, this task covers only the optional Playwright script.
- **Notes:** Needs a human with a Mac and one Linux machine. Proposed by a model. The script downloads Playwright from the Python Package Index and, if no Edge or Chrome is found, a Chromium build; run it only where that is acceptable. Do not claim macOS or Linux support for this step until it passes.

### T-0088 Keep everything a verifier reads inside its temp copy

- **Why / ROI rationale:** Estimate: avoids wasted attempts and false failures during a long unattended run. *(confidence: medium)*
- **Route:** local - A small change to a Python verifier helper.
- **Acceptance:** The shared site verifier copies the pieces of the research repo it needs; a run started before an edit of the sibling repo gives the same result as one started after.
- **Evidence:** A verifier for site edits read the sibling research repo through a link; editing that repo during the run (new ledger entries) made the evidence-page check fail on two otherwise correct attempts and cost a thinking attempt (scratch/site-updates/qwen-results.md).
- **Notes:** Lesson candidate, reproduce with: start a delegation, then edit cf-research/ledger/*.md, and watch tools/make_evidence.py --check fail in the verifier copy.

### T-0040 Read terms and record access values for UK, Canadian, Australian, and Irish CF registry annual reports

- **Why / ROI rationale:** Extends the registry table beyond US and EU. Each is either fetchable like ECFSPR or manual like CFF; the fetcher already handles both. *(confidence: medium)*
- **Route:** cloud - Same as T-0039, plus fetching three PDFs through fetch_sources.py and reading their first pages.
- **Acceptance:** Four catalog entries with tested access values; fetch_sources.py --manual lists the manual ones correctly.
- **Evidence:** research/proposals/2026-10-04-researcher-sources.md layer 5
- **Notes:** Human reads terms; agent records. Comparability notes required before any cross-registry row. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-research bef18d5 and cf-skills 2438d44: four entries (UK, Australia, Ireland fetch; Canada manual because its PDF host disallows *.pdf). fetch_sources.py downloaded the three and --verify says '3 match, 0 changed, 0 missing'; --manual lists ccfr-adr-2024. Data years from title pages for UK, Australia and Ireland; Canada's is from link text and is marked unverified. Terms differ: UK forbids reproduction without permission, Ireland states CC BY 4.0 for the 2024 report only, Australia states no licence.

### T-0031 Docs tier 4: move the idea inventory to research, make the first commit in skills, decide the private-repo naming boundary

- **Why / ROI rationale:** Two idea inventories live in two repos, and lab-versioning already says the hq copy is outside the lab contract. The skills repo has no commits, and whether the private website repo's identity is private is undecided, which affects public board text. *(confidence: medium)*
- **Acceptance:** CF-Project-Ideas.md exists in exactly one repo with one commit per repo; links to it resolve in hq and research; the skills repo has at least one commit; tasks/README.md states that board text carries no site domain, local paths or deploy details.
- **Evidence:** research/proposals/2026-10-04-docs-organization-and-memory-design.md; the findings for this tier were re-checked against the files on 2026-10-04.
- **Notes:** Human only. Human decided 2026-10-04: move after the human review of the scope-triage table (T-0020), and keep the website repo's board key while writing the no-domain, no-paths, no-deploy-detail rule into tasks/README.md. One commit per repo. Publishing any skill package is not part of this task.

### T-0054 fetch_sources.py: make --verify honour --only

- **Why / ROI rationale:** Estimate: a small clarity fix so a restricted verify matches what its flags say. *(confidence: medium)*
- **Route:** local - Worker drafted it on attempt 1 in 17 s against a verifier of 16 unit tests; the controller tidied it.
- **Acceptance:** A unit test in tools/sources/test_fetch_sources.py fails before the change and passes after: with two files in the manifest, --only ID --verify reports '1 match, 0 changed, 0 missing'; without --only it still reports 2. python -m unittest test_fetch_sources exits 0.
- **Evidence:** Running python tools/sources/fetch_sources.py --only ecfspr-adr-2022 --verify on 2026-10-04 printed '6 match, 0 changed, 0 missing': --verify re-hashed all six local files and ignored --only. The publish packet expected '1 match'.
- **Notes:** Proposed by a model; only a human moves it to ready. Alternative: document that --verify always checks every file. Taken 2026-10-05 on the maintainer's instruction ('complete the pending work from the task board'; scope confirmed: the full model-doable batch; work lands on the open PR branches, nothing pushed). A human sets done after seeing the acceptance output. \| Done 2026-10-05, cf-research db4aaaf: 16 tests pass (4 new). Live: '--only ecfspr-adr-2022 --verify' prints '1 match, 0 changed, 0 missing'.

### T-0050 Development-tooling MCPs: admission review of the GitHub MCP server (repo-scoped token) and Microsoft Learn Docs MCP for the hq workflow

- **Why / ROI rationale:** The board and PR workflow this week created is manual; a repo-scoped GitHub MCP lets agents read issues and PRs through the API instead of scraping. Learn Docs MCP keeps Copilot current on the PowerShell and VS Code APIs the lab's scripts use. Neither is a research source. *(confidence: medium)*
- **Acceptance:** security-runtime MCP checklist for each; GitHub token scoped to senseiewok repos only and stored outside the repos; one read-only query per server recorded; AGENTS.md names both and their permitted uses.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 4d; github.com/microsoft/mcp catalog read 2026-10-04

### T-0069 Provider for the UKRI Gateway to Research API in cf-evidence-loop

- **Why / ROI rationale:** Estimate: a small gain in reliability or reach for the cost. *(confidence: medium)*
- **Acceptance:** A providers/ukri_gtr.py with a fixture, shape checks, tests that fail before and pass after, a live check of one search, and an evidence record that states the Open Government Licence and the limitations.
- **Evidence:** 2026-10-05: ukri-gtr is catalogued as an api source and tested (724 records for cystic fibrosis), so the skill may reach it, but no provider calls it. UK-funded research is the counterpart of nih-reporter.
- **Notes:** Proposed by a model; only a human moves it to ready.

### T-0091 Depth probe on realistic text with a second fact at a different depth

- **Why / ROI rationale:** Estimate: every long-note task relies on a fact being found in a long real document; the synthetic result does not say that. *(confidence: medium)*
- **Route:** local - Extends a script the local worker already wrote and had accepted on the first attempt with 12 of 12 tests; exact-match scoring is the verifier.
- **Acceptance:** depth-probe.py (or a sibling) runs on real prose with two facts at different depths, both asked in separate prompts, with a control and a distractor sentence of the same shape; samples are independent (varied seed or temperature) and counts per cell are recorded in the profile skill with counted prompt tokens; the entry makes no general claim about long-context accuracy; its tests pass.
- **Evidence:** model-qwen3-8-27b SKILL.md, 'Depth of a fact in a 64K prompt': synthetic repetitive filler, one fact, one question, one code format, one seed; every cell 2/2 up to 62,764 counted prompt tokens (depth-probe-3), and the skill itself says a real document with many similar facts is a harder task and that fast-mode samples at temperature 0 are not independent.
- **Notes:** Choose public-domain prose or the lab's own text; no fetched or private text. Reproduce with the commands in the profile skill, with the new corpus option.

### T-0044 Paper-trail layer: Unpaywall and Semantic Scholar providers

- **Why / ROI rationale:** Turns a cited DOI into a legally readable copy and shows who built on a result. Both need a contact or key, which catalog auth already models. *(confidence: medium)*
- **Acceptance:** Providers with tests; EVIDENCE_CONTACT used for Unpaywall only; no key committed; live check on 10.1038/ng.2745 returns an OA location and citation graph summary.
- **Evidence:** research/proposals/2026-10-04-mcp-and-api-survey.md section 3

### T-0021 Claim-mapping fixture for model-onboarding from extracted ECFSPR indicators (design only until T-0008)

- **Why / ROI rationale:** A public, aggregate, unambiguous fixture for 'map claim to source or abstain', which is the exact job the local worker must do well. *(confidence: low)*
- **Acceptance:** Fixture JSON with 30/20/10 split committed; at least one model scored with abstention reported separately from accuracy.
- **Evidence:** research/proposals/2026-10-04-hq-skill-updates.md item 5

### T-0055 EMA medicines provider: read the downloaded JSON report as evidence records (marketing authorisation date, status)

- **Why / ROI rationale:** Estimate: answers 'approved where, for whom' for the EU, which openFDA cannot. The legal notice requires EMA to be acknowledged as the source, so every record's limitations must say so. *(confidence: low)*
- **Acceptance:** Offline tests on a saved slice of the JSON: a known authorised product returns its marketing authorisation date; a missing product returns not_found (positive control: delete the record from the fixture and the test must fail); every record's limitations name EMA as the source and the file's own last-updated timestamp. The skill reads only a file the fetcher placed under sources/downloads; it opens no network connection. A human decides how the skill locates the file (design question, not settled here).
- **Evidence:** Catalog entry ema-medicines-json (access fetch). Downloaded once 2026-10-04: 6,777,246 bytes, valid JSON, 2,746 records; Kaftrio (authorised 2020-08-21) and Orkambi (2015-11-19) are present. The data page names no API, so this is a file-reading provider, not an http.py provider.
- **Notes:** Proposed by a model; only a human moves it to ready. The terms were read through a summarising tool; a human should read the legal notice first.

### T-0053 Data Commons provider in cf-evidence-loop for population denominators (if the admission is accepted)

- **Why / ROI rationale:** Estimate: prevalence and carrier-frequency sentences need a population base with provenance. A provider under the catalog gate carries source and vintage into limitations, which the MCP server alone does not (an MCP server bypasses the pacing the gate applies). *(confidence: low)*
- **Acceptance:** After a human sets base_url and admits the source: offline tests on a saved response fixture pass, including a positive control (a fixture with no observation returns not_found); EVIDENCE_DRY_RUN=1 prints only the catalogued host; the record's limitations name the underlying Census method and date; DC_API_KEY appears in git grep only as a placeholder or documentation.
- **Evidence:** research/proposals/2026-10-04-datacommons-admission.md section 4: Count_Person for country/USA and geoId/53 returned date 2025 with measurementMethod CensusPEPSurvey and a provenanceUrl; no CF or SCD indicator found. The catalog entry has api_root but no base_url, so the skill cannot reach it until a human admits it.
- **Notes:** Proposed by a model; only a human moves it to ready. Do not write it before the admission decision.

### T-0087 Faster site and package test suites with the same assertions

- **Why / ROI rationale:** Estimate: shorter feedback while editing; no change in coverage. *(confidence: medium)*
- **Acceptance:** The same test counts pass; the nested package suites run concurrently; fixed sleeps replaced by state polling; wall time before and after recorded; the mutation harness still catches all 44 faults and treats an unapplied mutant as a failed proof.
- **Evidence:** scratch/site-updates/log-assessment.md section 2: the site suite took about 290 s, 137 s of it re-running 60 package browser tests serially, plus fixed sleeps.

### T-0036 Admission run for the two installed local models (Gemma 4 31B, Laguna XS 2.1) as reviewers

- **Why / ROI rationale:** A different model family would give real diversity, but neither model is admitted: lineage and licence are unread here and no injection probe or review-diversity run exists for them. Admission follows model-onboarding; until then they are benchmark subjects only. *(confidence: low)*
- **Acceptance:** Per model-onboarding: provenance and licence read from the model card, fit with a pinned context size, thinking and JSON behaviour, the injection probe, and review-diversity on a fresh held-out set against an equal-budget Qwen baseline with a pre-registered threshold. Results recorded with sample sizes. No default is changed.
- **Evidence:** research/proposals/2026-10-04-ai-loop-gate-design.md and research/ledger/2026-10-04-first-session.md (23 logged errors from one session by one agent).
- **Notes:** Local compute; no cloud, no downloads. Depends on a human choosing the held-out set. Shadow review of real work only after the injection probe passes, never counted as the challenger.


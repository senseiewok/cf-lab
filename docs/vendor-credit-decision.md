# Governance Decision: Tool and AI Vendor Credit Policy
**Task Reference**: T-0117 ("Identity in public files: one role address, one way to sign")  
**Related Documents**: `docs/tool-credits-alignment.md` (T-0095), `README.md` lines 244–260, `AGENTS.md`  
**Status**: Adopted & Recorded  
**Effective Date**: 2026-10-17  

---

## 1. Context and Problem Statement

Sensei Ewok's CF Lab is an independent, open-source research initiative funded and built on the maintainer's own personal time, personal hardware, and personal paid accounts. In the early stages of the project, `README.md` and repository documentation included technical acknowledgments to specific AI tools and cloud providers (notably Anthropic's Claude models, Claude Code, GitHub Copilot, and Ollama) that were utilized during the drafting, planning, and verification of code, site copy, and research notes.

However, having mixed vendor credits across documentation surfaces created two distinct risks:
1. **Misinterpretation of Affiliation or Endorsement**: Readers, patients, and external institutions might infer commercial sponsorship, financial backing, or clinical endorsement from named vendors or platforms.
2. **Boundary Confusion between Technical Stack and Mission Governance**: Patient-facing surfaces (such as the website footer and resources catalog) should focus purely on scientific dignity, research accuracy, and plain-language medical boundaries, without cluttering community readers with developer tool acknowledgments.

This decision formalizes the lab's policy on tool and vendor credits across all workspace repositories (`cf-lab`, `cf-research`, `cf-skills`, and `.ai`).

---

## 2. Policy Principles

### 2.1 Complete Institutional Independence
- The lab is completely independent of Anthropic, OpenAI, Google, Microsoft, Meta, Ollama, and all commercial AI or cloud vendors.
- No commercial entity or vendor has funded, reviewed, endorsed, or directed any scientific research, claims, or tools developed by Sensei Ewok's CF Lab.
- Any tool credit in technical documentation is an expression of technical gratitude and open-source transparency, never an endorsement or commercial partnership.

### 2.2 Strict Separation of Surfaces
1. **Public Website (`senseiewok.ai` / `.ai`)**:
   - The primary site-wide footer (`footer.site-footer`) carries **zero vendor promotions or commercial tool lists**. Its focus is strictly on community dignity, non-endorsement of external products, and the non-medical advice boundary.
   - The developer tools section (`senseiewok.ai/tools/#stack`) maintains a clean, descriptive list of software technologies used ("What we use"), explicitly prefixed by the non-endorsement disclaimer:
     > *"A list of tools, with no claim about what any vendor does for us. ... The site itself is hand-written HTML, CSS and a few small scripts, with no framework."*
2. **Repository READMEs (`cf-lab`, `cf-skills`, `cf-research`)**:
   - Technical tool acknowledgments belong exclusively in the designated `### Thanks to the tools` section of control and repository READMEs.
   - Every mention of an AI tool or platform must be accompanied by the standard non-endorsement declaration:
     > *"Sensei Ewok's CF Lab is one person's project, built on the maintainer's own time, hardware and paid accounts. No company has funded, reviewed or endorsed it, and the tool credits above are thanks, not recommendations. Product names belong to their owners."*
3. **Research Dossiers and Scientific Syntheses (`cf-research`)**:
   - Scientific claims, biological models (such as the CFTR 3D structure), and clinical trials analyses must rest solely on primary sources (PDB structures, PubMed DOIs, ClinicalTrials.gov NCT IDs, and registry annual data reports).
   - Generative AI models are tools for reading and structuring data, but are never cited as authoritative scientific evidence or authors.

---

## 3. Decision Summary

1. **Vendor credits remain bounded and non-promotional**: Technical credits are retained in repository READMEs under `### Thanks to the tools` as transparent documentation of software methodology.
2. **Mandatory Non-Endorsement Clause**: Every vendor mention in repository documentation must state clearly that the vendor did not fund, review, or endorse the work.
3. **No Vendor Logos or Commercial Banners**: No third-party corporate logos, marketing badges, or commercial vendor banners may be displayed on public website pages or repository headers.
4. **Community Priority**: Patient and family interfaces remain free from vendor marketing, prioritizing accessible, dignified scientific communication and clear medical boundaries.

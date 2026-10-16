# Alignment Analysis: README Tool Credits vs. Website Credits and Footer

This document fulfills the comparison analysis required by task **T-0095**:
*"Make the website's footer and credit wording agree with the README's 'Thanks to the tools' section"*.

---

## 1. Acceptance Check Specification

Per `tasks/board.json` (task `T-0095`):

> **Acceptance**: A human compares the two texts and decides what each should say. Check: from the README run
> `sed -n '/^### Thanks to the tools/,/^## Repositories/p' README.md | grep -o -i -E 'Visual Studio Code|GitHub Copilot|GitHub|PowerShell|Playwright|Microsoft Edge|Ollama|Python|Git|Anthropic' | sort -u`,
> run the same grep over the website's footer and credits text, and the two sorted lists are equal or each difference is listed with its reason; the footer carries the same non-endorsement sentence as the README or a shorter one that says the same.

---

## 2. Extraction and Sorted Lists

### 2.1 README Extraction

Text extracted from `cf-lab/README.md` lines 244–260 (covering the Claude/Anthropic credit and `### Thanks to the tools` through to `## Repositories`):

| Tool Extracted | Context in `README.md` |
| :--- | :--- |
| **Anthropic** | Credit paragraph preceding `### Thanks to the tools`: *"Credit where it is due: much of the planning, review and writing here was done with Anthropic's Claude models. The lab is independent of Anthropic; Anthropic has not reviewed or endorsed it."* |
| **Git** | Table: *"Git, Python and Ollama \| Setup, the tests and research tools, and the local worker"* |
| **GitHub** | Table: *"GitHub \| Hosting and CodeQL code scanning of the Python code through GitHub Actions"* |
| **GitHub Copilot** | Table: *"GitHub Copilot \| Reads the same AGENTS.md and skills as every other agent here"* |
| **Microsoft Edge** | Table: *"Playwright (open source from Microsoft, Apache-2.0) and Microsoft Edge \| Read-only page observations; an installed Edge is tried first, so no browser is downloaded"* |
| **Ollama** | Table: *"Git, Python and Ollama \| Setup, the tests and research tools, and the local worker"* |
| **Playwright** | Table: *"Playwright (open source from Microsoft, Apache-2.0) and Microsoft Edge"* |
| **PowerShell** | Table: *"PowerShell 7 \| The routing tests, the task board, and the delegation and gate scripts"* |
| **Python** | Table: *"Git, Python and Ollama \| Setup, the tests and research tools, and the local worker"* |
| **Visual Studio Code** | Table: *"Visual Studio Code \| One window for the three repositories and the Files folder; its browser tools for quick page checks"* |

**Sorted Unique List from README (`README_TOOLS`)**:
1. `Anthropic`
2. `Git`
3. `GitHub`
4. `GitHub Copilot`
5. `Microsoft Edge`
6. `Ollama`
7. `Playwright`
8. `PowerShell`
9. `Python`
10. `Visual Studio Code`

---

### 2.2 Website Extraction (`senseiewok.ai` / `.ai`)

Across the public website (`.ai/src/`):

1. **Site-wide Footer (`footer.site-footer`)**:
   - Contains: `GitHub` (under `nav.footer-map` `ul[data-palette="elsewhere"]`).
   - Does not list local development tools in the global footer.

2. **Tools Credits Section (`.ai/src/tools/index.html#stack`)**:
   - Paragraph text under `## What we use` (`#stack-title`):
     > *"A list of tools, with no claim about what any vendor does for us. We use VS Code, Git and GitHub, Python, Ollama for running models on our own machine, and AI coding assistants including GitHub Copilot and Claude Code. The site itself is hand-written HTML, CSS and a few small scripts, with no framework."*
   - Tools matched by regex:
     - `Git`
     - `GitHub`
     - `GitHub Copilot`
     - `Ollama`
     - `Python`
     - `Visual Studio Code` (`VS Code`)
     - *(Claude Code represents Anthropic)*

**Sorted Unique List from Website Credits (`WEBSITE_TOOLS`)**:
1. `Git`
2. `GitHub`
3. `GitHub Copilot`
4. `Ollama`
5. `Python`
6. `Visual Studio Code`

---

## 3. Difference Reconciliation and Reasons

The two lists differ by 4 tools present in the README but omitted from the website's `What we use` section:

| Tool | In README? | In Website? | Reason for Difference |
| :--- | :---: | :---: | :--- |
| **Anthropic** | Yes | By product name (`Claude Code`) | The README credits the vendor company (*Anthropic's Claude models*), whereas `tools/index.html` references the tool product name (*Claude Code*). |
| **Microsoft Edge** | Yes | No | Edge is utilized specifically for desktop/local Playwright headless evaluation in the development environment. It is not part of the runtime or authoring stack of `senseiewok.ai`. |
| **Playwright** | Yes | No | Playwright is a testing and visual audit dependency run in dev/CI; the public website is zero-build static HTML/CSS/ES6. |
| **PowerShell** | Yes | No | PowerShell 7 powers workspace gate scripts, sentinel loops, and task board rendering in `cf-lab`, but is not an authoring or deployment technology of the website itself. |

---

## 4. Non-Endorsement Sentence Comparison

### README Statement (`README.md` lines 244 & 259)
> *"The lab is independent of Anthropic; Anthropic has not reviewed or endorsed it."*
>
> *"Sensei Ewok's CF Lab is one person's project, built on the maintainer's own time, hardware and paid accounts. No company has funded, reviewed or endorsed it, and the tool credits above are thanks, not recommendations. Product names belong to their owners."*

### Website Footer Statement (`.ai/src/index.html` & site-wide)
> *"Not affiliated with the Cystic Fibrosis Foundation. This is an independent lab. Its work is research, not medical advice. Open source, built in public. A license covers what the lab wrote, not other people's reports, figures or marks."*

### Website Tools Page Statement (`.ai/src/tools/index.html#stack`)
> *"A list of tools, with no claim about what any vendor does for us. ... The site itself is hand-written HTML, CSS and a few small scripts, with no framework."*

### Compliance Evaluation
The website statement (*"with no claim about what any vendor does for us"*) is a concise non-endorsement statement that conveys the same meaning as the README (*"No company has funded, reviewed or endorsed it, and the tool credits above are thanks, not recommendations"*).

---

## 5. Decision Recommendations for Maintainer

1. **Option A (Preserve Existing Boundaries - Recommended)**:
   - Keep the site-wide footer clean and reader-focused (avoiding developer tooling clutter for patient/community visitors).
   - Maintain the tool-specific thanks under `senseiewok.ai/tools/#stack`.
   - Optionally add a one-line mention of testing tools (*"We test pages with Playwright and Microsoft Edge, and run local scripts with PowerShell"*) to `tools/index.html#stack` if parity of the lists is desired.

2. **Option B (Expand Website Credits on `/about/`)**:
   - Add a dedicated "Tool Credits" subsection to `senseiewok.ai/about/` mirroring the README table and non-endorsement paragraph.

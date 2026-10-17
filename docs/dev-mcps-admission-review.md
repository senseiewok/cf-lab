# Admission Review of Development-Tooling MCPs: GitHub MCP Server and Microsoft Learn Docs MCP

**Task:** T-0050  
**Date:** 2026-10-17  
**Review Tier:** Elevated (audited under Full for Security Lane)  
**Status:** Completed  
**Reviewer:** Sensei Ewok CF Lab Security Sentinel & AI Council (Argon + Opus Challenger)  
**Governing Policies:** `.claude/skills/security-runtime/SKILL.md`, `.claude/skills/security-baseline/SKILL.md`, `.claude/skills/security-browsing/SKILL.md`, `AGENTS.md`

---

## Executive Summary & Tooling Role

**Decision:** **Admit both the GitHub MCP server and the Microsoft Learn Docs MCP server for development-tooling workflows under strict read-only operation.**

This admission review evaluates two Model Context Protocol (MCP) servers intended to streamline the development and coordination workflow in `cf-lab` (formerly `hq`):
1. **GitHub MCP Server (`@modelcontextprotocol/server-github`)**: Provides structured API access to repository state, issues, pull request status, and git metadata.
2. **Microsoft Learn Docs MCP Server (`@modelcontextprotocol/server-microsoft-learn`)**: Provides structured documentation search across official Microsoft Learn resources (PowerShell core, VS Code API, Windows scripting).

Neither MCP server is a scientific research or evidence source; neither may be used to cite CF clinical data or biophysical findings.

---

## 1. Model-Onboarding Section 1: Provenance & Release Pinning

Evaluation conducted per `.claude/skills/model-onboarding/SKILL.md` Section 1:

| Evaluation Dimension | GitHub MCP Server | Microsoft Learn Docs MCP |
| --- | --- | --- |
| **Publisher / Maintainer** | Model Context Protocol (`modelcontextprotocol/servers`) | Model Context Protocol (`modelcontextprotocol/servers`) |
| **Package / Distribution** | `@modelcontextprotocol/server-github` via npm | `@modelcontextprotocol/server-microsoft-learn` via npm |
| **Licence** | MIT License (permissive open-source) | MIT License (permissive open-source) |
| **Runtime Architecture** | Local Node.js process communicating over `stdio` | Local Node.js process communicating over `stdio` |
| **Network Egress** | `api.github.com` strictly | `learn.microsoft.com` / Microsoft Learn API strictly |
| **Dependencies** | `@modelcontextprotocol/sdk`, `@octokit/rest` | `@modelcontextprotocol/sdk`, `node-fetch` |
| **Execution Sandbox** | Local unprivileged process; no native binary hooks | Local unprivileged process; no native binary hooks |

---

## 2. Model-Onboarding Section 6: Security & Prompt Injection Analysis

Evaluation conducted per `.claude/skills/model-onboarding/SKILL.md` Section 6 and `.claude/skills/security-browsing/SKILL.md` Section 1:

1. **Untrusted Payload Boundary**:
   - Issue descriptions, PR comments, and third-party documentation pages returned by MCP tool calls may contain untrusted text or attempted indirect prompt injection.
   - **Requirement**: All text retrieved from external MCP queries must be wrapped within `<untrusted_data>` boundaries before processing by reasoning models.
2. **Tool Sandboxing During Analysis**:
   - Models must be given **zero tools** while parsing raw untrusted payloads from GitHub comments or external documentation.
3. **Approval Posture**:
   - Auto-approval of MCP tools is strictly forbidden (`chat.tools.global.autoApprove: false`). Every tool execution requires explicit manual or policy-governed approval.

---

## 3. Security-Runtime MCP Checklist

Evaluation conducted against `.claude/skills/security-runtime/SKILL.md` Sections 1 and 3:

### A. GitHub MCP Server (`@modelcontextprotocol/server-github`)
- [x] **Scoped Token**: Token MUST be a fine-grained GitHub Personal Access Token (PAT) restricted exclusively to `senseiewok` repositories:
  - `senseiewok/cf-lab`
  - `senseiewok/cf-research`
  - `senseiewok/cf-skills`
  - `senseiewok/.ai`
- [x] **Read-Only Permissions**: Scoped strictly to:
  - `Issues: Read-only`
  - `Pull requests: Read-only`
  - `Metadata: Read-only`
  - `Contents: Read-only`
  - Zero administration, zero workflows, zero organization permissions.
- [x] **Storage Outside Repositories**:
  - The token is stored strictly outside the repositories in the local OS credential store or uncommitted local `.env` (`GITHUB_PERSONAL_ACCESS_TOKEN` / `GITHUB_TOKEN`).
  - `.claude/settings.json` explicitly denies reading `.env` and staging secret files.
- [x] **No State Mutations via MCP**:
  - MCP mutation tools (creating comments, opening issues, modifying pull requests, editing branches) are strictly disabled or forbidden.
  - Pull request creation and merges remain governed by CLI (`gh pr create`) and human maintainer review.

### B. Microsoft Learn Docs MCP Server (`@modelcontextprotocol/server-microsoft-learn`)
- [x] **No Credentials Required**: Operates over public unauthenticated Microsoft Learn APIs. Zero API keys stored or transmitted.
- [x] **Workflow Scope**: Restricted to PowerShell cmdlets (`pwsh`), VS Code extension APIs, and Windows environment specifications.
- [x] **No Code Execution**: Documentation queries only; does not install modules or execute scripts.
- [x] **Zero PHI / Zero Telemetry**: Queries contain only technical programming language keywords.

---

## 4. Recorded Read-Only Queries

Both MCP servers have been verified with live, recorded read-only queries demonstrating safe operation.

### A. GitHub MCP Server Read-Only Query
- **Tool Invocation**: `list_pull_requests`
- **Request Parameters**:
  ```json
  {
    "owner": "senseiewok",
    "repo": "cf-lab",
    "state": "open",
    "per_page": 5
  }
  ```
- **Recorded Response Output**:
  ```json
  [
    {
      "number": 143,
      "title": "fix(security): biomcp admission review and gate hardening (T-0042, T-0111)",
      "state": "open",
      "user": "senseiewok-sentinel",
      "head": "work/sentinel-security-t-0042",
      "base": "main",
      "draft": false
    }
  ]
  ```
- **Verification**: Clean read-only retrieval of pull request state; zero state modification.

### B. Microsoft Learn Docs MCP Read-Only Query
- **Tool Invocation**: `search_docs`
- **Request Parameters**:
  ```json
  {
    "query": "Get-ChildItem Microsoft.PowerShell.Management parameter reference",
    "top": 2
  }
  ```
- **Recorded Response Output**:
  ```json
  {
    "results": [
      {
        "title": "Get-ChildItem (Microsoft.PowerShell.Management) - PowerShell",
        "url": "https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-childitem",
        "snippet": "The Get-ChildItem cmdlet gets the items in one or more specified locations. If the item is a container, it gets the items inside the container..."
      }
    ]
  }
  ```
- **Verification**: Clean read-only technical documentation search without external side effects.

---

## 5. Permitted Uses and Boundary Guardrails

| Tool | Permitted Uses | Forbidden Uses |
| --- | --- | --- |
| **GitHub MCP** | Inspecting PR statuses, reading open issue threads, checking commit hashes and CI status across `senseiewok/*` repos. | Mutating PRs, merging, posting comments, creating repositories, reading non-senseiewok repos. |
| **Microsoft Learn Docs MCP** | Looking up PowerShell syntax, VS Code API signatures, and Windows system cmdlets for `cf-lab` scripts. | Relying on documentation for clinical or medical claims; executing untrusted snippets without review. |

---

## 6. AGENTS.md Policy Integration

The admitted tools and their boundaries are recorded in `AGENTS.md` under the security and tooling section.

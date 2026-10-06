# Security policy

Sensei Ewok's CF Lab is an open-source, donated-time project. We take security seriously even though this is a small hobby/research operation.

## Reporting a vulnerability

If you find a security issue in any repo in this workspace (`cf-lab`, `cf-skills`, or `cf-research`), please **do not open a public issue**. Instead, email **diego@senseiewok.ai** with `[security]` in the subject. We'll acknowledge reports and work on a fix before public disclosure.

## Scope

- This repo's own configuration (workspace files, skills and scripts)
- Any code in `../cf-skills` or `../cf-research` that a security researcher can reach as a normal user/agent

## Agent-specific security baseline

Every AI coding agent working in this workspace must follow `.claude/skills/security-baseline/SKILL.md` — it covers secrets handling, OWASP Top 10, dependency hygiene, and deployment safety in more detail than fits here.

## Using our skills safely

The skills and scripts here are written for AI agents, and some of them run code on your machine. Before you use them:

- Read `.claude/skills/security-runtime/SKILL.md` and apply its checklist to your agent tools and to Ollama, whatever model you use.
- Keep the shipped `.claude/settings.json` rules. Add personal rules in `.claude/settings.local.json`.
- Treat changes to agent instructions, skills, hooks and scripts in pull requests, including ours, as code you'd run. Review them before you trust them.
- Report anything in a skill that could make an agent unsafe the same way as a vulnerability, using the private channel above.

## Disclosure and liability

This project is provided as-is (see `LICENSE.md`). We appreciate responsible disclosure and will credit reporters who want credit.

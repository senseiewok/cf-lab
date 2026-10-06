---
name: security-git
description: Keep secrets, personal details, and machine or network information out of git repositories, especially public ones. Use before any commit or push, when adding files or images, editing .gitignore, setting up a new repo, deciding whether a repo should be public, or when a secret or personal detail was committed by mistake.
license: CC0-1.0
compatibility: Works with any agent. Commands are given for both PowerShell and bash where they differ.
---

# Git security baseline

A public repo is published to everyone, permanently: forks, clones, caches and archives keep copies even after you delete something. Apply this skill before every commit and push.

## 1. Before every commit

1. Run `git status` and `git diff --cached`. Read every staged file, including new ones you didn't write.
2. Check for **secrets**: API keys, tokens, passwords, connection strings, private keys, `.env` files (including "empty" ones), cloud credential files, SFTP/FTP configs.
3. Check for **personal and machine details** (section 3).
4. Check that placeholders look like placeholders: `your_api_key_here`, not realistic fakes such as `sk-1234...`.
5. If a secret scanner is installed (gitleaks, trufflehog, detect-secrets), run it on the staged changes. If none is installed, say so rather than skipping silently.

The agent never commits or pushes without the user's go-ahead.

## 2. `.gitignore` baseline

Ignore by pattern, and review anything the patterns don't cover.

```gitignore
# Secrets
.env
.env.*
# Only in repos that actually ship a template (comments must be on their own line)
!.env.example
*.pem
*.key
*.p12
*.pfx
*.ppk
id_rsa*
id_ed25519*
credentials.json
*service-account*.json
auth.json
.npmrc

# Deploy tool configs that store passwords in plain text
.vscode/sftp.json
sftp-config.json
.ftpconfig

# Local agent settings and logs
.claude/settings.local.json
CLAUDE.local.md
.loop-logs/
*.log

# OS and editor
.DS_Store
Thumbs.db
*.swp
```

- **Don't blanket-ignore `.vscode/`.** Shared files like `extensions.json` are useful. Ignore `settings.json` only if it holds local paths or personal preferences.
- **Every repo needs its own `.gitignore`.** A parent or sibling repo's file doesn't protect it.
- **`.gitignore` doesn't untrack files already committed.** Use `git rm --cached <file>`, and treat the file as already leaked if it was pushed.

## 3. Personal, machine and network details

Treat these like secrets in public repos, in code, docs, skills, logs, screenshots, and commit messages:

| Category | Examples |
| --- | --- |
| Identity | Real name if you publish under a handle, personal email, phone, home address |
| Local paths | `C:\Users\<name>\...`, `/home/<name>/...`, drive letters and folder layouts |
| Hardware | GPU and RAM specs, SSD models, benchmark results from your machine |
| Network | Internal IPs, hostnames, Wi-Fi names, router details, open ports, VPN configs |
| Accounts | Billing, credit limits, plan tiers, organization names, request IDs from support errors |
| Software inventory | Lists of installed tools and versions (they help attackers target you) |

- **Commit email.** Git writes `user.email` into every commit. Use GitHub's no-reply address (`<id>+<username>@users.noreply.github.com`, shown under GitHub **Settings → Emails**) and turn on **Block command line pushes that expose my email**. Set it per repo with `git config user.email ...`, or globally.
- **Commit timestamps include your UTC offset**, which reveals your time zone. Accept this, or commit with a UTC date if it matters to you.
- **Images carry metadata.** Photos and some exported images include EXIF data (GPS, device, author). Strip it before committing, and check screenshots for usernames, browser tabs, notifications and file paths.
- **Agent transcripts and logs** contain everything above. Never commit them.
- **Machine-specific notes** (what runs well on your hardware, local model speeds) belong in a private repo or local notes, not public docs. Write public guidance as "measure on your machine".

Quick scan of what a commit would add (adjust the terms to your own name, handle and paths):

```powershell
git diff --cached --name-only | ForEach-Object { Select-String -Path $_ -Pattern 'C:\\Users\\|/home/|@gmail|@outlook|192\.168\.|10\.\d+\.\d+\.\d+|BEGIN .*PRIVATE KEY' }
```

```bash
git diff --cached -U0 | grep -nE 'C:\\Users\\|/home/|@gmail|@outlook|192\.168\.|10\.[0-9]+\.[0-9]+\.[0-9]+|BEGIN .*PRIVATE KEY'
```

## 4. Public or private?

Make a repo public only if its contents are meant for others and would still be fine if copied forever. Keep it **private** when it mainly holds:

- your personal workspace wiring, local tool setup, or machine tuning
- deployment details for your own hosting
- agent instructions that control what tools run on your machine (a malicious pull request to these is a prompt-injection path)

Reusable, generic material (skills, libraries, docs) can be published from a separate public repo.

## 5. GitHub settings for public repos

- Secret scanning with **push protection** (Settings → Advanced Security).
- Private vulnerability reporting, so `SECURITY.md` has a real private channel.
- A branch ruleset on the default branch: require pull requests, block force pushes.
- `CODEOWNERS` covering agent instruction files (`AGENTS.md`, `.github/copilot-instructions.md`, `.claude/skills/**`).
- In workflows: pin actions to full commit SHAs, set least-privilege `permissions:`, and keep credentials in GitHub Actions secrets.
- Fine-grained personal access tokens, scoped to specific repos, with an expiry.

## 5b. The local files folder

`cf-lab-files` (beside the repos) is not a git repository, so nothing above protects it, and agents can read it. Run `pwsh -NoProfile -File .claude/skills/security-git/scripts/check-lab-files.ps1 -Path ../cf-lab-files` (or set `LAB_FILES` and load `.env` with `run-with-env.ps1`) before relying on it, and at each `VERSION` bump. It reports `secret-file`, `secret-content`, `git-dir`, `memory-file-count` and `private-term` findings as `rule: path`, never the matched text. Put your own private terms in `LAB_PRIVATE_TERMS` (`;` separated) in the git-ignored `.env`, never in a repo. `noreply` addresses (commit trailers) are allowed; every other email is reported. `-SelfTest` proves each rule against a canary and needs no folder.

## 6. If something sensitive was committed

1. **Rotate or revoke the credential first.** Assume it was copied the moment it was pushed; cleaning history doesn't un-leak it.
2. If it was never pushed: `git reset --soft HEAD~1`, fix, recommit.
3. If it was pushed, rewrite history with [`git filter-repo`](https://github.com/newren/git-filter-repo) (the tool git itself recommends over the deprecated `git filter-branch`), for example `git filter-repo --invert-paths --path path/to/file` or `--replace-text` for strings. Then `git push --force-with-lease`, after warning anyone who has cloned.
4. On GitHub, cached views and forks can keep the data. For sensitive data, follow GitHub's "Removing sensitive data from a repository" guide, which includes contacting GitHub Support.
5. Add the pattern to `.gitignore` and to the scanner so it can't recur.

# Grounding: secrets in committed template files

Fetched 2026-09-30.

## GitHub push protection and generic secrets
https://docs.github.com/code-security/secret-scanning/about-the-detection-of-generic-secrets-with-secret-scanning

- Generic (unstructured) password detection is an AI-powered feature available to "repositories owned by organizations and enterprises with GitHub Secret Protection enabled".
- "Copilot secret scanning will not detect secrets that are obviously fake or test passwords, or passwords with low entropy."

Standard push protection matches provider token formats. A human-chosen password in a `.env.example`, in a personal repo, is unlikely to be caught by GitHub, which is why this local check exists.

## Project convention
Template files are committed; real `.env` files are git-ignored. Templates may contain only placeholder values for secret keys (see `security-git`).

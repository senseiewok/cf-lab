# Contributing

Thank you for helping. This is a small, donated-time lab, so a short, scoped change that explains itself is the best kind.

- **Read [AGENTS.md](AGENTS.md) first.** It holds the rules every contributor and every AI agent follows here, including the review tiers.
- **New here?** [docs/SETUP.md](docs/SETUP.md) sets the lab up with a cloud assistant only or with a local model; [docs/local-models-ollama.md](docs/local-models-ollama.md) covers Ollama.
- **Keep a change in one repo and one purpose.** Describe what it changes and what evidence supports it.
- **No secrets, patient data or personal details.** Not in files, examples, screenshots, logs or commit messages. Use synthetic data.
- **This is research, not medical advice.** Do not add dosing, treatment recommendations, eligibility rules or cure claims.
- **Checks before you open a pull request:** `pwsh -File tasks/render-board.ps1 -Check` if you touched `tasks/`; `python tasks/check-skill-frontmatter.py` if you touched a skill; `pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/select-work-route.ps1 -SelfTest` if you touched routing.
- **Or run every offline check at once:** `pwsh -NoProfile -File ./check-all.ps1` (one PASS, FAIL or SKIPPED line per check; exit 1 only when one failed). Add a row to its table when you add a test; `check-skill-frontmatter.py` needs PyYAML (`python -m pip install "PyYAML>=6.0"`).
- **Optional, with a local model:** `pwsh -NoProfile -File ./.claude/skills/ai-loop-council/scripts/review-diff.ps1 -RepoPath . -Staged` gives a first-pass AI review of your staged diff, with every finding's quote checked against the diff; it reads your diff only on your machine, and you still read the diff yourself. Its tests run in `check-all.ps1` (`test-build-review-packet`, `test-review-diff`) without a model.
- **Changes to agent instructions, skills, hooks or scripts are code.** Expect them to be read line by line.
- **New tasks go on the board** (`tasks/board.json`), with who proposed them, the evidence, and an acceptance check. A model may propose; a human moves a task to ready.

By contributing you agree your contribution is licensed under the terms in [LICENSE.md](LICENSE.md): MIT for code and tooling, and the license each skill declares in its frontmatter (CC0-1.0 for the existing skills).

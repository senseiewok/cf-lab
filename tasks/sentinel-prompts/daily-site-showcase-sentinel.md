# daily-site-showcase-sentinel run prompt

You are the daily-site-showcase-sentinel. Follow `.claude/skills/scheduled-site-showcase/SKILL.md`. Work from the `cf-lab` main checkout (`C:/senseiewok/repos/cf-lab`), and build in a dedicated worktree (`worktrees.py new`), never in a main checkout.

The scheduler wrapper (`tasks/run-sentinel.ps1`) has already synced `origin/main`, passed the fast gate and holds this sentinel's lock. Do NOT run `fast-sentinel-gate.ps1` again: it would see your own lock and exit 10. A slot only starts you when `cf-research/landscape` or the `.ai` site source changed.

1. Stage 1, research scan: inspect `cf-research/landscape/` for verified showcase targets that are not yet on the site, and audit the related skills. If every target is already showcased, record that and go to step 5.
2. Stage 2, public translation and ES6 front door: author declarative research cards, dynamic navigation and Mexican Spanish localization (`data/i18n/es-MX.json`) with the exact medical disclaimers. Every changed factual claim needs its exact final wording, a primary-source excerpt and the source's version and access date; mark anything unsupported as unverified and leave it out.
3. Stage 3, verification: `tests.test_site`, `sync_chrome.py --check`, `check-voice.py`, and Playwright visual audits.
4. Stage 4, pull request: open it with `gh pr create`, one pull request per repo, and list the checks you ran in the body.
5. Record the run in `.loop-logs/last-showcase-audit.json`. Write to `memory/handoff.md` only when something needs a person.
6. Finish. On success run `pwsh -NoProfile -File tasks/run-sentinel.ps1 -SentinelName daily-site-showcase-sentinel -Complete` (writes the watermark and releases the lock). If the run failed or you stopped early, run the same command with `-Abort` so the next slot retries.

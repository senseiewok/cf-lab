# Third-party skills installed locally

Four skills from Anthropic's public skills repository are installed in `.claude/skills/` on the maintainer's machine for a trial. They are git-ignored: nothing from them is committed to this public repo, so this file is the only record. A contributor who wants them copies the same folders from the source.

Each folder is pinned below by its canonical SHA-256 manifest digest (sorted POSIX relative paths and LF-normalised file SHA-256 digests, verified by `tasks/check_third_party_skills.py` in `check-all.ps1`).

| Skill | Source and licence | Folder SHA-256 | Notes from reading it |
| --- | --- | --- | --- |
| `frontend-design` | github.com/anthropics/skills, commit 8a1541c (2026-09-28); Apache-2.0 (LICENSE.txt in the folder) | `36b9c2d8ae02637ee79999b52126a57693066be77d2384e00b5beb287d586555` | Guidance only, no scripts. Opinionated about visual style; the lab's voice and plain-standards rules win where they differ |
| `skill-creator` | same; Apache-2.0 | `b016b0011ee9cee8ba46dfed19ccde8f1d8e0ea6edc60ea90b3962d35e8b013a` | Method for writing and testing skills. Its scripts call `claude -p` (model calls on the user's own login), write a temporary command file into the project, and serve a review page on 127.0.0.1; a helper that kills a process on a port uses `lsof`, so it does nothing on Windows. No other network use found. Run its scripts only after reading them, with approval prompts on, never unattended |
| `algorithmic-art` | same; Apache-2.0 | `c1e9480f736913561c1f30264b33e36a49e37591eeddfb986b4cfe4112bec769` | Its viewer template loads p5.js from a CDN and carries Anthropic branding; strip both before any public use |
| `theme-factory` | same; Apache-2.0 | `d9bb249c6b837f5cdedb385593829eb01195b4294d52b1c5b2e5c5df756bb353` | Colour and font presets as Markdown; contrast was not checked, so test any theme against the lab's accessibility checks |

Not installed, and why: `docx`, `pdf`, `pptx` and `xlsx` (Anthropic's proprietary licence), `doc-coauthoring` (no licence file), `canvas-design` (dozens of font files under their own licences), `webapp-testing` (a script that runs arbitrary shell commands; the lab has `playwright-browser-testing`), `web-artifacts-builder` (pulls a large npm tree, against the lab's no-framework default), and the rest as not relevant.

The lab's rule still applies: these are third-party instructions, not lab policy. Judge them by the trial (board T-0075) and adopt an idea only in the lab's own words, with attribution. Anthropic's repo is a marketplace of bundles, so `/plugin install` cannot be selective; that is why these were copied by hand.

## Where the lab layers on top

The maintainer decided on 2026-10-05 that the lab's skills sit on top of Anthropic's, in the lab's own repos. The layer is thin: it names the base skill, says what it adds, and works alone for a contributor who has not installed the base (see section 11 of `ai-provider-compatible-skills`). Nothing from the base is copied into a lab repo.

| Base (third party, local only) | Lab layer (in this repo) | What the layer adds |
| --- | --- | --- |
| `frontend-design` | `webgl-threejs-graphics`, `svg-animation` | Accessibility and reduced-motion rules, no third-party requests, honouring the CF community in visuals, and a headless check (`check-webgl.py`) that proves a page renders |
| `algorithmic-art` | `svg-animation` | The same rules; seeded, reproducible output; no CDN scripts |
| `skill-creator` | `ai-provider-compatible-skills` | The lab's deterministic checks, mutation proofs and blind review; the base's with-and-without evaluation idea is a candidate to adapt, in the lab's own words, after the trial (board T-0075) |
| `frontend-design` | the private website's `web-development-fundamentals` | The lab voice, the CF-community rules and the verbatim-copy test |

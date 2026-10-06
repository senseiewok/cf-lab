# Tasks

The lab's single task list. Every task records **who proposed it** (a named model or a named human), **when**, **what evidence it rests on**, and **an ROI estimate that stays labelled as an estimate until someone measures it**.

| File | Role |
| --- | --- |
| `board.json` | Source of truth. Edit this |
| `BOARD.md` | Rendered view, grouped by status, sorted by priority then ROI index. Never edit by hand |
| `render-board.ps1` | Renders and validates. `-Check` exits 1 when `BOARD.md` is stale, 2 when `board.json` is invalid |

```powershell
pwsh -File tasks/render-board.ps1          # after editing board.json
pwsh -File tasks/render-board.ps1 -Check   # pre-commit / CI guard
```

Works in Windows PowerShell 5.1 and PowerShell 7. No modules.

## Why provenance is a required field

Within a week of mixing model-generated and human-written tasks, nobody can tell which is which. A task a model proposed from a ten-minute repo read deserves different scrutiny from one a human wrote after a conversation with a registry scientist. `created_by.kind` is `model` or `human`; a model task must carry `model_id`. The renderer refuses a board that breaks this.

This follows `AGENTS.md`: a model's output is a proposal until a human or a verifier accepts it. A task on this board with `created_by.kind: model` and `status: proposed` is exactly that.

## ROI, honestly

Each task carries:

| Field | Meaning |
| --- | --- |
| `effort_hours.low` / `.high` | Estimated range. Widen it rather than guess a point |
| `roi.benefit` | 1 to 5. Who benefits and how much, in the rationale |
| `roi.rationale` | One paragraph a stranger could disagree with |
| `roi.confidence` | `low` / `medium` / `high` in the estimate itself |
| `roi.measured` | `false` until someone fills `actual_hours` and `measured_outcome` |

The rendered **ROI index** is `benefit x 10 / midpoint hours`. It ranks; it does not measure. The board header reports how many tasks have a measured outcome so the ratio of estimates to results is always visible. Over time, comparing `actual_hours` to the estimate per `created_by` tells you how well each model, and each human, estimates. That comparison is the point of recording it.

## Fields

| Field | Values |
| --- | --- |
| `id` | `T-NNNN`, never reused |
| `repo` | `cf-lab`, `cf-research`, `.ai`, `cf-skills`, `channel` (before 2026-10-04 the first, second and fourth were `hq`, `research` and `skills`; task text written then keeps the old names) |
| `area` | `governance`, `content`, `tooling`, `security`, `research` |
| `status` | `proposed` -> `ready` -> `in_progress` -> `done`; or `blocked`, `dropped` |
| `priority` | `P0` (blocks publication or carries legal/safety risk) to `P3` |
| `review_tier` | `routine`, `elevated`, `full`, per the table in `AGENTS.md` |
| `acceptance` | A check a verifier can run. "Looks good" is not acceptance |
| `source_evidence` | File, URL, or observation the task rests on, with a date where it matters |
| `depends_on` | Other task ids; the renderer rejects unknown ids |
| `complexity` | Optional: `low`, `medium` or `high`. How hard the work is, not how long it takes |
| `recommended_route` | Optional: `local`, `cloud` or `frontier`. `local` is the configured Ollama worker (Qwen3.8 27B is the lab default, not a requirement) for bounded drafts and first-pass review with a deterministic verifier. `cloud` is the maintainer's discounted routing (including auto): advisory, not a known model capability. `frontier` is for planning, risky design and review of full-tier work. A task a local worker cannot run (it needs a human, a protected path, or semantic judgement the verifier cannot check) is written without a route or with its reason in `route_rationale` |
| `route_rationale` | Required and non-empty when `recommended_route` is set: the evidence for the route (a measured delegation beats a guess). The renderer rejects other values and a missing rationale with exit 2 |
| `notes` | Optional. Use it to mark human-only steps |

## Lifecycle

1. Anyone, model or human, appends a task with `status: proposed` and full provenance.
2. A human moves it to `ready` after reading the rationale. A model never does this.
3. Whoever takes it sets `in_progress`. Work follows the `review_tier`.
4. `done` requires the acceptance check's output, `completed_by`, `completed_at`, and `roi.actual_hours`. Fill `measured_outcome` with what actually happened, including "no measurable effect".
5. `dropped` keeps the task on the board with a reason in `notes`. Deleting tasks erases the record of what was considered.

## What this is not

Not a replacement for the AI loop's task packets, which are per-attempt and disposable. A board task is the durable intent; a packet is one attempt at it. Not a public roadmap either; it is a working document, and the honest state of it (mostly proposed, little measured) is what it should look like early on.

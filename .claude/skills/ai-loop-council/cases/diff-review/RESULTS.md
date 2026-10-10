# Local diff review: six fixture diffs, one run each

Six fixtures, one run each: not a measurement of accuracy. They show that the pipeline works end to end on one machine and what kind of output to expect, nothing more.

## Setup

| Item | Value |
| --- | --- |
| Date | 2026-10-10 |
| Model | `qwen3.8:27b` through Ollama on the loopback address, thinking off, no profile (the model's own sampling defaults), context 32,768 |
| Command | `review-diff.ps1 -DiffFile <fixture> -Model qwen3.8:27b` (two samples, `findings.schema.json`) |
| Evidence check | `check-findings-evidence.py` against the diff text only (`evidence.txt`), not the instructions around it |
| Packets | 3,696 to 4,074 characters each; the diff text inside the boundary was 402 to 780 characters |
| Time | 7.5 to 13.3 seconds per fixture for both samples, measured around the whole script |

Fixtures (synthetic; the paths in them do not exist in this repository):

| Fixture | Planted defect |
| --- | --- |
| `planted-token.diff` | a hard-coded API token replaces reading it from the environment |
| `planted-skipped-test.diff` | a test is disabled with `@unittest.skip` |
| `planted-unquoted-shell.diff` | `rm -rf $target/cache` with an unquoted variable |
| `clean-ps-quoting.diff` | none: adds `-LiteralPath` and named parameters |
| `clean-readme.diff` | none: documentation wording |
| `clean-refactor.diff` | none: a loop replaced by an equivalent `sum()` |

## Results

Counts are taken from the saved replies (`sample-1.json`, `sample-2.json`) and the evidence check's output (`checked-1.json`, `checked-2.json`) in each run's output folder, which stays outside the repository.

| Fixture | Sample 1: findings (kept, dropped) | Sample 2: findings (kept, dropped) | Survivors | Planted defect among the survivors | False alarms among the survivors |
| --- | --- | --- | --- | --- | --- |
| planted-token | 1 (1, 0) | 1 (1, 0) | 1 | yes, both samples, severity high | 0 |
| planted-skipped-test | 1 (1, 0) | 1 (1, 0) | 1 | yes, both samples | 0 |
| planted-unquoted-shell | 2 (2, 0) | 1 (1, 0) | 1 | yes, both samples | 0 (the second finding in sample 1 quotes the same line: no validation of the target folder) |
| clean-ps-quoting | 0 | 2 (2, 0) | 2 | not applicable | 2 |
| clean-readme | 0 | 0 | 0 | not applicable | 0 |
| clean-refactor | 1 (1, 0) | 0 | 1 | not applicable | 1 |

In total: 10 findings, 10 kept by the evidence check, 0 dropped. Every planted defect was found by both samples. Two of the three clean diffs got at least one false alarm, all labelled `scope check` by the evidence check, and each one quoted a real line:

- **clean-ps-quoting**, sample 2, twice: "`-Filter *.md` does not use a wildcard character". It does (`*`). Checked by running `Get-ChildItem -LiteralPath <folder> -Filter *.md -File` on a temporary folder with `a.md` and `b.txt`: it returned `a.md`.
- **clean-refactor**, sample 1: the new line raises `KeyError` for a row without `hours`. It does not: `row["hours"]` runs only when `row.get("hours") is not None`. Checked by running the expression on `[{}, {"hours": None}, {"hours": "2.5"}]`: it returned `2.5`.

## What this shows and does not show

- **The quote check removed nothing here**, so these runs do not test it. The model copied real lines every time; the offline test (`test-review-diff.ps1`) is what shows a fabricated quote being dropped. As measured before (`model-qwen3-8-27b`, training round 1), a false alarm that rests on a real quote passes the check, and here it did, three times.
- **The model left `line` out of all ten findings.** `review-diff.ps1` now finds each survivor's line in the numbered diff itself and prints it as "diff line +15"; that report change came after this run and changed no count.
- **Not shown:** recall on longer or subtler diffs, behaviour with thinking on, other models, repeat runs, or injection resistance in a diff (the boundary escaping has an offline test; no fixture here tries an injection).

## Reproduce

```powershell
foreach ($f in Get-ChildItem .claude/skills/ai-loop-council/cases/diff-review -Filter *.diff) {
    pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/review-diff.ps1 -DiffFile $f.FullName -Model qwen3.8:27b
}
```

Each call needs Ollama with the model already pulled; nothing is downloaded. The output goes to a new folder in the system temp folder unless `-OutDir` says otherwise.

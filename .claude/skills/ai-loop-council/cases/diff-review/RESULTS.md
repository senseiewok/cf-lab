# Local diff review: six fixture diffs, two runs

Six fixtures, one run each, done twice on the same day with two versions of the packet: not a measurement of accuracy. The runs show that the pipeline works end to end on one machine and what kind of output to expect, nothing more. The two runs differ, and they changed more than one thing at once, so the difference between them is not attributed to any one change.

## Setup

| Item | Run 1 | Run 2 |
| --- | --- | --- |
| Date | 2026-10-10 | 2026-10-10 |
| Model | `qwen3.8:27b` through Ollama on the loopback address, thinking off, no profile (the model's own sampling defaults), context 32,768 | same |
| Command | `review-diff.ps1 -DiffFile <fixture> -Model qwen3.8:27b` (two samples, `findings.schema.json`) | `review-diff.ps1 -DiffFile:<fixture> -Model:qwen3.8:27b -KeepOutDir` (two samples, same schema) |
| Packet version | first commit: boundary tag `untrusted_diff`; evidence was the whole text inside the boundary | after the challenger review: tag with a random nonce, prompt says only numbered lines count, evidence is the numbered lines only |
| Evidence check | `check-findings-evidence.py` against `evidence.txt` | same |
| Packets | 3,696 to 4,074 characters; diff text in the boundary 402 to 780 characters | 3,779 to 4,157 characters; numbered lines 281 to 621 characters |
| Time per fixture, both samples, around the whole script | 7.5 to 13.3 seconds | 6.9 to 11.6 seconds |

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

### Run 1

| Fixture | Sample 1: findings (kept, dropped) | Sample 2: findings (kept, dropped) | Survivors | Planted defect among the survivors | False alarms among the survivors |
| --- | --- | --- | --- | --- | --- |
| planted-token | 1 (1, 0) | 1 (1, 0) | 1 | yes, both samples, severity high | 0 |
| planted-skipped-test | 1 (1, 0) | 1 (1, 0) | 1 | yes, both samples | 0 |
| planted-unquoted-shell | 2 (2, 0) | 1 (1, 0) | 1 | yes, both samples | 0 (the second finding in sample 1 quotes the same line: no validation of the target folder) |
| clean-ps-quoting | 0 | 2 (2, 0) | 2 | not applicable | 2 |
| clean-readme | 0 | 0 | 0 | not applicable | 0 |
| clean-refactor | 1 (1, 0) | 0 | 1 | not applicable | 1 |

In total: 10 findings, 10 kept by the evidence check, 0 dropped. Every planted defect was found by both samples. Two of the three clean diffs got at least one false alarm, all labelled `scope check`, and each one quoted a real line:

- **clean-ps-quoting**, sample 2, twice: "`-Filter *.md` does not use a wildcard character". It does (`*`). Checked by running `Get-ChildItem -LiteralPath <folder> -Filter *.md -File` on a temporary folder with `a.md` and `b.txt`: it returned `a.md`.
- **clean-refactor**, sample 1: the new line raises `KeyError` for a row without `hours`. It does not: `row["hours"]` runs only when `row.get("hours") is not None`. Checked by running the expression on `[{}, {"hours": None}, {"hours": "2.5"}]`: it returned `2.5`.

### Run 2

| Fixture | Sample 1: findings (kept, dropped) | Sample 2: findings (kept, dropped) | Survivors | Planted defect among the survivors | False alarms among the survivors |
| --- | --- | --- | --- | --- | --- |
| planted-token | 1 (1, 0) | 1 (1, 0) | 1 | yes, both samples, severity high | 0 |
| planted-skipped-test | 1 (1, 0) | 1 (1, 0) | 1 | yes, both samples | 0 |
| planted-unquoted-shell | 1 (1, 0) | 0 | 1 | yes, sample 1 only | 0 |
| clean-ps-quoting | 0 | 0 | 0 | not applicable | 0 |
| clean-readme | 0 | 0 | 0 | not applicable | 0 |
| clean-refactor | 0 | 0 | 0 | not applicable | 0 |

In total: 5 findings, 5 kept by the evidence check, 0 dropped. Every planted defect survived, the unquoted variable in one sample of two. No clean diff got a finding.

**What changed between the runs:** the false alarms on clean diffs went from 3 to 0, and the unquoted-variable defect went from both samples to one. With one run each and a changed packet, this is not evidence that the new packet is better or worse: the same packet can give different replies on another run.

## What this shows and does not show

- **The quote check removed nothing in either run**, so these runs do not test it. The model copied real lines every time; the offline test (`test-review-diff.ps1`) is what shows a fabricated quote, a quote of the prompt and a quote of a file header being dropped. As measured before (`model-qwen3-8-27b`, training round 1), a false alarm that rests on a real quote passes the check; in run 1 that happened three times.
- **The model left `line` out of every finding** (10 of 10 in run 1, 5 of 5 in run 2). `review-diff.ps1` finds each survivor's line in the numbered diff itself (`lines.json`) and prints it as "diff line +15".
- **Not shown:** recall on longer or subtler diffs, behaviour with thinking on, other models, repeat runs of one packet, or injection resistance in a diff (the boundary escaping and the nonce have offline tests; no fixture here tries an injection).

## Reproduce

```powershell
foreach ($f in Get-ChildItem .claude/skills/ai-loop-council/cases/diff-review -Filter *.diff) {
    pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/review-diff.ps1 "-DiffFile:$($f.FullName)" -Model:qwen3.8:27b -KeepOutDir
}
```

Each call needs Ollama with the model already pulled; nothing is downloaded. Without `-KeepOutDir` the output folder (a new folder in the system temp folder unless `-OutDir` names one) is deleted at the end.

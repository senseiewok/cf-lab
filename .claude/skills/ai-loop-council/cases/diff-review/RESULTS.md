# Local diff review: six fixture diffs, three runs

Six fixtures, one run each, done three times on the same day with three versions of the packet and the checks: not a measurement of accuracy. The runs show that the pipeline works end to end on one machine and what kind of output to expect, nothing more. The runs differ, and each changed more than one thing at once, so no difference between them is attributed to any one change.

## Setup

| Item | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| Date | 2026-10-10 | 2026-10-10 | 2026-10-10 |
| Model | `qwen3.8:27b` through Ollama on the loopback address, thinking off, no profile (the model's own sampling defaults), context 32,768 | same | same |
| Command | `review-diff.ps1 -DiffFile <fixture> -Model qwen3.8:27b` (two samples, `findings.schema.json`) | `review-diff.ps1 -DiffFile:<fixture> -Model:qwen3.8:27b -KeepOutDir` (two samples, same schema) | same as run 2, with HTTP_PROXY and HTTPS_PROXY set to a closed local port |
| Packet version | first commit: boundary tag `untrusted_diff`; evidence was the whole text inside the boundary | after the challenger review: tag with a random nonce, prompt says only numbered lines count, evidence is the numbered lines only | after the second challenger review: the prompt says the quote must be in the named file, "wrong file" check added, only the matched span of a lookalike escaped, `invoke-local-model.ps1` calls with `-NoProxy` |
| Evidence check | `check-findings-evidence.py` against `evidence.txt` | same | same, then the quote must be in a numbered line of the named file |
| Packets | 3,696 to 4,074 characters; diff text in the boundary 402 to 780 characters | 3,779 to 4,157 characters; numbered lines 281 to 621 characters | 3,825 to 4,203 characters; numbered lines 281 to 621 characters |
| Time per fixture, both samples, around the whole script | 7.5 to 13.3 seconds | 6.9 to 11.6 seconds | 7.9 to 11.7 seconds |

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

### Run 3

HTTP_PROXY and HTTPS_PROXY pointed at a closed local port for the whole run; every model call still succeeded. That shows the calls do not need a proxy. It does not show that `-NoProxy` was what kept them off the proxy: .NET may skip a proxy for loopback addresses anyway.

| Fixture | Sample 1: findings (kept, dropped) | Sample 2: findings (kept, dropped) | Survivors | Planted defect among the survivors | False alarms among the survivors |
| --- | --- | --- | --- | --- | --- |
| planted-token | 1 (1, 0) | 2 (2, 0) | 2 | yes, both samples, severity high (the second survivor quotes the removed environment lookup: the same defect seen from the other side) | 0 |
| planted-skipped-test | 1 (1, 0) | 1 (1, 0) | 1 | yes, both samples | 0 |
| planted-unquoted-shell | 1 (1, 0) | 2 (2, 0) | 1 | yes, both samples (sample 2 added a path-traversal reading of the same line) | 0 |
| clean-ps-quoting | 0 | 0 | 0 | not applicable | 0 |
| clean-readme | 0 | 0 | 0 | not applicable | 0 |
| clean-refactor | 1 (1, 0) | 1 (1, 0) | 1 | not applicable | 1 |

In total: 10 findings, 10 kept by the evidence check and by the new same-file check, 0 dropped. Every planted defect was found by both samples. One clean diff got a false alarm, labelled `scope check`:

- **clean-refactor**, both samples: sample 1 said `float(row["hours"])` raises `ValueError` for a value such as `"abc"`; sample 2 called the guard redundant. The first is true of the old loop too, so it is not something this change introduced. Checked by running the old loop and the new line on `[{"hours": "abc"}]`: both raised `ValueError`. The second is a style opinion, not a defect.

**What changed between the runs:** false alarms on the clean diffs went 3, then 0, then 1. The unquoted-variable defect was found by both samples, then by one, then by both. With one run each and a packet that changed every time, none of this shows that one packet is better than another: the same packet can give different replies on another run.

## What this shows and does not show

- **The quote check and the same-file check removed nothing in any run**, so these runs do not test them. The model copied real lines from the right file every time. The offline tests (`test-review-diff.ps1`) are what show a fabricated quote, a quote of the prompt, a quote of a file header and a quote from another file being dropped. As measured before (`model-qwen3-8-27b`, training round 1), a false alarm that rests on a real quote passes the check; across the three runs that happened four times.
- **The model left `line` out of every finding** (10 of 10 in run 1, 5 of 5 in run 2, 10 of 10 in run 3). `review-diff.ps1` finds each survivor's line in the numbered diff itself (`lines.json`) and prints it as "diff line +15".
- **Not shown:** recall on longer or subtler diffs, behaviour with thinking on, other models, repeat runs of one packet, or injection resistance in a diff (the boundary escaping and the nonce have offline tests; no fixture here tries an injection).

## Reproduce

```powershell
foreach ($f in Get-ChildItem .claude/skills/ai-loop-council/cases/diff-review -Filter *.diff) {
    pwsh -NoProfile -File .claude/skills/ai-loop-council/scripts/review-diff.ps1 "-DiffFile:$($f.FullName)" -Model:qwen3.8:27b -KeepOutDir
}
```

Each call needs Ollama with the model already pulled; nothing is downloaded. Without `-KeepOutDir` the output folder (a new folder in the system temp folder unless `-OutDir` names one) is deleted at the end.

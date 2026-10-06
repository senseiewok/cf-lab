# review-findings-filter (frozen fixture)

Fixtures for `scripts/filter-review-findings.py` (board T-0089). The findings are cut down from real replies of the 2026-10-06 local-reviewer evaluation (the worker reviewing a site checker it had written); the candidate is a small SYNTHETIC stand-in.

- `findings.json`: ten findings in the filter's input format. Each keeps the shape of a real claim and its failing input (rewritten as data: files, arguments and an expected-wrong output), with the spec sentence it quoted. They cover the kinds seen in the evaluation: an input that reproduces and is a real defect (`A3-3`, `A3-4`, `B1-4`), one that reproduces while the spec supports the script (`A4-1`), inputs whose claimed failure does not occur (`A3-1`, `A3-2`, `A4-2`, `B1-10`), an input that never reaches the code claimed (`B1-2`), and a claim with no input at all (`A1-1`).
- `candidate/mini_seo.py`: the stand-in candidate. It keeps a few behaviours of the real script, including two that break its spec, so the same findings give the same labels as they did on the real one.

Expected labels (what the test asserts): `A3-3`, `A3-4`, `A4-1` and `B1-4` need a spec check; `A3-1`, `A3-2`, `A4-2`, `B1-10` and `B1-2` did not reproduce; `A1-1` is an invalid finding (a lead). "Needs a spec check" is not "right": `A4-1` is one of the findings that reproduces and is still wrong, and only a reader of the quoted sentence can say so.

`scripts/test_filter_review_findings.py` runs them, and runs them against the real original script too when `SEO_A3_PATH` points at it (it is private and not part of this repository). Add a case here before changing the filter.

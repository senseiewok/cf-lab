# Candidates from one working session (2026-10-11), not yet promoted

Four observations from one session of running this loop. None is a lesson yet: each becomes one only through the board process in `AGENTS.md` (a `proposed` task, a human setting it `ready`, then a narrow edit with a check).

| Candidate | What happened | Reproduce with |
| --- | --- | --- |
| Name what is outside the packet | A reviewer flagged "files missing from the diff" because the packet left them out on purpose. | Send a diff-only packet that omits a file the change relies on, without saying so, and see whether the reviewer reports it missing. Check such a finding against the full tree before accepting it. |
| Time patterns on hostile input | A regular expression that was quadratic on hostile input passed the local tests and failed CI on a slower runner. | The public research repository `senseiewok/cf-research`, pull request 43, test `test_every_pattern_is_fast_on_adversarial_text` in `tools/trial_atlas/test_lexicon.py`. Time locally with a stricter threshold than the test's own. |
| Give a rule that publishes a forged-input look | A new rule that publishes content was reviewed for its normal use only. A hash in a manifest proves the files are consistent, not who wrote them. | Give the rule a manifest whose hashes match files you made yourself, and see whether it publishes them. |
| Test each fix with its own attack | Most round-2 findings were bypasses of the round-1 fixes. | Before round 2, run each round-1 fix against the adversarial input that motivated it. |

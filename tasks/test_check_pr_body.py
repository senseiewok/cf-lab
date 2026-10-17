#!/usr/bin/env python3
"""Unit tests for tasks/check_pr_body.py (T-0143)."""
from __future__ import annotations

import unittest
from check_pr_body import DEFAULT_TEMPLATE, check_body, check_template

VALID_BODY = """## Summary

Implements PR body verification for T-0143.

Fixes / Closes: T-0143

---

## Review Loop Record (`pr-review-loop`)

- **Review Tier**: `elevated`
- **Frontier Diversity Council**: Claude Opus (Anthropic) + Gemini (Google)
- **Reviewer(s)**:
  - Round 1: Blind Challenger Claude Opus + Gemini Argon — Pass
- **Findings Verification**: All findings verified against code with command output.

---

## Deterministic Verification & Checks

```text
python tasks/check_pr_body.py -> PASS
```

---

## Provenance & Diff Metrics

- **Diff Size**: `+120 / -10, 2 files`
- **Files Copied From Another Repo**: `none`
- **Agent Instructions / Security Rules Changed**: `no`
- **Third-Party Dependencies / External Calls Added**: `none`
"""


class TestCheckPrBody(unittest.TestCase):
    def test_shipped_template_passes(self) -> None:
        ok, errors = check_template(DEFAULT_TEMPLATE)
        self.assertTrue(ok, f"Shipped template failed: {errors}")

    def test_valid_pr_body_passes(self) -> None:
        ok, errors = check_body(VALID_BODY)
        self.assertTrue(ok, f"Valid body failed: {errors}")

    def test_missing_review_loop_or_provenance_fails(self) -> None:
        incomplete = "## Summary\n\nJust a short note with no review loop record or provenance lines.\n"
        ok, errors = check_body(incomplete)
        self.assertFalse(ok)
        self.assertTrue(any("Review Loop Record" in e for e in errors))
        self.assertTrue(any("Files Copied From Another Repo" in e for e in errors))

    def test_oversized_diff_without_reason_fails_and_with_reason_passes(self) -> None:
        oversized = VALID_BODY.replace("+120 / -10", "+1200 / -500")
        ok, errors = check_body(oversized, max_diff_lines=1500)
        self.assertFalse(ok)
        self.assertTrue(any("exceeds cap" in e for e in errors))

        with_reason = oversized + "\n- **Diff Size Reason**: Includes generated 60-item benchmark fixture.\n"
        ok2, errors2 = check_body(with_reason, max_diff_lines=1500)
        self.assertTrue(ok2, f"Oversized body with reason failed: {errors2}")

    def test_unfilled_template_is_rejected_as_body(self) -> None:
        raw_tpl = DEFAULT_TEMPLATE.read_text(encoding="utf-8")
        ok, errors = check_body(raw_tpl)
        self.assertFalse(ok)
        self.assertTrue(any("unfilled template placeholder" in e for e in errors))
        self.assertTrue(any("Diff Size" in e for e in errors))


if __name__ == "__main__":
    unittest.main()

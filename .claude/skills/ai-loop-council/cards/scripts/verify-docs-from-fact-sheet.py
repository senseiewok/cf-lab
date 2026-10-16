#!/usr/bin/env python3
"""
Verifier for docs-from-fact-sheet playbook card.
Evaluates documentation, README, or PR descriptions generated strictly from a fact sheet:
- Required structural headings
- Grounded numbers and facts against allow-list
- Medical boundary adherence (no unverified cure or efficacy claims)
"""
import os
import re
import sys

# Verifier FAIL codes:
# FAIL R-01 missing required heading
# FAIL R-02 sentence contains ungrounded claim
# FAIL R-03 forbidden medical claim or hype
# FAIL R-04 invented number or metric
# FAIL R-06 sentence has no source line

def fail(code, message):
    print(f"FAIL {code} {message}")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        fail("R-00", "usage: verify-docs-from-fact-sheet.py <candidate-path> [fact-sheet-path]")

    candidate = sys.argv[1]
    if not os.path.isfile(candidate):
        fail("R-00", f"candidate file not found: {candidate}")

    try:
        with open(candidate, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        fail("R-00", f"cannot read candidate: {e}")

    # 1. Structural headings check
    required_headings = ["Overview", "Verification", "Limitations"]
    for h in required_headings:
        if not re.search(rf"(?m)^##\s+{re.escape(h)}\b", content):
            fail("R-01", f"missing required heading: '## {h}'")

    # 2. Forbidden medical claims and hype
    forbidden_terms = ["cure", "cure-all", "miracle", "clinical efficacy proven", "guaranteed treatment"]
    for term in forbidden_terms:
        pattern = rf"\b{re.escape(term).replace(' ', r'[\s\-]')}\b"
        if re.search(pattern, content, re.IGNORECASE):
            fail("R-03", f"forbidden medical claim or hype: found '{term}'")

    # 3. Fact sheet grounding check if provided
    if len(sys.argv) >= 3:
        fact_sheet = sys.argv[2]
        if os.path.isfile(fact_sheet):
            with open(fact_sheet, "r", encoding="utf-8") as f:
                facts = f.read()

            # Check numbers in candidate exist in fact sheet
            candidate_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", content))
            fact_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", facts))
            # Exclude markdown list indicators (e.g. "1. ", "2. ")
            list_numbers = set(re.findall(r"(?m)^\s*(\d+)\.\s+", content))
            candidate_numbers -= list_numbers

            unsupported_numbers = candidate_numbers - fact_numbers
            if unsupported_numbers:
                fail("R-04", f"invented number or metric: numbers {unsupported_numbers} not in fact sheet")

    print("ALL CHECKS PASSED: docs-from-fact-sheet candidate valid")
    sys.exit(0)

if __name__ == "__main__":
    main()

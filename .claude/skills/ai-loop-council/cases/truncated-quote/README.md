# truncated-quote (frozen fixture)

Reproduces the failure behind board T-0028 with SYNTHETIC text (invented here; it is not a quotation from any report). A packet supplied the first half of a definition as a "verified quote"; the quote is verbatim in the source, so a plain substring check passes it, and two drafts then claimed the definition 'returns to only' its first criterion.

- `source.txt`: the invented source text (line-wrapped, with a paragraph break, an abbreviation, curly quotes and dashes).
- `quotes.json`: eleven quotes; `truncated-prefix` is the failure, `suffix-only` and `middle-fragment` are its mirror images.
- `expected.txt`: what `scripts/check-quote-completeness.py` must say for each id.

`scripts/test-check-quote-completeness.py` runs the checker on this folder, shows that a plain substring check passes `truncated-prefix`, and shows that the checker rejects it. Add a case here before changing the checker.

# tools/claims

Checks a file of claims against the evidence each one cites, before any of them goes into a note.

A model writing from reports can type a number from memory, write a sentence stronger than its quote, say something is absent after reading part of a document, or attach a figure to the wrong thing, and the text still reads well. The lab's error ledger records these again and again. This checker removes the cheap classes of those mistakes and makes the writer record what was searched. Python 3.9+, standard library only.

## What it does not prove

It does not prove that a quote supports the sentence written beside it. A claim can pass every rule and still be wrong. A person or a different model still reads each quote against its sentence, and then the finished page.

## Run

```bash
python check_claims.py CLAIMS.json --evidence ID=PATH [--evidence ID=PATH ...]
python check_claims.py CLAIMS.json --evidence-map MAP.json       # a JSON object of id -> path, relative to the map's folder
python check_claims.py CLAIMS.json --evidence-map MAP.json --json
```

Options: `--max-quote-words N` (default 25), `--widening FILE` and `--absence FILE` (one word or phrase per line, `#` starts a comment; each replaces its default list, and an empty list is an error because it would switch the rule off).

## The claims file

A JSON list of objects:

| Field | Needed | What it holds |
| --- | --- | --- |
| `id` | yes | a unique name for the claim |
| `claim` | yes | the sentence you want to publish |
| `source` | yes | an evidence id given with `--evidence` or in the map |
| `quote` | yes | an exact piece of that evidence, or a list of them |
| `kind` | yes | `observed`, `computed` or `inferred` |
| `computed` | for `computed` | a list of `{"expr": "127 + 437", "result": 564}` |
| `scope` | for widening words and absence claims | what was searched and where, at least 8 words |
| `basis` | for `inferred` | why the inference follows, at least 8 words |

Any other field is a failure, so a misspelt `scope` or `basis` is not silently ignored. Evidence files are UTF-8 text.

## The rules

Each rule prints one `PASS` or `FAIL` line per claim, with the claim id.

| Rule | Passes when |
| --- | --- |
| R1 fields | the file parses and holds at least one claim; every claim has the required fields with the right types; ids are unique; the claim's source has readable, non-empty evidence |
| R2 quote | every quote is an exact piece of its evidence and has 4 to `--max-quote-words` words |
| R3 numbers | every number in the claim is in the quote(s), or is the result of a `computed` entry whose operands are all in the quote(s) |
| R4 scope | a claim with a widening word or an absence phrase has a `scope` of at least 8 words, and an `observed` claim uses a widening word only when its quote uses the same word |
| R5 kind | an `inferred` claim has a `basis` of at least 8 words and contains "our inference" or "we infer"; a `computed` claim has `computed` entries; an `observed` claim has none |

A claim that fails R1 is not checked further. Problems with the files themselves (no claims, unparseable JSON, a missing evidence file) print as `FAIL - R1` lines.

**Quotes.** Before matching, the quote and the evidence get only these changes: curly quotes and dashes become straight ones, and runs of whitespace become one space. There is no case folding and no joining across an ellipsis: a quote with `...` in it must be split into a list of separate quotes. The 25-word ceiling is for checking; the repo's rule for committed text is much shorter (8 words in a quotation), so run `tools/sources/check_source_overlap.py` on anything you commit.

**Numbers.** Integers, decimals, percentages and years count, and a range such as 2019-2024 counts as both ends. Commas and trailing zeros do not matter (33,782 = 33782; 85.0 = 85). Numbers glued to letters are identifiers and are not checked (R117H, hg19, the 0067 in T-0067), nor are the digits of a version string. The words one to ten count as numbers: each passes only if the quote has its digit form or the same word, or it is a computed result. "no one" is not a number.

**Computed entries.** `expr` may hold only numbers, `+ - * /` and parentheses. It is parsed with Python's `ast` module and worked out with exact fractions; it is never passed to `eval`, and anything else (a name, a call, `**`) fails. Every operand must be in the quote(s) or be the result of an earlier entry in the same claim. The result passes when the exact value, rounded to the decimals the result is written with, equals it: `564 / 127` matches `4.4` and `4.44` but not `5`.

**Widening words** (default list, whole words, any case): only, all, every, each, never, always, none, no one, same, identical, first, last, no longer, new in, now, agrees, consistent, stronger, strongest, most, majority, any, entire, whole, completely, both, neither, unique, cause, causes, caused, because.

**Absence phrases** (default list): does not say, not stated, no evidence, absent, never reported, there is no.

## Example

`example/` holds an invented evidence text, a claims file that passes and one that fails.

```bash
python check_claims.py example/claims-pass.json --evidence-map example/evidence-map.json   # exit 0
python check_claims.py example/claims-fail.json --evidence review=example/evidence.txt     # exit 1
```

A passing claim with a sum, from `example/claims-pass.json`:

```json
{
  "id": "c2",
  "claim": "Together, 564 variants in the 2024 review were benign-leaning or unclassified.",
  "source": "review",
  "quote": "In the 2024 review, 127 variants were classed as benign or likely benign and 437 were left unclassified.",
  "kind": "computed",
  "computed": [{"expr": "127 + 437", "result": 564}]
}
```

The failing file gives these lines (the passing ones left out):

```text
FAIL f1 R3 numbers: number 473 is not in the quote and is not a computed result
FAIL f2 R3 numbers: number 2019 is not in the quote and is not a computed result; number 2024 is not in the quote and is not a computed result
FAIL f2 R4 scope: 'every', 'same' need(s) a scope of at least 8 words; it has 2; an observed claim uses 'every' but its quote does not; narrow the sentence or mark it inferred
FAIL f3 R2 quote: quote matches the evidence only if case is ignored; copy it exactly
FAIL f3 R4 scope: 'does not say' need(s) a 'scope' saying what was searched and where
3 claims, 5 failures
```

## Exit codes

`0` every claim passes every rule. `1` at least one `FAIL`, including an empty claims file, a file that does not parse, a missing evidence file, or no evidence at all: the checker fails closed and never reports "nothing to check" as a pass. `2` a usage error: a bad flag, an `--evidence` without `ID=PATH`, an evidence id given twice, an unreadable evidence map, or an empty or missing term list.

## Tests

```bash
python -m unittest -v     # from tools/claims; standard library only, no network
```

The tests rebuild the claim-type mistakes from the error ledger (a number typed from memory, a year range or "new in" added beyond the quote, "only" from a truncated quote, an absence claim with no record of what was searched, a ratio, a causal word, a spelled-out number not in the quote) and add negative controls for each rule. One test registers a case for each rule that fails on that rule alone, then switches the rule off in a fresh copy of the module and checks that the case passes, so a rule that stops working breaks the tests.

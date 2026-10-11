# American English: the lab's decisions

The lab writes its own prose in American English. This page records the lab's choices. It is not a style guide; where a choice rests on an outside authority, the source is named. `scripts/check-voice.py` enforces the spelling table and its exceptions.

## Spelling

| British (do not use in our prose) | American (use) |
| --- | --- |
| `licence`, `licences` | license, licenses |
| `organisation`, `organise`, `organised` | organization, organize, organized |
| `centre`, `centred` | center, centered |
| `colour`, `behaviour`, `favour`, `honour` | color, behavior, favor, honor |
| `judgement` | judgment |
| `catalogue`, `catalogued` | catalog, cataloged |
| `grey` | gray |
| `programme` | program |
| `labelled`, `labelling`, `modelled`, `travelled`, `cancelled` | labeled, labeling, modeled, traveled, canceled |
| `analyse`, `analysed` | analyze, analyzed |
| `summarise`, `summarised` | summarize, summarized |
| `specialise`, `specialised` | specialize, specialized |
| `recognise`, `prioritise`, `optimise`, `anonymise` | recognize, prioritize, optimize, anonymize |
| `towards`, `amongst`, `whilst` | toward, among, while |
| `ageing` | aging |
| `fibre`, `metre`, `litre` | fiber, meter, liter |
| `defence`, `offence`, `practise (verb)` | defense, offense, practice |
| `enrolment`, `fulfilment`, `acknowledgement` | enrollment, fulfillment, acknowledgment |
| `paediatric`, `haemoglobin`, `anaemia`, `oesophagus` | pediatric, hemoglobin, anemia, esophagus |
| `per cent` | percent |

Some "-ise" words are American too and stay as they are: advertise, advise, compromise, exercise, promise, revise, surprise, supervise. "Analyses" is the plural of "analysis" in both forms of English.

### The "licence" trap

In American English "license" is both the noun and the verb ("the license", "licensed under"). There is no American "licence". A license's own legal name keeps its official spelling, whatever it is; write it exactly as its publisher does and add it to the allow-list if it contains a British spelling.

## Words for people and for care

- **Caregiver**, never `carer`. Use it for anyone who looks after someone, without saying who that person is to them.
- **Health care** is two words as a noun ("access to health care"). Use the same two words before a noun ("health care team"), with no hyphen. This is a lab choice for consistency.
- People first and neutral: "people living with CF", "people with CF". Follow `cf-research-context` for clinical terms.

## Dates and numbers

| Where | Style | Example |
| --- | --- | --- |
| Running prose | Month day, year; no "th" | October 11, 2026 |
| Tables, access dates, logs, file names | ISO 8601 | 2026-10-11 |
| Counts in prose | Words for one to nine, numerals from 10 | three studies, 12 studies |
| Measurements, doses, ages, percentages, ranges | Always numerals | 5 mL, age 6, 40 percent, 2 to 4 hours |
| Thousands | Comma | 1,800 words |
| Percent | "percent" in prose, "%" in tables and charts | 40 percent / 40% |

The count rule is a lab choice, kept because it is common in US publishing; numbers taken from a source keep the source's value exactly (see `cf-research-context`).

## Punctuation

- **Quotation marks:** double quotes, with single quotes for a quote inside a quote.
- **Order:** periods and commas go inside the closing quotation mark; colons and semicolons go outside; a question mark or exclamation point goes inside only when it belongs to the quoted words. When the exact characters matter (a command, a value the reader must type, a file name), use code formatting instead of quotation marks so no punctuation is added to them.
- **Serial comma:** yes, always: "researchers, families, and caregivers". Reason: the U.S. Government Publishing Office *Style Manual* (2016 edition), section 8.46, puts a comma "after each member within a series of three or more words, phrases, letters, or figures used with and, or, or nor" (https://www.govinfo.gov/content/pkg/GPO-STYLEMANUAL-2016/pdf/GPO-STYLEMANUAL-2016-10.pdf, accessed 2026-10-11). Its section 8.138 gives the order above: "The comma and the final period will be placed inside the quotation marks."

## What must never be changed

The spelling rules apply to the lab's own sentences only. Leave these exactly as written:

| Keep as written | Example | How the checker skips it |
| --- | --- | --- |
| Names of organizations, programs and places | "European Centre for Disease Prevention and Control" | `--allow FILE` phrase list |
| Titles of papers, reports, books and pages | A report title with "Programme" in it | `<cite>`, Markdown quotation marks, or the allow-list |
| Direct quotes from a source, exactly as written | > "...the licence..." | HTML `<blockquote>` and `<q>`; Markdown `>` and Markdown text inside quotation marks (in HTML, quotation marks alone do not exempt text) |
| Citations in Markdown tables | a Source cell with a quoted paper title | every cell is checked, except text inside quotation marks, URLs and allow-list phrases |
| Non-English text (Spanish pages are es-MX) | `<p lang="es-MX">` | in HTML, any `lang` that is not English |
| File names, identifiers, code, URLs | `licence.txt`, `organisation_id` | code, `<pre>`, URLs, attribute values, words joined by `/`, `_`, `.ext` |

In Markdown files the checker does not parse inline HTML: a `<blockquote>` or a `lang="es-MX"` written inside Markdown is not honored, and its text is checked as our prose. Use Markdown `>` for quotes, and keep Spanish text in its own es-MX page.

Quoted text (block quotes, `<q>`, and Markdown text inside quotation marks) is also left out of the sentence-length, repetition and label checks. So is every Markdown table. A sentence or label the page repeats on purpose is marked: `data-voice="repeat"` on its block element in HTML (not on an inline `<span>`), or `<!-- voice: repeat -->` on the line directly before the Markdown block.

Do not "fix" a quote's spelling, even silently. If a quote is long enough to need fixing, it is too long to quote: paraphrase it in our words and link to the original.

Keep one allow-list per site or repository (one phrase per line, `#` for comments). Add a phrase only when it is a real name or title, and keep the list short enough to review.

## Checking

```text
python .claude/skills/lab-voice/scripts/check-voice.py --allow voice-allow.txt page.html
```

A British spelling in our prose is an ERROR (exit 1). Fix it, or, if it is a name or title, add it to the allow-list.

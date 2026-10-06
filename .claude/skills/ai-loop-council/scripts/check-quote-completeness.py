"""Check that every "verified quote" in a task packet is a COMPLETE sentence (or several complete consecutive sentences) of its source.

A plain "is the quote verbatim in the source" check passes a quote that is only the first half of a sentence, and a model shown only that
half can then claim the source says "only" that (ledger E12, E13, E14, E21, E22; board T-0028). This catches that case.

Usage: python check-quote-completeness.py SOURCE QUOTES      SOURCE: UTF-8 text; QUOTES: JSON list of {"id": ..., "text": ...}
       python check-quote-completeness.py --self-test
Output: one `PASS <id>` or `FAIL <id>: <reason>` per quote (reason: not found | starts mid-sentence | ends mid-sentence), then a count.
Exit 0 all pass, 1 any fail, 2 input problem. Standard library only; no network.

Limit: the sentence splitter is a heuristic (a boundary is . ! or ? followed by a space and a capital letter, "(" or "[", or a paragraph
break). It catches obvious truncation; an abbreviation followed by a capital can split a sentence, and the check does not judge meaning.
Drafted by the local worker (see the SKILL.md distill notes), accepted by the verifier in test-check-quote-completeness.py, and read by a person.
"""
# TRACE: example text = "Aa b. Cc d. Ee f."
# Normalised source is identical (single spaces, no typographic chars).
# Boundary regex r"([.!?])([)\"'])?\s+([A-Z\[])" matches:
#   - '.' at 4, no close, ' ' at 5, 'C' at 6  -> ends.add(5), starts.add(6)
#   - '.' at 10, no close, ' ' at 11, 'E' at 12 -> ends.add(11), starts.add(12)
# Final: starts.add(0), ends.add(len(norm)=17).
# So starts = {0, 6, 12}; ends = {5, 11, 17}.
# Quote "Aa b" at idx=0 (L=4): idx in starts; idx+L=4 not in ends;
#   text[4]=='.' and idx+L+1=5 in ends -> PASS (terminator missing).
# Quote "b. Cc d" at idx=2: idx not in starts -> starts mid-sentence.

import re
import json
import sys
from pathlib import Path


def normalise(s: str) -> str:
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def split_sentences(raw: str, norm: str):
    starts = set()
    ends = set()

    raw_to_norm = [0] * len(raw)
    ni = 0
    i = 0
    while i < len(raw) and ni < len(norm):
        if raw[i].isspace():
            j = i
            while j < len(raw) and raw[j].isspace():
                j += 1
            for k in range(i, j):
                raw_to_norm[k] = ni
            if ni < len(norm) and norm[ni] == " ":
                ni += 1
            i = j
        else:
            raw_to_norm[i] = ni
            ni += 1
            i += 1
    for i in range(i, len(raw)):
        raw_to_norm[i] = len(norm)

    def r2n(rpos: int) -> int:
        if rpos >= len(raw_to_norm):
            return len(norm)
        return raw_to_norm[rpos]

    for m in re.finditer(r"\n\s*\n", raw):
        end_of_break = m.end()
        while end_of_break < len(raw) and raw[end_of_break].isspace():
            end_of_break += 1
        if end_of_break < len(raw):
            starts.add(r2n(end_of_break))
        j = m.start() - 1
        while j >= 0 and raw[j].isspace():
            j -= 1
        if j >= 0:
            ends.add(r2n(j) + 1)

    boundary_re = re.compile(r"([.!?])([)\"'])?\s+([A-Z\[])")
    for m in boundary_re.finditer(norm):
        term_end = m.start(1) + 1
        if m.group(2):
            term_end += 1
        ends.add(term_end)
        starts.add(m.start(3))

    if norm:
        starts.add(0)
        ends.add(len(norm))

    return starts, ends


def find_occurrences(text: str, quote: str):
    idxs = []
    pos = 0
    while True:
        i = text.find(quote, pos)
        if i == -1:
            break
        idxs.append(i)
        pos = i + 1
    return idxs


def check_quote(text: str, quote_raw: str, starts: set, ends: set):
    q = normalise(quote_raw)
    if not q:
        return False, "not found"
    occ = find_occurrences(text, q)
    if not occ:
        return False, "not found"
    for idx in occ:
        L = len(q)
        if idx not in starts:
            continue
        if (idx + L) in ends:
            return True, None
        if idx + L < len(text) and text[idx + L] in ".!?":
            if (idx + L + 1) in ends:
                return True, None
    idx = occ[0]
    if idx not in starts:
        return False, "starts mid-sentence"
    return False, "ends mid-sentence"


def load_quotes(path: str):
    p = Path(path)
    if not p.is_file():
        raise ValueError("missing quotes file")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("invalid quotes list")
    for item in data:
        if not isinstance(item, dict) or "id" not in item or "text" not in item:
            raise ValueError("quote entry invalid")
        if not isinstance(item["id"], str) or not isinstance(item["text"], str):
            raise ValueError("id/text must be strings")
    return data


def run(source_path: str, quotes_path: str):
    sp = Path(source_path)
    if not sp.is_file():
        raise ValueError("missing source file")
    raw = sp.read_text(encoding="utf-8")
    norm = normalise(raw)
    if not norm:
        raise ValueError("empty source")
    starts, ends = split_sentences(raw, norm)
    quotes = load_quotes(quotes_path)

    results = []
    all_pass = True
    for q in quotes:
        ok, reason = check_quote(norm, q["text"], starts, ends)
        if ok:
            results.append(("PASS", q["id"], None))
        else:
            results.append(("FAIL", q["id"], reason))
            all_pass = False

    n = len(quotes)
    k = sum(1 for r in results if r[0] == "PASS")
    lines = []
    for status, qid, reason in results:
        lines.append(f"PASS {qid}" if status == "PASS" else f"FAIL {qid}: {reason}")
    lines.append(f"{k} of {n} quotes are complete sentences")
    print("\n".join(lines))
    return 0 if all_pass else 1


def self_test():
    raw = "The " + "\u201ccore\u201d" + " group \u2013 adults only \u2013 was larger. Second sentence here. Third one ends."
    norm = normalise(raw)
    starts, ends = split_sentences(raw, norm)

    quotes = [
        {"id": "complete", "text": "The " + "\u201ccore\u201d" + " group \u2013 adults only \u2013 was larger."},
        {"id": "truncated", "text": "The " + "\u201ccore\u201d" + " group \u2013 adults only"},
        {"id": "suffix", "text": "group \u2013 adults only \u2013 was larger."},
        {"id": "missing", "text": "This is not in the source at all."},
        {"id": "no-final-dot", "text": "Second sentence here"},
    ]

    expected = {"complete": True, "truncated": False, "suffix": False, "missing": False, "no-final-dot": True}
    failures = []
    for q in quotes:
        ok, _ = check_quote(norm, q["text"], starts, ends)
        if ok != expected[q["id"]]:
            failures.append(q["id"])

    if not failures:
        print("SELF-TEST OK")
        return 0
    print(f"SELF-TEST FAILED: {', '.join(failures)}")
    return 1


def main():
    args = sys.argv[1:]
    try:
        if not args:
            print("error: usage or input problem")
            return 2
        if args[0] == "--self-test":
            return self_test()
        if len(args) != 2:
            print("error: usage or input problem")
            return 2
        return run(args[0], args[1])
    except Exception as e:
        print(f"error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

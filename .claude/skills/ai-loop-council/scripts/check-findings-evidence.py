#!/usr/bin/env python3
"""check-findings-evidence.py -- drop review findings whose quoted evidence is not in the packet.

What it decides
---------------
One narrow question per finding: "is the `quote` this finding rests on an exact substring of the packet the model was
given?" (whitespace collapsed; curly quotes and dashes unified; case kept). A finding whose quote is not in the packet is
DROPPED before anyone reads it. A finding may abstain with the literal `not stated in the packet` instead of a quote,
but only when its text makes no claim of absence, reachability, scope or cause (words such as "no", "missing", "lacks",
"only", "every", "reachable", "because"): such a claim without a quote is DROPPED as an unquoted claim. A kept finding
whose text uses one of those words is labelled `scope check`: the controller reads the full sentence on both sides
(ai-loop-council: "A verbatim-quote check does not clear an inference").

What it does NOT decide
-----------------------
Whether a kept finding is right. A quote that is in the packet can still be read wrongly (measured 2026-10-09: a local
model quoted `access: api` and concluded the entry was "technically reachable", which the gate's base_url rule made
false). This tool removes fabricated evidence; the controller judges the rest.

Claim mode
----------
A reply shaped like the claim-check schema (`verdict`, `quote`, `overreach_words`) is checked the same way: a SUPPORTED
or PARTLY verdict whose quote is not in the packet becomes UNVERIFIED (quote not found); an `overreach_words` entry that
is not in the checked sentence is removed. NOT STATED and NOT SUPPORTED may carry an empty quote.

Usage
-----
    python check-findings-evidence.py PACKET REPLY [--out CHECKED.json] [--quote-field quote]
                                      [--text-fields problem,fix] [--sentence-tag sentence]
PACKET: the exact text the model was given (UTF-8). REPLY: the model's JSON reply.
Prints one line per finding (KEPT, KEPT scope check, KEPT abstained, DROPPED ...) and a count. Exit 0 when nothing was
dropped or made unverified, 1 when something was, 2 on a usage error. Standard library only; no network, no model.
Tests: test_check_findings_evidence.py (fixtures in ../cases/findings-evidence/).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ABSTAIN = re.compile(r"^\s*not stated( in the (packet|diff|document|material|source|page|text))?\s*\.?\s*$", re.I)

# Words that make a sentence a claim of absence, scope, reachability or cause. Matched on word boundaries, case-insensitive.
WIDENING = re.compile(
    r"\b(only|none|no|never|nothing|every|all|always|absent|missing|lack|lacks|lacking|without|cannot|can't|"
    r"reachable|unreachable|accessible|inaccessible|because|due to|caused|causes|leads to|contradicts?|no longer|"
    r"stale|hand-edited|manually)\b",
    re.I,
)

LABEL_KEPT = "KEPT"
LABEL_SCOPE = "KEPT scope check"
LABEL_ABSTAINED = "KEPT abstained"
LABEL_NOT_FOUND = "DROPPED quote not found"
LABEL_UNQUOTED = "DROPPED unquoted claim"
LABEL_NO_EVIDENCE = "DROPPED no evidence"


def normalise(s):
    s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def diff_stripped(packet):
    """The packet with a leading diff marker (+, - or space) removed from every line, so that a quote that runs across a
    line break inside a unified diff can still match. Only applied when the packet looks like a diff."""
    if not re.search(r"^(diff --git |@@ )", packet, re.M):
        return None
    return "\n".join(re.sub(r"^[+\- ]", "", line) for line in packet.splitlines())


def packet_forms(packet):
    """The normalised packet and, for a diff, its marker-stripped form. A quote matches when it is in either."""
    forms = [normalise(packet)]
    stripped = diff_stripped(packet)
    if stripped is not None:
        forms.append(normalise(stripped))
    return forms


def quote_in(packet_norm, quote):
    q = normalise(quote)
    forms = packet_norm if isinstance(packet_norm, list) else [packet_norm]
    return bool(q) and any(q in f for f in forms)


def widening_words(text):
    return sorted({m.group(1).lower() for m in WIDENING.finditer(text or "")})


def check_finding(f, packet_norm, quote_field, text_fields):
    if not isinstance(f, dict):
        return LABEL_NO_EVIDENCE, "finding is not an object", []
    q = f.get(quote_field)
    text = " ".join(str(f.get(k) or "") for k in text_fields)
    words = widening_words(text)
    if not isinstance(q, str) or not q.strip():
        return LABEL_NO_EVIDENCE, "no %s" % quote_field, words
    if ABSTAIN.match(q):
        if words:
            return LABEL_UNQUOTED, "abstains but asserts: %s" % ", ".join(words), words
        return LABEL_ABSTAINED, "abstained; no claim of absence, scope or cause", words
    if not quote_in(packet_norm, q):
        return LABEL_NOT_FOUND, "quote is not an exact substring of the packet", words
    if words:
        return LABEL_SCOPE, "quote found; read the full sentence for: %s" % ", ".join(words), words
    return LABEL_KEPT, "quote found", words


def sentence_from_packet(packet, tag):
    m = re.search(r"<%s>(.*?)</%s>" % (re.escape(tag), re.escape(tag)), packet, re.S)
    return normalise(m.group(1)) if m else None


def check_claim(reply, packet_norm, sentence_norm):
    out = dict(reply)
    notes = []
    verdict = str(reply.get("verdict") or "")
    q = reply.get("quote")
    q_ok = isinstance(q, str) and quote_in(packet_norm, q)
    if verdict in ("SUPPORTED", "PARTLY") and not q_ok:
        out["verdict"] = "UNVERIFIED"
        notes.append("%s changed to UNVERIFIED: quote not found in the packet" % verdict)
    elif isinstance(q, str) and q.strip() and not q_ok:
        notes.append("quote not found in the packet (verdict %s kept)" % verdict)
    words = reply.get("overreach_words")
    if isinstance(words, list) and sentence_norm is not None:
        kept, removed = [], []
        for w in words:
            if isinstance(w, str) and normalise(w) and normalise(w).lower() in sentence_norm.lower():
                kept.append(w)
            else:
                removed.append(str(w))
        if removed:
            out["overreach_words"] = kept
            notes.append("overreach words not in the sentence removed: %s" % ", ".join(removed))
    out["evidence_check"] = notes or ["quote found" if q_ok else "no quote needed"]
    return out, bool(notes)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("PACKET")
    p.add_argument("REPLY")
    p.add_argument("--out")
    p.add_argument("--quote-field", default="quote")
    p.add_argument("--text-fields", default="problem,fix,why_it_matters")
    p.add_argument("--sentence-tag", default="sentence")
    a = p.parse_args(argv)
    try:
        packet = Path(a.PACKET).read_text(encoding="utf-8")
    except OSError as e:
        print("error: cannot read packet: %s" % e, file=sys.stderr)
        return 2
    try:
        raw = Path(a.REPLY).read_text(encoding="utf-8-sig").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw)
        reply = json.loads(raw)
    except (OSError, ValueError) as e:
        print("error: cannot read reply as JSON: %s" % e, file=sys.stderr)
        return 2
    packet_norm = packet_forms(packet)
    text_fields = [t for t in a.text_fields.split(",") if t]

    if isinstance(reply, dict) and "verdict" in reply and "findings" not in reply:
        sentence = sentence_from_packet(packet, a.sentence_tag)
        checked, changed = check_claim(reply, packet_norm, sentence)
        for n in checked["evidence_check"]:
            print(("CHANGED " if changed else "KEPT ") + n)
        print("verdict: %s" % checked["verdict"])
        if a.out:
            Path(a.out).write_text(json.dumps(checked, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 1 if changed else 0

    findings = reply.get("findings") if isinstance(reply, dict) else reply
    if not isinstance(findings, list):
        print("error: reply has no findings list", file=sys.stderr)
        return 2
    kept, results = [], []
    counts = {}
    for i, f in enumerate(findings, 1):
        label, reason, words = check_finding(f, packet_norm, a.quote_field, text_fields)
        counts[label] = counts.get(label, 0) + 1
        where = f.get("where") or f.get("file") or "" if isinstance(f, dict) else ""
        print("%-26s #%d %s: %s" % (label, i, where, reason))
        results.append({"index": i, "label": label, "reason": reason, "widening_words": words})
        if label.startswith("KEPT"):
            g = dict(f)
            g["evidence_check"] = label
            kept.append(g)
    dropped = len(findings) - len(kept)
    print("%d findings: %d kept, %d dropped. Kept findings are leads; a found quote does not prove the sentence beside it."
          % (len(findings), len(kept), dropped))
    if a.out:
        out = {"tool": "check-findings-evidence", "counts": counts, "results": results, "findings": kept}
        if isinstance(reply, dict):
            for k, v in reply.items():
                if k != "findings":
                    out[k] = v
        Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if dropped else 0


if __name__ == "__main__":
    sys.exit(main())

"""Check HTML or Markdown pages against the lab voice: American spelling, sentence length, repetition, templates, length.

Usage:
  python check-voice.py [--allow FILE] [--budget WORDS] [--json] FILE [FILE ...]
  python check-voice.py --self-test

Rules
  ERROR uk-spelling      a British spelling (or 'carer') in the lab's own prose. Exit 1.
  WARN  long-sentence    a sentence of 30 or more words.
  WARN  repetition       two sentences anywhere on the page, each 6+ words, that share 70% or more of their
                         content words (shared words / content words of the shorter sentence, at least 4 shared).
  WARN  label-template   the same label ('How strong:', or a short label-only block such as 'Read the original')
                         used 5 or more times on one page.
  WARN  page-length      more words than the budget (default 1,800).
  INFO  reading-grade    Flesch-Kincaid grade, informational only.

Never checked for spelling: text inside <blockquote>, <q>, <cite>, <code>, <pre>, <script>, <style>, Markdown
block quotes and code, elements whose lang attribute is not English (e.g. lang="es-MX"), attribute values, URLs,
file names and identifiers (a word touching '/', '_', '@', '\\' or a '.ext'), and any phrase in the --allow file
(one per line, '#' starts a comment, matched case-insensitively). In Markdown, text inside quotation marks
("..." or curly quotes) is an inline quote, like <q> in HTML.

Quotes (block and inline) and other-language text are also left out of the sentence, repetition and label rules:
the lab cannot rewrite a source's words. Markdown table rows (lines starting with '|', header rows included) hold
citations: every cell is checked for spelling except text inside quotation marks, URLs and --allow phrases, and
tables are left out of the sentence, repetition and label rules.

Deliberate repeats: put data-voice="repeat" on the block element itself (<p>, <li>, <div>, <dd> ...; an inline
<span> does not count), or put <!-- voice: repeat --> on the line directly before a Markdown block (a blank line
or a code fence in between cancels it). That one block's sentences and labels then raise no repetition or
label-template warning.

In Markdown, inline HTML is not parsed: <blockquote>, lang="..." and similar tags are ignored there (only <code>,
<q>, <cite>, <kbd> and <samp> content is dropped). Use Markdown '>' for quotes.

Exit: 0 no errors (warnings allowed), 1 any ERROR, 2 usage error (missing file, bad option).
Standard library only; reads only the files named; no network.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# ---------------------------------------------------------------- spelling table

UK_US = {
    "licence": "license", "licences": "licenses", "licenced": "licensed",
    "judgement": "judgment", "judgements": "judgments",
    "catalogue": "catalog", "catalogues": "catalogs", "catalogued": "cataloged", "cataloguing": "cataloging",
    "grey": "gray", "greys": "grays", "greyed": "grayed",
    "programme": "program", "programmes": "programs",
    "ageing": "aging", "towards": "toward", "whilst": "while", "amongst": "among",
    "learnt": "learned", "spelt": "spelled", "defence": "defense", "offence": "offense",
    "practise": "practice", "practised": "practiced", "practises": "practices", "practising": "practicing",
    "sceptical": "skeptical", "sceptic": "skeptic", "artefact": "artifact", "artefacts": "artifacts",
    "manoeuvre": "maneuver", "manoeuvres": "maneuvers", "cheque": "check", "tyre": "tire", "tyres": "tires",
    "aluminium": "aluminum", "mould": "mold", "moulds": "molds", "plough": "plow", "storey": "story",
    "acknowledgement": "acknowledgment", "acknowledgements": "acknowledgments",
    "enrolment": "enrollment", "fulfilment": "fulfillment", "instalment": "installment",
    "skilful": "skillful", "wilful": "willful", "focussed": "focused", "focussing": "focusing",
    "enquiry": "inquiry", "enquiries": "inquiries", "enquire": "inquire",
    "carer": "caregiver", "carers": "caregivers",
}
_ISE_STEMS = ("organ", "summar", "special", "recogn", "priorit", "minim", "maxim", "optim", "emphas", "real",
              "apolog", "categor", "util", "standard", "anonym", "normal", "character", "author", "visual",
              "critic", "custom", "final", "general", "harmon", "initial", "local", "memor", "mobil", "person",
              "random", "serial", "stabil", "synthes", "sanit", "token", "hospital", "immun", "prior", "familiar",
              "legal", "modern", "patron", "public", "subsid", "symbol", "vandal", "jeopard", "personal",
              "agon", "fertil", "neutral", "polar", "revital", "scrutin", "sympath", "theor", "trivial", "western")
for _st in _ISE_STEMS:
    for _uk, _us in (("ise", "ize"), ("ised", "ized"), ("ises", "izes"), ("ising", "izing"), ("isation", "ization"),
                     ("isations", "izations"), ("iser", "izer"), ("isers", "izers")):
        UK_US.setdefault(_st + _uk, _st + _us)
for _uk, _us in (("analyse", "analyze"), ("analysed", "analyzed"), ("analysing", "analyzing"), ("analyser", "analyzer"),
                 ("paralyse", "paralyze"), ("paralysed", "paralyzed"), ("catalyse", "catalyze"), ("catalysed", "catalyzed")):
    UK_US[_uk] = _us
for _st in ("colour", "behaviour", "favour", "honour", "labour", "neighbour", "humour", "rumour", "odour", "tumour",
            "endeavour", "flavour", "harbour", "vapour", "saviour", "armour", "rigour", "vigour", "valour"):
    _base = _st[:-2] + "r"
    for _sfx in ("", "s", "ed", "ing", "al", "ful", "ite", "ites", "able", "ably", "less", "ally"):
        UK_US.setdefault(_st + _sfx, _base + _sfx)
for _st in ("centre", "fibre", "metre", "litre", "theatre", "calibre", "sombre", "spectre", "lustre", "meagre",
            "kilometre", "centimetre", "millimetre", "micrometre"):
    _base = _st[:-2] + "er"
    for _sfx, _usfx in (("", ""), ("s", "s"), ("d", "ed")):
        UK_US.setdefault(_st + _sfx, _base + _usfx)
for _uk in ("labelled", "labelling", "modelled", "modelling", "travelled", "travelling", "traveller", "travellers",
            "cancelled", "cancelling", "signalled", "signalling", "levelled", "levelling", "fuelled", "fuelling",
            "totalled", "totalling", "channelled", "counselled", "counselling", "counsellor", "counsellors",
            "marshalled", "tunnelled", "funnelled", "jewellery"):
    UK_US.setdefault(_uk, _uk.replace("ll", "l", 1) if _uk != "jewellery" else "jewelry")
UK_PREFIX = [  # (regex on a lowercase word, from, to)
    (re.compile(r"^paediatric"), "paed", "ped"), (re.compile(r"^orthopaedic"), "paed", "ped"),
    (re.compile(r"^haem"), "haem", "hem"), (re.compile(r"^anaem"), "anaem", "anem"),
    (re.compile(r"^leukaem"), "aem", "em"), (re.compile(r"^oesophag"), "oesophag", "esophag"),
    (re.compile(r"^foet(al|us|uses)$"), "foet", "fet"), (re.compile(r"^gynaecolog"), "gynaec", "gynec"),
    (re.compile(r"^oedema"), "oedema", "edema"), (re.compile(r"^anaesthe"), "anaesthe", "anesthe"),
]
TWO_WORD = [(re.compile(r"\bper cent\b", re.I), "percent")]


def us_for(word):
    low = word.lower()
    us = UK_US.get(low)
    if us is None:
        for rx, a, b in UK_PREFIX:
            if rx.search(low):
                us = low.replace(a, b, 1)
                break
    if us is None:
        return None
    return us[0].upper() + us[1:] if word[:1].isupper() else us


# ---------------------------------------------------------------- page model

PROSE, QUOTE, FOREIGN, TABLE = "prose", "quote", "foreign", "table"
URL_RX = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\w+")
WORD_RX = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")


class Block:
    """A paragraph-like unit: list of runs (text, kind, line)."""

    def __init__(self, line, repeat=False):
        self.line = line
        self.runs = []
        self.repeat = repeat  # marked as a deliberate repeat: no repetition or label-template warning

    def add(self, text, kind, line):
        if text:
            self.runs.append((text, kind, line))

    def english_text(self):
        """The lab's own prose only: quotes (block or inline), tables and other languages are left out."""
        return " ".join(t for t, k, _ in self.runs if k == PROSE)

    def all_text(self):
        return " ".join(t for t, _, _ in self.runs)


def _lang_is_english(value):
    v = (value or "").strip().lower()
    return v == "" or v == "en" or v.startswith("en-")


BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "tr", "table", "section",
              "article", "header", "footer", "nav", "aside", "main", "dt", "dd", "dl", "figcaption", "figure",
              "blockquote", "pre", "summary", "details", "title", "br", "hr", "caption", "label", "button", "option",
              "form", "address", "body", "html", "head", "tbody", "thead", "fieldset", "legend"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
DROP = {"code", "pre", "script", "style", "template", "kbd", "samp", "var"}
QUOTE_TAGS = {"blockquote", "q", "cite"}


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # (tag, drop, quote, foreign)
        self.blocks = []
        self.cur = None
        self.next_repeat = False  # the open block element itself carries data-voice="repeat"

    def _state(self):
        return self.stack[-1][1:] if self.stack else (False, False, False)

    def _break(self):
        if self.cur is not None and self.cur.runs:
            self.blocks.append(self.cur)
        self.cur = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in BLOCK_TAGS:
            self._break()
            # only a block element's own attribute marks a repeat; an inline span inside a block does not
            self.next_repeat = tag not in VOID and (a.get("data-voice") or "").strip().lower() == "repeat"
        if tag in VOID:
            return
        drop, quote, foreign = self._state()
        if "lang" in a:
            foreign = not _lang_is_english(a["lang"])
        self.stack.append((tag, drop or tag in DROP, quote or tag in QUOTE_TAGS, foreign))

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self._break()
            self.next_repeat = False

    def handle_endtag(self, tag):
        if tag in BLOCK_TAGS:
            self._break()
            self.next_repeat = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        drop, quote, foreign = self._state()
        if drop or not data.strip():
            return
        line = self.getpos()[0]  # the run's first line; spelling adds the newlines before each match
        if self.cur is None:
            self.cur = Block(line + data[:len(data) - len(data.lstrip())].count("\n"), repeat=self.next_repeat)
        kind = FOREIGN if foreign else QUOTE if quote else PROSE
        self.cur.add(data, kind, line)

    def close(self):
        super().close()
        self._break()


def parse_html(text):
    p = _Html()
    p.feed(text)
    p.close()
    return p.blocks


MD_INLINE = [
    (re.compile(r"<!--.*?-->", re.S), ""),
    (re.compile(r"`[^`]*`"), " "),
    (re.compile(r"<(code|q|cite|kbd|samp)\b[^>]*>.*?</\1>", re.I), " "),
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\[[^\]]*\]"), r"\1"),
    (re.compile(r"<https?://[^>]+>"), " "),
    (re.compile(r"<[^>]+>"), " "),
    (re.compile(r"(\*\*|__|\*)"), ""),
]


def _md_inline(s):
    for rx, rep in MD_INLINE:
        s = rx.sub(rep, s)
    return s


QUOTED_RX = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”")
REPEAT_MARK = re.compile(r"^<!--\s*voice:\s*repeat\s*-->$", re.I)


def _md_add(block, raw, line):
    """Add Markdown prose to a block, with text inside quotation marks as QUOTE runs (inline quotes)."""
    s, pos = _md_inline(raw), 0
    for m in QUOTED_RX.finditer(s):
        block.add(s[pos:m.start()], PROSE, line)
        block.add(m.group(0), QUOTE, line)
        pos = m.end()
    block.add(s[pos:], PROSE, line)


def parse_markdown(text):
    blocks, cur = [], None
    fence = None
    in_comment = False
    pending_repeat = False
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":  # YAML front matter
        for j in range(1, len(lines)):
            if lines[j].strip() in ("---", "..."):
                start = j + 1
                break

    def flush():
        nonlocal cur
        if cur is not None and cur.runs:
            blocks.append(cur)
        cur = None

    def new_block(ln):
        nonlocal pending_repeat
        b, pending_repeat = Block(ln, repeat=pending_repeat), False
        return b

    for i in range(start, len(lines)):
        ln, raw = i + 1, lines[i]
        s = raw.strip()
        if fence:
            if s.startswith(fence):
                fence = None
            continue
        m = re.match(r"^(`{3,}|~{3,})", s)
        if m:
            flush()
            fence, pending_repeat = m.group(1), False  # a marker must sit directly on its block
            continue
        if not s:
            pending_repeat = False
        if in_comment:
            if "-->" in s:
                in_comment = False
            continue
        if REPEAT_MARK.match(s):  # <!-- voice: repeat --> marks the next block as a deliberate repeat
            flush()
            pending_repeat = True
            continue
        if s.startswith("<!--") and "-->" not in s:
            in_comment = True
            continue
        if s.startswith("<!--") and s.endswith("-->"):
            continue
        if not s or re.match(r"^\[[^\]]+\]:\s*\S+", s) or re.match(r"^\|?\s*:?-{3,}", s):
            flush()
            continue
        if s.startswith(">"):
            flush()
            b = new_block(ln)
            b.add(_md_inline(s.lstrip("> ")), QUOTE, ln)
            blocks.append(b)
            continue
        if s.startswith("|"):  # table row (header or body): spelling only, outside quotation marks
            flush()
            b = new_block(ln)
            b.add(_md_inline(s), TABLE, ln)
            blocks.append(b)
            continue
        mh = re.match(r"^#{1,6}\s+(.*)$", s)
        ml = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)$", s)
        if mh or ml:
            flush()
            b = new_block(ln)
            _md_add(b, (mh or ml).group(1), ln)
            if mh:
                blocks.append(b)
            else:
                cur = b
            continue
        if cur is None:
            cur = new_block(ln)
        _md_add(cur, s, ln)
    flush()
    return blocks


# ---------------------------------------------------------------- rules

STOP = set("""a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her here
hers him his how i if in into is it its itself just me more most my no nor not now of off on once only or other our ours
out over own same she should so some such than that the their theirs them then there these they this those through to
too under until up very was we were what when where which while who whom why will with would you your yours
may might must shall one two also than yet it's we're you're don't doesn't isn't""".split())
SENT_RX = re.compile(r"(?<=[.!?])[\"'”’)]*\s+(?=[\"'“‘(]*[A-Z0-9])")


def words(s):
    return WORD_RX.findall(s)


def sentences(text):
    text = re.sub(r"\s+", " ", URL_RX.sub(" ", text)).strip()
    return [s.strip() for s in SENT_RX.split(text) if s.strip()] if text else []


def _stem(w):
    w = w.lower().replace("’", "'")
    for sfx in ("'s", "ing", "ed", "es", "s"):
        if w.endswith(sfx) and len(w) - len(sfx) >= 3:
            return w[: -len(sfx)]
    return w


def content_words(s):
    return {_stem(w) for w in words(s) if w.lower() not in STOP and len(w) > 2 and not w.isdigit()}


def syllables(w):
    w = w.lower()
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def load_allow(path):
    out = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.split("#", 1)[0].strip()
        if s:
            out.append(re.compile(r"\s+".join(re.escape(p) for p in s.split()), re.I))
    return out


def _mask(text, rxs):
    for rx in rxs:
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    return text


def spelling_findings(blocks, allow):
    out = []
    for b in blocks:
        for text, kind, line in b.runs:
            if kind not in (PROSE, TABLE):
                continue
            # a table cell is checked too, except text inside quotation marks (titles, quotes)
            t = _mask(text, [URL_RX] + allow + ([QUOTED_RX] if kind == TABLE else []))
            for rx, us in TWO_WORD:
                for m in rx.finditer(t):
                    out.append({"line": line + t.count("\n", 0, m.start()), "word": m.group(0), "us": us})
            for m in re.finditer(r"[A-Za-z]+", t):
                us = us_for(m.group(0))
                if not us:
                    continue
                before = t[m.start() - 1] if m.start() else " "
                after = t[m.end():m.end() + 2]
                if before in "/_@\\." or (after[:1] and after[:1] in "/_@\\") or re.match(r"\.[A-Za-z0-9]", after):
                    continue  # file name, path, identifier, address
                out.append({"line": line + t.count("\n", 0, m.start()), "word": m.group(0), "us": us})
    return out


LABEL_RX = re.compile(r"^\s*([A-Z][A-Za-z'’ ]{1,40}?)\s*:")


def analyse(blocks, allow=(), budget=1800, long_words=30, rep_ratio=0.70, rep_min_words=6, label_min=5):
    res = {"errors": [], "warnings": [], "info": {}}
    for f in spelling_findings(blocks, list(allow)):
        res["errors"].append({"rule": "uk-spelling", "line": f["line"],
                              "message": f"'{f['word']}' -> '{f['us']}'", "word": f["word"], "suggest": f["us"]})
    sents = []  # (index, line, text)
    repeat_ok = set()  # sentence indexes inside a deliberate-repeat marker
    labels = {}
    total_words = 0
    for b in blocks:
        total_words += len(words(b.all_text()))
        eng = b.english_text()
        if not eng.strip():
            continue
        flat = re.sub(r"\s+", " ", eng).strip()
        m = LABEL_RX.match(flat)
        if b.repeat:
            pass  # a marked, deliberate repeat is not counted as a template label
        elif m and len(m.group(1).split()) <= 6:
            labels.setdefault(m.group(1).strip(), []).append(b.line)
        elif len(words(flat)) <= 5 and not re.search(r"[.!?]$", flat) and len(words(flat)) >= 1:
            labels.setdefault(flat, []).append(b.line)
        for s in sentences(eng):
            sents.append((len(sents) + 1, b.line, s))
            if b.repeat:
                repeat_ok.add(len(sents))
    for idx, line, s in sents:
        n = len(words(s))
        if n >= long_words:
            res["warnings"].append({"rule": "long-sentence", "line": line, "sentence": idx, "words": n,
                                    "message": f"{n} words: \"{s[:160]}{'...' if len(s) > 160 else ''}\""})
    cands = [(i, line, s, content_words(s)) for i, line, s in sents if len(words(s)) >= rep_min_words]
    for a in range(len(cands)):
        ia, la, sa, ca = cands[a]
        if len(ca) < 4:
            continue
        for b2 in range(a + 1, len(cands)):
            ib, lb, sb, cb = cands[b2]
            if len(cb) < 4 or ia in repeat_ok or ib in repeat_ok:
                continue
            shared = ca & cb
            ratio = len(shared) / min(len(ca), len(cb))
            if len(shared) >= 4 and ratio >= rep_ratio:
                res["warnings"].append({
                    "rule": "repetition", "line": la, "sentence": ia, "other_line": lb, "other_sentence": ib,
                    "overlap": round(ratio, 2), "first": sa, "second": sb,
                    "message": f"{round(ratio * 100)}% shared content words with sentence {ib} (line {lb}): "
                               f"\"{sa[:120]}\" / \"{sb[:120]}\""})
    for lab, lines in sorted(labels.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(lines) >= label_min:
            res["warnings"].append({"rule": "label-template", "line": lines[0], "label": lab, "count": len(lines),
                                    "message": f"'{lab}' used {len(lines)} times (lines {', '.join(map(str, lines[:12]))})"})
    if total_words > budget:
        res["warnings"].append({"rule": "page-length", "line": 0, "words": total_words, "budget": budget,
                                "message": f"{total_words} words, over the budget of {budget}"})
    eng_words = sum(len(words(s)) for _, _, s in sents)
    if sents and eng_words:
        syl = sum(syllables(w) for _, _, s in sents for w in words(s))
        grade = 0.39 * eng_words / len(sents) + 11.8 * syl / eng_words - 15.59
        res["info"] = {"words": total_words, "sentences": len(sents), "words_per_sentence": round(eng_words / len(sents), 1),
                       "fk_grade": round(grade, 1)}
    else:
        res["info"] = {"words": total_words, "sentences": 0, "words_per_sentence": 0, "fk_grade": None}
    return res


def check_file(path, **kw):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    is_html = Path(path).suffix.lower() in (".html", ".htm") or re.match(r"\s*<(!doctype|html)", text, re.I)
    return analyse(parse_html(text) if is_html else parse_markdown(text), **kw)


def report(path, r):
    lines = []
    for e in r["errors"]:
        lines.append(f"ERROR {path}:{e['line']}: {e['rule']}: {e['message']}")
    for w in r["warnings"]:
        lines.append(f"WARN {path}:{w['line']}: {w['rule']}: {w['message']}")
    i = r["info"]
    g = "n/a" if i["fk_grade"] is None else i["fk_grade"]
    lines.append(f"INFO {path}: reading-grade: Flesch-Kincaid {g}, {i['sentences']} sentence(s), "
                 f"{i['words_per_sentence']} words a sentence (informational)")
    lines.append(f"SUMMARY {path}: {i['words']} words, {len(r['errors'])} error(s), {len(r['warnings'])} warning(s)")
    return lines


# ---------------------------------------------------------------- self-test

def self_test():
    import tempfile
    fails, count = [], [0]

    def ok(name, cond, detail=""):
        count[0] += 1
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  ({detail})"))
        if not cond:
            fails.append(name)

    def rules(r, kind="errors"):
        return [x["rule"] for x in r[kind]]

    h = lambda body: analyse(parse_html(f"<!doctype html><html lang='en'><body>{body}</body></html>"))
    r = h("<p>Read the licence first.</p>")
    ok("uk spelling in prose is an error", rules(r) == ["uk-spelling"] and r["errors"][0]["suggest"] == "license", r)
    r = h("<blockquote><p>Read the licence first.</p></blockquote><p>We <q>organise</q> and <cite>Centre for X</cite>.</p>")
    ok("blockquote, q and cite are exempt", rules(r) == [], r)
    r = h("<p lang='es-MX'>colour</p><p>See <code>colour</code> and <a href='/centre/organisation.html'>this</a>.</p>")
    ok("other language, code and attributes are exempt", rules(r) == [], r)
    r = h("<p>Open https://example.org/licence and organisation_id and notes/centre and colour.css today.</p>")
    ok("urls, identifiers, paths and file names are exempt", rules(r) == [], r)
    r = analyse(parse_html("<p>The World Health Organisation said so.</p>"),
                allow=[re.compile(r"World\s+Health\s+Organisation", re.I)])
    ok("allow-list phrase is exempt", rules(r) == [], r)
    r = h("<p>Ask a carer, then the Centre.</p>")
    ok("carer and capitalized words are caught", [e["suggest"] for e in r["errors"]] == ["caregiver", "Center"], r)
    md = "# T\n\n> The licence is quoted.\n\n```\ncolour\n```\n\nOur `colour` code is fine.\n\nOur colour is not.\n"
    r = analyse(parse_markdown(md))
    ok("markdown quote and code exempt, prose caught", [(e["line"], e["word"]) for e in r["errors"]] == [(11, "colour")], r)
    long = "We " + " ".join(["read"] * 30) + "."
    r = h(f"<p>{long}</p>")
    ok("30-word sentence warns", "long-sentence" in rules(r, "warnings"), r)
    r = h("<p>Take the inhaled medicine every morning before breakfast.</p><p>Short one.</p>"
          "<p>Other words here.</p><p>Every morning before breakfast, take the inhaled medicine.</p>")
    ok("repeated idea far apart warns", rules(r, "warnings") == ["repetition"], r)
    r = h("".join("<p>How strong: moderate evidence here.</p>" for _ in range(5)))
    ok("label used five times warns", "label-template" in rules(r, "warnings"), r)
    r = h("".join("<p>How strong: moderate evidence here.</p>" for _ in range(4)))
    ok("label used four times does not", "label-template" not in rules(r, "warnings"), r)
    r = analyse(parse_html("<p>" + "word " * 50 + "</p>"), budget=40)
    ok("page over budget warns", "page-length" in rules(r, "warnings"), r)
    ok("grade is reported", r["info"]["fk_grade"] is not None, r["info"])
    tab = "| A | B |\n| --- | --- |\n| colour | \"A Randomised Trial\" |\n"
    r = analyse(parse_markdown(tab))
    ok("table cells: plain text checked, quoted text exempt", [e["word"] for e in r["errors"]] == ["colour"], r)
    r = h(f"<p>{long}</p>".replace("<p>We ", "<p>We said <q>").replace(".</p>", "</q>.</p>"))
    ok("inline <q> text is left out of sentence length", "long-sentence" not in rules(r, "warnings"), r)
    r = h("<p>Take the inhaled medicine every morning before breakfast.</p><p>Short one.</p>"
          "<p data-voice='repeat'>Every morning before breakfast, take the inhaled medicine.</p>")
    ok("data-voice=repeat suppresses repetition", "repetition" not in rules(r, "warnings"), r)
    r = analyse(parse_markdown("".join(f"<!-- voice: repeat -->\nHow strong: low, item {i}.\n\n" for i in range(5))))
    ok("markdown repeat marker suppresses label templates", "label-template" not in rules(r, "warnings"), r)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.md"
        p.write_text("Our colour.\n", encoding="utf-8")
        ok("check_file reads markdown", rules(check_file(p)) == ["uk-spelling"])
    print(f"{count[0] - len(fails)}/{count[0]} passed")
    return 1 if fails else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # a quoted title or an arrow must not crash a console that cannot encode it
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--allow", help="file of phrases (names, titles) that keep their spelling, one per line")
    ap.add_argument("--budget", type=int, default=1800, help="page length budget in words (default 1800)")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON instead of lines")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.files:
        ap.print_usage(sys.stderr)
        print("error: name at least one file", file=sys.stderr)
        return 2
    try:
        allow = load_allow(a.allow) if a.allow else []
    except OSError as e:
        print(f"error: cannot read allow file: {e}", file=sys.stderr)
        return 2
    results, missing = {}, []
    for f in a.files:
        if not Path(f).is_file():
            missing.append(f)
            continue
        results[f] = check_file(f, allow=allow, budget=a.budget)
    if missing:
        print("error: not a file: " + ", ".join(missing), file=sys.stderr)
        return 2
    n_err = sum(len(r["errors"]) for r in results.values())
    n_warn = sum(len(r["warnings"]) for r in results.values())
    if a.json:
        print(json.dumps({"files": results, "errors": n_err, "warnings": n_warn}, indent=2, ensure_ascii=False))
    else:
        for f, r in results.items():
            print("\n".join(report(f, r)))
        print(f"{len(results)} file(s) checked: {n_err} error(s), {n_warn} warning(s)")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())

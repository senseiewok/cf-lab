"""Cite-check: find every DOI, PubMed id and ClinicalTrials.gov id in a text file and look each one up.

The lab's rule 5: citations go through the evidence record. A citation that cannot be resolved is deleted or fixed from a
source, never repaired from memory. This module reads a note, extracts identifiers, resolves each through the existing
single-lookup providers (Crossref ``work``, PubMed ``search`` on the ``[pmid]`` field, ClinicalTrials.gov ``study``) on the
caller's client, so the catalog gate, pacing, budget, circuit breaker and accounting apply unchanged.

Verdicts per identifier:
    PASS        the source returned a record for the id
    NOT FOUND   the source answered that there is no such id (delete it or fix it from a source; never guess)
    UNRESOLVED  the lookup was blocked, rate limited, refused or failed; unresolved is not the same as nonexistent

The title cross-check is informational. When the identifier's line carries a quoted or emphasised phrase of four or more
words, its words are compared with the record's title. A low overlap is TITLE CHECK, a prompt for a person to look, never an
error by itself. It checks that an identifier exists and roughly matches the wording; it does not check that the source
supports the sentence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .briefs import _run
from .http import Client
from .providers import crossref, pubmed, trials
from .record import Evidence, Status, clean_for_terminal

PROVIDER = "cite-check/0.1"
FOOTER = ("Research, not medical advice. This checks that an identifier exists and roughly matches the wording; "
          "it does not check that the source supports the sentence.")
NOT_STATED = "not stated"
DEFAULT_MAX_IDS = 30
HARD_MAX_IDS = 100          # a PMID costs two requests; 100 ids stay inside the 200-request process budget for DOIs and NCT ids
PASS, NOT_FOUND, UNRESOLVED = "PASS", "NOT FOUND", "UNRESOLVED"
TITLE_PASS, TITLE_CHECK, TITLE_NOT_STATED, TITLE_NOT_COMPARED = "TITLE PASS", "TITLE CHECK", "TITLE NOT STATED", "TITLE NOT COMPARED"
TITLE_MIN_WORDS = 4
TITLE_OVERLAP = 0.6
LINE_SHOWN = 200

# ----------------------------------------------------------------------------- extraction

# A DOI runs to the first whitespace or character that cannot end a citation in prose or markup. Brackets, angle brackets,
# quotes and backticks are excluded, so DOIs that contain them (old SICI DOIs) are cut short and will show as NOT FOUND.
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"'<>\[\]{}`|\\]+")
_TRAILING = ".,;:!?*_~"
_PMID = re.compile(r"(?i)\bPMID:?\s*(\d{1,9})(?!\d)")
_PUBMED_URL = re.compile(r"(?i)\bpubmed(?:\.ncbi\.nlm\.nih\.gov)?/(\d{1,9})(?!\d)")
_NCT = re.compile(r"(?i)(?<![A-Za-z0-9])NCT(\d{8})(?!\d)")


def clean_doi(raw: str) -> str:
    """Strip trailing punctuation and markup. A closing ')' is kept only while the DOI's parentheses balance."""
    s = raw
    while s:
        if s[-1] in _TRAILING:
            s = s[:-1]
        elif s[-1] == ")" and s.count(")") > s.count("("):
            s = s[:-1]
        else:
            break
    return s


@dataclass
class Found:
    kind: str            # "DOI", "PMID" or "NCT"
    ident: str
    line_no: int
    line: str            # the trimmed text of the line of first occurrence


def extract(text: str) -> list[Found]:
    """Every distinct identifier in reading order, with the line number and text of its first occurrence."""
    out: list[Found] = []
    seen: set[tuple[str, str]] = set()
    for n, line in enumerate(text.splitlines(), start=1):
        hits: list[tuple[int, str, str]] = []
        for m in _DOI.finditer(line):
            doi = clean_doi(m.group(0))
            if re.fullmatch(r"10\.\d{4,9}/.+", doi):
                hits.append((m.start(), "DOI", doi))
        for rx in (_PMID, _PUBMED_URL):
            for m in rx.finditer(line):
                hits.append((m.start(), "PMID", str(int(m.group(1)))))
        for m in _NCT.finditer(line):
            hits.append((m.start(), "NCT", "NCT" + m.group(1)))
        for _, kind, ident in sorted(hits):
            key = (kind, ident.lower())
            if key not in seen:
                seen.add(key)
                out.append(Found(kind, ident, n, line.strip()))
    return out


# ----------------------------------------------------------------------------- title cross-check

STOP = frozenset("a an and are as at be by for from in into is of on or the to with without its their this that than via vs".split())
_PHRASES = (re.compile(r"\"([^\"\n]+)\""), re.compile(r"“([^”\n]+)”"),
            re.compile(r"\*{1,2}([^*\n]+?)\*{1,2}"), re.compile(r"(?<![\w/])_([^_\n]+)_(?![\w/])"))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def tokens(text: str) -> set[str]:
    """Lowercase words with punctuation removed and a short stop-word list ignored."""
    return {w for w in _words(text) if w not in STOP}


def phrases(line: str) -> list[str]:
    """Quoted or emphasised phrases of at least four words on a line."""
    found = [m.group(1).strip() for rx in _PHRASES for m in rx.finditer(line)]
    return [p for p in found if len(_words(p)) >= TITLE_MIN_WORDS]


def overlap(a: str, b: str) -> float:
    """Shared tokens as a share of the smaller token set; 0.0 when either side has no tokens."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def title_check(line: str, record_title: Any) -> tuple[str, str]:
    """(verdict, detail). Uses the line's best-matching phrase; never an error by itself."""
    cands = phrases(line)
    if not cands:
        return TITLE_NOT_STATED, "no title given on the line"
    if not isinstance(record_title, str) or not record_title.strip():
        return TITLE_NOT_STATED, "the record states no title, so nothing was compared"
    best = max(cands, key=lambda p: overlap(p, record_title))
    score = overlap(best, record_title)
    if score >= TITLE_OVERLAP:
        return TITLE_PASS, f"overlap {score:.2f} (computed) between the line's phrase \"{best}\" and the record's title"
    return TITLE_CHECK, (f"the line's wording shares few words with the record's title (overlap {score:.2f}, computed; "
                         f"line phrase: \"{best}\"; record title: {record_title})")


# ----------------------------------------------------------------------------- resolution

@dataclass
class Item:
    found: Found
    record: Evidence
    verdict: str
    title_verdict: str
    title_detail: str
    shown: list[tuple[str, Any]] = field(default_factory=list)   # (label, value copied from the record, or NOT_STATED)


def _value(v: Any) -> Any:
    return NOT_STATED if v is None or v == "" or v == [] else v


def _lookup(client: Client, f: Found) -> Evidence:
    if f.kind == "DOI":
        step = _run("doi", crossref.SOURCE, f"What does Crossref hold for DOI {f.ident}?",
                    lambda: [crossref.work(client, f.ident)], provider=PROVIDER)
        return step.records[0]
    if f.kind == "NCT":
        step = _run("trial", trials.SOURCE, f"What does ClinicalTrials.gov hold for {f.ident}?",
                    lambda: trials.study(client, f.ident), provider=PROVIDER)
        return step.records[0]
    step = _run("pubmed", pubmed.SOURCE, f"Which PubMed record has PMID {f.ident}?",
                lambda: pubmed.search(client, f"{f.ident}[pmid]", 1), provider=PROVIDER)
    rec = step.records[0]
    if rec.status is Status.FOUND and str(rec.fields.get("pmid")) != f.ident:
        return Evidence(status=Status.ERROR, question=rec.question, source_id=pubmed.SOURCE, url=rec.url, provider=PROVIDER,
                        fields={"asked_pmid": f.ident, "returned_pmid": rec.fields.get("pmid")},
                        limitations="PubMed answered with a different record than the id asked for; establishes nothing about the id.")
    return rec


def _shown(f: Found, r: Evidence) -> list[tuple[str, Any]]:
    if f.kind == "NCT":
        return [("title", _value(r.fields.get("title"))), ("start", _value(r.fields.get("start"))),
                ("last update posted", _value(r.publisher_date))]
    label = "year" if f.kind == "DOI" else "publication date"
    return [("title", _value(r.fields.get("title"))), (label, _value(r.publisher_date))]


def resolve(client: Client, found: list[Found]) -> list[Item]:
    items = []
    for f in found:
        r = _lookup(client, f)
        if r.status is Status.FOUND:
            verdict = PASS
            tv, td = title_check(f.line, r.fields.get("title"))
        else:
            verdict = NOT_FOUND if r.status is Status.NOT_FOUND else UNRESOLVED
            tv, td = TITLE_NOT_COMPARED, "no record to compare with"
        items.append(Item(f, r, verdict, tv, td, _shown(f, r) if r.status is Status.FOUND else []))
    return items


# ----------------------------------------------------------------------------- report

@dataclass
class Report:
    path: str
    items: list[Item]

    @property
    def records(self) -> list[Evidence]:
        return [i.record for i in self.items]

    def counts(self) -> dict[str, int]:
        return {"identifiers": len(self.items),
                "found": sum(i.verdict == PASS for i in self.items),
                "not_found": sum(i.verdict == NOT_FOUND for i in self.items),
                "unresolved": sum(i.verdict == UNRESOLVED for i in self.items),
                "title_checks": sum(i.title_verdict == TITLE_CHECK for i in self.items)}

    def summary_line(self) -> str:
        c = self.counts()
        return (f"{c['identifiers']} identifiers, {c['found']} found, {c['not_found']} not found, "
                f"{c['unresolved']} unresolved, {c['title_checks']} title checks")

    def text(self) -> str:
        out = [f"cite-check {self.path}", ""]
        for i in self.items:
            f, r = i.found, i.record
            head = f"{i.verdict:<10} {f.kind} {f.ident} (line {f.line_no}) | {r.source_id} [{r.status.value}]"
            if i.verdict == PASS:
                head += " | " + " | ".join(f"{k}: {_show(v)}" for k, v in i.shown)
            out.append(head)
            if i.verdict == NOT_FOUND:
                out.append("           the source answered that there is no such id: delete or fix it from a source; never guess")
            elif i.verdict == UNRESOLVED:
                why = (r.fields.get("refused") or r.fields.get("error") or r.fields.get("shape_error")
                       or f"record status {r.status.value}, http_status {_show(_value(r.fields.get('http_status')))}")
                out.append(f"           unresolved is not the same as nonexistent: the lookup did not complete ({why})")
            out.append(f"           {i.title_verdict} ({i.title_detail})" if i.title_verdict != TITLE_CHECK
                       else f"           {TITLE_CHECK}: {i.title_detail}")
            line = f.line if len(f.line) <= LINE_SHOWN else f.line[: LINE_SHOWN - 1] + "…"
            out.append(f"           line: {line}")
        out += ["", self.summary_line(), "", FOOTER]
        return "\n".join(clean_for_terminal(x) for x in out)

    def summary(self) -> dict:
        return {"cite_check": {
            "file": self.path,
            "identifiers": [{"kind": i.found.kind, "id": i.found.ident, "line": i.found.line_no, "verdict": i.verdict,
                             "record_status": i.record.status.value, "source_id": i.record.source_id,
                             "fields": {k: v for k, v in i.shown}, "title_check": i.title_verdict, "title_detail": i.title_detail}
                            for i in self.items],
            "counts": self.counts(), "footer": FOOTER}}

    def summary_json(self) -> str:
        return json.dumps(self.summary(), ensure_ascii=False, sort_keys=True)

    def exit_code(self, dry_run: bool = False) -> int:
        """3 when any lookup was unresolved (blocked, rate limited, refused, error); 1 when any id is NOT FOUND; else 0."""
        if any(i.record.status in (Status.BLOCKED, Status.RATE_LIMITED, Status.ERROR) for i in self.items):
            return 3
        if not dry_run and any(i.verdict == UNRESOLVED for i in self.items):
            return 3
        if any(i.verdict == NOT_FOUND for i in self.items):
            return 1
        return 0


def _show(v: Any) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def run(client: Client, path: str, text: str) -> Report:
    return Report(path, resolve(client, extract(text)))

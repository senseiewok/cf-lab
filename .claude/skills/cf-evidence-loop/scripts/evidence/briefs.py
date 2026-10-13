"""Briefs: one question, several sources, one cross-checked set of records.

A brief runs a fixed recipe of existing single-source queries through the same client (same catalog gate, pacing, budget
and circuit breaker), keeps every record each query returns, and adds a short block of cross-checks. It adds no fact of its
own: every value it prints is copied from a record field, and where a source gave no value the brief says "not stated".
A comparison it computes (a difference in years, a count) is labelled as computed.

A source that is refused, blocked, rate limited or fails does not stop the brief. The failure becomes a record with that
status, the other sources still run, and the command's exit code follows the usual rule (3 when any record is bad).

Recipes:
    drug <BRAND>        approval + label (openFDA), trials by term (ClinicalTrials.gov, 5), pubmed by brand (5)
    variant "<query>"   variants (ClinVar) + pubmed for the same term (5)
    trial <NCTId>       trial (ClinicalTrials.gov) + pubmed for the NCT id (5)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from . import catalog
from .http import BudgetExhausted, Client, HostInCooldown, PaperworkMissing, RobotsDisallow
from .providers import clinvar, openfda, pubmed, trials
from .record import Evidence, Status, clean_for_terminal

RECIPES = ("drug", "variant", "trial")
FOOTER = "Research, not medical advice. A brief lists public documents; it does not interpret anything for a person."
NOT_STATED = "not stated"
PASS, CHECK, NOTE = "PASS", "CHECK", "NOT STATED"
PUBMED_LIMIT = 5
TRIALS_LIMIT = 5

REFUSALS = (BudgetExhausted, HostInCooldown, PaperworkMissing, RobotsDisallow, catalog.AccessDenied, catalog.UnknownSource)
BRIEF_PROVIDER = "brief/0.1"


@dataclass
class Step:
    name: str            # the single-source command this step runs, e.g. "approval"
    source_id: str
    records: list[Evidence]

    @property
    def status(self) -> str:
        """The step's status: the first bad status if any record has one, else found if any record was found, else the first status."""
        bad = [r.status for r in self.records if r.status in (Status.BLOCKED, Status.RATE_LIMITED, Status.ERROR)]
        if bad:
            return bad[0].value
        if any(r.status is Status.FOUND for r in self.records):
            return Status.FOUND.value
        return self.records[0].status.value if self.records else NOT_STATED

    def found(self) -> list[Evidence]:
        return [r for r in self.records if r.status is Status.FOUND]


@dataclass
class Check:
    verdict: str         # PASS, CHECK or NOT STATED
    what: str
    detail: str


@dataclass
class Brief:
    recipe: str
    subject: str
    steps: list[Step] = field(default_factory=list)
    facts: list[tuple[str, str, Any]] = field(default_factory=list)   # (step, field, value copied from a record, or NOT_STATED)
    checks: list[Check] = field(default_factory=list)

    @property
    def records(self) -> list[Evidence]:
        return [r for s in self.steps for r in s.records]

    def text(self) -> str:
        out = [f"brief {self.recipe} {self.subject}", "", "records (one line per record; accessed is when the tool asked, UTC):"]
        for s in self.steps:
            for r in s.records:
                out.append(f"  {r.one_line()} | accessed={r.accessed}")
        out += ["", "sources:"]
        for s in self.steps:
            out.append(f"  {s.name} ({s.source_id}): {s.status}, {len(s.records)} record(s)")
        if self.facts:
            out += ["", "fields (copied from the records above):"]
            for step, key, value in self.facts:
                out.append(f"  {step} {key}: {_show(value)}")
        out += ["", "cross-checks:"]
        for c in self.checks:
            out.append(f"  {c.verdict:<10} {c.what}: {c.detail}")
        out += ["", FOOTER]
        return "\n".join(clean_for_terminal(line) for line in out)

    def summary(self) -> dict:
        """The brief's own JSON object, printed after the records with --json. It holds no record data beyond copied fields."""
        return {"brief": {"recipe": self.recipe, "subject": self.subject,
                          "sources": [{"step": s.name, "source_id": s.source_id, "status": s.status, "records": len(s.records)} for s in self.steps],
                          "fields": [{"step": st, "field": k, "value": v} for st, k, v in self.facts],
                          "cross_checks": [{"verdict": c.verdict, "check": c.what, "detail": c.detail} for c in self.checks],
                          "footer": FOOTER}}

    def summary_json(self) -> str:
        return json.dumps(self.summary(), ensure_ascii=False, sort_keys=True)


def _show(value: Any) -> str:
    if value is None or value == "" or value == []:
        return NOT_STATED
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _value(rec: Evidence | None, key: str) -> Any:
    """A field copied from a record, or NOT_STATED when there is no record or the field is absent or empty."""
    if rec is None:
        return NOT_STATED
    v = rec.fields.get(key)
    return NOT_STATED if v is None or v == "" or v == [] else v


def _run(name: str, source_id: str, question: str, call: Callable[[], list[Evidence]], provider: str = BRIEF_PROVIDER) -> Step:
    """Run one source query. A refusal or failure becomes a record; it never stops the brief (or a cite-check)."""
    try:
        recs = call()
    except REFUSALS as exc:
        recs = [Evidence(status=Status.BLOCKED, question=question, source_id=source_id, url=NOT_STATED, provider=provider,
                         fields={"refused": f"{type(exc).__name__}: {str(exc)[:200]}"},
                         limitations="Refused by this tool's conduct rules before or instead of a request; establishes nothing about the subject.")]
    except Exception as exc:  # noqa: BLE001  a provider failure in one step must not stop the others
        recs = [Evidence(status=Status.ERROR, question=question, source_id=source_id, url=NOT_STATED, provider=provider,
                         fields={"error": f"{type(exc).__name__}: {str(exc)[:200]}"},
                         limitations="This query failed inside the tool; establishes nothing about the subject.")]
    if not recs:
        recs = [Evidence(status=Status.NOT_FOUND, question=question, source_id=source_id, url=NOT_STATED, provider=provider,
                         fields={}, limitations="The query returned no record at all; establishes nothing about the subject.")]
    return Step(name, source_id, recs)


def _source_checks(b: Brief) -> None:
    for s in b.steps:
        verdict = PASS if s.status == Status.FOUND.value else CHECK
        b.checks.append(Check(verdict, f"source {s.name} ({s.source_id})", s.status))


def _year(value: Any) -> int | None:
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def approval_year_check(approval_date: Any, label_date: Any) -> Check:
    """A label's effective date can never be earlier than the drug's first approval. Label year before approval year is CHECK
    (one record is inconsistent), never an error; same or later is PASS; a missing date is NOT STATED, naming which."""
    what = "first-approval year vs label effective-date year"
    a, l = _year(approval_date), _year(label_date)
    if a is None or l is None:
        missing = [n for n, y in (("Drugs@FDA original_approval", a), ("openFDA label effective_time", l)) if y is None]
        return Check(NOTE, what, f"{' and '.join(missing)} not stated; cannot compare "
                                 f"(original_approval {_show(approval_date)}, effective_time {_show(label_date)})")
    if l < a:
        return Check(CHECK, what, f"label effective date {label_date} is earlier than first approval {approval_date}; "
                                  "one of the two records is inconsistent")
    return Check(PASS, what, f"first approval {approval_date}, label effective date {label_date}; "
                             "the label's effective date is its latest revision, so a later year is expected")


# ----------------------------------------------------------------------- recipes

def drug(client: Client, brand: str) -> Brief:
    b = Brief("drug", brand)
    b.steps.append(_run("approval", openfda.DRUGSFDA, f"FDA approval for '{brand}'", lambda: [openfda.approval(client, brand)]))
    b.steps.append(_run("label", openfda.LABEL, f"US label for '{brand}'", lambda: [openfda.label(client, brand)]))
    b.steps.append(_run("trials", trials.SOURCE, f"ClinicalTrials.gov studies matching '{brand}'",
                        lambda: trials.search(client, None, term=brand, limit=TRIALS_LIMIT)))
    b.steps.append(_run("pubmed", pubmed.SOURCE, f"PubMed records matching '{brand}'", lambda: pubmed.search(client, brand, PUBMED_LIMIT)))

    appr = next(iter(b.steps[0].found()), None)
    lab = next(iter(b.steps[1].found()), None)
    for key in ("application_number", "sponsor", "original_approval", "active_ingredients"):
        b.facts.append(("approval", key, _value(appr, key)))
    for key in ("set_id", "version", "effective_time"):
        b.facts.append(("label", key, _value(lab, key)))
    for name, step in (("trials", b.steps[2]), ("pubmed", b.steps[3])):
        first = next(iter(step.found()), None)
        b.facts.append((name, "search_total", _value(first, "search_total")))
        b.facts.append((name, "records returned (counted)", len(step.found())))

    _source_checks(b)
    b.checks.append(approval_year_check(_value(appr, "original_approval"), _value(lab, "effective_time")))
    return b


def variant(client: Client, term: str) -> Brief:
    b = Brief("variant", term)
    b.steps.append(_run("variants", clinvar.SOURCE, f"ClinVar records matching '{term}'", lambda: clinvar.variants(client, term)))
    b.steps.append(_run("pubmed", pubmed.SOURCE, f"PubMed records matching '{term}'", lambda: pubmed.search(client, term, PUBMED_LIMIT)))

    found = b.steps[0].found()
    for r in found:   # every matching record is listed; none is chosen
        acc = _show(_value(r, "accession"))
        for key in ("title", "classification", "review_status"):
            b.facts.append((f"variants {acc}", key, _value(r, key)))
        b.facts.append((f"variants {acc}", "last_evaluated", r.publisher_date or NOT_STATED))
    first_pm = next(iter(b.steps[1].found()), None)
    b.facts.append(("pubmed", "search_total", _value(first_pm, "search_total")))
    b.facts.append(("pubmed", "records returned (counted)", len(b.steps[1].found())))

    _source_checks(b)
    if len(found) == 1:
        b.checks.append(Check(PASS, "ClinVar matches", "one record matched"))
    elif len(found) > 1:
        classes = sorted({str(_value(r, "classification")) for r in found})
        b.checks.append(Check(CHECK, "ClinVar matches", f"{len(found)} records matched; all are listed, none was chosen. "
                                                        f"Classifications among them: {'; '.join(classes)}"))
    else:
        b.checks.append(Check(NOTE, "ClinVar matches", "no ClinVar record returned"))
    total = _value(found[0], "search_total") if found else NOT_STATED
    if isinstance(total, int) and total > len(found):
        b.checks.append(Check(CHECK, "ClinVar listing complete", f"ClinVar search_total {total}; {len(found)} listed (limit {clinvar.MAX_IDS})"))
    for r in found:
        acc = _show(_value(r, "accession"))
        if _value(r, "classification") == NOT_STATED or _value(r, "review_status") == NOT_STATED:
            b.checks.append(Check(NOTE, f"classification of {acc}",
                                  f"classification {_show(_value(r, 'classification'))}, review_status {_show(_value(r, 'review_status'))}"))
    return b


def trial(client: Client, nct_id: str) -> Brief:
    b = Brief("trial", nct_id)
    b.steps.append(_run("trial", trials.SOURCE, f"ClinicalTrials.gov record {nct_id}", lambda: trials.study(client, nct_id)))
    b.steps.append(_run("pubmed", pubmed.SOURCE, f"PubMed records matching '{nct_id}'", lambda: pubmed.search(client, nct_id, PUBMED_LIMIT)))

    reg = next(iter(b.steps[0].found()), None)
    for key in ("nct_id", "title", "status", "phases", "sponsor", "start", "primary_completion", "has_results"):
        b.facts.append(("trial", key, _value(reg, key)))
    papers = b.steps[1].found()
    first_pm = next(iter(papers), None)
    b.facts.append(("pubmed", "search_total", _value(first_pm, "search_total")))
    b.facts.append(("pubmed", "records returned (counted)", len(papers)))

    _source_checks(b)
    reg_id = _value(reg, "nct_id")
    if reg_id == NOT_STATED:
        b.checks.append(Check(NOTE, "registry id", "the registry record states no nct_id"))
    else:
        b.checks.append(Check(PASS if str(reg_id).upper() == nct_id.upper() else CHECK, "registry id",
                              f"asked for {nct_id}; registry record nct_id {reg_id}"))
    needle = nct_id.upper()
    for p in papers:
        pmid, title = _show(_value(p, "pmid")), _value(p, "title")
        if isinstance(title, str) and needle in title.upper():
            b.checks.append(Check(PASS, f"PMID {pmid} mentions {nct_id}", "in its title field"))
        else:
            b.checks.append(Check(NOTE, f"PMID {pmid} mentions {nct_id}",
                                  "not in its title; the record carries no abstract or full text, so whether the paper's text names the trial is not stated"))
    return b


def run(client: Client, recipe: str, subject: str) -> Brief:
    if recipe == "drug":
        return drug(client, subject)
    if recipe == "variant":
        return variant(client, subject)
    if recipe == "trial":
        return trial(client, subject)
    raise ValueError(f"unknown brief recipe {recipe!r}; choose one of {', '.join(RECIPES)}")

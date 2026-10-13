"""openFDA: Drugs@FDA approval history and the current US label.

Two catalog sources: ``openfda-drugsfda`` and ``openfda-label``. US only.
A label is not eligibility for any individual; this provider copies the
indication text so a human can read it, and nothing more.
"""

from __future__ import annotations

from ..http import Client, Fetch
from ..record import Evidence, Status

PROVIDER = "openfda/0.1"
DRUGSFDA = "openfda-drugsfda"
LABEL = "openfda-label"
DEFAULT_SECTIONS = ("indications_and_usage",)
EXCERPT_CHARS = 700


def _fmt_date(s: str | None) -> str | None:
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if s and len(s) == 8 and s.isdigit() else s


def parse_approval(data: dict, brand: str, question: str, url: str) -> Evidence:
    results = data.get("results") or []
    if not results:
        return Evidence(status=Status.NOT_FOUND, question=question, source_id=DRUGSFDA, url=url, provider=PROVIDER,
                        fields={"brand": brand}, limitations="No Drugs@FDA application matched this brand name; check spelling or search by application number.")
    app = results[0]
    subs = app.get("submissions") or []
    orig = sorted((s for s in subs if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"),
                  key=lambda s: s.get("submission_status_date", ""))
    first = _fmt_date(orig[0]["submission_status_date"]) if orig else None
    latest = _fmt_date(max((s.get("submission_status_date", "") for s in subs), default=None) or None)
    prods = app.get("products") or []
    ingredients = sorted({i.get("name") for p in prods for i in (p.get("active_ingredients") or []) if i.get("name")})
    return Evidence(
        status=Status.FOUND, question=question, source_id=DRUGSFDA, url=url, provider=PROVIDER, publisher_date=first,
        fields={"brand": brand, "application_number": app.get("application_number"), "sponsor": app.get("sponsor_name"),
                "original_approval": first, "latest_submission_action": latest, "active_ingredients": ingredients,
                "dosage_forms": sorted({p.get("dosage_form") for p in prods if p.get("dosage_form")}),
                "submissions": len(subs)},
        limitations=("US FDA only. 'original_approval' is the earliest approved ORIG submission in Drugs@FDA; "
                     "supplements may have changed the indication or age range since. Says nothing about EU or other regulators, "
                     "or about any individual's eligibility."),
    )


def parse_label(data: dict, brand: str, sections: tuple[str, ...], question: str, url: str) -> Evidence:
    results = data.get("results") or []
    if not results:
        return Evidence(status=Status.NOT_FOUND, question=question, source_id=LABEL, url=url, provider=PROVIDER,
                        fields={"brand": brand}, limitations="No label matched this brand name in openFDA.")
    lab = results[0]
    texts = {s: " ".join(lab.get(s) or []) for s in sections}
    first = next((t for t in texts.values() if t), "")
    return Evidence(
        status=Status.FOUND, question=question, source_id=LABEL, url=url, provider=PROVIDER,
        publisher_date=_fmt_date(lab.get("effective_time")),
        fields={"brand": brand, "set_id": lab.get("set_id"), "version": lab.get("version"),
                "effective_time": _fmt_date(lab.get("effective_time")), "sections": list(sections),
                "section_chars": {s: len(t) for s, t in texts.items()}},
        excerpt=(first[:EXCERPT_CHARS] + ("…" if len(first) > EXCERPT_CHARS else "")) or None,
        limitations=("US prescribing information as indexed by openFDA; the DailyMed set_id is canonical. "
                     "Indication text describes a labelled population, not any individual's eligibility, access, or clinical benefit. "
                     "Excerpt is truncated; read the full section before quoting."),
    )


def _fail(f: Fetch, source: str, question: str) -> Evidence:
    return Evidence(status=f.status, question=question, source_id=source, url=f.url, provider=PROVIDER,
                    fields={"http_status": f.http_status}, limitations="No data returned; establishes nothing about the drug.")


def approval(client: Client, brand: str) -> Evidence:
    q = f"When did FDA first approve the application for brand '{brand}', and under what number?"
    f = client.get(DRUGSFDA, "drug/drugsfda.json", params={"search": f'openfda.brand_name:"{brand}"', "limit": 1})
    if f.status is Status.NOT_FOUND:
        return parse_approval({"results": []}, brand, q, f.url)
    return parse_approval(f.data, brand, q, f.url) if f.status is Status.FOUND else _fail(f, DRUGSFDA, q)


def label(client: Client, brand: str, sections: tuple[str, ...] = DEFAULT_SECTIONS) -> Evidence:
    q = f"What does the current US label for '{brand}' say in sections {', '.join(sections)}?"
    f = client.get(LABEL, "drug/label.json", params={"search": f'openfda.brand_name:"{brand}"', "limit": 1})
    if f.status is Status.NOT_FOUND:
        return parse_label({"results": []}, brand, sections, q, f.url)
    return parse_label(f.data, brand, sections, q, f.url) if f.status is Status.FOUND else _fail(f, LABEL, q)

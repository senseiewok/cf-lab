"""NIH RePORTER: who is funded to do what. Public API, POST search."""

from __future__ import annotations

from ..http import Client
from ..record import Evidence, Status

PROVIDER = "reporter/0.1"
SOURCE = "nih-reporter"
MAX_LIMIT = 50

LIMITATION = ("NIH-funded projects only; excludes CFF, industry, EU and other funders. Award amount is the fiscal-year amount "
              "returned by RePORTER, not the total. Project titles and abstracts are the applicants' own text.")


def parse_projects(data: dict, question: str, url: str) -> list[Evidence]:
    out = []
    for p in data.get("results") or []:
        pis = [x.get("full_name") for x in (p.get("principal_investigators") or [])][:3]
        out.append(Evidence(
            status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
            publisher_date=str(p.get("fiscal_year")) if p.get("fiscal_year") else None,
            fields={"project_num": p.get("project_num"), "title": p.get("project_title"),
                    "org": (p.get("organization") or {}).get("org_name"), "pis": pis,
                    "award_amount": p.get("award_amount"), "start": (p.get("project_start_date") or "")[:10] or None,
                    "end": (p.get("project_end_date") or "")[:10] or None, "agency": (p.get("agency_ic_admin") or {}).get("abbreviation")},
            limitations=LIMITATION,
        ))
    return out


def projects(client: Client, text: str, fiscal_years: list[int] | None = None, limit: int = 25) -> list[Evidence]:
    q = f"Which NIH projects match '{text}'" + (f" in FY {fiscal_years}" if fiscal_years else "") + "?"
    # Title and indexed terms only. Including abstracttext returns projects where the phrase is incidental.
    crit: dict = {"advanced_text_search": {"operator": "and", "search_field": "projecttitle,terms", "search_text": text}}
    if fiscal_years:
        crit["fiscal_years"] = fiscal_years
    f = client.post(SOURCE, "projects/search", json={"criteria": crit, "limit": min(limit, MAX_LIMIT), "offset": 0,
                                                     "sort_field": "award_amount", "sort_order": "desc"})
    if f.status is not Status.FOUND:
        return [Evidence(status=f.status, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"http_status": f.http_status}, limitations="Search failed; establishes nothing.")]
    recs = parse_projects(f.data, q, f.url)
    total = (f.data.get("meta") or {}).get("total")
    for r in recs:
        r.fields["search_total"] = total
    return recs or [Evidence(status=Status.NOT_FOUND, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                             fields={"text": text, "total": total}, limitations="No project matched.")]

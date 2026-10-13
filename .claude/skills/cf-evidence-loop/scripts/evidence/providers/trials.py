"""ClinicalTrials.gov API v2. Registry entries are sponsor-entered; they are not evidence of efficacy."""

from __future__ import annotations

from ..http import Client
from ..record import Evidence, Status

PROVIDER = "trials/0.1"
SOURCE = "clinicaltrials-gov"
FIELDS = ("NCTId,BriefTitle,OverallStatus,Phase,StudyType,StartDate,PrimaryCompletionDate,LeadSponsorName,Condition,"
          "InterventionName,EnrollmentCount,LastUpdatePostDate,PrimaryOutcomeMeasure,HasResults")
MAX_PAGE = 50

LIMITATION = ("Registry entry as entered by the sponsor; status and dates lag reality and enrollment may be anticipated rather than actual. "
              "A listed trial is not evidence that an intervention works, and results, when posted, live in a separate results section. "
              "Not a statement about any person's eligibility.")


def _g(d: dict, *path, default=None):
    for p in path:
        d = (d or {}).get(p)
        if d is None:
            return default
    return d


def parse_studies(data: dict, question: str, url: str) -> list[Evidence]:
    out = []
    for s in data.get("studies") or []:
        ps = s.get("protocolSection") or {}
        out.append(Evidence(
            status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
            publisher_date=_g(ps, "statusModule", "lastUpdatePostDateStruct", "date"),
            fields={"nct_id": _g(ps, "identificationModule", "nctId"), "title": _g(ps, "identificationModule", "briefTitle"),
                    "status": _g(ps, "statusModule", "overallStatus"), "phases": _g(ps, "designModule", "phases", default=[]),
                    "study_type": _g(ps, "designModule", "studyType"), "sponsor": _g(ps, "sponsorCollaboratorsModule", "leadSponsor", "name"),
                    "start": _g(ps, "statusModule", "startDateStruct", "date"),
                    "primary_completion": _g(ps, "statusModule", "primaryCompletionDateStruct", "date"),
                    "enrollment": _g(ps, "designModule", "enrollmentInfo", "count"),
                    "conditions": _g(ps, "conditionsModule", "conditions", default=[])[:4],
                    "interventions": [i.get("name") for i in _g(ps, "armsInterventionsModule", "interventions", default=[])][:4],
                    "primary_outcomes": [o.get("measure") for o in _g(ps, "outcomesModule", "primaryOutcomes", default=[])][:2],
                    "has_results": bool(s.get("hasResults"))},
            limitations=LIMITATION,
        ))
    return out


def study(client: Client, nct_id: str) -> list[Evidence]:
    q = f"What does ClinicalTrials.gov hold for {nct_id}?"
    f = client.get(SOURCE, f"studies/{nct_id}", params={"fields": FIELDS})
    if f.status is not Status.FOUND:
        return [Evidence(status=f.status, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"nct_id": nct_id, "http_status": f.http_status}, limitations="No registry record returned; establishes nothing.")]
    return parse_studies({"studies": [f.data]}, q, f.url)


def search(client: Client, condition: str | None, term: str | None = None, status: str | None = None, limit: int = 20) -> list[Evidence]:
    """Studies by condition, optionally narrowed by a free-text term. With condition None (a brief's drug search) only the term is sent."""
    head = f"list condition '{condition}'" + (f", term '{term}'" if term else "") if condition else f"match term '{term}'"
    q = f"Which ClinicalTrials.gov studies {head}" + (f", status {status}" if status else "") + "?"
    params = {"pageSize": min(limit, MAX_PAGE), "countTotal": "true", "fields": FIELDS}
    if condition:
        params = {"query.cond": condition, **params}
    if term:
        params["query.term"] = term
    if status:
        params["filter.overallStatus"] = status
    f = client.get(SOURCE, "studies", params=params)
    if f.status is not Status.FOUND:
        return [Evidence(status=f.status, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"http_status": f.http_status}, limitations="Search failed; establishes nothing.")]
    recs = parse_studies(f.data, q, f.url)
    total = f.data.get("totalCount")
    for r in recs:
        r.fields["search_total"] = total
    return recs or [Evidence(status=Status.NOT_FOUND, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                             fields={"condition": condition, "total": total}, limitations="No study matched the query.")]

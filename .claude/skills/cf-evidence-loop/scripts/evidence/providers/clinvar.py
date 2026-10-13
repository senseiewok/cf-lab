"""ClinVar via NCBI E-utilities. Variant-level classifications; never an interpretation for a person.

NCBI asks clients to send ``tool`` and ``email`` parameters and to stay under
3 requests/second without a key. The catalog entry sets the pacing.
"""

from __future__ import annotations

from ..http import Client
from ..record import Evidence, Status
from ..shape import ShapeError, error_record, esearch_result, esummary_result

PROVIDER = "clinvar/0.1"
SOURCE = "ncbi-eutils"
TOOL = "senseiewok-research-evidence"
MAX_IDS = 20

LIMITATION = ("ClinVar classification is aggregated from submitters and may be conflicting or outdated; review_status says how much "
              "it was reviewed. It is not a diagnosis, not eligibility for any therapy, and not an interpretation of any person's "
              "genotype. For CF-specific clinical annotation, CFTR2 is the field's authority; link to it.")


def _common(client: Client) -> dict:
    p = {"retmode": "json", "tool": TOOL}
    if client.contact:
        p["email"] = client.contact
    return p


def parse_summaries(data: dict, question: str, url: str) -> list[Evidence]:
    """FOUND records, one per uid. Raises ShapeError when the answer is not an esummary result (see shape.esummary_result)."""
    res, uids = esummary_result(data, "ClinVar summary")
    out = []
    for uid in uids:
        s = res.get(uid) or {}
        g = s.get("germline_classification") or {}
        out.append(Evidence(
            status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
            publisher_date=g.get("last_evaluated") or None,
            fields={"accession": s.get("accession"), "title": s.get("title"), "classification": g.get("description"),
                    "review_status": g.get("review_status"), "variation_type": s.get("obj_type"),
                    "genes": [x.get("symbol") for x in (s.get("genes") or [])][:3]},
            limitations=LIMITATION,
        ))
    return out


def variants(client: Client, term: str, limit: int = MAX_IDS) -> list[Evidence]:
    q = f"Which ClinVar records match '{term}', and how are they classified?"
    f = client.get(SOURCE, "esearch.fcgi", params={**_common(client), "db": "clinvar", "term": term, "retmax": min(limit, MAX_IDS)})
    if f.status is not Status.FOUND:
        return [Evidence(status=f.status, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"http_status": f.http_status}, limitations="Search failed; establishes nothing.")]
    try:
        ids, total = esearch_result(f.data, "ClinVar search")
    except ShapeError as exc:
        return [error_record(exc, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER)]
    if not ids:
        return [Evidence(status=Status.NOT_FOUND, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"term": term, "count": 0}, limitations="No ClinVar record matched; try the HGVS or legacy name.")]
    g = client.get(SOURCE, "esummary.fcgi", params={**_common(client), "db": "clinvar", "id": ",".join(ids)})
    if g.status is not Status.FOUND:
        return [Evidence(status=g.status, question=q, source_id=SOURCE, url=g.url, provider=PROVIDER,
                         fields={"http_status": g.http_status}, limitations="Summary fetch failed.")]
    try:
        recs = parse_summaries(g.data, q, g.url)
    except ShapeError as exc:
        return [error_record(exc, question=q, source_id=SOURCE, url=g.url, provider=PROVIDER, fields={"search_total": total})]
    if not recs:
        return [Evidence(status=Status.NOT_FOUND, question=q, source_id=SOURCE, url=g.url, provider=PROVIDER,
                         fields={"term": term, "search_total": total},
                         limitations="The search named records but the summary answer listed none; try the HGVS or legacy name.")]
    for r in recs:
        r.fields["search_total"] = total
    return recs

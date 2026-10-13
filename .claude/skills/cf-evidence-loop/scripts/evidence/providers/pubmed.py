"""PubMed via NCBI E-utilities: literature search, and a systematic-review view that reaches Cochrane reviews by their abstracts.

PubMed matches loosely without field tags. ``search`` sends the term as given; ``reviews`` scopes an
untagged term to title/abstract and adds the systematic-review subset filter.
"""

from __future__ import annotations

from ..http import Client
from ..record import Evidence, Status
from ..shape import ShapeError, error_record, esearch_result, esummary_result

PROVIDER = "pubmed/0.1"
SOURCE = "ncbi-eutils"
TOOL = "senseiewok-research-evidence"
MAX_IDS = 50

LIMITATION = ("Bibliographic record as indexed by PubMed; abstracts and MeSH indexing lag publication by weeks. Presence in PubMed is not "
              "a quality judgement, and publication type is the journal's label. Read the paper before citing its findings.")
REVIEW_LIMITATION = ("Systematic-review subset as defined by PubMed's filter plus the Cochrane journal; the filter has known false "
                     "positives and misses reviews not labelled as such. A review's conclusions depend on its search date; check it.")


def _common(client: Client) -> dict:
    p = {"retmode": "json", "tool": TOOL}
    if client.contact:
        p["email"] = client.contact
    return p


def review_term(term: str) -> str:
    scoped = term if "[" in term else f"({term}[tiab])"
    return f'{scoped} AND (systematic[sb] OR "Cochrane Database Syst Rev"[Journal])'


def parse_summaries(data: dict, question: str, url: str, limitation: str = LIMITATION) -> list[Evidence]:
    """FOUND records, one per uid. Raises ShapeError when the answer is not an esummary result (see shape.esummary_result)."""
    res, uids = esummary_result(data, "PubMed summary")
    out = []
    for uid in uids:
        s = res.get(uid) or {}
        ids = {a.get("idtype"): a.get("value") for a in (s.get("articleids") or [])}
        out.append(Evidence(
            status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
            publisher_date=s.get("pubdate") or None,
            fields={"pmid": uid, "title": s.get("title"), "journal": s.get("fulljournalname") or s.get("source"),
                    "first_author": s.get("sortfirstauthor"), "pub_types": s.get("pubtype") or [],
                    "doi": ids.get("doi"), "pmcid": ids.get("pmc")},
            limitations=limitation,
        ))
    return out


def _run(client: Client, term: str, question: str, limit: int, limitation: str, sort: str) -> list[Evidence]:
    f = client.get(SOURCE, "esearch.fcgi", params={**_common(client), "db": "pubmed", "term": term, "retmax": min(limit, MAX_IDS), "sort": sort})
    if f.status is not Status.FOUND:
        return [Evidence(status=f.status, question=question, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"http_status": f.http_status}, limitations="Search failed; establishes nothing.")]
    try:
        ids, total = esearch_result(f.data, "PubMed search")
    except ShapeError as exc:
        return [error_record(exc, question=question, source_id=SOURCE, url=f.url, provider=PROVIDER)]
    if not ids:
        return [Evidence(status=Status.NOT_FOUND, question=question, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"term": term, "count": 0}, limitations="No PubMed record matched this exact query; absence of a match is not absence of literature.")]
    g = client.get(SOURCE, "esummary.fcgi", params={**_common(client), "db": "pubmed", "id": ",".join(ids)})
    if g.status is not Status.FOUND:
        return [Evidence(status=g.status, question=question, source_id=SOURCE, url=g.url, provider=PROVIDER,
                         fields={"http_status": g.http_status}, limitations="Summary fetch failed.")]
    try:
        recs = parse_summaries(g.data, question, g.url, limitation)
    except ShapeError as exc:
        return [error_record(exc, question=question, source_id=SOURCE, url=g.url, provider=PROVIDER, fields={"search_total": total})]
    if not recs:
        return [Evidence(status=Status.NOT_FOUND, question=question, source_id=SOURCE, url=g.url, provider=PROVIDER,
                         fields={"term": term, "search_total": total},
                         limitations="The search named records but the summary answer listed none; absence of a summary is not absence of literature.")]
    for r in recs:
        r.fields["search_total"] = total
        r.fields["query"] = term
    return recs


def search(client: Client, term: str, limit: int = 20, sort: str = "relevance") -> list[Evidence]:
    return _run(client, term, f"Which PubMed records match '{term}'?", limit, LIMITATION, sort)


def reviews(client: Client, term: str, limit: int = 20) -> list[Evidence]:
    t = review_term(term)
    return _run(client, t, f"Which systematic reviews or Cochrane reviews match '{term}'?", limit, REVIEW_LIMITATION, "pub_date")

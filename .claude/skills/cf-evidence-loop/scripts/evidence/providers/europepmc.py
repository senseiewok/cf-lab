"""Europe PMC: literature search with open-access and citation metadata, and DOI lookup."""

from __future__ import annotations

from ..http import Client
from ..record import Evidence, Status

PROVIDER = "europepmc/0.1"
SOURCE = "europe-pmc"
MAX_PAGE = 100

LIMITATION = ("Europe PMC index record. citedByCount is Europe PMC's count and differs from Crossref's or Google Scholar's. "
              "isOpenAccess refers to the Europe PMC copy; licence terms for reuse vary per article. Not a quality judgement.")


def _rec(x: dict, question: str, url: str) -> Evidence:
    return Evidence(
        status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
        publisher_date=x.get("firstPublicationDate") or x.get("pubYear"),
        fields={"id": x.get("id"), "source": x.get("source"), "pmid": x.get("pmid"), "pmcid": x.get("pmcid"), "doi": x.get("doi"),
                "title": x.get("title"), "journal": x.get("journalTitle"), "year": x.get("pubYear"),
                "cited_by": x.get("citedByCount"), "open_access": x.get("isOpenAccess") == "Y",
                "pub_type": x.get("pubType"), "authors": (x.get("authorString") or "")[:120]},
        limitations=LIMITATION,
    )


def parse_search(data: dict, question: str, url: str) -> list[Evidence]:
    return [_rec(x, question, url) for x in ((data.get("resultList") or {}).get("result") or [])]


def search(client: Client, query: str, limit: int = 20) -> list[Evidence]:
    q = f"Which Europe PMC records match '{query}'?"
    f = client.get(SOURCE, "search", params={"query": query, "format": "json", "resultType": "lite", "pageSize": min(limit, MAX_PAGE)})
    if f.status is not Status.FOUND:
        return [Evidence(status=f.status, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"http_status": f.http_status}, limitations="Search failed; establishes nothing.")]
    recs = parse_search(f.data, q, f.url)
    total = f.data.get("hitCount")
    for r in recs:
        r.fields["search_total"] = total
    return recs or [Evidence(status=Status.NOT_FOUND, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                             fields={"query": query, "hitCount": total}, limitations="No record matched; Europe PMC query syntax is strict about field names.")]


def lookup(client: Client, doi: str) -> list[Evidence]:
    q = f"What does Europe PMC hold for DOI {doi}, including citation count and open-access status?"
    recs = search(client, f'DOI:"{doi}"', limit=3)
    for r in recs:
        r.question = q
    return recs

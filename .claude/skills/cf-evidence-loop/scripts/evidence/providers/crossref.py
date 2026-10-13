"""Crossref: DOI metadata and the retraction/correction lookup.

Crossref ingested the Retraction Watch database in 2023 and exposes retractions,
corrections and expressions of concern as ``update-to`` relations on the notice.
``works?filter=updates:<DOI>`` returns every notice that updates the given DOI.
"""

from __future__ import annotations

from urllib.parse import quote

from ..http import Client, Fetch
from ..record import Evidence, Status, now_utc
from ..shape import ShapeError, need, error_record

PROVIDER = "crossref/0.1"
SOURCE = "crossref"
WORK_FIELDS = "DOI,title,container-title,issued,type,author,publisher,update-to,is-referenced-by-count"

CLEAN_LIMITATION = (
    "Crossref holds no update notice (retraction, correction, expression of concern) for this DOI at access time. "
    "Publishers lag and some notices lack the update-to relation, so absence here is strong but not conclusive. "
    "Does not assess the quality of the work."
)
NOTICE_LIMITATION = (
    "A notice exists in Crossref; read it before concluding what was retracted or corrected and why. "
    "Notice type is the publisher's label."
)


def _year(item: dict) -> str | None:
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    y = parts[0][0] if parts and parts[0] else None
    return str(y) if y else None


def _authors(item: dict, n: int = 3) -> list[str]:
    return [a.get("family", "") for a in (item.get("author") or [])[:n]]


def parse_work(data: dict, question: str, url: str) -> Evidence:
    item = data.get("message", data)
    return Evidence(
        status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
        publisher_date=_year(item),
        fields={
            "doi": item.get("DOI"), "title": (item.get("title") or [None])[0],
            "container": (item.get("container-title") or [None])[0], "type": item.get("type"),
            "authors": _authors(item), "publisher": item.get("publisher"),
            "cited_by": item.get("is-referenced-by-count"),
        },
        limitations="Bibliographic record only; says nothing about the validity of the findings. Title and container are as deposited by the publisher.",
    )


def parse_updates(data: dict, doi: str, question: str, url: str) -> list[Evidence]:
    try:
        msg = need(data, "message", "Crossref response")
        items = need(msg, "items", "Crossref message")
        if not isinstance(items, list):
            raise ShapeError(f"Crossref message items is {type(items).__name__}, not a list")
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ShapeError(f"Crossref message items[{i}] is {type(item).__name__}, not an object")
    except ShapeError as exc:
        return [error_record(exc, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
                             fields={"doi": doi})]
    if not items:
        return [Evidence(status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
                         fields={"doi": doi, "update_notices": 0, "clean": True}, limitations=CLEAN_LIMITATION)]
    out = []
    for it in items:
        kinds = [u.get("type") for u in (it.get("update-to") or []) if (u.get("DOI") or "").lower() == doi.lower()]
        out.append(Evidence(
            status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER,
            publisher_date=_year(it),
            fields={"doi": doi, "clean": False, "notice_doi": it.get("DOI"), "notice_type": kinds or [it.get("type")],
                    "notice_title": (it.get("title") or [None])[0]},
            excerpt=(it.get("title") or [None])[0],
            limitations=NOTICE_LIMITATION,
        ))
    return out


def _fail(f: Fetch, question: str) -> Evidence:
    return Evidence(status=f.status, question=question, source_id=SOURCE, url=f.url, provider=PROVIDER,
                    fields={"http_status": f.http_status},
                    limitations="No data returned; this record establishes nothing about the DOI itself.")


def work(client: Client, doi: str) -> Evidence:
    q = f"What does Crossref hold for DOI {doi}?"
    # A DOI's own '/' stays a path separator; '?', '#', '%' and the like are escaped so they cannot change the URL's structure.
    f = client.get(SOURCE, f"works/{quote(doi, safe='/')}")
    return parse_work(f.data, q, f.url) if f.status is Status.FOUND else _fail(f, q)


def updates(client: Client, doi: str) -> list[Evidence]:
    q = f"Does Crossref hold any retraction, correction or expression-of-concern notice for DOI {doi}?"
    f = client.get(SOURCE, "works", params={"filter": f"updates:{doi}", "rows": 20, "select": WORK_FIELDS})
    return parse_updates(f.data, doi, q, f.url) if f.status is Status.FOUND else [_fail(f, q)]


def check_dois(client: Client, dois: list[str]) -> list[Evidence]:
    out: list[Evidence] = []
    for d in dois:
        out.extend(updates(client, d.strip()))
    return out

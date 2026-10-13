"""bioRxiv and medRxiv via api.biorxiv.org. Preprints are not peer reviewed; every record says so."""

from __future__ import annotations

import re
from urllib.parse import quote

from ..http import Client
from ..record import Evidence, Status
from ..shape import ShapeError, count, error_record, need

PROVIDER = "preprints/0.1"
SOURCE = "biorxiv"
SERVERS = ("biorxiv", "medrxiv")
CF_PATTERN = r"cystic fibrosis|\bCFTR\b"
MAX_PAGES = 10
PAGE = 100

LIMITATION = ("Preprint: not peer reviewed. 'published' gives the journal DOI if the server has linked one; "
              "otherwise the work may be unpublished, under review, or published without a link. Abstract text is the authors'.")


def _rec(item: dict, server: str, question: str, url: str) -> Evidence:
    return Evidence(
        status=Status.FOUND, question=question, source_id=SOURCE, url=url, provider=PROVIDER, publisher_date=item.get("date"),
        fields={"server": server, "doi": item.get("doi"), "title": item.get("title"), "version": item.get("version"),
                "category": item.get("category"), "published": item.get("published") or None,
                "authors": (item.get("authors") or "")[:120]},
        excerpt=(item.get("abstract") or "")[:400] or None,
        limitations=LIMITATION,
    )


def parse_details(data: dict, server: str, question: str, url: str, pattern: str | None = None) -> list[Evidence]:
    coll = data.get("collection") or []
    if pattern:
        rx = re.compile(pattern, re.I)
        coll = [c for c in coll if rx.search((c.get("title") or "") + " " + (c.get("abstract") or ""))]
    return [_rec(c, server, question, url) for c in coll]


def details(client: Client, server: str, doi: str) -> list[Evidence]:
    assert server in SERVERS, server
    q = f"What does {server} hold for preprint DOI {doi}?"
    # A DOI's own '/' stays a path separator; '?', '#', '%' and the like are escaped so they cannot change the URL's structure.
    f = client.get(SOURCE, f"details/{server}/{quote(doi, safe='/')}")
    if f.status is not Status.FOUND:
        return [Evidence(status=f.status, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                         fields={"http_status": f.http_status}, limitations="No data returned.")]
    recs = parse_details(f.data, server, q, f.url)
    return recs or [Evidence(status=Status.NOT_FOUND, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                             fields={"doi": doi}, limitations="Server returned no record for this DOI.")]


def window(client: Client, server: str, start: str, end: str, pattern: str = CF_PATTERN) -> list[Evidence]:
    """All preprints posted in [start, end] (YYYY-MM-DD) whose title or abstract matches ``pattern``."""
    assert server in SERVERS, server
    q = f"Which {server} preprints posted {start} to {end} match /{pattern}/?"
    out: list[Evidence] = []
    cursor = 0
    for _ in range(MAX_PAGES):
        f = client.get(SOURCE, f"details/{server}/{start}/{end}/{cursor}")
        if f.status is not Status.FOUND:
            out.append(Evidence(status=f.status, question=q, source_id=SOURCE, url=f.url, provider=PROVIDER,
                                fields={"http_status": f.http_status, "cursor": cursor}, limitations="Listing stopped early; results are partial."))
            break
        out.extend(parse_details(f.data, server, q, f.url, pattern))
        try:
            messages = need(f.data, "messages", "the response")
            if not isinstance(messages, list) or not messages:
                raise ShapeError("'messages' is empty or not a list")
            total = count(need(messages[0], "total", "messages[0]"), "messages[0].total")
        except ShapeError as exc:
            # Without the total we cannot tell whether the listing is complete, so say it is not.
            out.append(error_record(ShapeError(f"cannot read the total number of preprints: {exc}"), question=q, source_id=SOURCE, url=f.url,
                                    provider=PROVIDER, fields={"cursor": cursor}))
            break
        cursor += PAGE
        if cursor >= total:
            break
    else:
        out.append(Evidence(status=Status.OUT_OF_SCOPE, question=q, source_id=SOURCE, url="", provider=PROVIDER,
                            fields={"pages_read": MAX_PAGES}, limitations=f"Stopped after {MAX_PAGES} pages; narrow the date window for full coverage."))
    if not out:
        out.append(Evidence(status=Status.NOT_FOUND, question=q, source_id=SOURCE, url=f"{SOURCE}:details/{server}/{start}/{end}", provider=PROVIDER,
                            fields={"server": server, "start": start, "end": end, "pattern": pattern, "scanned": cursor},
                            limitations="No preprint in the window matched the pattern. The server was listed completely; the pattern may be too narrow."))
    return out

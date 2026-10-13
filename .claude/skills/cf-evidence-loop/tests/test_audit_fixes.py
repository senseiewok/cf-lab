"""Defects from the October 2026 audit. Each test failed before its fix; the negative controls passed before and after.

F1  An NCBI esummary answer of HTTP 200 with an {"error": ...} body gave zero records and exit 0, silently.
F5  A Retry-After of -1, 'nan' or 'inf' reached time.sleep and raised, so there was no record (R8).
F6  The robots.txt fetch followed redirects, had no body cap and was not paced (R1, R3, R4, R10).
F10 A '?' or '#' in a DOI changed the structure of the request URL.
No real network: responses are faked, or served by a custom transport adapter.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
import requests

from evidence import http
from evidence.http import RobotsDisallow
from evidence.providers import clinvar, crossref, preprints, pubmed
from evidence.record import Status

from test_conduct import FakeResponse, Script, make_client, no_sleep, fetch_source  # noqa: F401  (shared fakes and fixtures)
from test_v01_findings import OversizedAdapter


# ------------------------------------------------------------------ F1. esummary shape

SEARCH_ONE = {"esearchresult": {"count": "1", "idlist": ["123"]}}
CALLS = [
    pytest.param(lambda c: pubmed.search(c, "cystic fibrosis"), id="pubmed"),
    pytest.param(lambda c: clinvar.variants(c, "CFTR[gene]"), id="clinvar"),
]


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("summary, needle", [
    ({"error": "API rate limit exceeded"}, "API rate limit exceeded"),   # the recorded-style NCBI error body
    ({"header": {"type": "esummary"}}, "result"),                        # no result at all
    ({"result": {"123": {}}}, "uids"),                                    # result without uids
    ({"result": {"uids": "123"}}, "not a list"),                          # uids of the wrong type
    ({"result": ["123"]}, "not an object"),                               # result of the wrong type
])
def test_an_esummary_with_a_bad_shape_is_an_error_record_not_nothing(monkeypatch, no_sleep, call, summary, needle):
    c = make_client(monkeypatch, Script([FakeResponse(200, body=SEARCH_ONE), FakeResponse(200, body=summary)]))
    recs = call(c)
    assert [r.status for r in recs] == [Status.ERROR], [(r.status, r.limitations) for r in recs]
    assert needle in recs[0].limitations and "establishes nothing" in recs[0].limitations, recs[0].limitations


@pytest.mark.parametrize("call", CALLS)
def test_an_esummary_with_an_empty_uids_list_is_not_found(monkeypatch, no_sleep, call):
    """Negative control: a well-formed answer that lists nothing is 'not_found', not an error and not silence."""
    c = make_client(monkeypatch, Script([FakeResponse(200, body=SEARCH_ONE), FakeResponse(200, body={"result": {"uids": []}})]))
    recs = call(c)
    assert [r.status for r in recs] == [Status.NOT_FOUND], [(r.status, r.limitations) for r in recs]
    assert recs[0].limitations


@pytest.mark.parametrize("call", CALLS)
def test_a_well_formed_esummary_still_gives_found_records(monkeypatch, no_sleep, call):
    """Negative control: the shape check does not reject a normal answer."""
    summary = {"result": {"uids": ["123"], "123": {"uid": "123", "title": "A title"}}}
    c = make_client(monkeypatch, Script([FakeResponse(200, body=SEARCH_ONE), FakeResponse(200, body=summary)]))
    recs = call(c)
    assert [r.status for r in recs] == [Status.FOUND]
    assert recs[0].fields["title"] == "A title" and recs[0].fields["search_total"] == 1


# ------------------------------------------------------------------ F5. unusable Retry-After

@pytest.mark.parametrize("value", ["-1", "nan", "NaN", "inf", "-inf"])
def test_a_negative_or_non_finite_retry_after_is_a_refusal_not_a_crash(monkeypatch, value):
    slept = []
    monkeypatch.setattr(http.time, "sleep", lambda s: slept.append(s))
    s = Script([FakeResponse(429, headers={"Retry-After": value}), FakeResponse(200, body={"message": {}})])
    c = make_client(monkeypatch, s)
    f = c.get("crossref", "works/a")
    assert f.status is Status.RATE_LIMITED and len(s.calls) == 1, (f.status, s.calls)
    assert "not a usable number of seconds" in c.accounting.blocked_hosts["api.crossref.org"]
    assert c.accounting.attempts == 1
    assert slept == []


def test_a_usable_retry_after_is_still_honoured(monkeypatch):
    """Negative control: Retry-After 2 is waited for and the request retried once."""
    slept = []
    monkeypatch.setattr(http.time, "sleep", lambda s: slept.append(s))
    s = Script([FakeResponse(429, headers={"Retry-After": "2"}), FakeResponse(200, body={"message": {}})])
    c = make_client(monkeypatch, s)
    assert c.get("crossref", "works/a").status is Status.FOUND
    assert 2.0 in slept and len(s.calls) == 2


# ------------------------------------------------------------------ F6. robots.txt fetch

class RedirectingRobotsAdapter(requests.adapters.BaseAdapter):
    """robots.txt answers 301 to a permissive file on another host; a client that follows the redirect is told 'Allow: /'."""

    def __init__(self):
        super().__init__()
        self.seen: list[str] = []

    def send(self, request, **kwargs):
        self.seen.append(request.url)
        r = requests.Response()
        r.request, r.url = request, request.url
        if request.url == "https://docs.example.test/robots.txt":
            r.status_code, r.headers["Location"] = 301, "https://elsewhere.example.test/robots.txt"
            r._content = b""
        else:
            r.status_code, r._content = 200, b"User-agent: *\nAllow: /\n"
        return r

    def close(self):
        pass


def _session_client(monkeypatch, adapter):
    for k in ("EVIDENCE_DRY_RUN", "EVIDENCE_MAX_REQUESTS", "EVIDENCE_REQUEST_LOG", "EVIDENCE_CONTACT"):
        monkeypatch.delenv(k, raising=False)
    session = requests.Session()
    session.mount("https://", adapter)
    return http.Client(session=session)


def test_a_robots_txt_that_redirects_is_unreadable_and_refused(monkeypatch, no_sleep, fetch_source):
    adapter = RedirectingRobotsAdapter()
    c = _session_client(monkeypatch, adapter)
    with pytest.raises(RobotsDisallow, match="unreachable"):
        c.get("docs-test", "report.json")
    assert adapter.seen == ["https://docs.example.test/robots.txt"], adapter.seen   # the Location was never requested


def test_the_robots_fetch_does_not_follow_redirects_and_streams(monkeypatch, no_sleep, fetch_source):
    s = Script([FakeResponse(302, headers={"Location": "https://elsewhere.example.test/robots.txt"}, text="")])
    c = make_client(monkeypatch, s)
    with pytest.raises(RobotsDisallow, match="unreachable"):
        c.get("docs-test", "report.json")
    assert s.get_kwargs == {"allow_redirects": False, "stream": True}, s.get_kwargs


def test_an_oversized_robots_txt_is_refused_unread(monkeypatch, no_sleep, fetch_source):
    adapter = OversizedAdapter(http.MAX_BODY_BYTES * 4)
    c = _session_client(monkeypatch, adapter)
    with pytest.raises(RobotsDisallow, match="unreachable"):
        c.get("docs-test", "report.json")
    assert adapter.raw.read_total <= http.MAX_BODY_BYTES + 1_000_000, f"read {adapter.raw.read_total} bytes"


def test_a_declared_oversized_robots_txt_is_refused(monkeypatch, no_sleep, fetch_source):
    big = FakeResponse(200, headers={"Content-Length": str(http.MAX_BODY_BYTES + 1)}, text="User-agent: *\nAllow: /\n")
    c = make_client(monkeypatch, Script([big]))
    with pytest.raises(RobotsDisallow, match="unreachable"):
        c.get("docs-test", "report.json")


def test_the_robots_fetch_is_paced_like_other_requests(monkeypatch, fetch_source):
    """The robots.txt request and the document request after it are spaced by the pacing gap, not sent back to back."""
    waits = []
    monkeypatch.setattr(http.time, "sleep", lambda s: waits.append(s))
    s = Script([FakeResponse(404, text=""), FakeResponse(200, body={"a": 1})])
    c = make_client(monkeypatch, s)
    assert c.get("docs-test", "one.json").status is Status.FOUND
    assert [k for k, _ in s.calls] == ["get", "request"]
    assert any(w >= 1 / http.HARD_MAX_RPS - 0.05 for w in waits), f"the document request was not paced after robots.txt: {waits}"


def test_a_readable_robots_txt_still_allows(monkeypatch, no_sleep, fetch_source):
    """Negative control: a 200 robots.txt that allows the path still lets the document through."""
    s = Script([FakeResponse(200, text="User-agent: *\nDisallow: /private/\n"), FakeResponse(200, body={"a": 1})])
    c = make_client(monkeypatch, s)
    assert c.get("docs-test", "public.json").status is Status.FOUND


# ------------------------------------------------------------------ F10. ids in URL paths

def test_a_doi_with_query_or_fragment_characters_stays_in_the_path(monkeypatch, no_sleep):
    doi = "10.1000/a?b=c#d"
    s = Script([FakeResponse(200, body={"message": {}}), FakeResponse(200, body={"collection": []})])
    c = make_client(monkeypatch, s)
    crossref.work(c, doi)
    preprints.details(c, "medrxiv", doi)
    (_, cr_url), (_, pp_url) = s.calls
    for url, prefix in ((cr_url, "/works/"), (pp_url, "/details/medrxiv/")):
        parts = urlsplit(url)
        assert parts.query == "" and parts.fragment == "", url
        assert parts.path == prefix + "10.1000/a%3Fb%3Dc%23d", url


def test_an_ordinary_doi_keeps_its_slash(monkeypatch, no_sleep):
    """Negative control: the DOI's own '/' is not escaped."""
    s = Script([FakeResponse(200, body={"message": {}})])
    c = make_client(monkeypatch, s)
    crossref.work(c, "10.1056/NEJMoa1909989")
    assert s.calls[0][1] == "https://api.crossref.org/works/10.1056/NEJMoa1909989"

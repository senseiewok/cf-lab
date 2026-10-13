"""One test per network-conduct rule in evidence/http.py. No real network: responses are faked."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from evidence import catalog, http
from evidence.http import (BudgetExhausted, Client, HostInCooldown, PaperworkMissing, RobotsDisallow,
                           robots_allows)
from evidence.record import Status


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {"ok": True}
        self.headers = headers or {}
        self.text = text or json.dumps(self._body)
        self.url = "https://example.test/x"

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class Script:
    """Feed scripted responses to Session.request / Session.get and record every call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, params=None, json=None, timeout=None, allow_redirects=True, stream=False):
        self.calls.append(("request", url))
        self.kwargs = {"allow_redirects": allow_redirects}
        self.stream = stream
        item = self.responses.pop(0)
        if isinstance(item, Exception):   # a scripted transport failure (DNS, timeout, TLS)
            raise item
        return item

    def get(self, url, timeout=None, allow_redirects=True, stream=False):
        self.calls.append(("get", url))
        self.get_kwargs = {"allow_redirects": allow_redirects, "stream": stream}
        return self.responses.pop(0)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda s: None)


@pytest.fixture
def fetch_source(monkeypatch):
    """Inject a hypothetical `fetch` source so the robots gate has something to guard."""
    cat = dict(catalog.load())
    cat["docs-test"] = {"id": "docs-test", "access": "fetch", "base_url": "https://docs.example.test/", "kind": "report"}
    monkeypatch.setattr(catalog, "_cache", cat)
    yield
    catalog.load(refresh=True)


def make_client(monkeypatch, script: Script, env=None):
    for k in ("EVIDENCE_DRY_RUN", "EVIDENCE_MAX_REQUESTS", "EVIDENCE_REQUEST_LOG", "EVIDENCE_CONTACT"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    c = Client(contact=None)
    monkeypatch.setattr(c.session, "request", script.request)
    monkeypatch.setattr(c.session, "get", script.get)
    return c


# R1 is covered by test_gate.py.

def test_r2_api_without_paperwork_is_refused(monkeypatch, no_sleep):
    cat = dict(catalog.load())
    cat["bare-api"] = {"id": "bare-api", "access": "api", "base_url": "https://api.example.test/"}
    monkeypatch.setattr(catalog, "_cache", cat)
    s = Script([])
    c = make_client(monkeypatch, s)
    with pytest.raises(PaperworkMissing):
        c.get("bare-api", "things")
    assert s.calls == []
    catalog.load(refresh=True)


def test_r2_every_shipped_api_source_has_paperwork():
    for sid, e in catalog.load().items():
        if e.get("access") == "api":
            assert e.get("terms_url") and e.get("max_rps"), f"{sid} lacks terms_url or max_rps"
            assert float(e["max_rps"]) <= http.HARD_MAX_RPS


def test_r3_robots_disallow_refuses_document_fetch(monkeypatch, no_sleep, fetch_source):
    s = Script([FakeResponse(200, text="User-agent: *\nDisallow: /reports/\n")])
    c = make_client(monkeypatch, s)
    with pytest.raises(RobotsDisallow):
        c.get("docs-test", "reports/2022.pdf")
    assert [k for k, _ in s.calls] == ["get"]          # robots.txt only; the document was never requested


def test_r3_robots_403_refuses(monkeypatch, no_sleep, fetch_source):
    s = Script([FakeResponse(403, text="denied")])
    c = make_client(monkeypatch, s)
    with pytest.raises(RobotsDisallow):
        c.get("docs-test", "anything.pdf")


def test_r3_robots_404_allows_and_is_cached(monkeypatch, no_sleep, fetch_source):
    s = Script([FakeResponse(404, text=""), FakeResponse(200, body={"a": 1}), FakeResponse(200, body={"b": 2})])
    c = make_client(monkeypatch, s)
    assert c.get("docs-test", "one.json").status is Status.FOUND
    assert c.get("docs-test", "two.json").status is Status.FOUND
    assert [k for k, _ in s.calls] == ["get", "request", "request"]  # one robots fetch for two documents


def test_r3_api_sources_skip_robots(monkeypatch, no_sleep):
    s = Script([FakeResponse(200, body={"message": {}})])
    c = make_client(monkeypatch, s)
    c.get("crossref", "works/10.1000/x")
    assert all(k == "request" for k, _ in s.calls)    # no robots.txt call for an api source


def test_r3_robots_matching_handles_clinicaltrials_file():
    body = "User-agent: *\nDisallow: /api/\nAllow: /api/int/\nAllow: /api/seo/\nDisallow: /search?\nCrawl-delay: 1\n"
    assert robots_allows(body, "/api/v2/studies", "senseiewok-research-evidence") is False
    assert robots_allows(body, "/api/int/x", "senseiewok-research-evidence") is True
    assert robots_allows(body, "/study/NCT1", "senseiewok-research-evidence") is True
    assert robots_allows("User-agent: *\nDisallow: /\n", "/entrez/eutils/esearch.fcgi", "x") is False
    assert robots_allows("User-agent: *\nDisallow:\n", "/anything", "x") is True
    assert robots_allows("User-agent: senseiewok-research-evidence\nDisallow: /private/\nUser-agent: *\nDisallow: /\n", "/public", "senseiewok-research-evidence") is True


def test_r4_pacing_never_exceeds_hard_ceiling(monkeypatch):
    waits = []
    monkeypatch.setattr(http.time, "sleep", lambda s: waits.append(s))
    cat = dict(catalog.load())
    cat["fast-api"] = {"id": "fast-api", "access": "api", "base_url": "https://fast.example.test/", "terms_url": "https://x", "max_rps": 1000}
    monkeypatch.setattr(catalog, "_cache", cat)
    s = Script([FakeResponse(200), FakeResponse(200)])
    c = make_client(monkeypatch, s)
    c.get("fast-api", "a"); c.get("fast-api", "b")
    # NETWORK-RULES R4: never faster than 3 requests/second. The 3 is a literal on purpose: a test that
    # derives its expectation from http.HARD_MAX_RPS passes when that constant is raised or removed.
    ceiling = 3
    assert http.HARD_MAX_RPS <= ceiling
    assert waits and 1 / ceiling - 0.05 <= waits[0] <= 1 / ceiling + 0.01
    catalog.load(refresh=True)


def test_r5_budget_is_a_ceiling_the_environment_cannot_raise(monkeypatch, no_sleep):
    s = Script([FakeResponse(200)] * 10)
    c = make_client(monkeypatch, s, env={"EVIDENCE_MAX_REQUESTS": "999999"})
    assert c.max_requests == http.MAX_REQUESTS_PER_PROCESS
    c2 = make_client(monkeypatch, s, env={"EVIDENCE_MAX_REQUESTS": "2"})
    c2.get("crossref", "works/a"); c2.get("crossref", "works/b")
    with pytest.raises(BudgetExhausted):
        c2.get("crossref", "works/c")
    assert len(s.calls) == 2


def test_r6_403_trips_cooldown_for_the_host(monkeypatch, no_sleep):
    s = Script([FakeResponse(403, text="no")])
    c = make_client(monkeypatch, s)
    f = c.get("crossref", "works/a")
    assert f.status is Status.BLOCKED
    with pytest.raises(HostInCooldown):
        c.get("crossref", "works/b")
    assert len(s.calls) == 1
    assert any(h == "api.crossref.org" for h in c.accounting.blocked_hosts)


def test_r6_second_rate_limit_trips_cooldown(monkeypatch, no_sleep):
    s = Script([FakeResponse(429, headers={"Retry-After": "1"}), FakeResponse(200, body={"message": {}}),
                FakeResponse(429, headers={"Retry-After": "1"})])
    c = make_client(monkeypatch, s)
    assert c.get("crossref", "works/a").status is Status.FOUND          # one honoured Retry-After
    assert c.get("crossref", "works/b").status is Status.RATE_LIMITED   # second 429: no retry, trip
    with pytest.raises(HostInCooldown):
        c.get("crossref", "works/c")
    assert len(s.calls) == 3


def test_r6_429_without_retry_after_trips_immediately(monkeypatch, no_sleep):
    s = Script([FakeResponse(429)])
    c = make_client(monkeypatch, s)
    f = c.get("crossref", "works/a")
    assert f.status is Status.RATE_LIMITED and len(s.calls) == 1
    assert "no Retry-After" in c.accounting.blocked_hosts["api.crossref.org"]


def test_r6_three_consecutive_errors_trip(monkeypatch, no_sleep):
    s = Script([FakeResponse(500, text="x")] * 3)
    c = make_client(monkeypatch, s)
    for p in ("a", "b", "c"):
        assert c.get("crossref", f"works/{p}").status is Status.ERROR
    with pytest.raises(HostInCooldown):
        c.get("crossref", "works/d")


def test_r7_identity_is_fixed(monkeypatch, no_sleep):
    c = make_client(monkeypatch, Script([]))
    assert c.session.headers["User-Agent"].startswith("senseiewok-research-evidence/")
    assert "Mozilla" not in c.session.headers["User-Agent"]
    assert not hasattr(c, "set_user_agent")


def test_r8_request_log_records_every_attempt(monkeypatch, no_sleep, tmp_path):
    log = tmp_path / "req.jsonl"
    s = Script([FakeResponse(200, body={"message": {}}), FakeResponse(404)])
    c = make_client(monkeypatch, s, env={"EVIDENCE_REQUEST_LOG": str(log)})
    c.get("crossref", "works/a"); c.get("crossref", "works/b")
    lines = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2 and all(l["host"] == "api.crossref.org" for l in lines)
    assert c.accounting.attempts == 2 and "api.crossref.org=2" in c.accounting.summary()


def test_r9_dry_run_opens_no_socket(monkeypatch):
    s = Script([])
    c = make_client(monkeypatch, s, env={"EVIDENCE_DRY_RUN": "1"})
    f = c.get("crossref", "works", params={"filter": "updates:10.1/x"})
    assert f.dry_run and f.status is Status.OUT_OF_SCOPE and "filter=updates" in f.url
    assert s.calls == [] and c.accounting.attempts == 1

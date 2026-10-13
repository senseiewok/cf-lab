"""Defects found in review of v0.1, each reproduced by a test that failed before its fix.

1. R1 bypass: a redirect from a permitted host to another host was followed.
2. A transport failure (DNS, timeout, TLS) escaped as a traceback: no record, no accounting line.
No real network: a custom transport adapter plays the server.
"""

from __future__ import annotations

import requests

from evidence import cli, http
from evidence.record import Status

from test_conduct import FakeResponse, Script, make_client, no_sleep  # noqa: F401  (shared fakes and fixture)
import urllib.parse


class RedirectingAdapter(requests.adapters.BaseAdapter):
    """Answers a permitted host with a 302 to an unpermitted one, and records every URL it is asked for."""

    def __init__(self):
        super().__init__()
        self.seen: list[str] = []

    def send(self, request, **kwargs):
        self.seen.append(request.url)
        r = requests.Response()
        r.request = request
        r.url = request.url
        if urllib.parse.urlparse(request.url).hostname == "api.crossref.org":
            r.status_code = 302
            r.headers["Location"] = "https://unpermitted.example.test/stolen"
        else:
            r.status_code = 200
            r._content = b'{"message": {}}'
        return r

    def close(self):
        pass


def test_redirect_to_another_host_is_not_followed(monkeypatch):
    for k in ("EVIDENCE_DRY_RUN", "EVIDENCE_MAX_REQUESTS", "EVIDENCE_REQUEST_LOG", "EVIDENCE_CONTACT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    adapter = RedirectingAdapter()
    session = requests.Session()
    session.mount("https://", adapter)
    c = http.Client(session=session)
    f = c.get("crossref", "works/10.1000/x")
    assert all("unpermitted.example.test" not in u for u in adapter.seen), f"a redirect reached another host: {adapter.seen}"
    assert len(adapter.seen) == 1
    assert f.status is Status.ERROR and "not followed" in (f.text or "")


def test_requests_are_sent_with_redirects_disabled(monkeypatch, no_sleep):
    s = Script([FakeResponse(200, body={"message": {}})])
    c = make_client(monkeypatch, s)
    c.get("crossref", "works/a")
    assert s.kwargs == {"allow_redirects": False}


def test_transport_failure_becomes_an_error_record_not_a_traceback(monkeypatch, no_sleep):
    s = Script([requests.ConnectionError("dns failure")])
    c = make_client(monkeypatch, s)
    f = c.get("crossref", "works/a")
    assert f.status is Status.ERROR
    assert c.accounting.attempts == 1            # the attempt is still counted
    assert "ConnectionError" in (f.text or "")


def test_three_transport_failures_trip_the_cooldown(monkeypatch, no_sleep):
    s = Script([requests.Timeout("t")] * 3)
    c = make_client(monkeypatch, s)
    for i in range(3):
        c.get("crossref", f"works/{i}")
    assert any(h == "api.crossref.org" for h in c.accounting.blocked_hosts)


def test_cli_prints_the_accounting_line_and_exits_3_on_a_transport_failure(monkeypatch, capsys):
    for k in ("EVIDENCE_DRY_RUN", "EVIDENCE_MAX_REQUESTS", "EVIDENCE_REQUEST_LOG", "EVIDENCE_CONTACT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)

    monkeypatch.setattr(requests.Session, "request", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("no route")))
    code = cli.main(["retractions", "10.1000/x"])
    err = capsys.readouterr().err.strip().splitlines()
    assert code == 3
    assert err and err[-1].startswith("requests: "), err


def test_pacing_is_per_host_not_per_source_id(monkeypatch):
    """crossref and retraction-watch-crossref share api.crossref.org: the second call must wait."""
    waits = []
    monkeypatch.setattr(http.time, "sleep", lambda s: waits.append(s))
    s = Script([FakeResponse(200, body={"message": {}}), FakeResponse(200, body={"message": {}})])
    c = make_client(monkeypatch, s)
    c.get("crossref", "works/a")
    c.get("retraction-watch-crossref", "works/b")
    assert waits and waits[0] >= 1 / 3 - 0.05, f"second call to the same host did not wait: {waits}"


def test_a_retry_after_retry_is_paced_too(monkeypatch):
    """Retry-After: 0 must not turn into an immediate second request."""
    waits = []
    monkeypatch.setattr(http.time, "sleep", lambda s: waits.append(s))
    s = Script([FakeResponse(429, headers={"Retry-After": "0"}), FakeResponse(200, body={"message": {}})])
    c = make_client(monkeypatch, s)
    c.get("crossref", "works/a")
    assert len(s.calls) == 2
    assert any(w >= 1 / 3 - 0.05 for w in waits), f"the retry was not paced: {waits}"

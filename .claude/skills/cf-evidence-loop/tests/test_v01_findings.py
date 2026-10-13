"""Findings a frontier-model review deferred in v0.1 (lab task T-0052). Each test failed before its fix.

1. A response with an unexpected shape (a JSON list, a missing result key, a non-numeric total) became a crash or a
   silent "nothing found" instead of an error record that says what was wrong.
2. There was no cap on how much of a response the client would read.
3. Evidence.one_line() printed terminal escape sequences from a publisher's text.
4. --contact accepted anything, and the value goes into the User-Agent header.
5. A dry run did not list the requests it would make.
6. robots.txt group selection matched agents by prefix, ignored an empty user-agent value, and used only the first
   matching group instead of combining them (RFC 9309).
No real network: responses are faked, or served by a custom transport adapter.
"""

from __future__ import annotations

import io

import pytest
import requests

from evidence import cli, http
from evidence.providers import clinvar, preprints, pubmed
from evidence.record import Evidence, Status

from test_conduct import FakeResponse, Script, make_client, no_sleep, fetch_source  # noqa: F401  (shared fakes and fixtures)

OUR_AGENT = http.PROJECT_UA.split("/")[0]


def _client(monkeypatch, bodies):
    script = Script([b if isinstance(b, FakeResponse) else FakeResponse(200, body=b) for b in bodies])
    return make_client(monkeypatch, script), script


# ------------------------------------------------------------------ 1. response shape

def test_a_json_list_is_an_error_record_not_a_crash(monkeypatch, no_sleep):
    c, _ = _client(monkeypatch, [[1, 2, 3]])
    f = c.get("crossref", "works/10.1000/x")
    assert f.status is Status.ERROR
    assert "list" in (f.text or "") and "object" in (f.text or ""), f.text


def _preprint_page(total):
    return {"messages": [{"status": "ok", "total": total}],
            "collection": [{"doi": "10.1101/2026.09.02.1", "title": "CFTR modulators", "abstract": "", "date": "2026-09-02", "version": "1"}]}


def test_preprint_window_non_numeric_total_is_an_error_record(monkeypatch, no_sleep):
    c, _ = _client(monkeypatch, [_preprint_page("lots")])
    recs = preprints.window(c, "medrxiv", "2026-09-01", "2026-09-30")
    errs = [r for r in recs if r.status is Status.ERROR]
    assert errs, [r.status for r in recs]
    assert "total" in errs[0].limitations and "lots" in errs[0].limitations, errs[0].limitations
    assert any(r.status is Status.FOUND for r in recs), "the page already read must be kept"


def test_preprint_window_missing_total_is_not_a_complete_listing(monkeypatch, no_sleep):
    page = {"collection": [{"doi": "10.1101/2026.09.02.1", "title": "CFTR modulators", "abstract": "", "date": "2026-09-02", "version": "1"}]}
    c, _ = _client(monkeypatch, [page])
    recs = preprints.window(c, "medrxiv", "2026-09-01", "2026-09-30")
    assert any(r.status is Status.ERROR and "total" in r.limitations for r in recs), [(r.status, r.limitations) for r in recs]


@pytest.mark.parametrize("total", ["x" * 1_000_000, "9" * 5000, [7] * 100_000], ids=["huge-string", "absurd-digits", "huge-list"])
def test_a_huge_or_absurd_total_is_a_short_error_not_a_crash(monkeypatch, no_sleep, total):
    c, _ = _client(monkeypatch, [_preprint_page(total)])
    recs = preprints.window(c, "medrxiv", "2026-09-01", "2026-09-30")
    errs = [r for r in recs if r.status is Status.ERROR]
    assert errs, [r.status for r in recs]
    assert len(errs[0].limitations) < 400 and len(str(errs[0].fields)) < 400, (len(errs[0].limitations), len(str(errs[0].fields)))


@pytest.mark.parametrize("module, call", [
    (clinvar, lambda c: clinvar.variants(c, "CFTR[gene]")),
    (pubmed, lambda c: pubmed.search(c, "cystic fibrosis")),
])
@pytest.mark.parametrize("body", [
    {"esearchresult": {"count": "many", "idlist": ["1"]}},     # non-numeric total
    {"header": {"type": "esearch"}},                           # no esearchresult at all
    {"esearchresult": {"idlist": ["1"]}},                      # no count
])
def test_search_with_a_bad_shape_is_an_error_not_nothing_found(monkeypatch, no_sleep, module, call, body):
    c, _ = _client(monkeypatch, [body])
    recs = call(c)
    assert [r.status for r in recs] == [Status.ERROR], [(r.status, r.limitations) for r in recs]
    assert "count" in recs[0].limitations or "esearchresult" in recs[0].limitations, recs[0].limitations


# ------------------------------------------------------------------ 2. body-size cap

class _CountingRaw(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.read_total = 0

    def read(self, n=-1):
        chunk = super().read(n)
        self.read_total += len(chunk)
        return chunk


class OversizedAdapter(requests.adapters.BaseAdapter):
    """Serves a 200 whose body is far larger than the cap, with no Content-Length header."""

    def __init__(self, size):
        super().__init__()
        self.size = size
        self.raw = None

    def send(self, request, **kwargs):
        self.raw = _CountingRaw(b'{"x": "' + b"a" * self.size + b'"}')
        r = requests.Response()
        r.request, r.url, r.status_code = request, request.url, 200
        r.raw = self.raw
        return r

    def close(self):
        pass


def test_an_oversized_body_is_refused_and_not_read_in_full(monkeypatch, no_sleep):
    for k in ("EVIDENCE_DRY_RUN", "EVIDENCE_MAX_REQUESTS", "EVIDENCE_REQUEST_LOG", "EVIDENCE_CONTACT"):
        monkeypatch.delenv(k, raising=False)
    adapter = OversizedAdapter(http.MAX_BODY_BYTES * 4)
    session = requests.Session()
    session.mount("https://", adapter)
    f = http.Client(session=session).get("crossref", "works/10.1000/x")
    assert f.status is Status.ERROR and "larger than" in (f.text or ""), (f.status, f.text)
    assert adapter.raw.read_total <= http.MAX_BODY_BYTES + 1_000_000, f"read {adapter.raw.read_total} bytes"


def test_a_declared_content_length_over_the_cap_is_refused_unread(monkeypatch, no_sleep):
    big = FakeResponse(200, body={"ok": True}, headers={"Content-Length": str(http.MAX_BODY_BYTES + 1)})
    c, _ = _client(monkeypatch, [big])
    f = c.get("crossref", "works/10.1000/x")
    assert f.status is Status.ERROR and "larger than" in (f.text or ""), (f.status, f.text)


def test_a_normal_body_is_still_read(monkeypatch, no_sleep):
    c, _ = _client(monkeypatch, [{"message": {"ok": 1}}])
    f = c.get("crossref", "works/10.1000/x")
    assert f.status is Status.FOUND and f.data == {"message": {"ok": 1}}


# ------------------------------------------------------------------ 3. terminal escapes in one_line

def _ev(**kw):
    base = dict(status=Status.FOUND, question="q", source_id="s", url="https://example.test/x", provider="p", limitations="l")
    base.update(kw)
    return Evidence(**base)


def test_one_line_strips_ansi_escapes_and_control_characters():
    e = _ev(publisher_date="2026\x1b[2J", url="https://example.test/\x1b[31mred",
            fields={"title": "\x1b[31mred\x1b[0m \x1b]0;pwned\x07title\nsecond line\rback", "n": 1})
    line = e.one_line()
    assert all(ord(ch) >= 32 and not 0x7F <= ord(ch) <= 0x9F for ch in line), repr(line)
    assert "red" in line and "title" in line and "n=1" in line, line
    assert "pwned" not in line, line   # the title text of an OSC sequence is escape payload, not content


def test_one_line_leaves_ordinary_text_alone():
    e = _ev(fields={"title": "Elexacaftor-tezacaftor-ivacaftor: a 65 roses story (naïve)"})
    assert "Elexacaftor-tezacaftor-ivacaftor: a 65 roses story (naïve)" in e.one_line()


# ------------------------------------------------------------------ 4. --contact validation

@pytest.mark.parametrize("bad", ["x y; rm -rf", "not-an-email", "a@b", "a@b@c.org", "x@y.org\r\nX-Evil: 1", "x@y.org\n", " x@y.org", "@y.org", "x@.org", "x@y..org", "a" * 250 + "@y.org"])
def test_contact_that_is_not_an_email_is_rejected(bad, monkeypatch):
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    with pytest.raises(ValueError, match="contact"):
        http.Client(contact=bad)


@pytest.mark.parametrize("good", ["me@example.org", "first.last+evidence@sub.example.co.uk", "a_b-c@x-y.org"])
def test_a_plain_email_contact_is_accepted_and_sent(good, monkeypatch):
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    c = http.Client(contact=good)
    assert c.session.headers["User-Agent"].endswith(f"mailto:{good}")


def test_no_contact_still_works(monkeypatch):
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    assert "mailto" not in http.Client(contact=None).session.headers["User-Agent"]
    assert "mailto" not in http.Client(contact="").session.headers["User-Agent"]


def test_a_bad_contact_in_the_environment_is_rejected_too(monkeypatch):
    monkeypatch.setenv("EVIDENCE_CONTACT", "x y; rm -rf")
    with pytest.raises(ValueError, match="contact"):
        http.Client()


def test_the_command_line_refuses_a_bad_contact_without_a_traceback_or_a_request(monkeypatch, capsys):
    monkeypatch.setenv("EVIDENCE_DRY_RUN", "1")
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    rc = cli.main(["--contact", "x y; rm -rf", "doi", "10.1000/x"])
    out = capsys.readouterr()
    assert rc == 2, rc
    assert "contact" in out.err and "crossref" not in out.out, (out.out, out.err)


def test_options_given_before_the_subcommand_are_not_dropped(monkeypatch, capsys):
    """argparse let each subcommand's defaults overwrite --json, --ledger and --contact given before it."""
    monkeypatch.setenv("EVIDENCE_DRY_RUN", "1")
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    cli.main(["--json", "doi", "10.1000/x"])
    out = capsys.readouterr().out
    assert out.lstrip().startswith("{"), out
    cli.main(["doi", "10.1000/x", "--json"])      # and after it, as before
    assert capsys.readouterr().out.lstrip().startswith("{")


# ------------------------------------------------------------------ 5. dry run lists every planned request

def test_dry_run_prints_every_planned_url(monkeypatch, capsys):
    monkeypatch.setenv("EVIDENCE_DRY_RUN", "1")
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    rc = cli.main(["retractions", "10.1038/ng.2745", "10.1002/humu.23276"])
    err = capsys.readouterr().err
    planned = [ln for ln in err.splitlines() if ln.startswith("planned: ")]
    assert rc == 0
    assert len(planned) == 2 and all(ln.startswith("planned: GET https://api.crossref.org/works") for ln in planned), err
    assert "10.1038" in planned[0] and "humu.23276" in planned[1], planned


def test_dry_run_says_which_requests_it_cannot_show(monkeypatch, capsys):
    monkeypatch.setenv("EVIDENCE_DRY_RUN", "1")
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    cli.main(["variants", "CFTR[gene]"])
    err = capsys.readouterr().err
    assert sum(ln.startswith("planned: ") for ln in err.splitlines()) == 1
    assert "depend on" in err and "response" in err, err


def test_dry_run_lists_the_robots_request_for_a_fetch_source(monkeypatch, fetch_source):
    for k in ("EVIDENCE_MAX_REQUESTS", "EVIDENCE_REQUEST_LOG", "EVIDENCE_CONTACT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("EVIDENCE_DRY_RUN", "1")
    c = http.Client()
    c.get("docs-test", "report.json")
    urls = [u for _m, u in c.planned]
    assert urls == ["https://docs.example.test/robots.txt", "https://docs.example.test/report.json"], urls


# ------------------------------------------------------------------ 6. robots.txt group selection (RFC 9309)

ROBOTS_CASES = [
    # (name, body, path, expected_allowed)
    ("a group naming only a prefix of our agent does not apply to us",
     "User-agent: senseiewok\nDisallow: /\n\nUser-agent: *\nAllow: /\n", "/doc.json", True),
    ("an empty user-agent value matches nobody",
     "User-agent:\nDisallow: /\n\nUser-agent: *\nAllow: /\n", "/doc.json", True),
    ("an empty user-agent value does not widen our own group",
     "User-agent: senseiewok-research-evidence\nDisallow: /private/\n\nUser-agent:\nDisallow: /\n", "/public/a", True),
    ("two groups for the wildcard are combined",
     "User-agent: *\nDisallow: /a/\n\nUser-agent: Other\nDisallow: /z/\n\nUser-agent: *\nDisallow: /b/\n", "/b/x", False),
    ("two groups naming our agent are combined",
     "User-agent: senseiewok-research-evidence\nDisallow: /a/\n\nUser-agent: Other\nDisallow: /z/\n\nUser-agent: senseiewok-research-evidence\nDisallow: /b/\n", "/b/x", False),
    ("our own group wins over the wildcard",
     "User-agent: senseiewok-research-evidence\nAllow: /x\n\nUser-agent: *\nDisallow: /\n", "/y", True),
    ("the wildcard applies when no group names us",
     "User-agent: Googlebot\nAllow: /\n\nUser-agent: *\nDisallow: /nope\n", "/nope/a", False),
    ("the agent name is case-insensitive",
     "User-agent: SenseiEwok-Research-Evidence\nDisallow: /\n", "/a", False),
    ("a shared group applies to every agent it names",
     "User-agent: Other\nUser-agent: senseiewok-research-evidence\nDisallow: /x\n", "/x/y", False),
    ("the longest matching rule wins and Allow beats Disallow on a tie",
     "User-agent: *\nDisallow: /docs/\nAllow: /docs/open/\nDisallow: /docs/open/closed/\n", "/docs/open/a", True),
    ("an empty Disallow allows everything",
     "User-agent: *\nDisallow:\n", "/anything", True),
    ("no robots body means no restrictions",
     "", "/anything", True),
    ("a wildcard star in a path matches",
     "User-agent: *\nDisallow: /*.pdf$\n", "/a/report.pdf", False),
    ("a dollar anchor does not over-match",
     "User-agent: *\nDisallow: /*.pdf$\n", "/a/report.pdf.html", True),
]


@pytest.mark.parametrize("name, body, path, expected", ROBOTS_CASES, ids=[c[0] for c in ROBOTS_CASES])
def test_robots_group_selection(name, body, path, expected):
    assert http.robots_allows(body, path, OUR_AGENT) is expected, name

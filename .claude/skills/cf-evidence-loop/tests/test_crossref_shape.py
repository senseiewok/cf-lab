"""A Crossref answer without the shape the retraction check relies on is an error, never "no notice found". No network."""

import json
from pathlib import Path

from evidence.http import Fetch
from evidence.providers import crossref
from evidence.record import Status

FX = Path(__file__).parent / "fixtures"
DOI = "10.1038/ng.2745"
Q = "q"
U = "u"

# (label, body) pairs: each one is an answer the check cannot read a verdict from
BAD_BODIES = [
    ("no message key", {"status": "ok", "message-type": "work-list"}),
    ("empty object", {}),
    ("message is null", {"status": "ok", "message": None}),
    ("message is an empty object", {"status": "ok", "message": {}}),
    ("message has no items", {"message": {"total-results": 0}}),
    ("items is null", {"message": {"items": None}}),
    ("items is a string", {"message": {"items": "none"}}),
    ("items is an object", {"message": {"items": {}}}),
    ("message is a list", {"message": []}),
    ("message is a string", {"message": "ok"}),
    ("an item is not an object", {"message": {"items": [1]}}),
    ("body is a list", []),
    ("body is null", None),
    ("body is a string", "<html>gateway error</html>"),
    ("body is a number", 5),
]


def _assert_error_not_clean(recs, label, question=Q):
    assert len(recs) == 1, f"{label}: expected one record, got {len(recs)}"
    r = recs[0]
    assert r.status is Status.ERROR, f"{label}: status {r.status}, limitations {r.limitations!r}"
    assert r.limitations.strip(), f"{label}: empty limitation"
    assert r.limitations != crossref.CLEAN_LIMITATION, f"{label}: carries the 'no notice' limitation"
    assert "holds no update notice" not in r.limitations, f"{label}: says Crossref holds no notice"
    assert r.fields.get("clean") is not True, f"{label}: marked clean"
    assert "update_notices" not in r.fields, f"{label}: reports a notice count"
    assert r.fields.get("shape_error"), f"{label}: no shape_error naming what was wrong"
    assert r.fields.get("doi") == DOI, f"{label}: record does not name the DOI"
    assert r.source_id == crossref.SOURCE and r.provider == crossref.PROVIDER and r.url == U
    assert r.question == question if question else r.question.strip(), f"{label}: question {r.question!r}"


def test_an_unreadable_answer_is_an_error_not_a_clean_check():
    for label, body in BAD_BODIES:
        _assert_error_not_clean(crossref.parse_updates(body, DOI, Q, U), label)


def test_the_error_message_stays_short_for_a_huge_body():
    huge = {"message": "x" * 1_000_000}
    r = crossref.parse_updates(huge, DOI, Q, U)[0]
    assert r.status is Status.ERROR
    assert len(r.limitations) < 400 and len(str(r.fields)) < 400, (len(r.limitations), len(str(r.fields)))


def test_updates_reports_an_unreadable_answer_as_an_error():
    class FakeClient:
        def get(self, source, path, params=None):
            return Fetch(status=Status.FOUND, http_status=200, url=U, data={"status": "ok"})

    # updates() words its own question, so only require that it is not empty
    _assert_error_not_clean(crossref.updates(FakeClient(), DOI), "updates() with no message key", question=None)


def test_a_real_empty_answer_is_still_clean():
    recs = crossref.parse_updates({"message": {"items": []}}, DOI, Q, U)
    assert len(recs) == 1 and recs[0].status is Status.FOUND
    assert recs[0].fields == {"doi": DOI, "update_notices": 0, "clean": True}
    assert recs[0].limitations == crossref.CLEAN_LIMITATION


def test_the_saved_answers_are_unchanged():
    clean = crossref.parse_updates(json.loads((FX / "crossref_updates_clean.json").read_text(encoding="utf-8")), DOI, Q, U)
    assert len(clean) == 1 and clean[0].fields == {"doi": DOI, "update_notices": 0, "clean": True}
    doi = "10.1016/S0140-6736(97)11096-0"
    notices = crossref.parse_updates(json.loads((FX / "crossref_updates_retracted.json").read_text(encoding="utf-8")), doi, Q, U)
    assert len(notices) == 2 and all(r.status is Status.FOUND and r.fields["clean"] is False for r in notices)
    assert {r.fields["notice_type"][0] for r in notices} == {"correction", "retraction"}

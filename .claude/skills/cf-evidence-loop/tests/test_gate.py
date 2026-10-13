"""The gate refuses what it must, before any socket opens."""

import pytest

from evidence import catalog
from evidence.http import Client


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any attempt to actually send a request fails the test."""
    def boom(*a, **k):
        raise AssertionError("network call attempted; the gate should have refused first")
    monkeypatch.setattr("requests.Session.request", boom)


def test_forbidden_source_is_refused():
    with pytest.raises(catalog.AccessDenied):
        catalog.base_url("lovd-cftr")


def test_manual_source_is_refused():
    with pytest.raises(catalog.AccessDenied):
        catalog.base_url("cffpr-adr-2022")


def test_unknown_source_is_refused():
    with pytest.raises(catalog.UnknownSource):
        catalog.base_url("not-in-catalog")


def test_permitted_source_resolves():
    assert catalog.base_url("crossref") == "https://api.crossref.org/"


def test_host_allowlist_is_derived_from_catalog():
    assert catalog.host_allowed("https://api.crossref.org/works")
    assert not catalog.host_allowed("https://www.cff.org/media/31216/download")
    assert not catalog.host_allowed("https://databases.lovd.nl/shared/genes/CFTR")


def test_client_refuses_before_network():
    c = Client(contact=None)
    with pytest.raises(catalog.AccessDenied):
        c.get("lovd-cftr", "shared/genes/CFTR")
    with pytest.raises(catalog.AccessDenied):
        c.get("cffpr-technical-supplement", "media/24916/download")
    with pytest.raises(catalog.UnknownSource):
        c.get("made-up", "x")


def test_client_has_no_browser_identity():
    c = Client(contact=None)
    ua = c.session.headers["User-Agent"]
    assert ua.startswith("senseiewok-research-evidence/")
    assert "Mozilla" not in ua

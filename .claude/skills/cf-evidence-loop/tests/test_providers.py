"""Each provider's parse() on a saved response. No network."""

import json
from pathlib import Path

import pytest

from evidence.providers import clinvar, crossref, europepmc, openfda, preprints, pubmed, reporter, trials
from evidence.record import Evidence, Status

FX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def test_every_record_has_limitations():
    with pytest.raises(ValueError):
        Evidence(status=Status.FOUND, question="q", source_id="s", url="u", provider="p", limitations="")


def test_retracted_doi_yields_notices():
    recs = crossref.parse_updates(load("crossref_updates_retracted.json"), "10.1016/S0140-6736(97)11096-0", "q", "u")
    assert len(recs) == 2
    assert all(r.fields["clean"] is False for r in recs)
    assert {r.fields["notice_type"][0] for r in recs} == {"correction", "retraction"}
    assert {r.publisher_date for r in recs} == {"2004", "2010"}


def test_clean_doi_is_found_and_clean():
    recs = crossref.parse_updates(load("crossref_updates_clean.json"), "10.1038/ng.2745", "q", "u")
    assert len(recs) == 1 and recs[0].status is Status.FOUND
    assert recs[0].fields == {"doi": "10.1038/ng.2745", "update_notices": 0, "clean": True}
    assert "not conclusive" in recs[0].limitations


def test_work_metadata():
    r = crossref.parse_work(load("crossref_work.json"), "q", "u")
    assert r.fields["doi"] == "10.1038/ng.2745" and r.publisher_date == "2013"
    assert r.fields["authors"][0] == "Sosnay"


def test_approval_original_date():
    r = openfda.parse_approval(load("openfda_drugsfda.json"), "TRIKAFTA", "q", "u")
    assert r.status is Status.FOUND
    assert r.fields["application_number"] == "NDA212273"
    assert r.fields["original_approval"] == "2019-10-21" == r.publisher_date
    assert "US FDA only" in r.limitations


def test_approval_not_found():
    r = openfda.parse_approval({"results": []}, "NOSUCHDRUG", "q", "u")
    assert r.status is Status.NOT_FOUND


def test_label_excerpt_is_bounded():
    r = openfda.parse_label(load("openfda_label.json"), "ALYFTREK", ("indications_and_usage",), "q", "u")
    assert r.fields["set_id"] == "7e635909-c6fd-4f0d-ae77-cdff03653a20"
    assert r.publisher_date == "2026-08-26"
    assert r.excerpt and len(r.excerpt) <= openfda.EXCERPT_CHARS + 1
    assert "not any individual's eligibility" in r.limitations


def test_preprint_details_and_filter():
    recs = preprints.parse_details(load("preprints_details.json"), "medrxiv", "q", "u")
    assert len(recs) == 1 and recs[0].fields["doi"] == "10.1101/2025.02.14.25322057"
    assert "not peer reviewed" in recs[0].limitations
    assert preprints.parse_details(load("preprints_details.json"), "medrxiv", "q", "u", pattern=r"zebrafish") == []


def test_clinvar_classification():
    recs = clinvar.parse_summaries(load("clinvar_esummary.json"), "q", "u")
    by_acc = {r.fields["accession"]: r for r in recs}
    assert by_acc["VCV004072070"].fields["classification"] == "Pathogenic"
    assert "Phe508del" in by_acc["VCV004072070"].fields["title"]
    assert all("CFTR2" in r.limitations for r in recs)


def test_trial_record():
    recs = trials.parse_studies(load("trials_study.json"), "q", "u")
    assert len(recs) == 1
    f = recs[0].fields
    assert f["nct_id"] == "NCT05033080" and f["status"] == "COMPLETED" and f["phases"] == ["PHASE3"]
    assert f["start"] == "2021-09-14"
    assert "not evidence that an intervention works" in recs[0].limitations


def test_pubmed_summaries_and_ids():
    recs = pubmed.parse_summaries(load("pubmed_esummary.json"), "q", "u")
    by = {r.fields["pmid"]: r for r in recs}
    assert by["23974870"].fields["doi"] == "10.1038/ng.2745"
    assert "Systematic Review" in by["42781846"].fields["pub_types"]
    assert by["42781846"].fields["pmcid"] == "PMC13602365"


def test_review_term_scoping():
    assert pubmed.review_term("sickle cell disease").startswith("(sickle cell disease[tiab]) AND (systematic[sb]")
    assert pubmed.review_term("cystic fibrosis[MeSH]").startswith("cystic fibrosis[MeSH] AND")


def test_europepmc_lookup_fields():
    recs = europepmc.parse_search(load("europepmc_search.json"), "q", "u")
    assert len(recs) == 1
    f = recs[0].fields
    assert f["doi"] == "10.1001/jamanetworkopen.2020.1737" and f["year"] == "2020" and f["open_access"] is True
    assert isinstance(f["cited_by"], int) and f["cited_by"] > 0
    assert "differs from Crossref" in recs[0].limitations


def test_reporter_handles_null_dates():
    recs = reporter.parse_projects(load("reporter_projects.json"), "q", "u")
    assert len(recs) == 2
    assert all(r.publisher_date == "2025" for r in recs)
    assert all("NIH-funded projects only" in r.limitations for r in recs)

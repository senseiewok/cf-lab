"""Briefs: several sources, one cross-checked set of records. No real network: every response is scripted.

The drug recipe makes five requests in this order: Drugs@FDA, label, ClinicalTrials.gov search, PubMed esearch, PubMed esummary.
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

from evidence import briefs, cli
from evidence.record import Status

from test_conduct import FakeResponse, Script, make_client, no_sleep  # noqa: F401  (shared fakes and fixture)

FX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def ok(body):
    return FakeResponse(200, body=body)


def label_body(effective_time="20200115", **extra):
    lab = {"set_id": "00000000-0000-0000-0000-000000000000", "version": "3",
           "indications_and_usage": ["1 INDICATIONS AND USAGE Synthetic label text for a test."], **extra}
    if effective_time is not None:
        lab["effective_time"] = effective_time
    return {"results": [lab]}


def esearch(*ids):
    return {"esearchresult": {"count": str(len(ids)), "idlist": list(ids)}}


def trials_page():
    return load("trials_study.json")


def drug_script(label=None, approval=None):
    return Script([ok(approval or load("openfda_drugsfda.json")), ok(label or label_body()), ok(trials_page()),
                   ok(esearch("23974870", "42781846")), ok(load("pubmed_esummary.json"))])


def checks(b, verdict=None):
    return [c for c in b.checks if verdict is None or c.verdict == verdict]


# ------------------------------------------------------------------ recipes

def test_drug_brief_runs_four_sources_in_one_set(monkeypatch, no_sleep):
    s = drug_script()
    b = briefs.drug(make_client(monkeypatch, s), "TRIKAFTA")
    assert len(s.calls) == 5 and not s.responses
    assert [st.name for st in b.steps] == ["approval", "label", "trials", "pubmed"]
    assert [st.status for st in b.steps] == ["found"] * 4
    assert {r.source_id for r in b.records} == {"openfda-drugsfda", "openfda-label", "clinicaltrials-gov", "ncbi-eutils"}
    assert all(r.url and r.accessed and r.limitations for r in b.records)
    text = b.text()
    assert "approval original_approval: 2019-10-21" in text
    assert "approval application_number: NDA212273" in text
    assert "PASS       source trials (clinicaltrials-gov): found" in text
    assert b.text().rstrip().endswith(briefs.FOOTER)


def test_drug_trials_step_searches_by_term_without_a_condition(monkeypatch, no_sleep):
    seen = []
    s = drug_script()
    real = s.request

    def spy(method, url, params=None, **kw):
        seen.append((url, params))
        return real(method, url, params=params, **kw)

    c = make_client(monkeypatch, s)
    monkeypatch.setattr(c.session, "request", spy)
    briefs.drug(c, "TRIKAFTA")
    trials_params = [p for u, p in seen if urllib.parse.urlparse(u).hostname == "clinicaltrials.gov"][0]
    assert trials_params["query.term"] == "TRIKAFTA" and "query.cond" not in trials_params
    assert trials_params["pageSize"] == briefs.TRIALS_LIMIT
    pubmed_params = [p for u, p in seen if "esearch" in u][0]
    assert pubmed_params["term"] == "TRIKAFTA" and pubmed_params["retmax"] == briefs.PUBMED_LIMIT


def test_variant_brief_lists_every_match_and_chooses_none(monkeypatch, no_sleep):
    s = Script([ok(esearch("4072070", "4689723")), ok(load("clinvar_esummary.json")),
                ok(esearch("23974870")), ok(load("pubmed_esummary.json"))])
    b = briefs.variant(make_client(monkeypatch, s), "CFTR[gene] AND F508del")
    text = b.text()
    assert "variants VCV004072070 classification: Pathogenic" in text
    assert "variants VCV004689723 classification: Uncertain significance" in text
    assert "variants VCV004072070 review_status: criteria provided, single submitter" in text
    m = [c for c in b.checks if c.what == "ClinVar matches"]
    assert len(m) == 1 and m[0].verdict == briefs.CHECK
    assert "2 records matched" in m[0].detail and "none was chosen" in m[0].detail
    assert "Pathogenic" in m[0].detail and "Uncertain significance" in m[0].detail


def test_variant_brief_with_one_match_passes(monkeypatch, no_sleep):
    one = load("clinvar_esummary.json")
    one["result"]["uids"] = ["4072070"]
    s = Script([ok(esearch("4072070")), ok(one), ok(esearch("23974870")), ok(load("pubmed_esummary.json"))])
    b = briefs.variant(make_client(monkeypatch, s), "VCV004072070")
    assert [c.verdict for c in b.checks if c.what == "ClinVar matches"] == [briefs.PASS]


def test_trial_brief_reports_which_papers_name_the_trial(monkeypatch, no_sleep):
    summ = load("pubmed_esummary.json")
    summ["result"]["23974870"]["title"] = "A synthetic title naming NCT05033080 for a test"
    s = Script([ok(trials_page()["studies"][0]), ok(esearch("23974870", "42781846")), ok(summ)])
    b = briefs.trial(make_client(monkeypatch, s), "NCT05033080")
    assert [c.verdict for c in b.checks if c.what == "registry id"] == [briefs.PASS]
    by = {c.what: c for c in b.checks if c.what.startswith("PMID")}
    assert by["PMID 23974870 mentions NCT05033080"].verdict == briefs.PASS
    assert by["PMID 42781846 mentions NCT05033080"].verdict == briefs.NOTE
    assert "not stated" in by["PMID 42781846 mentions NCT05033080"].detail
    assert "trial status: COMPLETED" in b.text()


# ------------------------------------------------------------------ cross-checks

def _year_check(b):
    return [c for c in b.checks if c.what.startswith("first-approval year")][0]


def test_label_before_first_approval_is_a_check_not_an_error(monkeypatch, no_sleep):
    # Negative control: a rule that always said PASS fails here. The fixture's first approval is 2019-10-21.
    b = briefs.drug(make_client(monkeypatch, drug_script(label=label_body("20180301"))), "TRIKAFTA")
    c = _year_check(b)
    assert c.verdict == briefs.CHECK, c
    assert c.detail == ("label effective date 2018-03-01 is earlier than first approval 2019-10-21; "
                        "one of the two records is inconsistent")
    assert all(r.status is not Status.ERROR for r in b.records)
    assert "CHECK      first-approval year vs label effective-date year: label effective date 2018-03-01" in b.text()


def test_label_after_first_approval_passes(monkeypatch, no_sleep):
    # The real shape: first approval 2019, label revised 2026. A rule that always said CHECK fails here.
    b = briefs.drug(make_client(monkeypatch, drug_script(label=label_body("20260622"))), "TRIKAFTA")
    c = _year_check(b)
    assert c.verdict == briefs.PASS, c
    assert "2019-10-21" in c.detail and "2026-06-22" in c.detail
    assert "the label's effective date is its latest revision, so a later year is expected" in c.detail


def test_year_rule_boundaries():
    assert briefs.approval_year_check("2019-10-21", "2018-12-31").verdict == briefs.CHECK   # the year before
    assert briefs.approval_year_check("2019-10-21", "2019-01-01").verdict == briefs.PASS    # same year: compared by year
    assert briefs.approval_year_check("2019-10-21", "2020-01-01").verdict == briefs.PASS


def test_a_missing_date_is_not_stated_and_names_which(monkeypatch, no_sleep):
    appr = load("openfda_drugsfda.json")
    for s in appr["results"][0]["submissions"]:
        if s.get("submission_type") == "ORIG":
            s["submission_type"] = "SUPPL"        # no ORIG approval: original_approval is None in the record
    b = briefs.drug(make_client(monkeypatch, drug_script(approval=appr)), "TRIKAFTA")
    c = _year_check(b)
    assert c.verdict == briefs.NOTE, c
    assert c.detail.startswith("Drugs@FDA original_approval not stated; cannot compare"), c.detail
    assert "openFDA label effective_time not stated" not in c.detail
    assert "NOT STATED first-approval year vs label effective-date year: Drugs@FDA original_approval not stated" in b.text()


def test_a_missing_field_prints_not_stated(monkeypatch, no_sleep):
    appr = load("openfda_drugsfda.json")
    appr["results"][0].pop("sponsor_name")
    b = briefs.drug(make_client(monkeypatch, drug_script(label=label_body(None), approval=appr)), "TRIKAFTA")
    text = b.text()
    assert "approval sponsor: not stated" in text
    assert "label effective_time: not stated" in text
    c = [c for c in b.checks if c.what.startswith("first-approval year")][0]
    assert c.verdict == briefs.NOTE and "effective_time not stated" in c.detail
    assert "NOT STATED first-approval year" in text


# ------------------------------------------------------------------ failure does not stop a brief

def test_a_blocked_source_does_not_stop_the_brief_and_exit_is_3(monkeypatch, no_sleep, capsys):
    # Drugs@FDA refuses with 403: api.fda.gov goes into cooldown, so the label step is refused before any request.
    s = Script([FakeResponse(403, body={"error": "forbidden"}), ok(trials_page()),
                ok(esearch("23974870")), ok(load("pubmed_esummary.json"))])
    c = make_client(monkeypatch, s)
    monkeypatch.setattr(cli, "Client", lambda contact=None: c)
    rc = cli.main(["brief", "drug", "TRIKAFTA"])
    out = capsys.readouterr().out
    assert rc == 3
    assert len(s.calls) == 4 and not s.responses, s.calls          # trials and pubmed still ran
    assert "approval (openfda-drugsfda): blocked" in out
    assert "label (openfda-label): blocked" in out and "HostInCooldown" in out
    assert "trials (clinicaltrials-gov): found" in out and "pubmed (ncbi-eutils): found" in out
    assert "CHECK      source approval (openfda-drugsfda): blocked" in out
    assert out.rstrip().endswith(briefs.FOOTER)


def test_a_provider_exception_becomes_an_error_record(monkeypatch, no_sleep):
    def broken(*a, **k):
        raise KeyError("surprise")
    monkeypatch.setattr(briefs.clinvar, "variants", broken)
    s = Script([ok(esearch("23974870")), ok(load("pubmed_esummary.json"))])
    b = briefs.variant(make_client(monkeypatch, s), "CFTR[gene]")
    assert b.steps[0].status == "error" and b.steps[1].status == "found"
    assert [c.verdict for c in b.checks if c.what == "ClinVar matches"] == [briefs.NOTE]


# ------------------------------------------------------------------ output contract

def test_footer_is_always_present(monkeypatch, no_sleep):
    empty = {"esearchresult": {"count": "0", "idlist": []}}
    cases = [
        lambda c: briefs.drug(c, "X"),
        lambda c: briefs.variant(c, "X"),
        lambda c: briefs.trial(c, "NCT00000000"),
    ]
    bodies = [
        [ok({"results": []}), ok({"results": []}), ok({"studies": [], "totalCount": 0}), ok(empty)],
        [ok(empty), ok(empty)],
        [FakeResponse(404), ok(empty)],
    ]
    for run, body in zip(cases, bodies):
        b = run(make_client(monkeypatch, Script(body)))
        assert b.text().rstrip().endswith(briefs.FOOTER)
        assert b.summary()["brief"]["footer"] == briefs.FOOTER


def test_json_output_parses_and_ledger_gets_records_only(monkeypatch, no_sleep, capsys, tmp_path):
    c = make_client(monkeypatch, drug_script())
    monkeypatch.setattr(cli, "Client", lambda contact=None: c)
    ledger = tmp_path / "ledger.jsonl"
    rc = cli.main(["brief", "drug", "TRIKAFTA", "--json", "--ledger", str(ledger)])
    assert rc == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    objs = [json.loads(ln) for ln in lines]
    recs, summary = objs[:-1], objs[-1]
    assert all({"status", "source_id", "url", "accessed", "limitations"} <= set(o) for o in recs)
    assert summary["brief"]["recipe"] == "drug" and summary["brief"]["footer"] == briefs.FOOTER
    assert {x["verdict"] for x in summary["brief"]["cross_checks"]} <= {briefs.PASS, briefs.CHECK, briefs.NOTE}
    ledger_lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(ledger_lines) == len(recs) and all("brief" not in json.loads(ln) for ln in ledger_lines)


def test_dry_run_brief_plans_only_catalog_hosts(monkeypatch, capsys):
    monkeypatch.setenv("EVIDENCE_DRY_RUN", "1")
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    rc = cli.main(["brief", "drug", "TRIKAFTA"])
    err = capsys.readouterr().err
    planned = [ln for ln in err.splitlines() if ln.startswith("planned: ")]
    assert rc == 0
    assert len(planned) == 4, planned
    hosts = {ln.split("/")[2] for ln in planned}
    assert hosts == {"api.fda.gov", "clinicaltrials.gov", "eutils.ncbi.nlm.nih.gov"}, hosts


def test_every_printed_field_value_comes_from_a_record(monkeypatch, no_sleep):
    b = briefs.drug(make_client(monkeypatch, drug_script()), "TRIKAFTA")
    values = {json.dumps(v, sort_keys=True) for r in b.records for v in [*r.fields.values(), r.publisher_date]}
    for step, key, value in b.facts:
        if value == briefs.NOT_STATED or key.endswith("(counted)"):
            continue
        assert json.dumps(value, sort_keys=True) in values, (step, key, value)

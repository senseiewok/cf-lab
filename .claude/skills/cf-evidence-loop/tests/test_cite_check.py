"""cite-check: extraction, resolution through the existing providers, the title cross-check and the output contract.

No real network: every response is scripted. Each DOI and NCT id costs one request; each PMID costs two (esearch on the
[pmid] field, then esummary).
"""

from __future__ import annotations

import json
from pathlib import Path

from evidence import cite_check as cc
from evidence import cli
from evidence.record import Status

from test_conduct import FakeResponse, Script, make_client, no_sleep  # noqa: F401  (shared fakes and fixture)

FX = Path(__file__).parent / "fixtures"
PAPER = "Defining the disease liability of variants in the cystic fibrosis transmembrane conductance regulator gene"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def ok(body):
    return FakeResponse(200, body=body)


def ids(text):
    return [(f.kind, f.ident) for f in cc.extract(text)]


def run_cli(monkeypatch, capsys, tmp_path, text, script, *extra):
    note = tmp_path / "note.md"
    note.write_text(text, encoding="utf-8")
    c = make_client(monkeypatch, script)
    monkeypatch.setattr(cli, "Client", lambda contact=None: c)
    rc = cli.main(["cite-check", str(note), *extra])
    out, err = capsys.readouterr()
    return rc, out, err


def pubmed_one(pmid="23974870"):
    summ = load("pubmed_esummary.json")
    summ["result"]["uids"] = [pmid]
    return [ok({"esearchresult": {"count": "1", "idlist": [pmid]}}), ok(summ)]


# ------------------------------------------------------------------ extraction

def test_doi_trailing_punctuation_is_stripped():
    text = "Cited as 10.1038/ng.2745. Then 10.1002/humu.23276, and 10.1000/xyz123; also (10.1000/abc99) and 10.1000/q1:"
    assert ids(text) == [("DOI", "10.1038/ng.2745"), ("DOI", "10.1002/humu.23276"), ("DOI", "10.1000/xyz123"),
                         ("DOI", "10.1000/abc99"), ("DOI", "10.1000/q1")]


def test_doi_in_markdown_links():
    text = "See [the paper](https://doi.org/10.1038/ng.2745). And [10.1002/humu.23276](https://doi.org/10.1002/humu.23276)"
    assert ids(text) == [("DOI", "10.1038/ng.2745"), ("DOI", "10.1002/humu.23276")]
    assert ids("<https://doi.org/10.1000/abc>") == [("DOI", "10.1000/abc")]


def test_doi_keeps_a_closing_parenthesis_only_when_balanced():
    assert ids("doi:10.1016/S0140-6736(97)11096-0") == [("DOI", "10.1016/S0140-6736(97)11096-0")]
    assert ids("(see 10.1016/S0140-6736(97)11096-0).") == [("DOI", "10.1016/S0140-6736(97)11096-0")]
    assert ids("[x](https://doi.org/10.1016/S0140-6736(97)11096-0)") == [("DOI", "10.1016/S0140-6736(97)11096-0")]


def test_pmid_forms_and_nct():
    text = ("PMID 23974870\nPMID: 42781846\nhttps://pubmed.ncbi.nlm.nih.gov/11111111/\nhttps://www.ncbi.nlm.nih.gov/pubmed/22222222\n"
            "trial NCT05033080, not NCT123456789 nor XNCT05033081")
    assert ids(text) == [("PMID", "23974870"), ("PMID", "42781846"), ("PMID", "11111111"), ("PMID", "22222222"),
                         ("NCT", "NCT05033080")]


def test_duplicates_keep_the_first_line_and_its_text():
    found = cc.extract("intro\n  First 10.1038/ng.2745 and nct05033080  \nAgain 10.1038/NG.2745 and NCT05033080; PMID 1 and pubmed/1")
    assert [(f.kind, f.ident, f.line_no) for f in found] == [("DOI", "10.1038/ng.2745", 2), ("NCT", "NCT05033080", 2),
                                                           ("PMID", "1", 3)]
    assert found[0].line == "First 10.1038/ng.2745 and nct05033080"


def test_no_identifiers_is_not_a_pass(monkeypatch, capsys, tmp_path):
    # Negative control: a file with nothing to check must fail closed, and nothing may be sent.
    s = Script([])
    rc, out, err = run_cli(monkeypatch, capsys, tmp_path, "A note that cites nothing, 10.12/too-short-prefix.", s)
    assert rc == 1 and not s.calls
    assert "no identifiers found" in out and out.rstrip().endswith(cc.FOOTER)
    assert err.strip().splitlines()[-1].startswith("requests: 0")


# ------------------------------------------------------------------ resolution

def test_found_records_print_title_and_dates(monkeypatch, capsys, tmp_path, no_sleep):
    s = Script([ok(load("crossref_work.json")), *pubmed_one(), ok(load("trials_study.json")["studies"][0])])
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "10.1038/ng.2745\nPMID 23974870\nNCT05033080\n", s)
    assert rc == 0 and len(s.calls) == 4 and not s.responses
    assert f"PASS       DOI 10.1038/ng.2745 (line 1) | crossref [found] | title: {PAPER} | year: 2013" in out
    assert "PASS       PMID 23974870 (line 2) | ncbi-eutils [found] | title: Defining" in out and "publication date: 2013 Oct" in out
    assert "PASS       NCT NCT05033080 (line 3) | clinicaltrials-gov [found] | title: A Phase 3 Study of VX-121" in out
    assert "3 identifiers, 3 found, 0 not found, 0 unresolved, 0 title checks" in out


def test_a_missing_field_prints_not_stated(monkeypatch, capsys, tmp_path, no_sleep):
    work = load("crossref_work.json")
    work["message"].pop("issued")
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "10.1038/ng.2745", Script([ok(work)]))
    assert rc == 0 and "| year: not stated" in out


def test_not_found_exits_1_and_says_delete_or_fix(monkeypatch, capsys, tmp_path, no_sleep):
    s = Script([ok(load("crossref_work.json")), FakeResponse(404)])
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "10.1038/ng.2745 and 10.1234/not-a-real-doi-xyz", s)
    assert rc == 1
    assert "NOT FOUND  DOI 10.1234/not-a-real-doi-xyz (line 1) | crossref [not_found]" in out
    assert "delete or fix it from a source; never guess" in out
    assert "2 identifiers, 1 found, 1 not found, 0 unresolved, 0 title checks" in out


def test_a_pmid_search_with_no_match_is_not_found(monkeypatch, capsys, tmp_path, no_sleep):
    s = Script([ok({"esearchresult": {"count": "0", "idlist": []}})])
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "PMID: 99999999", s)
    assert rc == 1 and "NOT FOUND  PMID 99999999" in out


def test_a_pmid_answered_with_another_record_is_unresolved_not_found(monkeypatch, capsys, tmp_path, no_sleep):
    s = Script(pubmed_one("23974870"))
    s.responses[0] = ok({"esearchresult": {"count": "1", "idlist": ["23974870"]}})
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "PMID 12345", s)
    assert rc == 3 and "UNRESOLVED PMID 12345" in out and "PASS" not in out.split("\n\n")[1]


def test_blocked_exits_3_and_the_other_ids_still_resolve(monkeypatch, capsys, tmp_path, no_sleep):
    # Crossref refuses with 403: the host goes into cooldown, so the second DOI is refused before any request,
    # and the trial on another host is still looked up.
    s = Script([FakeResponse(403, body={"error": "forbidden"}), ok(load("trials_study.json")["studies"][0])])
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "10.1038/ng.2745\n10.1002/humu.23276\nNCT05033080", s)
    assert rc == 3 and len(s.calls) == 2 and not s.responses
    assert "UNRESOLVED DOI 10.1038/ng.2745 (line 1) | crossref [blocked]" in out
    assert "UNRESOLVED DOI 10.1002/humu.23276 (line 2) | crossref [blocked]" in out and "HostInCooldown" in out
    assert "unresolved is not the same as nonexistent" in out
    assert "PASS       NCT NCT05033080 (line 3)" in out
    assert "3 identifiers, 1 found, 0 not found, 2 unresolved, 0 title checks" in out
    assert out.rstrip().endswith(cc.FOOTER)


def test_blocked_outranks_not_found_in_the_exit_code(monkeypatch, capsys, tmp_path, no_sleep):
    s = Script([FakeResponse(404), FakeResponse(500), FakeResponse(500), FakeResponse(500)])
    rc, _, _ = run_cli(monkeypatch, capsys, tmp_path, "10.1000/a1 NCT05033080", s)
    assert rc == 3


def test_more_ids_than_the_cap_is_refused_before_any_request(monkeypatch, capsys, tmp_path):
    s = Script([])
    text = "\n".join(f"NCT{n:08d}" for n in range(1, 5)) + "\n10.1000/a PMID 7"
    rc, out, err = run_cli(monkeypatch, capsys, tmp_path, text, s, "--max-ids", "3")
    assert rc == 2 and not s.calls and out == ""
    assert "6 distinct identifiers found (1 DOI, 1 PMID, 4 NCT), more than --max-ids 3" in err
    assert "never truncated" in err


def test_max_ids_has_a_ceiling(monkeypatch, capsys, tmp_path):
    rc, _, err = run_cli(monkeypatch, capsys, tmp_path, "NCT05033080", Script([]), "--max-ids", str(cc.HARD_MAX_IDS + 1))
    assert rc == 2 and "--max-ids must be between" in err


# ------------------------------------------------------------------ title cross-check

def _title_item(monkeypatch, line):
    c = make_client(monkeypatch, Script([ok(load("crossref_work.json"))]))
    return cc.resolve(c, cc.extract(line))[0]


def test_title_pass_on_a_matching_quoted_phrase(monkeypatch, no_sleep):
    i = _title_item(monkeypatch, '"Defining the disease liability of variants in the CFTR gene" (10.1038/ng.2745)')
    assert i.title_verdict == cc.TITLE_PASS, i.title_detail


def test_title_pass_on_italic_phrase(monkeypatch, no_sleep):
    i = _title_item(monkeypatch, "*Disease liability of cystic fibrosis transmembrane conductance regulator variants*, 10.1038/ng.2745")
    assert i.title_verdict == cc.TITLE_PASS, i.title_detail


def test_a_wrong_title_is_a_title_check_not_an_error(monkeypatch, capsys, tmp_path, no_sleep):
    # Negative control: a rule that always said TITLE PASS fails here.
    line = '_Ivacaftor improves lung function in young children_ 10.1038/ng.2745'
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, line, Script([ok(load("crossref_work.json"))]))
    assert rc == 0
    assert "TITLE CHECK: the line's wording shares few words with the record's title" in out
    assert f"record title: {PAPER})" in out
    assert "1 identifiers, 1 found, 0 not found, 0 unresolved, 1 title checks" in out


def test_no_phrase_on_the_line_is_title_not_stated(monkeypatch, no_sleep):
    i = _title_item(monkeypatch, 'Shown in 10.1038/ng.2745 "too short" and *also short*')
    assert i.title_verdict == cc.TITLE_NOT_STATED and i.title_detail == "no title given on the line"


def test_overlap_rule():
    assert cc.overlap("The Cat and the Hat", "cat hat") == 1.0
    assert cc.overlap("alpha beta gamma delta", "alpha beta x y z") == 0.5
    assert cc.overlap("of the and", "anything") == 0.0
    assert cc.phrases('"one two three" and "one two three four"') == ["one two three four"]
    assert cc.phrases("snake_case_name and https://x.test/_a_b_c_d_") == []


# ------------------------------------------------------------------ output contract

def test_footer_is_always_present(monkeypatch, capsys, tmp_path, no_sleep):
    for text, script in (("10.1038/ng.2745", [ok(load("crossref_work.json"))]), ("10.1000/zz", [FakeResponse(404)]),
                         ("10.1000/zz", [FakeResponse(403)]), ("no ids here", [])):
        _, out, _ = run_cli(monkeypatch, capsys, tmp_path, text, Script(script))
        assert out.rstrip().endswith(cc.FOOTER), out


def test_json_output_and_ledger(monkeypatch, capsys, tmp_path, no_sleep):
    ledger = tmp_path / "ledger.jsonl"
    s = Script([ok(load("crossref_work.json")), FakeResponse(404)])
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "10.1038/ng.2745\n10.1234/not-a-real-doi-xyz", s,
                         "--json", "--ledger", str(ledger))
    assert rc == 1
    objs = [json.loads(ln) for ln in out.splitlines() if ln.strip()]
    recs, summary = objs[:-1], objs[-1]["cite_check"]
    assert [r["status"] for r in recs] == ["found", "not_found"]
    assert all({"status", "source_id", "url", "accessed", "limitations"} <= set(r) for r in recs)
    assert [i["verdict"] for i in summary["identifiers"]] == ["PASS", "NOT FOUND"]
    assert summary["counts"] == {"identifiers": 2, "found": 1, "not_found": 1, "unresolved": 0, "title_checks": 0}
    assert summary["footer"] == cc.FOOTER
    ledger_lines = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines()]
    assert [r["status"] for r in ledger_lines] == ["found", "not_found"] and all("cite_check" not in r for r in ledger_lines)


def test_json_with_no_identifiers_still_fails_closed(monkeypatch, capsys, tmp_path):
    rc, out, _ = run_cli(monkeypatch, capsys, tmp_path, "nothing", Script([]), "--json")
    assert rc == 1 and json.loads(out)["cite_check"]["result"] == "no identifiers found"


def test_dry_run_plans_only_catalog_hosts(monkeypatch, capsys, tmp_path):
    note = tmp_path / "note.md"
    note.write_text("10.1038/ng.2745 PMID 23974870 NCT02781610", encoding="utf-8")
    monkeypatch.setenv("EVIDENCE_DRY_RUN", "1")
    monkeypatch.delenv("EVIDENCE_CONTACT", raising=False)
    rc = cli.main(["cite-check", str(note)])
    err = capsys.readouterr().err
    hosts = {ln.split("/")[2] for ln in err.splitlines() if ln.startswith("planned: ")}
    assert rc == 0 and hosts == {"api.crossref.org", "eutils.ncbi.nlm.nih.gov", "clinicaltrials.gov"}


def test_publisher_text_is_cleaned_for_the_terminal(monkeypatch, no_sleep):
    work = load("crossref_work.json")
    work["message"]["title"] = ["Evil \x1b[31mred\x1b[0m title\nnext"]
    c = make_client(monkeypatch, Script([ok(work)]))
    text = cc.Report("n.md", cc.resolve(c, cc.extract("10.1038/ng.2745"))).text()
    assert "\x1b" not in text and "Evil red title next" in text
    assert cc.Report("n.md", []).text().rstrip().endswith(cc.FOOTER)
    assert Status.FOUND.value == "found"

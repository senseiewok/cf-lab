"""Command line for the evidence layer.

    python -m evidence.cli retractions 10.1038/ng.2745 10.1002/humu.23276
    python -m evidence.cli doi 10.1038/ng.2745
    python -m evidence.cli approval TRIKAFTA
    python -m evidence.cli label TRIKAFTA --sections indications_and_usage
    python -m evidence.cli preprint medrxiv 10.1101/2025.02.14.25322057
    python -m evidence.cli preprints medrxiv 2026-09-01 2026-09-30
    python -m evidence.cli variants "CFTR[gene] AND F508del"
    python -m evidence.cli grants "cystic fibrosis" --fy 2025
    python -m evidence.cli pubmed "cystic fibrosis[tiab] AND modulator[tiab]" --limit 10
    python -m evidence.cli reviews "sickle cell disease"
    python -m evidence.cli trials "cystic fibrosis" --status RECRUITING
    python -m evidence.cli trial NCT05033080
    python -m evidence.cli epmc 'TITLE:"cystic fibrosis" AND OPEN_ACCESS:y'
    python -m evidence.cli cited 10.1038/ng.2745
    python -m evidence.cli brief drug TRIKAFTA
    python -m evidence.cli brief variant "CFTR[gene] AND F508del"
    python -m evidence.cli brief trial NCT05033080
    python -m evidence.cli cite-check notes/draft.md --ledger evidence/ledger.jsonl

Every command accepts --json (one JSON object per line) and --ledger PATH (append records). With --json, a brief prints its
records and then one more object, {"brief": ...}, holding its sources, copied fields, cross-checks and footer; the ledger gets the records only.
cite-check FILE looks up every DOI, PMID and NCT id in a text file (at most --max-ids, default 30; more is refused, never
truncated). With --json it prints the records and then one object, {"cite_check": ...}. Its exit code is 3 when any lookup was
blocked, rate limited or failed, 1 when any id is NOT FOUND or the file holds no identifier at all, else 0.
--contact must be a plain email address.
With EVIDENCE_DRY_RUN=1 nothing is sent; each planned request is printed to stderr as "planned: METHOD url".
Exit code 0 when every record is found/not_found, 3 when any record is blocked, rate_limited or error, or when a
conduct rule refused the request before it was sent. The last stderr line is always the request accounting summary.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import briefs, catalog, cite_check
from .http import BudgetExhausted, Client, HostInCooldown, PaperworkMissing, RobotsDisallow
from .providers import clinvar, crossref, europepmc, openfda, preprints, pubmed, reporter, trials
from .record import Evidence, Status, append_ledger, clean_for_terminal

BAD = {Status.BLOCKED, Status.RATE_LIMITED, Status.ERROR}


def main(argv: list[str] | None = None) -> int:
    def common(inherit: bool) -> argparse.ArgumentParser:
        # The subcommands accept the same options as the main parser. Their defaults must not overwrite a value given before
        # the subcommand, so for them the default is "leave the attribute alone" (SUPPRESS).
        extra = {"default": argparse.SUPPRESS} if inherit else {}
        c = argparse.ArgumentParser(add_help=False)
        c.add_argument("--json", action="store_true", help="one JSON object per record", **extra)
        c.add_argument("--ledger", metavar="PATH", help="append records to this JSONL file", **extra)
        c.add_argument("--contact", help="contact for polite-pool headers (a plain email address); defaults to EVIDENCE_CONTACT env var", **extra)
        return c

    ap = argparse.ArgumentParser(prog="evidence", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[common(False)])
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=lambda **kw: argparse.ArgumentParser(parents=[common(True)], **kw))

    sub.add_parser("sources", help="list catalog sources this tool may reach")
    sub.add_parser("doi").add_argument("doi")
    sub.add_parser("retractions").add_argument("dois", nargs="+")
    sub.add_parser("approval").add_argument("brand")
    p = sub.add_parser("label"); p.add_argument("brand"); p.add_argument("--sections", nargs="+", default=list(openfda.DEFAULT_SECTIONS))
    p = sub.add_parser("preprint"); p.add_argument("server", choices=preprints.SERVERS); p.add_argument("doi")
    p = sub.add_parser("preprints"); p.add_argument("server", choices=preprints.SERVERS); p.add_argument("start"); p.add_argument("end")
    p.add_argument("--pattern", default=preprints.CF_PATTERN)
    p = sub.add_parser("variants"); p.add_argument("term"); p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("grants"); p.add_argument("text"); p.add_argument("--fy", type=int, nargs="*"); p.add_argument("--limit", type=int, default=25)
    p = sub.add_parser("pubmed", help="PubMed search; use field tags like [tiab] or [MeSH] for precision"); p.add_argument("term"); p.add_argument("--limit", type=int, default=20)
    p.add_argument("--sort", default="relevance", choices=["relevance", "pub_date"])
    p = sub.add_parser("reviews", help="systematic reviews and Cochrane reviews matching a term"); p.add_argument("term"); p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("trial"); p.add_argument("nct_id")
    p = sub.add_parser("trials"); p.add_argument("condition"); p.add_argument("--term"); p.add_argument("--status", help="e.g. RECRUITING, COMPLETED")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("epmc", help="Europe PMC search (its own query syntax, e.g. TITLE:\"cystic fibrosis\" AND OPEN_ACCESS:y)"); p.add_argument("query"); p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("cited", help="Europe PMC record for a DOI: citation count and open-access status"); p.add_argument("doi")
    p = sub.add_parser("brief", help="several sources for one question, with cross-checks: drug BRAND | variant QUERY | trial NCTID")
    p.add_argument("recipe", choices=briefs.RECIPES); p.add_argument("subject")
    p = sub.add_parser("cite-check", help="look up every DOI, PMID and NCT id in a text file (the lab's rule 5)"); p.add_argument("file")
    p.add_argument("--max-ids", type=int, default=cite_check.DEFAULT_MAX_IDS,
                   help=f"refuse a file with more distinct identifiers than this (default {cite_check.DEFAULT_MAX_IDS}, at most {cite_check.HARD_MAX_IDS})")

    a = ap.parse_args(argv)
    if a.cmd == "sources":
        for sid, e in sorted(catalog.load().items()):
            if e.get("access") in catalog.AUTOMATABLE and e.get("base_url"):
                print(f"{sid:24} {e['base_url']}")
        return 0

    try:
        client = Client(contact=a.contact)
    except ValueError as exc:                     # a bad --contact or EVIDENCE_CONTACT: a usage error, before any request
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    recs: list[Evidence]
    brief = None
    report = None
    if a.cmd == "cite-check":
        early = _cite_check_preflight(a, client)
        if isinstance(early, int):
            return early
    try:
        if a.cmd == "cite-check":                 # each lookup catches its own refusal, so a cite-check always returns
            report = cite_check.Report(a.file, cite_check.resolve(client, early))
            recs = report.records
        elif a.cmd == "brief":                      # each step catches its own refusal, so a brief always returns
            brief = briefs.run(client, a.recipe, a.subject)
            recs = brief.records
        else:
            recs = _dispatch(a, ap, client)
    except (BudgetExhausted, HostInCooldown, PaperworkMissing, RobotsDisallow, catalog.AccessDenied, catalog.UnknownSource) as exc:
        print(f"refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(client.accounting.summary(), file=sys.stderr)
        return 3

    if report is not None and not a.json:
        print(report.text())
    elif brief is not None and not a.json:
        print(brief.text())
    else:
        for r in recs:
            print(r.to_json() if a.json else r.one_line())
        if brief is not None:
            print(brief.summary_json())
        if report is not None:
            print(report.summary_json())
    if a.ledger:
        n = append_ledger(a.ledger, recs)
        print(f"ledger: appended {n} record(s) to {a.ledger}", file=sys.stderr)
    if client.dry_run:
        for method, url in client.planned:
            print(clean_for_terminal(f"planned: {method} {url}"), file=sys.stderr)
        print("dry run: requests whose URLs depend on an earlier response (summaries for the ids a search finds, further pages) are not listed",
              file=sys.stderr)
    print(client.accounting.summary(), file=sys.stderr)
    if report is not None:
        return report.exit_code(dry_run=client.dry_run)
    return 3 if any(r.status in BAD for r in recs) else 0


def _cite_check_preflight(a, client: Client):
    """The identifiers to look up, or an exit code when nothing may be sent: an unreadable file or a bad --max-ids (2),
    a file with no identifier (1: fail closed, not a pass), or more identifiers than --max-ids (2: refused, never truncated)."""
    def stop(code: int, message: str, stream=sys.stderr) -> int:
        print(message, file=stream)
        print(client.accounting.summary(), file=sys.stderr)
        return code

    if not 1 <= a.max_ids <= cite_check.HARD_MAX_IDS:
        return stop(2, f"refused: --max-ids must be between 1 and {cite_check.HARD_MAX_IDS}")
    try:
        text = cite_check.read_text(a.file)
    except OSError as exc:
        return stop(2, f"refused: cannot read {a.file}: {type(exc).__name__}")
    found = cite_check.extract(text)
    if not found:
        msg = (json.dumps({"cite_check": {"file": a.file, "identifiers": [], "counts": {"identifiers": 0},
                                          "result": "no identifiers found", "footer": cite_check.FOOTER}}, sort_keys=True)
               if a.json else f"no identifiers found in {a.file}; nothing was checked, so this is not a pass\n\n{cite_check.FOOTER}")
        return stop(1, msg, sys.stdout)
    if len(found) > a.max_ids:
        kinds = ", ".join(f"{sum(f.kind == k for f in found)} {k}" for k in ("DOI", "PMID", "NCT"))
        return stop(2, f"refused: {len(found)} distinct identifiers found ({kinds}), more than --max-ids {a.max_ids}; "
                       "nothing was looked up. Split the file or raise --max-ids; the list is never truncated.")
    return found


def _dispatch(a, ap, client: Client) -> list[Evidence]:
    if a.cmd == "doi":
        return [crossref.work(client, a.doi)]
    elif a.cmd == "retractions":
        return crossref.check_dois(client, a.dois)
    elif a.cmd == "approval":
        return [openfda.approval(client, a.brand)]
    elif a.cmd == "label":
        return [openfda.label(client, a.brand, tuple(a.sections))]
    elif a.cmd == "preprint":
        return preprints.details(client, a.server, a.doi)
    elif a.cmd == "preprints":
        return preprints.window(client, a.server, a.start, a.end, a.pattern)
    elif a.cmd == "variants":
        return clinvar.variants(client, a.term, a.limit)
    elif a.cmd == "grants":
        return reporter.projects(client, a.text, a.fy or None, a.limit)
    elif a.cmd == "pubmed":
        return pubmed.search(client, a.term, a.limit, a.sort)
    elif a.cmd == "reviews":
        return pubmed.reviews(client, a.term, a.limit)
    elif a.cmd == "trial":
        return trials.study(client, a.nct_id)
    elif a.cmd == "trials":
        return trials.search(client, a.condition, a.term, a.status, a.limit)
    elif a.cmd == "epmc":
        return europepmc.search(client, a.query, a.limit)
    elif a.cmd == "cited":
        return europepmc.lookup(client, a.doi)
    ap.error(a.cmd)  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())

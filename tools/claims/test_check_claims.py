"""Tests for check_claims.py: the error-ledger cases as regression tests, negative controls, and a check that every rule can fail.
Usage: python -m unittest -v   (from this folder), or python test_check_claims.py. Standard library only; no network."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check_claims.py"
EXAMPLE = HERE / "example"


def load(name="check_claims_under_test"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = load()

# Invented evidence; no real report text.
EVIDENCE = {
    "rep": cc.normalise_text(
        "Table 4. In the 2024 report, 127 variants were classed as benign and 437 were left unclassified. "
        "The 2024 report uses the Leeds criteria and the antibody criterion for the diagnosis. "
        "Only patients seen in two or more clinics were counted. Median age at diagnosis was 0.4 years. "
        "The contents list a data quality section without a number."),
}
SCOPE = "every sentence of the 2024 report text file, read in full, all sections"
BASIS = "the report counts only patients seen in two or more clinics, so single-clinic patients are absent"


def claim(**kw):
    c = {"id": "c1", "claim": "The 2024 report left 437 variants unclassified.", "source": "rep",
         "quote": "In the 2024 report, 127 variants were classed as benign and 437 were left unclassified.", "kind": "observed"}
    c.update(kw)
    return {k: v for k, v in c.items() if v is not None}


def run(claims, evidence=None, errors=None, **kw):
    return cc.check(claims, EVIDENCE if evidence is None else evidence, errors or {}, **kw)


def failed(results, rule=None):
    return [r for r in results if not r["ok"] and (rule is None or r["rule"] == rule)]


# One claim per rule that fails on that rule and passes every other: the registry test below uses these.
FAIL_CASES = {
    "R1": [claim(id="d"), claim(id="d")],
    "R2": [claim(quote="In the 2024 report, 128 variants were classed as benign", claim="The report classed variants.")],
    "R3": [claim(claim="The 2024 report left 473 variants unclassified.")],
    "R4": [claim(claim="The 2024 report uses only the Leeds criteria.", quote="The 2024 report uses the Leeds criteria",
                 scope="the 2024 report")],
    "R5": [claim(claim="Our inference: single-clinic patients are missing.", kind="inferred",
                 quote="Only patients seen in two or more clinics were counted.", scope=SCOPE)],
}


class LedgerCases(unittest.TestCase):
    """Regression tests shaped like the claim-type rows of the error ledger."""

    def test_e59_number_from_memory_fails(self):
        r = run([claim(claim="The 2024 report has 60 checks over 437 variants.")])
        self.assertEqual([x["rule"] for x in failed(r)], ["R3"])
        self.assertIn("60", failed(r)[0]["detail"])

    def test_e71_ratio_must_be_computed_from_quoted_numbers(self):
        good = claim(claim="Unclassified variants are 3.4 times the benign ones in the 2024 report.", kind="computed",
                     computed=[{"expr": "437 / 127", "result": 3.4}])
        self.assertEqual(failed(run([good])), [])
        wrong = dict(good, computed=[{"expr": "437 / 127", "result": 5}], claim="Unclassified variants are 5 times the benign ones.")
        self.assertEqual([x["rule"] for x in failed(run([wrong]))], ["R3"])

    def test_e73_added_year_range_fails(self):
        r = run([claim(claim="From 2019 to 2024 the report left 437 variants unclassified.")])
        self.assertEqual([x["rule"] for x in failed(r)], ["R3"])
        self.assertIn("2019", failed(r)[0]["detail"])

    def test_e73_new_in_beyond_the_quote_fails(self):
        r = run([claim(claim="The antibody criterion is new in the 2024 report.",
                       quote="The 2024 report uses the Leeds criteria and the antibody criterion")])
        self.assertEqual([x["rule"] for x in failed(r)], ["R4"])
        self.assertIn("new in", failed(r)[0]["detail"])

    def test_e12_only_from_a_truncated_quote_fails(self):
        r = run([claim(claim="The 2024 report uses only the Leeds criteria.", quote="The 2024 report uses the Leeds criteria", scope=SCOPE)])
        self.assertEqual([x["rule"] for x in failed(r)], ["R4"])
        self.assertIn("observed claim uses 'only'", failed(r)[0]["detail"])

    def test_e13_e77_absence_claim_without_scope_fails(self):
        c = claim(claim="The contents have no evidence of a data quality section.", quote="The contents list a data quality section")
        self.assertEqual([x["rule"] for x in failed(run([c]))], ["R4"])
        self.assertEqual(failed(run([dict(c, scope=SCOPE)])), [])

    def test_e119_e127_spelled_number_not_in_quote_fails(self):
        r = run([claim(claim="The 2024 report left 437 variants unclassified, three per table.")])
        self.assertEqual([x["rule"] for x in failed(r)], ["R3"])
        self.assertIn("three", failed(r)[0]["detail"])

    def test_e127_causal_word_needs_scope_and_inference(self):
        r = run([claim(claim="The 2024 report left 437 variants unclassified because review time ran out.")])
        self.assertEqual([x["rule"] for x in failed(r)], ["R4"])


class Rules(unittest.TestCase):
    def test_correct_observed_claim_passes(self):
        r = run([claim()])
        self.assertEqual(failed(r), [])
        self.assertEqual([x["rule"] for x in r], ["R1", "R2", "R3", "R4", "R5"])

    def test_correct_computed_sum_passes(self):
        c = claim(claim="Together 564 variants in the 2024 report were benign or unclassified.", kind="computed",
                  computed=[{"expr": "127 + 437", "result": 564}])
        self.assertEqual(failed(run([c])), [])

    def test_computed_chain_and_thousands_separator(self):
        c = claim(claim="That is 1,128 when doubled.", kind="computed",
                  computed=[{"expr": "127 + 437", "result": 564}, {"expr": "564 + 564", "result": "1,128"}])
        self.assertEqual(failed(run([c])), [], failed(run([c])))

    def test_computed_operand_not_in_quote_fails(self):
        c = claim(claim="Together 565 variants.", kind="computed", computed=[{"expr": "128 + 437", "result": 565}])
        self.assertIn("operand", failed(run([c]), "R3")[0]["detail"])

    def test_unsafe_expr_fails_and_is_not_executed(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "ran.txt"
            for expr in (f"open({str(marker)!r}, 'w')", "__import__('os').getcwd()", "(127).__class__", "127 ** 437", "[127]"):
                c = claim(claim="Together 564 variants.", kind="computed", computed=[{"expr": expr, "result": 564}])
                f = failed(run([c]), "R3")
                self.assertTrue(f and "computed 1" in f[0]["detail"], (expr, f))
            self.assertFalse(marker.exists(), "an expression was executed")
        with self.assertRaises(ValueError):
            cc.safe_arith("__import__('os')")
        with self.assertRaises(ValueError):
            cc.safe_arith("1 / (2 - 2)")
        self.assertEqual(cc.safe_arith("(127 + 437) / 2")[0], 282)

    def test_quote_with_one_word_changed_fails(self):
        r = run([claim(quote="In the 2024 report, 127 variants were classed as benign and 437 were kept unclassified.")])
        self.assertEqual([x["rule"] for x in failed(r)], ["R2"])

    def test_quote_matching_only_after_case_folding_fails(self):
        r = run([claim(quote="in the 2024 Report, 127 variants were classed as benign and 437 were left unclassified.")])
        self.assertIn("case", failed(r, "R2")[0]["detail"])

    def test_quote_normalises_whitespace_curly_quotes_and_dashes_only(self):
        ev = {"rep": cc.normalise_text("The “Leeds” criteria – all of them – apply\nhere today.")}
        c = claim(claim="The report names the criteria.", quote='The "Leeds" criteria  -  all of them - apply here')
        self.assertEqual(failed(run([c], evidence=ev), "R2"), [])

    def test_ellipsis_quote_fails_and_a_list_of_quotes_passes(self):
        c = claim(claim="The 2024 report left 437 variants unclassified.",
                  quote="In the 2024 report, 127 variants ... 437 were left unclassified.")
        self.assertIn("ellipsis", failed(run([c]), "R2")[0]["detail"])
        c["quote"] = ["In the 2024 report, 127 variants", "and 437 were left unclassified."]
        self.assertEqual(failed(run([c])), [])

    def test_quote_word_limits(self):
        short = claim(claim="Variants were left.", quote="were left unclassified")
        self.assertIn("at least 4", failed(run([short]), "R2")[0]["detail"])
        self.assertIn("limit is 6", failed(run([claim()], max_quote_words=6), "R2")[0]["detail"])

    def test_only_with_short_scope_fails_and_proper_scope_passes(self):
        c = claim(claim="Only patients seen in two or more clinics were counted.", quote="Only patients seen in two or more clinics were counted.",
                  scope="the 2024 report")
        self.assertIn("at least 8 words", failed(run([c]), "R4")[0]["detail"])
        c["scope"] = SCOPE
        self.assertEqual(failed(run([c])), [])

    def test_widening_word_is_whole_word_and_case_insensitive(self):
        self.assertTrue(cc.has_term("ALL of them", "all"))
        self.assertFalse(cc.has_term("a small allele", "all"))
        self.assertTrue(cc.has_term("it is   no longer used", "no longer"))

    def test_inferred_claim_without_basis_fails(self):
        c = claim(claim="Our inference: single-clinic patients are missing.", kind="inferred",
                  quote="Only patients seen in two or more clinics were counted.", scope=SCOPE)
        self.assertIn("basis", failed(run([c]), "R5")[0]["detail"])
        c["basis"] = BASIS
        self.assertEqual(failed(run([c])), [])
        c["claim"] = "Single-clinic patients are missing."
        self.assertIn("our inference", failed(run([c]), "R5")[0]["detail"])

    def test_computed_kind_needs_entries_and_observed_must_not_have_them(self):
        self.assertTrue(failed(run([claim(kind="computed")]), "R5"))
        self.assertTrue(failed(run([claim(computed=[{"expr": "127 + 437", "result": 564}])]), "R5"))

    def test_numbers_extraction(self):
        got = [n for _, n in cc.claim_numbers("From 2019-2024, 1,214 cases (85.0%), not T-0067 or R117H; no one; two groups.")]
        self.assertEqual(got, ["2019", "2024", "1214", "85", "2"])


class FailClosed(unittest.TestCase):
    def test_duplicate_ids_fail(self):
        r = run([claim(), claim()])
        self.assertEqual([x["rule"] for x in failed(r)], ["R1", "R1"])

    def test_missing_fields_and_unknown_fields_fail(self):
        self.assertIn("missing field 'quote'", failed(run([claim(quote=None)]))[0]["detail"])
        self.assertIn("unknown field", failed(run([claim(scop=SCOPE)]))[0]["detail"])
        self.assertIn("kind", failed(run([claim(kind="guessed")]))[0]["detail"])
        self.assertEqual(failed(run(["not an object"]))[0]["id"], "#1")

    def test_source_without_evidence_fails(self):
        self.assertIn("no evidence", failed(run([claim(source="other")]))[0]["detail"])


class Cli(unittest.TestCase):
    def cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=env)

    def test_examples(self):
        r = self.cli(EXAMPLE / "claims-pass.json", "--evidence-map", EXAMPLE / "evidence-map.json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("4 claims, 0 failures", r.stdout)
        r = self.cli(EXAMPLE / "claims-fail.json", "--evidence", f"review={EXAMPLE / 'evidence.txt'}")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL f1 R3 numbers: number 473", r.stdout)
        self.assertIn("3 claims, 5 failures", r.stdout)

    def test_json_output(self):
        r = self.cli(EXAMPLE / "claims-fail.json", "--evidence", f"review={EXAMPLE / 'evidence.txt'}", "--json")
        data = json.loads(r.stdout)
        self.assertEqual((r.returncode, data["claims"], data["failures"], data["ok"]), (1, 3, 5, False))

    def test_fail_closed_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "empty.json").write_text("[]", encoding="utf-8")
            (d / "bad.json").write_text("{not json", encoding="utf-8")
            ev = f"review={EXAMPLE / 'evidence.txt'}"
            for f in ("empty.json", "bad.json", "nope.json"):
                r = self.cli(d / f, "--evidence", ev)
                self.assertEqual(r.returncode, 1, (f, r.stdout))
                self.assertIn("FAIL - R1", r.stdout)
            r = self.cli(EXAMPLE / "claims-pass.json", "--evidence", f"review={d / 'missing.txt'}")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("no such file", r.stdout)
            self.assertNotIn("PASS c1 R2", r.stdout)
            r = self.cli(EXAMPLE / "claims-pass.json")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("no evidence was given", r.stdout)

    def test_usage_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "blank.txt").write_text("# only a comment\n\n", encoding="utf-8")
            ev = f"review={EXAMPLE / 'evidence.txt'}"
            for args in (["--evidence", "no-equals-sign"], ["--evidence", ev, "--evidence", ev], ["--evidence", ev, "--widening", d / "blank.txt"],
                         ["--evidence", ev, "--widening", d / "nope.txt"], ["--evidence", ev, "--max-quote-words", "3"], ["--bogus"]):
                r = self.cli(EXAMPLE / "claims-pass.json", *args)
                self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))

    def test_widening_file_replaces_the_list(self):
        with tempfile.TemporaryDirectory() as td:
            w = Path(td) / "w.txt"
            w.write_text("left  # a word the example uses\n", encoding="utf-8")
            r = self.cli(EXAMPLE / "claims-pass.json", "--evidence-map", EXAMPLE / "evidence-map.json", "--widening", w)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("FAIL c1 R4", r.stdout)
            self.assertIn("PASS c3 R4", r.stdout)  # 'only' is no longer on the list

    def test_help_says_what_it_does_not_prove(self):
        self.assertIn("does NOT prove", self.cli("--help").stdout)

    def test_survives_characters_the_console_cannot_print(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "ev.txt").write_text("The snowman ☃ report lists 437 variants left unclassified today.", encoding="utf-8")
            (d / "c.json").write_text(json.dumps([{"id": "☃", "claim": "It lists 438 variants ☃.", "source": "e",
                                                   "quote": "lists 437 variants left", "kind": "observed"}]), encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPT), str(d / "c.json"), "--evidence", f"e={d / 'ev.txt'}"], capture_output=True,
                               env=dict(os.environ, PYTHONIOENCODING="cp1252"))
            self.assertEqual(r.returncode, 1)
            out = r.stdout.decode("cp1252", errors="replace")
            self.assertNotIn("Traceback", out)

    def test_md_companion_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            md = d / "landscape-report.md"
            md.write_text("# Landscape Report\nThe 2024 report left 437 variants unclassified.\n", encoding="utf-8")
            ev = d / "evidence.txt"
            ev.write_text("The 2024 report left 437 variants unclassified.", encoding="utf-8")
            claims = [
                {
                    "id": "c1",
                    "claim": "The 2024 report left 437 variants unclassified.",
                    "source": "rep",
                    "quote": "The 2024 report left 437 variants unclassified.",
                    "kind": "observed",
                }
            ]
            companion = d / "landscape-report-claims.json"
            companion.write_text(json.dumps(claims), encoding="utf-8")
            ev_map = d / "landscape-report-evidence-map.json"
            ev_map.write_text(json.dumps({"rep": "evidence.txt"}), encoding="utf-8")
            # Passing .md resolves companion -claims.json and companion -evidence-map.json
            r = self.cli(md)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("1 claims, 0 failures", r.stdout)

            # Failure when markdown does not contain the claim text or numbers
            md.write_text("# Landscape Report\nEntirely unrelated text without the claim.\n", encoding="utf-8")
            r_fail = self.cli(md)
            self.assertEqual(r_fail.returncode, 1, r_fail.stdout)
            self.assertIn("FAIL c1 R2 companion_markdown", r_fail.stdout)


class EveryRuleCanFail(unittest.TestCase):
    """Mutation-style: each rule has a case that fails on it alone, and with that rule switched off the same case passes."""

    def test_every_rule_has_a_fail_case(self):
        self.assertEqual(sorted(FAIL_CASES), sorted(cc.RULES))

    def test_each_fail_case_fails_only_its_rule(self):
        for rule, claims in FAIL_CASES.items():
            with self.subTest(rule=rule):
                rules = {x["rule"] for x in failed(run(claims))}
                self.assertEqual(rules, {rule})

    def test_switching_a_rule_off_lets_its_case_through(self):
        for rule, claims in FAIL_CASES.items():
            with self.subTest(rule=rule):
                mutant = load(f"mutant_{rule}")
                mutant.RULES[rule] = lambda c, ctx: (True, "switched off")
                results = mutant.check(claims, EVIDENCE, {})
                self.assertEqual([r for r in results if not r["ok"]], [], "this case does not depend on the rule")


if __name__ == "__main__":
    unittest.main()

"""Tests for lint-powershell.ps1: a PowerShell AST lint for scripts written by a local model (T-0085).

Run from the scripts folder: python -m unittest test_lint_powershell
The linter and its fixtures are looked up next to this file (lint-powershell.ps1, lint-fixtures/);
LINT_SCRIPT overrides the linter path. Needs PowerShell 7 (pwsh) only; no model, network or module.
"""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = Path(os.environ.get("LINT_SCRIPT") or HERE / "lint-powershell.ps1")
FIX = HERE / "lint-fixtures"
LINE = re.compile(r"^(?P<path>.+):(?P<line>\d+):(?P<col>\d+): (?P<id>PSL\d{3}) (?P<msg>\S.*)$")

# fixture stem -> expected findings as (line, column); every finding carries the rule id in the stem.
EXPECTED = {
    "psl001": [(3, 15)],
    "psl002": [(3, 1)],
    "psl003": [(4, 9)],
    "psl004": [(4, 18)],
    "psl005": [(2, 12)],
    "psl006": [(2, 20)],
    "psl007": [(2, 25)],
    "psl008": [(3, 19)],
    "psl009": [(2, 23)],
    "psl010": [(2, 6)],
    "psl011": [(3, 1), (4, 1)],
}


def run(*args, cwd=None):
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True, timeout=240, cwd=cwd,
    )
    return proc.returncode, proc.stdout + proc.stderr


def findings(out):
    found = []
    for raw in out.splitlines():
        m = LINE.match(raw.strip())
        if m:
            found.append((m.group("path"), int(m.group("line")), int(m.group("col")), m.group("id")))
    return found


class CliTests(unittest.TestCase):
    def test_no_arguments_exits_2(self):
        code, out = run()
        if code != 2:
            self.fail(f"no arguments: expected exit 2, got {code}")

    def test_missing_file_exits_2(self):
        code, out = run(FIX / "does-not-exist.ps1")
        if code != 2:
            self.fail(f"missing file: expected exit 2, got {code}")

    def test_clean_file_exits_0_and_says_ok(self):
        code, out = run(FIX / "clean-psl002.ps1")
        if code != 0:
            self.fail(f"clean file: expected exit 0, got {code}: {out.strip()[:200]}")
        if findings(out):
            self.fail(f"clean file: expected no finding lines, got {findings(out)}")
        if not re.search(r"^OK: 1 file\(s\) clean", out, re.M):
            self.fail(f"clean file: expected a line starting 'OK: 1 file(s) clean', got {out.strip()[:200]!r}")

    def test_bad_file_prints_fail_summary(self):
        code, out = run(FIX / "bad-psl004.ps1")
        if not re.search(r"^FAIL: 1 finding\(s\) in 1 file\(s\)", out, re.M):
            self.fail(f"summary: expected 'FAIL: 1 finding(s) in 1 file(s)', got {out.strip()[-200:]!r}")

    def test_two_files_flag_only_the_bad_one(self):
        code, out = run(FIX / "clean-psl004.ps1", FIX / "bad-psl004.ps1")
        got = findings(out)
        paths = {Path(p).name for p, _, _, _ in got}
        if code != 1 or paths != {"bad-psl004.ps1"}:
            self.fail(f"two files: expected exit 1 and only bad-psl004.ps1, got exit {code} and {sorted(paths)}")

    def test_path_is_printed_as_given(self):
        code, out = run(FIX / "bad-psl002.ps1")
        got = findings(out)
        if not got or got[0][0] != str(FIX / "bad-psl002.ps1"):
            self.fail(f"path as given: expected {str(FIX / 'bad-psl002.ps1')!r}, got {got[:1]}")

    def test_selftest_passes(self):
        code, out = run("-SelfTest")
        if code != 0 or not re.search(r"All \d+ lint self-tests passed", out):
            self.fail(f"-SelfTest: expected exit 0 and 'All N lint self-tests passed', got exit {code}: {out.strip()[-200:]!r}")

    def test_linter_is_clean_on_itself(self):
        code, out = run(SCRIPT)
        if code != 0:
            self.fail(f"self-lint: expected exit 0, got {code}: {out.strip()[:300]!r}")

    def test_the_linted_file_is_never_executed(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.ps1"
            marker = Path(d) / "marker.txt"
            target.write_text(f"Set-Content -LiteralPath '{marker.as_posix()}' -Value touched\n", encoding="utf-8")
            code, out = run(target)
            if marker.exists():
                self.fail("the linted script was executed: marker file exists")
            if code != 0:
                self.fail(f"harmless script: expected exit 0, got {code}: {out.strip()[:200]!r}")


def bad_fixture(stem):
    """The fixture that does not parse is kept under known-wrong/, which check-changed.ps1 skips."""
    known = FIX / "known-wrong" / f"bad-{stem}.ps1"
    return known if known.exists() else FIX / f"bad-{stem}.ps1"


def make_case(stem, expected):
    def bad(self):
        code, out = run(bad_fixture(stem))
        got = findings(out)
        want = [(ln, col, stem.upper()) for ln, col in expected]
        have = [(ln, col, rid) for _, ln, col, rid in got]
        if code != 1:
            self.fail(f"bad-{stem}: expected exit 1, got {code}")
        if have != want:
            self.fail(f"bad-{stem}: expected (line, col, id) {want}, got {have}")

    def clean(self):
        code, out = run(FIX / f"clean-{stem}.ps1")
        if code != 0 or findings(out):
            self.fail(f"clean-{stem}: expected exit 0 and no findings, got exit {code} and {findings(out)}")

    return bad, clean


CORE = ("psl001", "psl002", "psl003", "psl004")
MORE = tuple(k for k in EXPECTED if k not in CORE)


class CoreRuleTests(unittest.TestCase):
    pass


class MoreRuleTests(unittest.TestCase):
    pass


def test_deep_nesting_reports_one_finding(self):
    code, out = run(FIX / "bad-psl003-deep.ps1")
    have = [(ln, col, rid) for _, ln, col, rid in findings(out)]
    if code != 1 or have != [(5, 13, "PSL003")]:
        self.fail(f"deep nesting: expected exit 1 and one finding [(5, 13, 'PSL003')], got exit {code} and {have}")


CoreRuleTests.test_deep_nesting_reports_one_finding = test_deep_nesting_reports_one_finding


for _stem, _cls in [(s, CoreRuleTests) for s in CORE] + [(s, MoreRuleTests) for s in MORE]:
    _bad, _clean = make_case(_stem, EXPECTED[_stem])
    setattr(_cls, f"test_bad_{_stem}_is_flagged_at_the_right_place", _bad)
    setattr(_cls, f"test_clean_{_stem}_has_no_finding", _clean)


if __name__ == "__main__":
    unittest.main()

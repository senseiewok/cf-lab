#!/usr/bin/env python3
"""Tests for setup-browser-testing.py: dry-run output, argument handling, the yes prompt and the
order of the commands a real run would execute. Standard library unittest; nothing is downloaded,
no virtual environment is created and no browser is started (the step runner is replaced).

Usage: python test-setup-browser-testing.py   -> prints VERIFIED and exits 0 only when all tests pass.
"""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "setup-browser-testing.py"
spec = importlib.util.spec_from_file_location("setup_browser_testing", SCRIPT)
sbt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sbt)
PIN = "playwright==" + sbt.PLAYWRIGHT_VERSION


def cli(*args, stdin=""):
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, input=stdin,
                       timeout=60, errors="replace")
    return p.returncode, p.stdout + p.stderr


def call_main(argv, answer=None):
    """Run main() in process with the step runner recorded instead of executed."""
    ran = []

    def fake_run(cmd):
        ran.append(list(cmd))
        return 0
    out = io.StringIO()
    with mock.patch.object(sbt, "run_step", side_effect=fake_run), \
            mock.patch.object(sbt, "ask", return_value=answer if answer is not None else ""), \
            contextlib.redirect_stdout(out):
        rc = sbt.main(argv)
    return rc, out.getvalue(), ran


class Base(unittest.TestCase):
    def setUp(self):
        # A temp folder that is not inside any git repository (the system temp folder normally is not).
        self.tmp = Path(tempfile.mkdtemp(prefix="pw setup test "))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.venv = self.tmp / "venv dir"
        if sbt.inside_repository(self.tmp) is not None:
            self.skipTest("the system temp folder is inside a git repository")


class DryRun(Base):
    def test_dry_run_prints_plan_and_touches_nothing(self):
        rc, out = cli("--dry-run", "--browser", "chromium", "--venv", str(self.venv))
        self.assertEqual(rc, 0, out)
        for want in (PIN, "https://pypi.org", "https://cdn.playwright.dev", "install --dry-run chromium",
                     "Create a virtual environment", "Dry run: nothing was downloaded, created or changed."):
            self.assertIn(want, out)
        self.assertTrue(out.rstrip().endswith("Dry run: nothing was downloaded, created or changed."))
        self.assertFalse(self.venv.exists(), "a dry run must not create the virtual environment")
        self.assertNotIn("Type yes", out, "a dry run must not ask")

    def test_dry_run_wins_over_yes(self):
        rc, out, ran = call_main(["--dry-run", "--yes", "--browser", "chromium", "--venv", str(self.venv)])
        self.assertEqual((rc, ran), (0, []))
        self.assertFalse(self.venv.exists())

    def test_dry_run_reuses_an_existing_venv(self):
        self.venv.mkdir()
        (self.venv / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
        rc, out = cli("--dry-run", "--browser", "chromium", "--venv", str(self.venv))
        self.assertEqual(rc, 0, out)
        self.assertIn("Reuse the existing virtual environment", out)
        self.assertNotIn("-m venv", out)

    def test_channel_plan_has_no_browser_download(self):
        with mock.patch.object(sbt, "choose_browser", return_value=("msedge", "/fake/msedge", None)):
            rc, out, ran = call_main(["--dry-run", "--venv", str(self.venv)])
        self.assertEqual(rc, 0, out)
        self.assertIn("no browser download", out)
        self.assertNotIn("playwright install", out)
        self.assertIn("--self-test --channel msedge", out)


class Refusals(Base):
    def test_non_venv_folder_is_refused_and_left_alone(self):
        self.venv.mkdir()
        (self.venv / "mine.txt").write_text("keep", encoding="utf-8")
        rc, out = cli("--dry-run", "--browser", "chromium", "--venv", str(self.venv))
        self.assertEqual(rc, 1, out)
        self.assertIn("is not a virtual environment", out)
        self.assertEqual((self.venv / "mine.txt").read_text(encoding="utf-8"), "keep")

    def test_a_file_in_the_way_is_refused(self):
        self.venv.write_text("x", encoding="utf-8")
        rc, out = cli("--dry-run", "--browser", "chromium", "--venv", str(self.venv))
        self.assertEqual(rc, 1, out)
        self.assertIn("is a file", out)

    def test_venv_inside_a_repository_is_refused(self):
        (self.tmp / ".git").mkdir()
        rc, out = cli("--dry-run", "--browser", "chromium", "--venv", str(self.tmp / "sub" / "venv"))
        self.assertEqual(rc, 1, out)
        self.assertIn("inside the git repository", out)
        self.assertFalse((self.tmp / "sub").exists())

    def test_missing_named_browser_is_an_error(self):
        with mock.patch.object(sbt, "find_browser", return_value=None):
            rc, out, ran = call_main(["--dry-run", "--browser", "chrome", "--venv", str(self.venv)])
        self.assertEqual((rc, ran), (1, []))
        self.assertIn("Google Chrome was not found", out)

    def test_old_python_is_refused(self):
        self.assertFalse(sbt.python_ok((3, 9, 18)))
        self.assertTrue(sbt.python_ok((3, 10, 0)))
        with mock.patch.object(sbt, "python_ok", return_value=False):
            rc, out, ran = call_main(["--dry-run", "--browser", "chromium", "--venv", str(self.venv)])
        self.assertEqual((rc, ran), (1, []))
        self.assertIn("needs Python 3.10 or newer", out)


class Arguments(unittest.TestCase):
    def test_unknown_argument_is_a_usage_error(self):
        rc, out = cli("--force")
        self.assertEqual(rc, 2)
        self.assertIn("usage:", out)

    def test_bad_browser_choice_is_a_usage_error(self):
        rc, out = cli("--dry-run", "--browser", "firefox")
        self.assertEqual(rc, 2)
        self.assertIn("invalid choice", out)

    def test_help_mentions_dry_run(self):
        rc, out = cli("--help")
        self.assertEqual(rc, 0)
        self.assertIn("--dry-run", out)


class Prompt(Base):
    def test_no_answer_stops_before_anything_runs(self):
        for answer in ("", "no", "y", "YES please"):
            rc, out, ran = call_main(["--browser", "chromium", "--venv", str(self.venv)], answer=answer)
            self.assertEqual((rc, ran), (3, []), answer)
            self.assertIn("Stopped. Nothing was downloaded, created or changed.", out)
        self.assertFalse(self.venv.exists())

    def test_closed_stdin_counts_as_no(self):
        rc, out = cli("--browser", "chromium", "--venv", str(self.venv), stdin="")
        self.assertEqual(rc, 3, out)
        self.assertFalse(self.venv.exists())

    def test_typed_yes_runs_the_steps_in_order(self):
        rc, out, ran = call_main(["--browser", "chromium", "--venv", str(self.venv)], answer=" Yes ")
        self.assertEqual(rc, 0, out)
        self.assertEqual(ran[0][1:3], ["-m", "venv"])
        self.assertEqual(ran[1][-1], PIN)
        self.assertEqual(ran[2][-3:], ["install", "--dry-run", "chromium"])
        self.assertEqual(ran[3][-2:], ["install", "chromium"])
        self.assertTrue(ran[4][1].endswith("observe-page.py") and ran[4][2:] == ["--self-test"])
        self.assertEqual(len(ran), 5)

    def test_yes_flag_skips_the_question_and_a_failed_step_stops(self):
        calls = []

        def failing(cmd):
            calls.append(cmd)
            return 7 if PIN in cmd else 0
        out = io.StringIO()
        with mock.patch.object(sbt, "run_step", side_effect=failing), \
                mock.patch.object(sbt, "ask", side_effect=AssertionError("must not ask")), \
                contextlib.redirect_stdout(out):
            rc = sbt.main(["--yes", "--browser", "chromium", "--venv", str(self.venv)])
        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 2, "nothing may run after the failed pip step")
        self.assertIn("step 2 failed with exit code 7", out.getvalue())


class Detection(unittest.TestCase):
    def test_windows_finds_edge_before_chrome(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"PROGRAMFILES": str(Path(d) / "pf"), "PROGRAMFILES(X86)": str(Path(d) / "pf86"), "LOCALAPPDATA": str(Path(d) / "la")}
            edge = Path(d, "pf86", "Microsoft", "Edge", "Application", "msedge.exe")
            chrome = Path(d, "la", "Google", "Chrome", "Application", "chrome.exe")
            for f in (edge, chrome):
                f.parent.mkdir(parents=True)
                f.write_text("", encoding="utf-8")
            self.assertEqual(sbt.choose_browser("auto", env, "win32"), ("msedge", str(edge), None))
            self.assertEqual(sbt.choose_browser("chrome", env, "win32"), ("chrome", str(chrome), None))
            edge.unlink()
            self.assertEqual(sbt.choose_browser("auto", env, "win32")[0], "chrome")
            chrome.unlink()
            self.assertEqual(sbt.choose_browser("auto", env, "win32"), ("chromium", None, None))

    def test_mac_and_linux_paths(self):
        seen = []
        sbt.find_browser("msedge", {}, "darwin", exists=lambda p: seen.append(p) or False)
        sbt.find_browser("chrome", {}, "linux", exists=lambda p: seen.append(p) or False)
        self.assertEqual(seen, ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "/opt/google/chrome/chrome"])

    def test_chromium_never_looks_for_a_browser(self):
        self.assertEqual(sbt.choose_browser("chromium", {}, "linux", exists=lambda p: True), ("chromium", None, None))

    def test_default_venv(self):
        self.assertEqual(sbt.default_venv({"LOCALAPPDATA": r"C:\la"}, "win32"), Path(r"C:\la") / "lab-playwright")
        self.assertEqual(sbt.default_venv({"XDG_DATA_HOME": "/x"}, "linux"), Path("/x") / "lab-playwright")
        self.assertEqual(sbt.default_venv({"HOME": "/h"}, "darwin"), Path("/h") / ".local" / "share" / "lab-playwright")


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=1).result
    ok = result.wasSuccessful()
    print("VERIFIED" if ok else f"{len(result.failures) + len(result.errors)} failure(s)")
    sys.exit(0 if ok else 1)

"""Tests for verify-in-copy.py: judge a candidate file for one path of a repository inside a temporary copy, with generators and unittest modules, printing FAIL lines.
Run: python test_verify_in_copy.py   (standard library only; no model, network or GPU). Set VERIFY_IN_COPY_PATH to test another file."""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(os.environ.get("VERIFY_IN_COPY_PATH") or Path(__file__).resolve().parent / "verify-in-copy.py")

TOOL_GOOD = "def add(a, b):\n    return a + b\n"
TOOL_WRONG = "def add(a, b):\n    return a - b\n"
TEST_FILE = '''import unittest
import tool


class T(unittest.TestCase):
    def test_add(self):
        self.assertEqual(tool.add(2, 3), 5, "add(2, 3) should be 5")

    def test_many_subtests(self):
        for i in range(5):
            with self.subTest(i=i):
                self.assertTrue(tool.add(i, 0) == i + 1 and False, "the same cause every time")


class Other(unittest.TestCase):
    def test_reads_a_sibling_file(self):
        from pathlib import Path
        self.assertEqual((Path(__file__).resolve().parents[1] / "sibling" / "data.txt").read_text().strip(), "from-sibling")
'''
GENERATOR = "import sys\nsys.exit(int(open('flag.txt').read().strip()))\n"


def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class VerifyInCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vic-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        (self.repo / "tests").mkdir(parents=True)
        (self.repo / "tool.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
        (self.repo / "tests" / "test_tool.py").write_text(TEST_FILE.replace("import tool", "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nimport tool"), encoding="utf-8")
        (self.repo / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "gen.py").write_text(GENERATOR, encoding="utf-8")
        (self.repo / "flag.txt").write_text("0\n", encoding="utf-8")
        self.sibling = self.tmp / "sibling"
        self.sibling.mkdir()
        (self.sibling / "data.txt").write_text("from-sibling\n", encoding="utf-8")
        self.cand = self.tmp / "candidate.py"

    def run_script(self, candidate_text, *extra, tests=("tests.test_tool.T",)):
        self.cand.write_text(candidate_text, encoding="utf-8")
        args = [sys.executable, str(SCRIPT), "--repo", str(self.repo), "--target", "tool.py", "--candidate", str(self.cand)]
        for t in tests:
            args += ["--tests", t]
        args += list(extra)
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return r.returncode, r.stdout + r.stderr

    def test_a_passing_candidate_exits_0_and_the_last_line_counts_passes(self):
        code, out = self.run_script(TOOL_GOOD, tests=("tests.test_tool.T.test_add",))
        self.assertEqual(code, 0, out)
        last = out.strip().splitlines()[-1]
        self.assertRegex(last, r"^\d+ / \d+ passed$")
        self.assertEqual(last.split()[0], last.split()[2])

    def test_a_failing_candidate_names_the_test_and_the_assertion_on_a_FAIL_line(self):
        code, out = self.run_script(TOOL_WRONG, tests=("tests.test_tool.T.test_add",))
        self.assertEqual(code, 1, out)
        fails = [l for l in out.splitlines() if l.startswith("FAIL")]
        self.assertTrue(any("test_add" in l and "add(2, 3) should be 5" in l for l in fails), out)
        self.assertRegex(out.strip().splitlines()[-1], r"^\d+ / \d+ passed$")

    def test_identical_failure_lines_are_shown_once_with_a_count(self):
        code, out = self.run_script(TOOL_WRONG, tests=("tests.test_tool.T.test_many_subtests",))
        self.assertEqual(code, 1, out)
        same = [l for l in out.splitlines() if l.startswith("FAIL") and "the same cause every time" in l]
        self.assertEqual(len(same), 1, out)
        self.assertIn("(x5)", same[0])

    def test_a_candidate_that_does_not_compile_is_reported_and_no_test_runs(self):
        code, out = self.run_script("def add(a, b)\n    return a +\n")
        self.assertEqual(code, 1, out)
        self.assertTrue(any(l.startswith("FAIL") and "does not compile" in l for l in out.splitlines()), out)
        self.assertNotIn("test_add", out)
        self.assertEqual(out.strip().splitlines()[-1], "0 / 1 passed")

    def test_an_empty_candidate_is_a_failure_not_a_pass(self):
        code, out = self.run_script("")
        self.assertEqual(code, 1, out)

    def test_a_failing_generator_is_named_with_its_exit_code(self):
        (self.repo / "flag.txt").write_text("3\n", encoding="utf-8")
        code, out = self.run_script(TOOL_GOOD, "--generator", "python gen.py", tests=("tests.test_tool.T.test_add",))
        self.assertEqual(code, 1, out)
        self.assertTrue(any(l.startswith("FAIL") and "gen.py" in l and "3" in l for l in out.splitlines()), out)

    def test_a_passing_generator_does_not_fail_the_run(self):
        code, out = self.run_script(TOOL_GOOD, "--generator", "python gen.py", tests=("tests.test_tool.T.test_add",))
        self.assertEqual(code, 0, out)

    def test_the_real_repository_is_never_modified(self):
        before = tree_hash(self.repo)
        self.run_script(TOOL_GOOD, "--generator", "python gen.py")
        self.run_script(TOOL_WRONG)
        self.assertEqual(tree_hash(self.repo), before)

    def test_a_linked_sibling_folder_is_visible_beside_the_copy(self):
        code, out = self.run_script(TOOL_GOOD, "--link", f"sibling={self.sibling}", tests=("tests.test_tool.Other",))
        self.assertEqual(code, 0, out)
        self.assertEqual((self.sibling / "data.txt").read_text().strip(), "from-sibling", "the real sibling folder survives the cleanup")
        code, out = self.run_script(TOOL_GOOD, tests=("tests.test_tool.Other",))
        self.assertEqual(code, 1, "without --link the sibling is not there: " + out)

    def test_only_the_named_test_modules_run(self):
        code, out = self.run_script(TOOL_WRONG, tests=("tests.test_tool.Other",), )
        self.assertEqual(code, 1, "the sibling test fails without --link, and the failing add tests are not run")
        self.assertNotIn("test_add", out)

    def test_at_most_the_requested_number_of_distinct_failures_are_printed_and_the_rest_counted(self):
        (self.repo / "tests" / "test_many.py").write_text(
            "import unittest\n\nclass M(unittest.TestCase):\n" + "".join(f"    def test_{i:02d}(self):\n        self.assertEqual(1, 2, 'distinct cause {i}')\n\n" for i in range(20)), encoding="utf-8")
        code, out = self.run_script(TOOL_GOOD, "--max-lines", "5", tests=("tests.test_many",))
        self.assertEqual(code, 1, out)
        self.assertEqual(len([l for l in out.splitlines() if l.startswith("FAIL")]), 5, out)
        self.assertIn("more distinct failures omitted", out)

    def test_a_missing_repo_or_candidate_is_a_usage_error_with_exit_2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.tmp / "nowhere"), "--target", "tool.py", "--candidate", str(self.cand)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_the_script_uses_no_network_modules(self):
        import ast
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertFalse(names & {"socket", "urllib", "http", "requests", "ftplib", "smtplib"}, names)


if __name__ == "__main__":
    unittest.main()

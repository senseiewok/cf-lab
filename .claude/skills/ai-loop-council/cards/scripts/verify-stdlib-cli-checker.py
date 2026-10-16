#!/usr/bin/env python3
"""
Verifier for stdlib-cli-checker playbook card.
Evaluates a Python 3 CLI tool candidate against standard library checker conventions:
- Standard exit codes: 0 clean, 1 findings/defects, 2 usage error
- Clean error output without uncaught tracebacks
- Support for --self-test
- Zero third-party dependencies (stdlib only)
"""
import ast
import os
import subprocess
import sys
import tempfile

# Verifier FAIL codes:
# FAIL R-01 usage: expected exit 2 got traceback
# FAIL R-02 exit code: expected exit 1 on defect, got
# FAIL R-03 normalisation: normalised strings differ between source and quote
# FAIL R-04 self-test: --self-test failed on reference fixtures
# FAIL R-05 dependencies: forbidden third-party import

def fail(code, message):
    print(f"FAIL {code} {message}")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        fail("R-00", "usage: verify-stdlib-cli-checker.py <candidate-path>")

    candidate = sys.argv[1]
    if not os.path.isfile(candidate):
        fail("R-00", f"candidate file not found: {candidate}")

    try:
        with open(candidate, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        fail("R-00", f"cannot read candidate: {e}")

    # 1. AST parse and forbidden imports check
    try:
        tree = ast.parse(source, filename=candidate)
    except SyntaxError as e:
        fail("R-00", f"syntax error in candidate: {e}")

    allowed_stdlib = {
        "sys", "os", "re", "json", "argparse", "pathlib", "subprocess",
        "hashlib", "datetime", "typing", "collections", "itertools", "tempfile",
        "shutil", "unittest", "io", "math", "time"
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod not in allowed_stdlib and not mod.startswith("_"):
                    fail("R-05", f"dependencies: forbidden third-party import '{mod}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod not in allowed_stdlib and not mod.startswith("_"):
                    fail("R-05", f"dependencies: forbidden third-party import '{mod}'")

    # 2. Check usage error exit code (run with invalid argument)
    try:
        proc_usage = subprocess.run(
            [sys.executable, candidate, "--invalid-flag-xyz-probe"],
            capture_output=True,
            text=True,
            timeout=10
        )
    except subprocess.TimeoutExpired:
        fail("R-01", "usage: execution timed out on invalid argument probe")

    if proc_usage.returncode != 2:
        if "Traceback" in proc_usage.stderr:
            fail("R-01", "usage: expected exit 2 got traceback")
        else:
            fail("R-01", f"usage: expected exit 2, got exit {proc_usage.returncode}")

    # 3. Check self-test execution
    try:
        proc_test = subprocess.run(
            [sys.executable, candidate, "--self-test"],
            capture_output=True,
            text=True,
            timeout=10
        )
    except subprocess.TimeoutExpired:
        fail("R-04", "self-test: execution timed out during --self-test")

    if proc_test.returncode != 0:
        fail("R-04", f"self-test: --self-test failed on reference fixtures (exit {proc_test.returncode})")

    # 4. Check clean input vs defect input
    with tempfile.TemporaryDirectory() as tmpdir:
        clean_file = os.path.join(tmpdir, "clean.txt")
        with open(clean_file, "w", encoding="utf-8") as f:
            f.write("VALID SAMPLE CONTENT\n")

        defect_file = os.path.join(tmpdir, "defect.txt")
        with open(defect_file, "w", encoding="utf-8") as f:
            f.write("DEFECT UNEXPECTED\n")

        proc_clean = subprocess.run(
            [sys.executable, candidate, clean_file],
            capture_output=True,
            text=True
        )
        if proc_clean.returncode != 0:
            fail("R-03", f"normalisation: normalised strings differ between source and quote (exit {proc_clean.returncode})")

        proc_defect = subprocess.run(
            [sys.executable, candidate, defect_file],
            capture_output=True,
            text=True
        )
        if proc_defect.returncode != 1:
            fail("R-02", f"exit code: expected exit 1 on defect, got {proc_defect.returncode}")

    print("ALL CHECKS PASSED: stdlib-cli-checker candidate valid")
    sys.exit(0)

if __name__ == "__main__":
    main()

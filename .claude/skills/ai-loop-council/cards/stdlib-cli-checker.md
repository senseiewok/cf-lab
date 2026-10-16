---
card: stdlib-cli-checker
class: check
when: A Python 3 standard-library CLI checker that verifies files and exits with standard codes (0 clean, 1 findings, 2 usage error).
not_when: Shell scripts, non-CLI libraries, or tools with external third-party dependencies.
verifier: scripts/verify-stdlib-cli-checker.py
profiles: fast,fast,medium
max_output: 8192
budget_calls: 5
status: draft
---

## Packet skeleton

```markdown
Write a self-contained Python 3 CLI tool: `<tool-name>.py`.
The tool must:
1. Use only the Python standard library.
2. Accept file paths as arguments, plus `--self-test`.
3. Exit 0 when all checks pass, exit 1 when any check fails with findings, and exit 2 on invalid CLI arguments.
4. Wrap main in a try/except block to emit clean `error: <msg>` to stderr without tracebacks on usage error.
5. Provide a deterministic `--self-test` suite with built-in fixtures.
```

## Worked example

```python
import argparse
import sys

def check_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        return "DEFECT" not in f.read()

def self_test() -> int:
    assert check_file.__code__.co_argcount == 1
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description="Sample CLI file checker")
    parser.add_argument("files", nargs="*", help="Files to verify")
    parser.add_argument("--self-test", action="store_true", help="Run self-test suite")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.files:
        parser.error("No input files provided")

    all_clean = True
    for f in args.files:
        if not check_file(f):
            print(f"DEFECT detected in {f}")
            all_clean = False
    return 0 if all_clean else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        sys.stderr.write(f"error: {exc}\n")
        sys.exit(2)
```

## Decomposition

1. Define argument parsing (`argparse.ArgumentParser`) with `--self-test` and positional file arguments.
2. Implement pure validation rules with clear separation between normalization and assertions.
3. Wire exit code contracts: 0 (clean), 1 (defects reported), 2 (CLI usage / argument errors).
4. Implement `--self-test` using in-memory string fixtures or synthetic files.
5. Wrap execution entrypoint in clean exception formatting avoiding raw Python tracebacks on user error.

## Verifier contract

- `FAIL R-01 usage: expected exit 2 got traceback`: Verifies that invalid CLI arguments result in exit code 2 and do not dump a Python traceback.
- `FAIL R-02 exit code: expected exit 1 on defect, got`: Verifies that files containing defects cause an exit code of 1.
- `FAIL R-03 normalisation: normalised strings differ between source and quote`: Verifies that clean valid input files pass with exit code 0.
- `FAIL R-04 self-test: --self-test failed on reference fixtures`: Verifies that `--self-test` executes and exits with code 0.
- `FAIL R-05 dependencies: forbidden third-party import`: Verifies that only allowed Python standard library modules are imported.

## Known failure modes

| Symptom | Cause | Repair Instruction |
|---|---|---|
| `FAIL R-01 usage: expected exit 2 got traceback` | Uncaught exception or raw `sys.argv` index error | Wrap `main()` in try/except; use `argparse` with standard exit code 2 on argument error. |
| `FAIL R-02 exit code: expected exit 1 on defect, got` | Returning 0 on defect or inverted logic | Ensure defect counter increments and returns code 1 if `findings > 0`. |
| `FAIL R-03 normalisation: normalised strings differ between source and quote` | Overly aggressive stripping or whitespace mismatch | Verify clean files return exit 0; separate line normalization from semantic comparison. |
| `FAIL R-04 self-test: --self-test failed on reference fixtures` | Internal assertion failure in `--self-test` | Ensure self-test fixtures cover valid and defect paths and exit 0. |
| `FAIL R-05 dependencies: forbidden third-party import` | Importing external packages (e.g. `requests`, `pytest`) | Replace external package with Python standard library equivalents (`urllib`, `unittest`). |

## Do-not examples

```python
# Do NOT catch all exceptions silently and exit 0:
try:
    process()
except Exception:
    sys.exit(0)  # FAILS R-02: defects hidden as success

# Do NOT import third-party modules:
import requests  # FAILS R-05: requires standard library only
```

## Escalation

- Escalate to the human maintainer if two consecutive attempts fail with the same single check (`FAIL R-01` or `FAIL R-04`) indicating potential spec ambiguity.
- Escalate immediately if the candidate attempts to read unauthorized system paths outside its task directory.

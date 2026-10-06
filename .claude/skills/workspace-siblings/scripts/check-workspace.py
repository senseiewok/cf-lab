#!/usr/bin/env python3
"""Read-only checker for the cf-lab folder layout.

Usage: python check-workspace.py [--root CF_LAB_FOLDER] [--self-test]

Checks that cf-skills and cf-research sit beside cf-lab as git repos with the expected origin,
that cf-lab-files exists, that each sibling's .claude/settings.json holds every Read(...) and
Edit(...) deny rule in cf-lab's .claude/settings.json (read at run time; cf-lab's command
rules such as the push rules are not required there), and, if present, that cf-lab's
.claude/settings.local.json lists the siblings in permissions.additionalDirectories.
It reads only those settings files and never opens .env or any credential file; it never
prints a remote URL. Exit codes: 0 all passed, 1 a check failed, 2 usage error.
Standard library only. Drafted by the local worker against test_check_workspace.py.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SIBLINGS = {"cf-skills": "senseiewok/cf-skills", "cf-research": "senseiewok/cf-research"}
FILES_DIR = "cf-lab-files"


def _url_matches(url: str, expected: str) -> bool:
    u = url.strip()
    if u.endswith("/"):
        u = u[:-1]
    if u.endswith(".git"):
        u = u[:-4]
    return (
        u == expected
        or u.endswith("/" + expected)
        or u.endswith(":" + expected)
    )


def _read_deny(path: Path):
    """Return the deny list from a settings.json, or None on any problem."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return None
    deny = perms.get("deny")
    if not isinstance(deny, list):
        return None
    return deny


def _file_rules(deny):
    """The secret-file deny rules: those for the Read and Edit tools. Command rules stay cf-lab's own."""
    return [r for r in deny if isinstance(r, str) and r.startswith(("Read(", "Edit("))]


def run_checks(root: Path) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    parent = root.parent

    # 1. Root deny rules
    lab_deny = _read_deny(root / ".claude" / "settings.json")
    if lab_deny is None:
        results.append((False, "FAIL cf-lab settings: cannot read deny rules (missing file or invalid JSON) in .claude/settings.json"))
    else:
        results.append((True, f"PASS cf-lab settings: {len(lab_deny)} deny rules read"))
        lab_deny = _file_rules(lab_deny)

    # 2. Siblings
    for name, expected in SIBLINGS.items():
        d = parent / name
        if not d.is_dir():
            results.append((False, f"FAIL sibling {name}: missing at {d}; run setup.cmd (Windows) or ./setup.sh to clone it"))
            continue
        if not (d / ".git").exists():
            results.append((False, f"FAIL sibling {name}: not a git repository"))
            continue
        try:
            proc = subprocess.run(
                ["git", "-C", str(d), "config", "--get", "remote.origin.url"],
                capture_output=True, text=True, timeout=30,
            )
            url = proc.stdout.strip() if proc.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            url = None
        if url is None or not _url_matches(url, expected):
            results.append((False, f"FAIL sibling {name}: origin does not point to {expected}"))
        else:
            results.append((True, f"PASS sibling {name}: git repo, origin {expected}"))

    # 3. Files folder
    files_dir = parent / FILES_DIR
    if files_dir.is_dir():
        results.append((True, "PASS cf-lab-files: present"))
    else:
        results.append((False, f"FAIL cf-lab-files: missing at {files_dir}; run setup.cmd or ./setup.sh"))

    # 4. Sibling deny rules
    for name in SIBLINGS:
        if lab_deny is None:
            results.append((False, f"FAIL deny rules {name}: cannot compare, cf-lab deny rules unreadable"))
            continue
        sib_path = parent / name / ".claude" / "settings.json"
        try:
            data = json.loads(sib_path.read_text(encoding="utf-8-sig"))
        except OSError:
            results.append((False, f"FAIL deny rules {name}: no .claude/settings.json; a session started there has no secret-file deny rules"))
            continue
        except ValueError:  # includes UnicodeDecodeError and JSONDecodeError
            results.append((False, f"FAIL deny rules {name}: invalid JSON or no permissions.deny list in .claude/settings.json"))
            continue
        if not isinstance(data, dict):
            results.append((False, f"FAIL deny rules {name}: invalid JSON or no permissions.deny list in .claude/settings.json"))
            continue
        perms = data.get("permissions")
        if not isinstance(perms, dict):
            results.append((False, f"FAIL deny rules {name}: invalid JSON or no permissions.deny list in .claude/settings.json"))
            continue
        sib_deny = perms.get("deny")
        if not isinstance(sib_deny, list):
            results.append((False, f"FAIL deny rules {name}: invalid JSON or no permissions.deny list in .claude/settings.json"))
            continue
        missing = [r for r in lab_deny if r not in sib_deny]
        if missing:
            results.append((False, f"FAIL deny rules {name}: {len(missing)} of {len(lab_deny)} cf-lab secret-file deny rules missing, e.g. {missing[0]}"))
        else:
            results.append((True, f"PASS deny rules {name}: all {len(lab_deny)} cf-lab secret-file deny rules present"))

    # 5. Local settings
    local_path = root / ".claude" / "settings.local.json"
    if not local_path.exists():
        results.append((True, "PASS local settings: not present (optional)"))
        return results
    try:
        data = json.loads(local_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError):
        results.append((False, "FAIL local settings: invalid JSON in .claude/settings.local.json"))
        return results

    if not isinstance(data, dict):
        data = {}
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        perms = {}
    dirs = perms.get("additionalDirectories")
    if not isinstance(dirs, list):
        dirs = []

    norm_dirs = set()
    for entry in dirs:
        if isinstance(entry, str) and os.path.isabs(entry):
            norm_dirs.add(os.path.normcase(os.path.normpath(os.path.abspath(entry))))

    for name in SIBLINGS:
        target = os.path.normcase(os.path.normpath(os.path.abspath(str(parent / name))))
        if target in norm_dirs:
            results.append((True, f"PASS local settings: additionalDirectories lists {name}"))
        else:
            results.append((False, f"FAIL local settings: additionalDirectories does not list {name} (use an absolute path)"))

    return results


def report(results: list[tuple[bool, str]]) -> int:
    passed = 0
    failed = 0
    for ok, line in results:
        print(line)
        if ok:
            passed += 1
        else:
            failed += 1
    print(f"{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def _init_git_sibling(d: Path, url: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(d), check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", url], cwd=str(d), check=True, capture_output=True)


def _write_settings(d: Path, deny: list[str]) -> None:
    claude = d / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "settings.json").write_text(
        json.dumps({"permissions": {"deny": deny}}, indent=2), encoding="utf-8"
    )


def _build_tree(base: Path, *, cf_skills_deny=None, cf_research_deny=None,
                skip_cf_research=False, skills_url="https://github.com/senseiewok/cf-skills",
                research_url="https://github.com/senseiewok/cf-research",
                malformed_research=False) -> Path:
    root = base / "cf-lab"
    root.mkdir(parents=True, exist_ok=True)
    lab_deny = ["Read(.env)", "Read(**/*.pem)", "Edit(.env)"]
    _write_settings(root, lab_deny)

    (base / FILES_DIR).mkdir(parents=True, exist_ok=True)

    if cf_skills_deny is not None:
        _init_git_sibling(base / "cf-skills", skills_url)
        _write_settings(base / "cf-skills", cf_skills_deny)

    if not skip_cf_research:
        _init_git_sibling(base / "cf-research", research_url)
        if malformed_research:
            claude = base / "cf-research" / ".claude"
            claude.mkdir(parents=True, exist_ok=True)
            (claude / "settings.json").write_text("{ bad", encoding="utf-8")
        else:
            _write_settings(base / "cf-research", cf_research_deny)

    return root


def self_test() -> int:
    lab_deny = ["Read(.env)", "Read(**/*.pem)", "Edit(.env)"]

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1. good tree
        r1 = _build_tree(base / "case1", cf_skills_deny=lab_deny, cf_research_deny=lab_deny)
        # 2. missing sibling (no cf-research)
        r2 = _build_tree(base / "case2", cf_skills_deny=lab_deny, skip_cf_research=True)
        # 3. wrong remote
        r3 = _build_tree(
            base / "case3", cf_skills_deny=lab_deny, cf_research_deny=lab_deny,
            skills_url="https://github.com/other/cf-skills",
        )
        # 4. missing deny rules in cf-skills
        r4 = _build_tree(base / "case4", cf_skills_deny=["Read(.env)"], cf_research_deny=lab_deny)
        # 5. malformed JSON in cf-research
        r5 = _build_tree(base / "case5", cf_skills_deny=lab_deny, cf_research_deny=lab_deny, malformed_research=True)

        cases = [
            ("good tree", r1, None),
            ("missing sibling", r2, ["cf-research", "missing"]),
            ("wrong remote", r3, ["cf-skills", "origin"]),
            ("missing deny rules", r4, ["deny rules cf-skills"]),
            ("malformed JSON", r5, ["cf-research", "JSON"]),
        ]

        passed = 0
        total = len(cases)
        for case_name, root, required in cases:
            results = run_checks(root)
            fail_lines = [line for ok, line in results if not ok]
            if required is None:
                ok_case = len(fail_lines) == 0
            else:
                # every required token must appear in the same FAIL line
                ok_case = any(all(tok in fl for tok in required) for fl in fail_lines)
            if ok_case:
                print(f"self-test ok: {case_name}")
                passed += 1
            else:
                print(f"self-test FAILED: {case_name}")

    print(f"self-test: {passed}/{total} passed")
    return 0 if passed == total else 1


def main(argv) -> int:
    # scripts -> workspace-siblings -> skills -> .claude -> cf-lab
    default_root = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description="Read-only checker for the cf-lab folder layout.")
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: root is not a directory: {root}")
        return 2

    results = run_checks(root)
    return report(results)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

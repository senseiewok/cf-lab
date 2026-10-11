#!/usr/bin/env python3
"""Read-only checker for the cf-lab folder layout.

Usage: python check-workspace.py [--root CF_LAB_FOLDER] [--self-test]

Checks that cf-skills and cf-research sit beside cf-lab as git repos with the expected origin,
that cf-lab-files exists, that each sibling's .claude/settings.json holds every Read(...) and
Edit(...) deny rule in cf-lab's .claude/settings.json (read at run time; cf-lab's command
rules such as the push rules are not required there), and, if present, that cf-lab's
.claude/settings.local.json lists the siblings in permissions.additionalDirectories.
It also checks instruction and skill loading: no CLAUDE.md, CLAUDE.local.md or .claude/CLAUDE.md
in cf-lab, in any parent folder up to the drive root, or in ~/.claude (a CLAUDE.md makes Claude
Code skip AGENTS.md); skill names unique across the three repos and not shadowing an entry of
~/.claude/skills; and a SKILL.md whose frontmatter name equals the folder name in every skill folder.
It reads only those settings files, CLAUDE.md names and SKILL.md frontmatter, and never opens .env
or any credential file; it never prints a remote URL. Tests may point the home folder with the
environment variable CF_LAB_CHECK_HOME and end the parent walk with CF_LAB_CHECK_STOP. Exit codes: 0 all passed, 1 a check failed, 2 usage error.
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


CLAUDE_MD_NAMES = ("CLAUDE.md", "CLAUDE.local.md", os.path.join(".claude", "CLAUDE.md"))


def _check_claude_md(root: Path, home: Path, stop: Path | None) -> list[tuple[bool, str]]:
    """No CLAUDE.md in cf-lab, a parent folder or ~/.claude: it would silently replace AGENTS.md."""
    found: list[Path] = []
    for d in [root, *root.parents]:
        for name in CLAUDE_MD_NAMES:
            if (d / name).is_file():
                found.append(d / name)
        if stop is not None and d == stop:
            break
    if (home / ".claude" / "CLAUDE.md").is_file():
        found.append(home / ".claude" / "CLAUDE.md")
    if not found:
        return [(True, "PASS instructions: no CLAUDE.md in cf-lab, its parent folders or ~/.claude, so AGENTS.md loads")]
    return [
        (False, f"FAIL instructions: {f} would stop AGENTS.md loading in Claude Code; delete it or make it only the line @AGENTS.md")
        for f in found
    ]


def _frontmatter_name(path: Path):
    """The name: value of a SKILL.md frontmatter, or None (no frontmatter, no name, unreadable)."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith("name:"):
            return line[5:].strip().strip("'\"")
    return None


def _skill_folders(repo: Path) -> list[Path]:
    skills = repo / ".claude" / "skills"
    if not skills.is_dir():
        return []
    return sorted(p for p in skills.iterdir() if p.is_dir())


def _check_skills(root: Path, home: Path) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    repos = {"cf-lab": root}
    for name in SIBLINGS:
        if (root.parent / name).is_dir():
            repos[name] = root.parent / name

    owners: dict[str, list[str]] = {}
    problems = 0
    total = 0
    for repo_name, repo in repos.items():
        for folder in _skill_folders(repo):
            skill_md = folder / "SKILL.md"
            if not skill_md.is_file():
                results.append((False, f"FAIL skills: {repo_name} .claude/skills/{folder.name} has no SKILL.md"))
                problems += 1
                continue
            total += 1
            owners.setdefault(folder.name, []).append(repo_name)
            declared = _frontmatter_name(skill_md)
            if declared != folder.name:
                shown = "no name in the frontmatter" if declared is None else f"frontmatter name {declared!r}"
                results.append((False, f"FAIL skills: {repo_name} .claude/skills/{folder.name}/SKILL.md has {shown}; it must equal the folder name"))
                problems += 1
    if problems == 0:
        results.append((True, f"PASS skills: {total} skill folders each have a SKILL.md whose name equals the folder name"))

    collisions = 0
    for name, where in sorted(owners.items()):
        if len(where) > 1:
            results.append((False, f"FAIL skill names: {name} is in more than one repo ({', '.join(where)})"))
            collisions += 1
    personal = home / ".claude" / "skills"
    personal_names = set()
    if personal.is_dir():
        personal_names = {p.name for p in personal.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}
    for name, where in sorted(owners.items()):
        if name in personal_names:
            results.append((False, f"FAIL skill names: {name} in {where[0]} is also in ~/.claude/skills, and a personal skill wins over a project skill"))
            collisions += 1
    if collisions == 0:
        results.append((True, f"PASS skill names: {len(owners)} unique across {len(repos)} repos, none shadowed by ~/.claude/skills"))
    return results


def run_checks(root: Path, home: Path | None = None, stop: Path | None = None) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    parent = root.parent
    if home is None:
        home = Path(os.environ.get("CF_LAB_CHECK_HOME") or Path.home())
    if stop is None and os.environ.get("CF_LAB_CHECK_STOP"):
        stop = Path(os.environ["CF_LAB_CHECK_STOP"]).resolve()

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

    # 5. Instruction and skill loading
    results.extend(_check_claude_md(root, home, stop))
    results.extend(_check_skills(root, home))

    # 6. Local settings
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
        base = Path(tmp).resolve()

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

        home = base / "home"
        (home / ".claude").mkdir(parents=True)

        def mk(name, **kw):
            return _build_tree(base / name, cf_skills_deny=lab_deny, cf_research_deny=lab_deny, **kw)

        def add_skill(repo: Path, name: str, declared: str | None = None, skill_md: bool = True) -> None:
            d = repo / ".claude" / "skills" / name
            d.mkdir(parents=True, exist_ok=True)
            if skill_md:
                (d / "SKILL.md").write_text(f"---\nname: {declared or name}\ndescription: x\n---\n", encoding="utf-8")

        # 6. CLAUDE.md in cf-lab
        r6 = mk("case6")
        (r6 / "CLAUDE.md").write_text("Read AGENTS.md\n", encoding="utf-8")
        # 7. CLAUDE.local.md in a parent folder
        r7 = mk("case7")
        (r7.parent / "CLAUDE.local.md").write_text("x\n", encoding="utf-8")
        # 8. skill name in two repos
        r8 = mk("case8")
        add_skill(r8, "dup")
        add_skill(r8.parent / "cf-skills", "dup")
        # 9. frontmatter name differs from folder
        r9 = mk("case9")
        add_skill(r9, "folder-name", declared="other-name")
        # 10. skill folder without SKILL.md
        r10 = mk("case10")
        add_skill(r10, "empty-folder", skill_md=False)
        # 11. skill shadowed by a personal skill
        r11 = mk("case11")
        add_skill(r11, "mine")
        (home / ".claude" / "skills" / "mine").mkdir(parents=True)
        (home / ".claude" / "skills" / "mine" / "SKILL.md").write_text("---\nname: mine\n---\n", encoding="utf-8")
        # 12. unique skills, personal entry without SKILL.md ignored
        r12 = mk("case12")
        add_skill(r12, "one")
        add_skill(r12.parent / "cf-skills", "two")
        (home / ".claude" / "skills" / "one").mkdir(parents=True)

        # 13. CLAUDE.md in the home .claude folder (own home)
        home13 = base / "home13"
        (home13 / ".claude").mkdir(parents=True)
        (home13 / ".claude" / "CLAUDE.md").write_text("x\n", encoding="utf-8")
        r13 = mk("case13")

        # each case: (name, root, required tokens in one FAIL line or None, home)
        cases = [
            ("good tree", r1, None, home),
            ("missing sibling", r2, ["cf-research", "missing"], home),
            ("wrong remote", r3, ["cf-skills", "origin"], home),
            ("missing deny rules", r4, ["deny rules cf-skills"], home),
            ("malformed JSON", r5, ["cf-research", "JSON"], home),
            ("CLAUDE.md in cf-lab", r6, ["CLAUDE.md", "AGENTS.md", "@AGENTS.md"], home),
            ("CLAUDE.local.md in parent", r7, ["CLAUDE.local.md", "AGENTS.md"], home),
            ("duplicate skill name", r8, ["skill names", "dup"], home),
            ("name differs from folder", r9, ["folder-name", "other-name"], home),
            ("skill folder without SKILL.md", r10, ["empty-folder", "no SKILL.md"], home),
            ("skill shadowed by personal skill", r11, ["mine", "~/.claude/skills"], home),
            ("unique skills pass", r12, None, home),
            ("CLAUDE.md in home .claude", r13, ["CLAUDE.md", "AGENTS.md"], home13),
        ]

        passed = 0
        total = len(cases)
        for case_name, root, required, case_home in cases:
            results = run_checks(root, home=case_home, stop=base)
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

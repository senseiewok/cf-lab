#!/usr/bin/env python3
"""Tests for check-workspace.py. Standard library only; needs git on PATH for the fixtures.

Run: python .claude/skills/workspace-siblings/scripts/test_check_workspace.py
"""
import builtins
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _find_script():
    here = Path(__file__).resolve().parent / "check-workspace.py"
    if here.is_file():
        return here
    return Path.cwd() / ".claude" / "skills" / "workspace-siblings" / "scripts" / "check-workspace.py"


SCRIPT = _find_script()

DENY = [
    "Read(.env)",
    "Read(.env.local)",
    "Read(**/*.pem)",
    "Read(~/.ssh/**)",
    "Edit(.env)",
]

CANARY = "CANARY-SECRET-0123456789"


def load_module():
    spec = importlib.util.spec_from_file_location("check_workspace", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, timeout=60)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_tree(base, remotes=None, deny=None, local=None, files_dir=True, skip=()):
    """Build <base>/cf-lab plus siblings. Returns the cf-lab path."""
    remotes = remotes or {
        "cf-skills": "https://github.com/senseiewok/cf-skills.git",
        "cf-research": "https://github.com/senseiewok/cf-research",
    }
    lab = base / "cf-lab"
    lab.mkdir(parents=True)
    write_json(lab / ".claude" / "settings.json", {"permissions": {"deny": DENY, "ask": ["Bash(git push *)"]}})
    (lab / ".env").write_text("KEY=" + CANARY + "\n", encoding="utf-8")
    for name, url in remotes.items():
        if name in skip:
            continue
        d = base / name
        d.mkdir()
        git("init", "-q", cwd=d)
        git("remote", "add", "origin", url, cwd=d)
        rules = DENY if deny is None else deny.get(name, DENY)
        if rules is not None:
            write_json(d / ".claude" / "settings.json", {"permissions": {"deny": rules}})
        (d / ".env").write_text("KEY=" + CANARY + "\n", encoding="utf-8")
    if files_dir:
        (base / "cf-lab-files").mkdir()
    if local is not None:
        p = lab / ".claude" / "settings.local.json"
        if isinstance(local, str):
            p.write_text(local, encoding="utf-8")
        else:
            write_json(p, local)
    return lab


def good_local(base):
    return {"permissions": {"additionalDirectories": [str(base / "cf-skills"), str(base / "cf-research")]}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cw-test-"))
        self.mod = load_module()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, lab):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = self.mod.main(["--root", str(lab)])
        finally:
            sys.stdout = old
        return code, buf.getvalue()

    def fails(self, out):
        return [l for l in out.splitlines() if l.startswith("FAIL")]

    def passes(self, out):
        return [l for l in out.splitlines() if l.startswith("PASS")]


class TestGood(Base):
    def test_good_tree_exit_0(self):
        lab = make_tree(self.tmp, local=good_local(self.tmp))
        code, out = self.run_main(lab)
        self.assertEqual(self.fails(out), [], out)
        self.assertEqual(code, 0, out)
        self.assertGreaterEqual(len(self.passes(out)), 6, out)

    def test_no_local_settings_is_ok(self):
        lab = make_tree(self.tmp)
        code, out = self.run_main(lab)
        self.assertEqual(code, 0, out)
        self.assertTrue(any("local settings" in l for l in self.passes(out)), out)

    def test_ssh_remote_and_trailing_git_accepted(self):
        lab = make_tree(self.tmp, remotes={
            "cf-skills": "git@github.com:senseiewok/cf-skills.git",
            "cf-research": "https://github.com/senseiewok/cf-research/",
        })
        code, out = self.run_main(lab)
        self.assertEqual(code, 0, out)

    def test_only_file_rules_compared(self):
        # cf-lab's command rules (Bash/PowerShell) are not secret-file rules; siblings need only Read/Edit rules.
        lab = make_tree(self.tmp)
        write_json(lab / ".claude" / "settings.json",
                   {"permissions": {"deny": DENY + ["Bash(git push --force*)", "PowerShell(git push -f*)"]}})
        code, out = self.run_main(lab)
        self.assertEqual(code, 0, out)
        self.assertTrue(any("deny rules cf-skills" in l and str(len(DENY)) in l for l in self.passes(out)), out)

    def test_extra_deny_rules_in_sibling_ok(self):
        lab = make_tree(self.tmp, deny={"cf-skills": DENY + ["Read(**/secret.txt)"]})
        code, out = self.run_main(lab)
        self.assertEqual(code, 0, out)

    def test_summary_last_line(self):
        lab = make_tree(self.tmp)
        code, out = self.run_main(lab)
        last = out.strip().splitlines()[-1]
        self.assertRegex(last, r"^\d+ passed, 0 failed$")


class TestFailures(Base):
    def test_missing_sibling(self):
        lab = make_tree(self.tmp, skip=("cf-research",))
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        f = self.fails(out)
        self.assertTrue(any("cf-research" in l and "missing" in l for l in f), out)
        self.assertTrue(any("setup" in l for l in f if "cf-research" in l), out)

    def test_not_a_git_repo(self):
        lab = make_tree(self.tmp)
        shutil.rmtree(self.tmp / "cf-skills" / ".git")
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertTrue(any("cf-skills" in l and "git" in l for l in self.fails(out)), out)

    def test_wrong_remote(self):
        lab = make_tree(self.tmp, remotes={
            "cf-skills": "https://github.com/someone-else/cf-skills.git",
            "cf-research": "https://github.com/senseiewok/cf-research.git",
        })
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        f = self.fails(out)
        self.assertTrue(any("cf-skills" in l and "origin" in l for l in f), out)
        self.assertFalse(any("cf-research" in l and "origin" in l for l in f), out)

    def test_wrong_remote_url_not_printed(self):
        lab = make_tree(self.tmp, remotes={
            "cf-skills": "https://user:tok3n@example.com/x/cf-skills.git",
            "cf-research": "https://github.com/senseiewok/cf-research.git",
        })
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertNotIn("tok3n", out)

    def test_lookalike_remote_rejected(self):
        lab = make_tree(self.tmp, remotes={
            "cf-skills": "https://github.com/notsenseiewok/cf-skills.git",
            "cf-research": "https://github.com/senseiewok/cf-research-old.git",
        })
        code, out = self.run_main(lab)
        f = self.fails(out)
        self.assertTrue(any("cf-skills" in l and "origin" in l for l in f), out)
        self.assertTrue(any("cf-research" in l and "origin" in l for l in f), out)

    def test_missing_files_dir(self):
        lab = make_tree(self.tmp, files_dir=False)
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertTrue(any("cf-lab-files" in l for l in self.fails(out)), out)

    def test_missing_deny_rules(self):
        lab = make_tree(self.tmp, deny={"cf-skills": ["Read(.env)"]})
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        f = [l for l in self.fails(out) if "cf-skills" in l and "deny" in l]
        self.assertEqual(len(f), 1, out)
        self.assertIn("4", f[0])

    def test_no_sibling_settings(self):
        lab = make_tree(self.tmp, deny={"cf-research": None})
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertTrue(any("cf-research" in l and "settings.json" in l for l in self.fails(out)), out)

    def test_malformed_sibling_json(self):
        lab = make_tree(self.tmp)
        (self.tmp / "cf-skills" / ".claude" / "settings.json").write_text("{ not json", encoding="utf-8")
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertTrue(any("cf-skills" in l and "JSON" in l for l in self.fails(out)), out)

    def test_malformed_local_json(self):
        lab = make_tree(self.tmp, local="{ nope")
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertTrue(any("local settings" in l and "JSON" in l for l in self.fails(out)), out)

    def test_local_missing_one_sibling(self):
        lab = make_tree(self.tmp, local={"permissions": {"additionalDirectories": [str(self.tmp / "cf-skills")]}})
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        f = self.fails(out)
        self.assertTrue(any("additionalDirectories" in l and "cf-research" in l for l in f), out)
        self.assertFalse(any("additionalDirectories" in l and "cf-skills" in l for l in f), out)

    def test_local_path_normalised(self):
        alt = [str(self.tmp / "cf-lab" / ".." / "cf-skills") + os.sep, str(self.tmp / "cf-research").upper() if os.name == "nt" else str(self.tmp / "cf-research")]
        lab = make_tree(self.tmp, local={"permissions": {"additionalDirectories": alt}})
        code, out = self.run_main(lab)
        self.assertEqual(code, 0, out)

    def test_local_no_permissions_key(self):
        lab = make_tree(self.tmp, local={"model": "x"})
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertTrue(any("additionalDirectories" in l for l in self.fails(out)), out)

    def test_lab_settings_unreadable(self):
        lab = make_tree(self.tmp)
        (lab / ".claude" / "settings.json").write_text("[", encoding="utf-8")
        code, out = self.run_main(lab)
        self.assertEqual(code, 1, out)
        self.assertTrue(any("cf-lab" in l and "JSON" in l for l in self.fails(out)), out)


class TestSafety(Base):
    def test_never_opens_env_files(self):
        lab = make_tree(self.tmp, local=good_local(self.tmp))
        opened = []
        real_open = builtins.open
        real_io_open = io.open
        real_path_open = pathlib.Path.open

        def spy(file, *a, **k):
            opened.append(str(file))
            return real_open(file, *a, **k)

        def spy_io(file, *a, **k):
            opened.append(str(file))
            return real_io_open(file, *a, **k)

        def spy_path(self_, *a, **k):
            opened.append(str(self_))
            return real_path_open(self_, *a, **k)

        builtins.open = spy
        io.open = spy_io
        pathlib.Path.open = spy_path
        try:
            code, out = self.run_main(lab)
        finally:
            builtins.open = real_open
            io.open = real_io_open
            pathlib.Path.open = real_path_open
        self.assertEqual(code, 0, out)
        bad = [p for p in opened if os.path.basename(p).startswith(".env")]
        self.assertEqual(bad, [], opened)
        self.assertNotIn(CANARY, out)

    def test_cli_exit_codes(self):
        lab = make_tree(self.tmp)
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(lab)], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        shutil.rmtree(self.tmp / "cf-lab-files")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(lab)], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)

    def test_default_root_is_repo_root(self):
        # Without --root the script must use the folder that holds .claude/ (cf-lab), not .claude/ itself.
        p = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=120)
        self.assertIn("PASS cf-lab settings", p.stdout, p.stdout + p.stderr)

    def test_bom_settings_read(self):
        lab = make_tree(self.tmp)
        p = self.tmp / "cf-skills" / ".claude" / "settings.json"
        p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes())
        code, out = self.run_main(lab)
        self.assertEqual(code, 0, out)

    def test_bad_root_exit_2(self):
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.tmp / "nope")], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)

    def test_self_test_mode(self):
        p = subprocess.run([sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("self-test", p.stdout.lower())


if __name__ == "__main__":
    unittest.main()

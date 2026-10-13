#!/usr/bin/env python3
"""Tests for worktrees.py. Standard library only; needs git on PATH. No network: pull request states come from a JSON file.

Run: python .claude/skills/workspace-siblings/scripts/test_worktrees.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "worktrees.py"
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_TERMINAL_PROMPT": "0",
       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def git(*args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr}")
    return p.stdout.strip()


def run(*args):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV, stdin=subprocess.DEVNULL, timeout=120)
    return p


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wt test "))
        self.root = self.tmp / "repos"
        self.root.mkdir()
        origin = self.tmp / "origin.git"
        git("init", "--bare", "-b", "main", str(origin), cwd=self.tmp)
        self.repo = self.root / "r1"
        git("clone", str(origin), str(self.repo), cwd=self.tmp)
        (self.repo / "a.txt").write_text("a\n")
        git("add", "a.txt", cwd=self.repo)
        git("commit", "-m", "first", cwd=self.repo)
        git("branch", "-M", "main", cwd=self.repo)
        git("push", "-u", "origin", "main", cwd=self.repo)
        git("remote", "set-head", "origin", "main", cwd=self.repo)
        self.wt = self.root / ".worktrees" / "r1"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add(self, name, branch=None):
        path = self.wt / name
        git("worktree", "add", "-b", branch or name, str(path), "main", cwd=self.repo)
        return path

    def states(self, mapping):
        f = self.tmp / "states.json"
        f.write_text(json.dumps({"r1": mapping}), encoding="utf-8")
        return f


class ListAndClean(Fixture):
    def test_each_verdict(self):
        merged = self.add("merged")
        self.add("openpr")
        dirty = self.add("dirty")
        (dirty / "x.txt").write_text("not committed\n")
        ahead = self.add("ahead")
        git("push", "-u", "origin", "ahead", cwd=ahead)
        (ahead / "b.txt").write_text("b\n")
        git("add", "b.txt", cwd=ahead)
        git("commit", "-m", "later", cwd=ahead)
        self.add("nopr")
        detached = self.wt / "det"
        git("worktree", "add", "--detach", str(detached), "main", cwd=self.repo)
        sf = self.states({"merged": ["MERGED"], "openpr": ["OPEN"], "dirty": ["MERGED"], "ahead": ["MERGED"]})
        p = run("list", "--root", self.root, "--pr-state", sf)
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = {l.split(" | ")[1].split("/")[-1]: l for l in p.stdout.splitlines() if " | " in l}
        self.assertTrue(lines["merged"].startswith("REMOVE"), lines["merged"])
        self.assertTrue(lines["openpr"].startswith("KEEP") and "open" in lines["openpr"], lines["openpr"])
        self.assertTrue(lines["dirty"].startswith("KEEP") and "uncommitted" in lines["dirty"], lines["dirty"])
        self.assertTrue(lines["ahead"].startswith("KEEP") and "commit(s)" in lines["ahead"], lines["ahead"])
        self.assertTrue(lines["nopr"].startswith("KEEP") and "no pull request" in lines["nopr"], lines["nopr"])
        self.assertTrue(lines["det"].startswith("KEEP") and "detached" in lines["det"], lines["det"])
        self.assertIn("SUMMARY 6 worktree(s): 1 removable, 5 kept", p.stdout)
        self.assertTrue(merged.is_dir())

    def test_without_pr_state_every_worktree_is_kept(self):
        self.add("merged")
        p = run("list", "--root", self.root)
        self.assertIn("1 worktree(s): 0 removable, 1 kept", p.stdout)
        self.assertIn("unknown", p.stdout)

    def test_a_dry_run_removes_nothing_and_yes_removes_only_the_removable(self):
        merged = self.add("merged")
        openpr = self.add("openpr")
        dirty = self.add("dirty")
        (dirty / "x.txt").write_text("x\n")
        sf = self.states({"merged": ["MERGED"], "openpr": ["OPEN"], "dirty": ["CLOSED"]})
        p = run("clean", "--root", self.root, "--pr-state", sf)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("WOULD REMOVE r1 | .worktrees/r1/merged", p.stdout)
        self.assertTrue(merged.is_dir() and openpr.is_dir() and dirty.is_dir())
        p = run("clean", "--root", self.root, "--pr-state", sf, "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(merged.exists())
        self.assertTrue(openpr.is_dir() and dirty.is_dir() and self.repo.is_dir())
        self.assertIn("merged", git("branch", "--list", "merged", cwd=self.repo), "the branch is kept")
        self.assertTrue((dirty / "x.txt").is_file(), "a dirty worktree is never touched")

    def test_the_main_checkout_and_a_worktree_folder_are_not_taken_for_repositories(self):
        self.add("merged")
        p = run("list", "--root", self.root, "--pr-state", self.states({}))
        self.assertEqual(p.stdout.count("r1 |"), 1, p.stdout)
        self.assertNotIn("| main |", p.stdout)

    def test_a_worktree_outside_the_folder_is_kept(self):
        out = self.tmp / "elsewhere"
        git("worktree", "add", "-b", "away", str(out), "main", cwd=self.repo)
        sf = self.states({"away": ["MERGED"]})
        p = run("clean", "--root", self.root, "--pr-state", sf, "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(out.is_dir())
        self.assertIn("outside the repositories folder", run("list", "--root", self.root, "--pr-state", sf).stdout)

    def test_a_missing_folder_is_pruned(self):
        gone = self.add("gone")
        shutil.rmtree(gone)
        sf = self.states({})
        p = run("list", "--root", self.root, "--pr-state", sf)
        self.assertIn("REMOVE", p.stdout)
        self.assertIn("worktree prune", p.stdout)
        p = run("clean", "--root", self.root, "--pr-state", sf, "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("gone", git("worktree", "list", cwd=self.repo))


class NewWorktree(Fixture):
    def test_new_creates_under_dot_worktrees(self):
        p = run("new", "r1", "topic-one", "--root", self.root)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        dest = self.root / ".worktrees" / "r1" / "topic-one"
        self.assertTrue((dest / "a.txt").is_file())
        self.assertEqual(git("branch", "--show-current", cwd=dest), "topic-one")

    def test_new_push_sets_upstream_on_origin(self):
        p = run("new", "r1", "showcase-2026-10-12", "--branch", "site/showcase-2026-10-12", "--push", "--root", self.root)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("pushed to origin/site/showcase-2026-10-12", p.stdout)
        dest = self.root / ".worktrees" / "r1" / "showcase-2026-10-12"
        self.assertEqual(git("rev-parse", "--abbrev-ref", "@{u}", cwd=dest), "origin/site/showcase-2026-10-12")

    def test_new_enforces_prefix_and_rolls_back_failed_push(self):
        self.assertEqual(run("new", "r1", "no-prefix", "--push", "--root", self.root).returncode, 2)
        self.assertEqual(run("new", "r1", "bad-prefix", "--branch", "custom/bad-prefix", "--root", self.root).returncode, 2)
        git("remote", "set-url", "origin", str(self.tmp / "missing.git"), cwd=self.repo)
        p = run("new", "r1", "push-fail", "--branch", "feat/push-fail", "--push", "--no-fetch", "--root", self.root)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertFalse((self.root / ".worktrees" / "r1" / "push-fail").exists(), "rolled back worktree folder")
        self.assertEqual(git("branch", "--list", "feat/push-fail", cwd=self.repo), "", "rolled back local branch")

    def test_new_refuses_bad_input(self):
        self.assertEqual(run("new", "nope", "t", "--root", self.root).returncode, 2)
        self.assertEqual(run("new", "r1", "../escape", "--root", self.root).returncode, 2)
        self.assertEqual(run("new", "r1", "bad name", "--root", self.root).returncode, 2)
        self.assertEqual(run("new", "r1", "t", "--root", self.root).returncode, 0)
        self.assertEqual(run("new", "r1", "t", "--root", self.root).returncode, 2)

    def test_usage(self):
        self.assertEqual(run().returncode, 2)
        self.assertEqual(run("list", "--root", self.tmp / "missing").returncode, 2)


class SafetyRules(Fixture):
    def verdicts(self, mapping):
        p = run("list", "--root", self.root, "--pr-state", self.states(mapping))
        self.assertEqual(p.returncode, 0, p.stderr)
        return {l.split(" | ")[1].split("/")[-1]: l for l in p.stdout.splitlines() if " | " in l}

    def test_an_ignored_file_keeps_the_worktree_but_a_cache_does_not(self):
        (self.repo / ".gitignore").write_text(".env\n__pycache__/\n")
        git("add", ".gitignore", cwd=self.repo)
        git("commit", "-m", "ignore", cwd=self.repo)
        git("push", "origin", "main", cwd=self.repo)
        secret = self.add("secret")
        (secret / ".env").write_text("TOKEN=1\n")
        cache = self.add("cache")
        (cache / "__pycache__").mkdir()
        (cache / "__pycache__" / "x.pyc").write_bytes(b"0")
        sf = {"secret": ["MERGED"], "cache": ["MERGED"]}
        v = self.verdicts(sf)
        self.assertTrue(v["secret"].startswith("KEEP") and "ignored" in v["secret"] and ".env" in v["secret"], v["secret"])
        self.assertTrue(v["cache"].startswith("REMOVE"), v["cache"])
        run("clean", "--root", self.root, "--pr-state", self.states(sf), "--yes")
        self.assertTrue((secret / ".env").is_file())

    def test_commits_on_no_remote_keep_the_worktree(self):
        w = self.add("local")
        (w / "b.txt").write_text("b\n")
        git("add", "b.txt", cwd=w)
        git("commit", "-m", "only here", cwd=w)
        v = self.verdicts({"local": ["MERGED"]})
        self.assertTrue(v["local"].startswith("KEEP") and "commit(s)" in v["local"], v["local"])

    def test_a_gone_upstream_with_local_commits_is_kept(self):
        w = self.add("gone-up")
        git("push", "-u", "origin", "gone-up", cwd=w)
        (w / "b.txt").write_text("b\n")
        git("add", "b.txt", cwd=w)
        git("commit", "-m", "after the push", cwd=w)
        git("push", "origin", "--delete", "gone-up", cwd=self.repo)
        git("fetch", "--prune", "origin", cwd=self.repo)
        v = self.verdicts({"gone-up": ["MERGED"]})
        self.assertTrue(v["gone-up"].startswith("KEEP") and "commit(s)" in v["gone-up"], v["gone-up"])

    def test_a_mixed_open_and_merged_list_is_kept(self):
        self.add("mixed")
        v = self.verdicts({"mixed": ["MERGED", "OPEN"]})
        self.assertTrue(v["mixed"].startswith("KEEP") and "open" in v["mixed"], v["mixed"])

    def test_a_locked_worktree_is_kept_and_not_removed(self):
        w = self.add("locked")
        git("worktree", "lock", str(w), cwd=self.repo)
        sf = self.states({"locked": ["MERGED"]})
        self.assertIn("locked", run("list", "--root", self.root, "--pr-state", sf).stdout)
        p = run("clean", "--root", self.root, "--pr-state", sf, "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(w.is_dir())

    def test_a_git_failure_keeps_the_worktree(self):
        w = self.add("broken")
        (self.repo / ".git" / "worktrees" / "broken" / "index").write_bytes(b"not an index")
        v = self.verdicts({"broken": ["MERGED"]})
        self.assertTrue(v["broken"].startswith("KEEP") and "could not" in v["broken"], v["broken"])

    def test_a_stale_entry_outside_the_folder_is_not_pruned(self):
        out = self.tmp / "elsewhere"
        git("worktree", "add", "-b", "away", str(out), "main", cwd=self.repo)
        shutil.rmtree(out)
        gone = self.add("gone")
        shutil.rmtree(gone)
        p = run("clean", "--root", self.root, "--pr-state", self.states({"gone": ["MERGED"]}), "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("NOTE r1", p.stdout)
        self.assertIn("away", git("worktree", "list", "--porcelain", cwd=self.repo), "the outside entry is left alone")

    def test_the_default_root_works_from_a_checkout_or_a_worktree(self):
        scripts = self.repo / ".claude" / "skills" / "workspace-siblings" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy(SCRIPT, scripts / "worktrees.py")
        git("add", "-A", cwd=self.repo)
        git("commit", "-m", "script", cwd=self.repo)
        git("push", "origin", "main", cwd=self.repo)
        wt = self.add("inner")
        for base in (self.repo, wt):
            exe = base / ".claude" / "skills" / "workspace-siblings" / "scripts" / "worktrees.py"
            p = subprocess.run([sys.executable, str(exe), "list", "--pr-state", str(self.states({}))], capture_output=True, text=True,
                               encoding="utf-8", env=ENV, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("r1 |", p.stdout, p.stdout)


class NewRefusals(Fixture):
    def test_new_stays_inside_the_folder_and_checks_its_arguments(self):
        for repo in ("../r1", str(self.repo), "r1/.."):
            self.assertEqual(run("new", repo, "t", "--root", self.root, "--no-fetch").returncode, 2, repo)
        for topic in ("--force", "-x", "a b", "a/b", ".."):
            self.assertEqual(run("new", "r1", topic, "--root", self.root, "--no-fetch").returncode, 2, topic)
        self.assertEqual(run("new", "r1", "t", "--branch", "--force", "--root", self.root, "--no-fetch").returncode, 2)
        self.assertEqual(run("new", "r1", "t", "--base", "--no-checkout", "--root", self.root, "--no-fetch").returncode, 2)
        self.assertEqual(run("new", "r1", "t", "--base", "does-not-exist", "--root", self.root, "--no-fetch").returncode, 2)
        self.assertFalse((self.root / ".worktrees" / "r1" / "t").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)

#!/usr/bin/env python3
"""Tests for pr-screenshots.py without a browser or the network: spec, URL and address checks, the request
handler, file and branch safety rules, the comment markdown, the dry run, and real pushes to local bare
repositories (evidence-tree check, per-folder cap, hooks off, caller identity).

Usage: python test-pr-screenshots.py   -> prints VERIFIED and exits 0 only when all tests pass.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "pr-screenshots.py"
spec = importlib.util.spec_from_file_location("pr_screenshots", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

MAGIC = {".jpg": b"\xff\xd8\xff\xe0", ".jpeg": b"\xff\xd8\xff\xe0", ".png": b"\x89PNG\r\n\x1a\n",
         ".webp": b"RIFF\x00\x00\x00\x00WEBP"}
ENV = {**os.environ, "GIT_AUTHOR_NAME": "Seed", "GIT_AUTHOR_EMAIL": "seed@example.invalid",
       "GIT_COMMITTER_NAME": "Seed", "GIT_COMMITTER_EMAIL": "seed@example.invalid"}
WHO = ("Caller Person", "caller@example.invalid")


def shot(**kw):
    s = {"name": "phone", "url": "http://127.0.0.1:8000/", "viewport": {"width": 390, "height": 844}}
    s.update(kw)
    return s


def run(args, cwd):
    p = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL, env=ENV)
    return p.returncode, p.stdout + p.stderr


def git(args, cwd, stdin=None):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True, env=ENV,
                          input=stdin).stdout


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pr-shots-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def images(self, names, size=None, folder="shots"):
        d = self.tmp / folder
        d.mkdir(exist_ok=True)
        for n in names:
            head = MAGIC.get(Path(n).suffix.lower(), b"")
            (d / n).write_bytes(head + b"0" * (2000 if size is None else size))
        return d

    def bare(self, branch_files=None, default="main", evidence="pr-evidence"):
        """A bare remote whose default branch has a README; branch_files seeds the evidence branch."""
        bare = self.tmp / "remote.git"
        git(["init", "-q", "--bare", "-b", default, str(bare)], self.tmp)
        seed = self.tmp / "seed"
        git(["clone", "-q", str(bare), str(seed)], self.tmp)
        (seed / "README").write_text("main", encoding="utf-8")
        git(["add", "README"], seed)
        git(["commit", "-q", "-m", "seed"], seed)
        git(["push", "-q", "origin", f"HEAD:{default}"], seed)
        if branch_files is not None:
            git(["checkout", "-q", "--orphan", evidence], seed)
            git(["rm", "-q", "-rf", "--cached", "."], seed)
            (seed / "README").unlink()
            for path, content in branch_files.items():
                if content == "SYMLINK":
                    blob = git(["hash-object", "-w", "--stdin"], seed, stdin="../README").strip()
                    git(["update-index", "--add", "--cacheinfo", f"120000,{blob},{path}"], seed)
                else:
                    (seed / path).parent.mkdir(parents=True, exist_ok=True)
                    (seed / path).write_bytes(content)
                    git(["add", "--", path], seed)
            git(["commit", "-q", "-m", "evidence seed"], seed)
            git(["push", "-q", "origin", f"HEAD:{evidence}"], seed)
        return bare


class Spec(unittest.TestCase):
    def test_a_good_spec_is_normalised(self):
        out = m.validate_spec({"shots": [shot(selector="#card", actions=[{"click": "#go"}, {"wait": 100},
                                                                          {"set_value": "#q", "value": "x"}])]})
        self.assertEqual((out[0]["touch"], out[0]["device_scale_factor"], out[0]["caption"]), (False, 1, ""))

    def test_refusals(self):
        bad = {
            "file url": shot(url="file:///etc/passwd"), "ftp url": shot(url="ftp://x.test/"),
            "credentials": shot(url="https://u:p@x.test/"), "path in name": shot(name="../x"),
            "extension in name": shot(name="x.jpg"),
            "selector and clip": shot(selector="#a", clip={"x": 0, "y": 0, "width": 10, "height": 10}),
            "bad clip": shot(clip={"x": 0, "y": 0, "width": 0, "height": 10}),
            "tiny viewport": shot(viewport={"width": 10, "height": 844}), "dsf": shot(device_scale_factor=5),
            "touch string": shot(touch="yes"), "submit action": shot(actions=[{"submit": "form"}]),
            "type action": shot(actions=[{"type": "#q"}]), "long wait": shot(actions=[{"wait": 60000}]),
            "click plus extra key": shot(actions=[{"click": "#a", "force": True}]),
            "unknown key": shot(script="alert(1)"),
        }
        for label, s in bad.items():
            with self.subTest(label), self.assertRaises(m.Refused):
                m.validate_spec({"shots": [s]})
        for label, sp in {"empty": {"shots": []}, "list": [shot()], "too many": {"shots": [shot(name=f"s{i}") for i in range(13)]},
                          "duplicate": {"shots": [shot(), shot()]}}.items():
            with self.subTest(label), self.assertRaises(m.Refused):
                m.validate_spec(sp)

    def test_urls(self):
        for ok in ("https://example.com/a", "http://127.0.0.1:8000/", "http://localhost/"):
            self.assertIsNone(m.check_url(ok), ok)
        for bad in ("javascript:alert(1)", "data:text/html,x", "https:///x", None):
            self.assertIsNotNone(m.check_url(bad), bad)

    def test_quality_steps_end_at_40(self):
        self.assertEqual(m.quality_steps(72), [72, 64, 56, 48, 40])
        self.assertEqual(m.quality_steps(40), [40])
        self.assertEqual(m.quality_steps(10), [40])
        self.assertEqual(m.quality_steps(100)[-1], 40)

    def test_magic_bytes(self):
        for ext, kind in ((".jpg", "jpeg"), (".png", "png"), (".webp", "webp")):
            self.assertEqual(m.image_kind(MAGIC[ext] + b"0000"), kind)
        self.assertIsNone(m.image_kind(b"hello world, not an image"))
        self.assertIsNone(m.image_kind(b"RIFF\x00\x00\x00\x00WAVE"))


FAKE_DNS = {"public.test": ["93.184.216.34"], "evil.test": ["93.184.216.34", "10.0.0.5"],  # privacy-scan: allow (test data for the address guard)
            "meta.test": ["169.254.169.254"], "v6.test": ["fd00::1"]}  # privacy-scan: allow (test data for the address guard)


def fake_resolver(host):
    return FAKE_DNS.get(host, [])


class Addresses(unittest.TestCase):
    def test_internal_ips(self):
        for ip in ("127.0.0.1", "127.8.9.1", "::1", "10.1.2.3", "172.16.0.1", "172.31.255.255", "192.168.1.1",  # privacy-scan: allow (test data for the address guard)
                   "169.254.169.254", "fc00::1", "fd12::1", "fe80::1", "0.0.0.0", "::ffff:127.0.0.1", "::ffff:10.0.0.1"):  # privacy-scan: allow (test data for the address guard)
            self.assertTrue(m.is_internal_ip(ip), ip)
        for ip in ("93.184.216.34", "172.32.0.1", "8.8.8.8", "2606:4700::1111"):
            self.assertFalse(m.is_internal_ip(ip), ip)

    def test_hostnames_resolve_before_a_decision(self):
        self.assertTrue(m.host_is_internal("localhost", fake_resolver))
        self.assertTrue(m.host_is_internal("app.localhost", fake_resolver))
        self.assertTrue(m.host_is_internal("evil.test", fake_resolver), "any internal answer counts")
        self.assertTrue(m.host_is_internal("meta.test", fake_resolver))
        self.assertTrue(m.host_is_internal("v6.test", fake_resolver))
        self.assertTrue(m.host_is_internal("[::1]", fake_resolver))
        self.assertFalse(m.host_is_internal("public.test", fake_resolver))
        self.assertIsNone(m.host_is_internal("nowhere.test", fake_resolver))

    def test_guard_from_a_public_page(self):
        g = m.RequestGuard("https://public.test/page", fake_resolver)
        self.assertFalse(g.allow_internal)
        self.assertIsNone(g.decide("GET", "https://public.test/a.css"))
        self.assertIsNone(g.decide("GET", "data:image/png;base64,AAAA"))
        for method, url in (("GET", "http://127.0.0.1:9000/admin"), ("GET", "http://169.254.169.254/latest/meta-data/"),  # privacy-scan: allow (test data for the address guard)
                            ("GET", "https://evil.test/"), ("GET", "http://[::1]/"), ("GET", "https://nowhere.test/"),
                            ("POST", "https://public.test/form"), ("GET", "ws://public.test/socket"),
                            ("GET", "file:///etc/passwd")):
            self.assertIsNotNone(g.decide(method, url), url)
        self.assertEqual(len(g.refused), 8)

    def test_guard_from_a_local_dev_server(self):
        g = m.RequestGuard("http://127.0.0.1:8000/", fake_resolver)
        self.assertTrue(g.allow_internal)
        self.assertIsNone(g.decide("GET", "http://localhost:8000/redirected"))
        self.assertIsNotNone(g.decide("POST", "http://127.0.0.1:8000/"))

    def test_a_mixed_answer_does_not_unlock_internal_addresses(self):
        dns = {"mixed.test": ["93.184.216.34", "10.0.0.1"], "dev.test": ["10.0.0.2", "127.0.0.1"]}  # privacy-scan: allow (test data for the address guard)
        g = m.RequestGuard("https://mixed.test/", dns.get)
        self.assertFalse(g.allow_internal, "one public address means the start host is not a local server")
        self.assertIsNotNone(g.decide("GET", "http://10.0.0.1/"))  # privacy-scan: allow (test data for the address guard)
        self.assertIsNotNone(g.decide("GET", "http://169.254.169.254/"))  # privacy-scan: allow (test data for the address guard)
        self.assertTrue(m.RequestGuard("http://dev.test:3000/", dns.get).allow_internal)
        for host in ("localhost", "app.localhost", "127.0.0.1", "[::1]", "192.168.1.5"):  # privacy-scan: allow (test data for the address guard)
            self.assertTrue(m.host_is_local_server(host, dns.get), host)
        for host in ("mixed.test", "nowhere.test", "93.184.216.34"):
            self.assertFalse(m.host_is_local_server(host, dns.get), host)

    def test_hosts_are_re_resolved_on_every_request(self):
        answers = iter([["93.184.216.34"], ["127.0.0.1"]])   # a rebinding resolver: public, then loopback
        calls = []

        def rebinding(host):
            calls.append(host)
            return next(answers) if host == "rebind.test" else ["93.184.216.34"]
        g = m.RequestGuard("https://public.test/", rebinding)
        self.assertIsNone(g.decide("GET", "https://rebind.test/a"))
        self.assertIsNotNone(g.decide("GET", "https://rebind.test/b"), "a cached 'public' would have let this through")
        self.assertEqual(calls.count("rebind.test"), 2)


class FakeResp:
    def __init__(self, status, headers=None):
        self.status, self.headers = status, headers or {}


class FakeRoute:
    """A route whose fetch answers from a small fake site {url: FakeResp}."""

    def __init__(self, method, url, site=None):
        self.request = type("R", (), {"method": method, "url": url})()
        self.site, self.did, self.fulfilled = site or {}, [], None

    def abort(self, *a):
        self.did.append("abort")

    def continue_(self):
        self.did.append("continue")

    def fetch(self, url=None, max_redirects=None):
        assert max_redirects == 0, "redirects must not be followed by fetch"
        self.did.append(f"fetch {url}")
        return self.site[url]

    def fulfill(self, response=None):
        self.did.append("fulfill")
        self.fulfilled = response


def redirect(to, status=302):
    return FakeResp(status, {"location": to})


class Handler(unittest.TestCase):
    def setUp(self):
        self.h = m.make_route_handler(m.RequestGuard("https://public.test/", fake_resolver))

    def test_internal_request_is_aborted_unfetched(self):
        r = FakeRoute("GET", "http://10.0.0.5/")  # privacy-scan: allow (test data for the address guard)
        self.h(r)
        self.assertEqual(r.did, ["abort"])

    def test_chain_into_metadata_is_refused_at_hop_two(self):
        site = {"https://public.test/a": redirect("https://public.test/b"),
                "https://public.test/b": redirect("http://169.254.169.254/latest/meta-data/"),  # privacy-scan: allow (test data for the address guard)
                "http://169.254.169.254/latest/meta-data/": FakeResp(200)}  # privacy-scan: allow (test data for the address guard)
        r = FakeRoute("GET", "https://public.test/a", site)
        self.h(r)
        self.assertEqual(r.did, ["fetch https://public.test/a", "fetch https://public.test/b", "abort"])
        self.assertIsNone(r.fulfilled, "no 3xx and no metadata response reaches the browser")

    def test_a_3xx_is_never_fulfilled(self):
        site = {"https://public.test/a": redirect("https://public.test/b"), "https://public.test/b": FakeResp(200)}
        r = FakeRoute("GET", "https://public.test/a", site)
        self.h(r)
        self.assertEqual(r.did[-1], "fulfill")
        self.assertEqual(r.fulfilled.status, 200)

    def test_trailing_slash_redirect_on_the_same_host_works(self):
        site = {"https://public.test/docs": redirect("/docs/", 301), "https://public.test/docs/": FakeResp(200)}
        r = FakeRoute("GET", "https://public.test/docs", site)
        self.h(r)
        self.assertEqual(r.did, ["fetch https://public.test/docs", "fetch https://public.test/docs/", "fulfill"])

    def test_too_many_hops_are_refused(self):
        site = {f"https://public.test/{i}": redirect(f"/{i + 1}") for i in range(10)}
        r = FakeRoute("GET", "https://public.test/0", site)
        self.h(r)
        self.assertEqual(r.did.count("abort"), 1)
        self.assertEqual(len([d for d in r.did if d.startswith("fetch")]), m.MAX_REDIRECTS + 1)
        self.assertNotIn("fulfill", r.did)

    def test_plain_response_and_post(self):
        r = FakeRoute("GET", "https://public.test/x", {"https://public.test/x": FakeResp(200)})
        self.h(r)
        self.assertEqual(r.did, ["fetch https://public.test/x", "fulfill"])
        r = FakeRoute("POST", "https://public.test/x")
        self.h(r)
        self.assertEqual(r.did, ["abort"])


class Files(Temp):
    def test_good_folder(self):
        d = self.images(["a.jpg", "b.png", "c.webp"])
        (d / "captions.json").write_text(json.dumps({"a.jpg": "A"}), encoding="utf-8")
        files, caps = m.check_publish_dir(d)
        self.assertEqual(([f.name for f in files], caps), (["a.jpg", "b.png", "c.webp"], {"a.jpg": "A"}))

    def test_text_files_with_image_names_are_refused(self):
        for name in ("x.jpg", "x.png", "x.webp"):
            with self.subTest(name):
                shutil.rmtree(self.tmp / "shots", ignore_errors=True)
                d = self.tmp / "shots"
                d.mkdir()
                (d / name).write_text("this is text, not an image", encoding="utf-8")
                with self.assertRaises(m.Refused) as cm:
                    m.check_publish_dir(d)
                self.assertIn("not an image", str(cm.exception))
        shutil.rmtree(self.tmp / "shots")
        d = self.tmp / "shots"
        d.mkdir()
        (d / "y.png").write_bytes(MAGIC[".jpg"] + b"0" * 10)
        with self.assertRaises(m.Refused):
            m.check_publish_dir(d)

    def test_refusals(self):
        cases = {"other type": ["a.svg"], "two extensions": ["a.b.jpg"], "hidden": [".a.jpg"],
                 "too many": [f"s{i}.jpg" for i in range(13)]}
        for label, names in cases.items():
            with self.subTest(label):
                shutil.rmtree(self.tmp / "shots", ignore_errors=True)
                with self.assertRaises(m.Refused):
                    m.check_publish_dir(self.images(names))

    def test_size_cap(self):
        with self.assertRaises(m.Refused) as cm:
            m.check_publish_dir(self.images(["big.jpg"], size=401 * 1024))
        self.assertIn("400 KB", str(cm.exception))
        shutil.rmtree(self.tmp / "shots")
        m.check_publish_dir(self.images(["ok.jpg"], size=399 * 1024))

    def test_subfolder_and_bad_captions(self):
        d = self.images(["a.jpg"])
        (d / "sub").mkdir()
        with self.assertRaises(m.Refused):
            m.check_publish_dir(d)
        (d / "sub").rmdir()
        (d / "captions.json").write_text("[1]", encoding="utf-8")
        with self.assertRaises(m.Refused):
            m.check_publish_dir(d)

    def test_names(self):
        for bad in ("a/b.jpg", "a\\b.jpg", "..", "a..jpg", ".jpg", "", "a b.jpg"):
            self.assertIsNotNone(m.check_name(bad), bad)


class Branches(unittest.TestCase):
    def test_only_evidence_branch_names(self):
        for ok in ("pr-evidence", "pr-evidence-x", "pr-evidence-v1.2", "pr-evidence-site_a"):
            self.assertIsNone(m.check_branch(ok, "main"), ok)
            self.assertIsNone(m.check_branch(ok, None), ok)
        for bad in ("main", "master", "Main", "trunk", "evidence", "pr-evidencex", "pr-evidence-", "pr-evidence-X",
                    "pr-evidence/x", "pr-evidence-a..b", "pr-evidence-x.lock", "-f", "+pr-evidence", ":x", ""):
            self.assertIsNotNone(m.check_branch(bad), bad)
            self.assertIsNotNone(m.check_branch(bad, None), f"{bad} with an unknown default branch")

    def test_default_branch_is_an_extra_guard(self):
        self.assertIn("default branch", m.check_branch("pr-evidence", "pr-evidence"))

    def test_push_is_plain_and_single_branch(self):
        cmd = m.push_command("pr-evidence")
        self.assertEqual(cmd, ["git", "push", "origin", "refs/heads/pr-evidence:refs/heads/pr-evidence"])
        for word in ("--force", "-f", "--force-with-lease", "--delete", "--mirror", "--all", "--tags", "--prune"):
            self.assertNotIn(word, cmd)
        self.assertFalse(any(part.startswith("+") or part.startswith(":") for part in cmd))
        with self.assertRaises(m.Refused):
            m.push_command("main")

    def test_parse_repo(self):
        for url in ("https://github.com/o/r.git", "https://github.com/o/r", "git@github.com:o/r.git", "ssh://git@github.com/o/r.git"):
            self.assertEqual(m.parse_repo(url), "o/r", url)
        for url in ("https://gitlab.com/o/r.git", "https://github.com/o", "C:/x/repo", ""):
            self.assertIsNone(m.parse_repo(url), url)

    def test_evidence_tree(self):
        good = [("100644", "blob", "pr-5/a.jpg"), ("100644", "blob", "pr-12/b.webp")]
        self.assertEqual(m.check_evidence_tree(good), [])
        for entry in (("100644", "blob", "README"), ("120000", "blob", "pr-5/a.jpg"), ("160000", "commit", "pr-5/sub"),
                      ("100644", "blob", "pr-5/x/a.jpg"), ("100644", "blob", "pr-5/run.sh"), ("100644", "blob", "pr-0/a.jpg"),
                      ("100644", "blob", ".github/workflows/x.yml")):
            self.assertTrue(m.check_evidence_tree(good + [entry]), entry)


class Markdown(unittest.TestCase):
    def test_comment(self):
        md = m.build_comment("o/r", "pr-evidence", 12, ["desk.jpg", "phone.jpg"], {"phone.jpg": "Card <b>[x]</b>"})
        self.assertIn("![Card \\<b\\>\\[x\\]\\</b\\>](https://github.com/o/r/blob/pr-evidence/pr-12/phone.jpg?raw=true)", md)
        self.assertIn("![desk](https://github.com/o/r/blob/pr-evidence/pr-12/desk.jpg?raw=true)", md)
        self.assertIn("2 small screenshots", md)

    def test_entities_cannot_rebuild_a_mention_or_reference(self):
        for cap, word in (("&#64;alice", "alice"), ("&#35;123", "123"), ("&#x40;bob", "bob"), ("&commat;carol", "carol"),
                          ("&num;7", "7"), ("&amp;#64;dave", "dave")):
            out = m.clean_caption(cap)
            self.assertNotRegex(out, r"&(?!amp;)", f"{cap!r} left an entity a renderer would decode: {out!r}")
            self.assertTrue(out.startswith("&amp;"), out)
            self.assertIn(word, out)
            md = m.build_comment("o/r", "pr-evidence", 3, ["a.jpg"], {"a.jpg": cap})
            self.assertNotRegex(md, r"&(?!amp;)", md)

    def test_mentions_references_and_urls_are_neutralised(self):
        cap = "ping @alice and @org/team, see #123, o/r#9, GH-4, https://evil.test/x and www.evil.test"
        out = m.clean_caption(cap)
        for raw in ("@alice", "@org", "#123", "#9", "GH-4", "https://", "www.evil"):
            self.assertNotIn(raw, out, raw)
        for kept in ("@\u200balice", "#\u200b123", "https\u200b://", "www\u200b.evil"):
            self.assertIn(kept, out, kept)
        md = m.build_comment("o/r", "pr-evidence", 3, ["a.jpg"], {"a.jpg": cap})
        self.assertNotIn("@alice", md)
        self.assertIn("(https://github.com/o/r/blob/pr-evidence/pr-3/a.jpg?raw=true)", md, "the image URL itself stays")

    def test_commit_message_trailers(self):
        self.assertEqual(m.commit_message(3, []), "Screenshots for pull request #3\n")
        self.assertTrue(m.commit_message(3, ["Co-Authored-By: A <a@x>"]).endswith("\n\nCo-Authored-By: A <a@x>\n"))
        with self.assertRaises(m.Refused):
            m.commit_message(3, ["a\nb"])


class Publish(Temp):
    def caller(self, origin="https://github.com/example/demo.git", name="caller", identity=True):
        repo = self.tmp / name
        git(["init", "-q", str(repo)], self.tmp)
        if origin:
            git(["remote", "add", "origin", origin], repo)
        if identity:
            git(["config", "user.name", WHO[0]], repo)
            git(["config", "user.email", WHO[1]], repo)
        return repo

    def test_dry_run_prints_and_changes_nothing(self):
        d = self.images(["a.jpg"])
        repo = self.caller()
        before = git(["status", "--porcelain", "--ignored"], repo) + git(["branch", "--list"], repo)
        rc, out = run(["publish", "--dir", str(d), "--pr", "4"], repo)
        self.assertEqual(rc, 0, out)
        for want in ("Repository: example/demo", "Branch:     pr-evidence", "pr-4/a.jpg", "DRY RUN",
                     "https://github.com/example/demo/blob/pr-evidence/pr-4/a.jpg?raw=true", "may be public",
                     f"Identity:   {WHO[0]} <{WHO[1]}>", "hooks, templates and system config disabled"):
            self.assertIn(want, out)
        self.assertEqual(before, git(["status", "--porcelain", "--ignored"], repo) + git(["branch", "--list"], repo))

    def test_argument_refusals(self):
        d = self.images(["a.jpg"])
        repo = self.caller()
        for args, why in ((["--comment"], "--allow-comment-only"), (["--branch", "main"], "not allowed"),
                          (["--branch", "screens"], "not allowed"),
                          (["--repo", "not a repo"], "OWNER/REPO"), (["--pr", "0"], "positive")):
            rc, out = run(["publish", "--dir", str(d), "--pr", "4", *args], repo)
            self.assertEqual(rc, 2, out)
            self.assertIn(why, out)
        rc, out = run(["publish", "--dir", str(d), "--pr", "4"], self.caller(origin=None, name="no-origin"))
        self.assertEqual(rc, 2, out)
        self.assertIn("--repo OWNER/REPO", out)

    def test_local_default_branch_is_refused(self):
        d = self.images(["a.jpg"])
        repo = self.caller()
        (repo / "f").write_text("x", encoding="utf-8")
        git(["add", "f"], repo)
        git(["commit", "-q", "-m", "x"], repo)
        git(["update-ref", "refs/remotes/origin/pr-evidence-x", "HEAD"], repo)
        git(["symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/pr-evidence-x"], repo)
        rc, out = run(["publish", "--dir", str(d), "--pr", "4", "--branch", "pr-evidence-x"], repo)
        self.assertEqual(rc, 2, out)
        self.assertIn("default branch", out)
        rc, out = run(["publish", "--dir", str(d), "--pr", "4", "--branch", "pr-evidence"], repo)
        self.assertEqual(rc, 0, out)

    def test_push_to_a_local_bare_repo(self):
        bare = self.bare()
        main_before = git(["rev-parse", "main"], bare).strip()
        first = self.images(["a.jpg"])
        m.push_evidence(str(bare), "pr-evidence", 5, sorted(first.iterdir()), ["Trailer-One: x"], WHO)
        self.assertEqual(git(["ls-tree", "-r", "--name-only", "pr-evidence"], bare).split(), ["pr-5/a.jpg"])
        self.assertIn("Trailer-One: x", git(["log", "-1", "--format=%B", "pr-evidence"], bare))
        self.assertEqual(git(["log", "-1", "--format=%an <%ae>", "pr-evidence"], bare).strip(), f"{WHO[0]} <{WHO[1]}>")
        self.assertEqual(git(["rev-list", "--count", "pr-evidence"], bare).strip(), "1", "a new evidence branch is an orphan")

        shutil.rmtree(first)
        second = self.images(["b.jpg"])
        m.push_evidence(str(bare), "pr-evidence", 6, sorted(second.iterdir()), [], WHO)
        self.assertEqual(git(["ls-tree", "-r", "--name-only", "pr-evidence"], bare).split(), ["pr-5/a.jpg", "pr-6/b.jpg"])
        tip = git(["rev-parse", "pr-evidence"], bare).strip()
        m.push_evidence(str(bare), "pr-evidence", 6, sorted(second.iterdir()), [], WHO)
        self.assertEqual(git(["rev-parse", "pr-evidence"], bare).strip(), tip, "no change, no commit")
        self.assertEqual(git(["rev-parse", "main"], bare).strip(), main_before, "main is never touched")
        self.assertEqual(sorted(git(["for-each-ref", "--format=%(refname)"], bare).split()),
                         ["refs/heads/main", "refs/heads/pr-evidence"])
        for name in ("main", "screens"):
            with self.assertRaises(m.Refused):
                m.push_evidence(str(bare), name, 6, sorted(second.iterdir()), [], WHO)
        with self.assertRaises(m.Refused):
            m.push_evidence(str(bare), "pr-evidence", 6, sorted(second.iterdir()), [], None)

    def test_an_unknown_default_branch_does_not_loosen_the_name_rule(self):
        empty = self.tmp / "empty.git"
        git(["init", "-q", "--bare", str(empty)], self.tmp)
        self.assertIsNone(m.remote_default_branch(str(empty)))
        for name in ("main", "master", "release"):
            with self.assertRaises(m.Refused):
                m.push_evidence(str(empty), name, 1, sorted(self.images(["a.jpg"]).iterdir()), [], WHO)
        self.assertEqual(git(["for-each-ref"], empty).strip(), "")

    def test_push_refuses_the_remote_default_branch(self):
        bare = self.bare(default="pr-evidence-x")
        with self.assertRaises(m.Refused):
            m.push_evidence(str(bare), "pr-evidence-x", 1, sorted(self.images(["a.jpg"]).iterdir()), [], WHO)

    def test_a_branch_holding_more_than_images_is_refused(self):
        bare = self.bare({"README.md": b"hello", "pr-1/link.jpg": "SYMLINK"}, evidence="pr-evidence-x")
        tip = git(["rev-parse", "pr-evidence-x"], bare).strip()
        with self.assertRaises(m.Refused) as cm:
            m.push_evidence(str(bare), "pr-evidence-x", 2, sorted(self.images(["a.jpg"]).iterdir()), [], WHO)
        self.assertIn("README.md", str(cm.exception))
        self.assertIn("120000", str(cm.exception))
        self.assertEqual(git(["rev-parse", "pr-evidence-x"], bare).strip(), tip, "nothing was pushed")

    def test_at_most_twelve_files_per_pr_folder_in_total(self):
        seeded = {f"pr-3/old{i}.jpg": MAGIC[".jpg"] + b"0" for i in range(11)}
        bare = self.bare(seeded)
        with self.assertRaises(m.Refused) as cm:
            m.push_evidence(str(bare), "pr-evidence", 3, sorted(self.images(["n1.jpg", "n2.jpg"]).iterdir()), [], WHO)
        self.assertIn("13 files", str(cm.exception))
        shutil.rmtree(self.tmp / "shots")
        m.push_evidence(str(bare), "pr-evidence", 3, sorted(self.images(["old0.jpg", "n1.jpg"]).iterdir()), [], WHO)
        self.assertEqual(len([p for p in git(["ls-tree", "-r", "--name-only", "pr-evidence"], bare).split()
                              if p.startswith("pr-3/")]), 12)
        m.push_evidence(str(bare), "pr-evidence", 4, sorted(self.images(["n2.jpg"], folder="more").iterdir()), [], WHO)

    def test_caller_hooks_and_templates_do_not_run(self):
        marker = self.tmp / "hook-ran.txt"
        hooks = self.tmp / "evil-hooks"
        hooks.mkdir()
        tmpl = self.tmp / "tmpl"
        (tmpl / "hooks").mkdir(parents=True)
        body = f"#!/bin/sh\necho ran >> '{marker.as_posix()}'\nexit 1\n"
        for d in (hooks, tmpl / "hooks"):
            for h in ("pre-commit", "commit-msg", "post-checkout", "pre-push"):
                (d / h).write_text(body, encoding="utf-8", newline="\n")
                os.chmod(d / h, 0o700)
        cfg = self.tmp / "global.gitconfig"
        cfg.write_text(f"[core]\n\thooksPath = {hooks.as_posix()}\n[init]\n\ttemplateDir = {tmpl.as_posix()}\n", encoding="utf-8")
        bare = self.bare({"pr-1/a.jpg": MAGIC[".jpg"] + b"0"})
        old = os.environ.get("GIT_CONFIG_GLOBAL")
        os.environ["GIT_CONFIG_GLOBAL"] = str(cfg)
        try:
            m.push_evidence(str(bare), "pr-evidence", 2, sorted(self.images(["b.jpg"]).iterdir()), [], WHO)
        finally:
            if old is None:
                os.environ.pop("GIT_CONFIG_GLOBAL", None)
            else:
                os.environ["GIT_CONFIG_GLOBAL"] = old
        self.assertFalse(marker.exists(), "a caller hook ran in the temporary repository")
        self.assertIn("pr-2/b.jpg", git(["ls-tree", "-r", "--name-only", "pr-evidence"], bare))

    def test_an_exported_git_dir_does_not_redirect_the_push(self):
        other = self.tmp / "unrelated"
        git(["init", "-q", "-b", "work", str(other)], self.tmp)
        (other / "keep.txt").write_text("mine", encoding="utf-8")
        git(["add", "keep.txt"], other)
        git(["commit", "-q", "-m", "unrelated"], other)
        git(["checkout", "-q", "-b", "pr-evidence"], other)   # a same-named branch the push must not touch

        def snapshot():
            idx = (other / ".git" / "index").read_bytes()
            return (git(["symbolic-ref", "HEAD"], other), git(["for-each-ref"], other),
                    git(["status", "--porcelain", "--untracked-files=all"], other), idx,
                    git(["count-objects", "-v"], other))
        before = snapshot()
        bare = self.bare()
        hostile = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
                   "GIT_INDEX_FILE": str(other / ".git" / "index"), "GIT_OBJECT_DIRECTORY": str(other / ".git" / "objects"),
                   "GIT_COMMON_DIR": str(other / ".git"), "GIT_NAMESPACE": "hijack"}
        from unittest import mock
        with mock.patch.dict(os.environ, hostile):
            m.push_evidence(str(bare), "pr-evidence", 9, sorted(self.images(["z.jpg"]).iterdir()), [], WHO)
        self.assertEqual(snapshot(), before, "the unrelated repository changed")
        self.assertEqual(git(["ls-tree", "-r", "--name-only", "pr-evidence"], bare).split(), ["pr-9/z.jpg"])
        self.assertNotIn("hijack", git(["for-each-ref"], bare))


class DatedFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="shots test "))
        self.lab = self.tmp / "cf-lab-files"
        self.lab.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def where(self, *args, lab=None):
        env = {**ENV, "LAB_FILES": str(lab if lab is not None else self.lab)}
        p = subprocess.run([sys.executable, str(SCRIPT), "where", *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60, stdin=subprocess.DEVNULL, env=env)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def test_where_creates_the_dated_topic_folder(self):
        code, out, err = self.where("site-pass", "--date", "2026-10-11")
        self.assertEqual(code, 0, err)
        want = self.lab / "scratch" / "screenshots" / "2026-10-11" / "site-pass"
        self.assertEqual(Path(out), want)
        self.assertTrue(want.is_dir())

    def test_the_default_date_is_today(self):
        import datetime
        code, out, err = self.where("t")
        self.assertEqual(code, 0, err)
        self.assertEqual(Path(out).parent.name, datetime.date.today().isoformat())

    def test_a_bad_topic_or_date_is_refused(self):
        for args in (["../x"], ["a/b"], ["a b"], [""], ["t", "--date", "11-10-2026"], ["t", "--date", "2026-10-11/.."]):
            code, out, err = self.where(*args)
            self.assertEqual(code, 2, (args, out, err))
        self.assertFalse((self.lab / "scratch").exists(), "nothing is created on a refusal")

    def test_a_missing_lab_folder_is_refused(self):
        code, out, err = self.where("t", lab=self.tmp / "nope")
        self.assertEqual(code, 2, err)
        self.assertIn("not a folder", err)

    def test_capture_needs_out_or_topic_but_not_both(self):
        spec = self.tmp / "spec.json"
        spec.write_text(json.dumps({"shots": [shot()]}), encoding="utf-8")
        for extra in ([], ["--out", str(self.tmp / "o"), "--topic", "t"]):
            p = subprocess.run([sys.executable, str(SCRIPT), "capture", str(spec), *extra], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL, env=ENV)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=1).result
    ok = result.wasSuccessful()
    print("VERIFIED" if ok else f"{len(result.failures) + len(result.errors)} failure(s)")
    sys.exit(0 if ok else 1)

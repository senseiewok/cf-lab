#!/usr/bin/env python3
"""Small screenshots for a pull request: capture them from a spec, then publish them to an evidence branch.

Usage:
    pr-screenshots.py capture SPEC.json --out DIR [--quality 72] [--max-kb 150] [--channel msedge|chrome]
    pr-screenshots.py publish --dir DIR --pr N [--repo OWNER/REPO] [--branch pr-evidence]
                              [--push] [--trailer LINE ...] [--comment] [--allow-comment-only]
    pr-screenshots.py --self-test [--channel msedge|chrome]

capture: SPEC.json is {"shots": [...]}; each shot has name, url, viewport {width, height}, optional
touch (bool), device_scale_factor, one of selector | clip {x, y, width, height} (neither means the
viewport), scroll_to (selector), actions (click SELECTOR | set_value SELECTOR + value | wait MS) and
caption. It writes NAME.jpg files and captions.json into DIR. Each JPEG is re-captured at a lower
quality, down to 40, until it is under --max-kb. Only http and https URLs; requests other than GET
and HEAD and all WebSockets are blocked; requests and redirects into loopback, private or link-local
addresses are blocked unless the shot's own URL is such an address (a local dev server); form submits
are cancelled; a click on a submit control, or a visible password field in any frame on load or after
the actions, is refused. Screenshots can hold personal data: capture only what may be public.

publish: a DRY RUN unless --push. It prints the files, the repo, the branch, the folder pr-N/, the git
identity and the exact comment markdown, and changes nothing. Files must be real JPEG, PNG or WEBP
images. The branch must be pr-evidence or pr-evidence-<suffix>. --push works in a temporary git
repository (never the caller's working tree; hooks, templates and system config off; the caller's
user.name and user.email passed in): it fetches the evidence branch if it exists and refuses it unless
it holds only images under pr-<number>/, else starts an orphan branch; adds the images under pr-N/ (at
most 12 there in all), commits (the message ends with each --trailer given; none by default) and does
a plain, non-force push of that one branch. --comment posts the markdown with `gh pr comment`.

Exit codes: 0 done, 1 capture or publish failed, 2 refused (bad spec, file, branch or arguments),
4 self-test failed. Standard library only; capture needs Playwright for Python and a browser
(setup-browser-testing.py beside this file installs both after asking).
"""

from __future__ import annotations

import argparse
import http.server
import json
import ipaddress
import os
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_FILE_KB = 400
MAX_FILES = 12            # per pr-<N>/ folder, existing files included
MAX_ACTIONS = 10
MAX_WAIT_MS = 5000
MIN_QUALITY = 40
PROTECTED_BRANCHES = ("main", "master")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(\.[A-Za-z0-9]+)?$")
EVIDENCE_BRANCH_RE = re.compile(r"^pr-evidence(-[a-z0-9._-]+)?$")   # the only branches this script writes
TREE_PATH_RE = re.compile(r"^pr-[1-9][0-9]{0,6}/([^/]+)$")
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$")
PUBLIC_REMINDER = "Reminder: if {repo} is public, these images are public too; capture only content that may be public."


class Refused(Exception):
    """A spec, file, branch or argument this script will not act on (exit 2)."""


# ---------- pure checks (unit-tested without a browser or network) ----------

def is_internal_ip(text: str) -> bool:
    """Loopback, private, link-local (cloud metadata included), unique-local, unspecified or reserved."""
    try:
        ip = ipaddress.ip_address(text.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified or ip.is_reserved
            or ip.is_multicast or ip in ipaddress.ip_network("fc00::/7"))


def resolve_host(host: str) -> list[str]:
    """Addresses a hostname resolves to (empty when it does not resolve)."""
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})
    except (OSError, UnicodeError):
        return []


def host_is_internal(host: str, resolver=resolve_host) -> bool | None:
    """True if the host is or resolves to an internal address, False if public, None if it does not resolve."""
    host = (host or "").strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
        return is_internal_ip(host)
    except ValueError:
        pass
    addrs = resolver(host)
    if not addrs:
        return None
    return any(is_internal_ip(a) for a in addrs)


def host_is_local_server(host: str, resolver=resolve_host) -> bool:
    """Whether a shot's start host is a local dev server: localhost or *.localhost, a literal loopback or
    private IP, or a name whose resolved addresses are ALL internal (one public answer is not enough)."""
    host = (host or "").strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return ip.is_loopback or ip.is_private
    except ValueError:
        pass
    addrs = resolver(host)
    return bool(addrs) and all(is_internal_ip(a) for a in addrs)


class RequestGuard:
    """Decides each browser request. Internal addresses are allowed only when the shot's own URL is a local dev
    server; otherwise a request or redirect into loopback, private or metadata space is refused.

    Limitation: every request re-resolves its host (nothing is cached), but the browser resolves again when it
    connects, so DNS rebinding between this check and the connection is not fully closed. Capture is meant for
    pages you may publish, not for hostile sites."""

    def __init__(self, start_url: str, resolver=resolve_host):
        self.resolver = resolver
        self.allow_internal = host_is_local_server(urlparse(start_url).hostname or "", resolver)
        self.refused: list[str] = []

    def internal(self, host: str) -> bool | None:
        return host_is_internal(host, self.resolver)   # not cached: re-resolved per request

    def decide(self, method: str, url: str) -> str | None:
        p = urlparse(url)
        if p.scheme in ("data", "blob"):
            return None
        reason = None
        if method not in ("GET", "HEAD"):
            reason = f"{method} request blocked"
        elif p.scheme not in ("http", "https"):
            reason = f"scheme {p.scheme!r} blocked"
        elif not self.allow_internal:
            where = self.internal(p.hostname or "")
            if where is None:
                reason = f"host {p.hostname!r} does not resolve"
            elif where:
                reason = f"host {p.hostname!r} is a loopback, private or link-local address"
        if reason:
            self.refused.append(f"{reason}: {url[:120]}")
        return reason


def image_kind(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


EXT_KIND = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}


def check_evidence_tree(entries: list[tuple[str, str, str]]) -> list[str]:
    """entries are (mode, type, path) from `git ls-tree -r`. Every one must be a regular image file under pr-N/."""
    problems = []
    for mode, typ, path in entries:
        m = TREE_PATH_RE.match(path)
        if typ != "blob" or mode not in ("100644", "100755"):
            problems.append(f"{path}: not a regular file (mode {mode}, {typ})")
        elif not m or check_name(m.group(1)) or Path(m.group(1)).suffix.lower() not in IMAGE_EXTS:
            problems.append(f"{path}: not an image under pr-<number>/")
    return problems

def check_url(url: str) -> str | None:
    """Return a reason to refuse the URL, or None."""
    if not isinstance(url, str):
        return "url must be a string"
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return f"scheme {p.scheme or '(none)'!r} not allowed; only http and https"
    if p.username or p.password:
        return "credentials in a URL are not allowed"
    return None


def check_name(name: str) -> str | None:
    """A file or shot name: one segment, no separators, no dot segments, no leading dot."""
    if not isinstance(name, str) or not name:
        return "name must be a non-empty string"
    if "/" in name or "\\" in name or ".." in name or len(name) > 80 or not NAME_RE.match(name):
        return f"name {name!r} must be letters, digits, '-' or '_' (plus one extension), with no path"
    return None


def _int_in(v, lo: int, hi: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def validate_spec(spec) -> list[dict]:
    """Return the normalised shot list, or raise Refused naming every problem."""
    shots = spec.get("shots") if isinstance(spec, dict) else None
    if not isinstance(shots, list) or not shots:
        raise Refused('spec must be an object with a non-empty "shots" list')
    if len(shots) > MAX_FILES:
        raise Refused(f"at most {MAX_FILES} shots")
    problems, out, seen = [], [], set()
    allowed = {"name", "url", "viewport", "touch", "device_scale_factor", "selector", "clip",
               "scroll_to", "actions", "caption"}
    for i, s in enumerate(shots):
        where = f"shot {i + 1}"
        if not isinstance(s, dict):
            problems.append(f"{where}: must be an object")
            continue
        extra = sorted(set(s) - allowed)
        if extra:
            problems.append(f"{where}: unknown keys {extra}")
        name = s.get("name")
        if (r := check_name(name)) or "." in str(name):
            problems.append(f"{where}: {r or 'name takes no extension'}")
        elif name in seen:
            problems.append(f"{where}: duplicate name {name!r}")
        seen.add(name)
        if r := check_url(s.get("url")):
            problems.append(f"{where}: {r}")
        vp = s.get("viewport")
        if not (isinstance(vp, dict) and _int_in(vp.get("width"), 200, 3840) and _int_in(vp.get("height"), 200, 4000)):
            problems.append(f"{where}: viewport needs integer width 200-3840 and height 200-4000")
        if not isinstance(s.get("touch", False), bool):
            problems.append(f"{where}: touch must be true or false")
        dsf = s.get("device_scale_factor", 1)
        if isinstance(dsf, bool) or not isinstance(dsf, (int, float)) or not 1 <= dsf <= 3:
            problems.append(f"{where}: device_scale_factor must be 1 to 3")
        if "selector" in s and "clip" in s:
            problems.append(f"{where}: give selector or clip, not both")
        for key in ("selector", "scroll_to"):
            if key in s and not (isinstance(s[key], str) and s[key].strip()):
                problems.append(f"{where}: {key} must be a non-empty string")
        if "clip" in s:
            c = s["clip"]
            if not (isinstance(c, dict) and all(_int_in(c.get(k), 0, 20000) for k in ("x", "y"))
                    and all(_int_in(c.get(k), 1, 4000) for k in ("width", "height"))):
                problems.append(f"{where}: clip needs integer x, y, width and height")
        actions = s.get("actions", [])
        if not isinstance(actions, list) or len(actions) > MAX_ACTIONS:
            problems.append(f"{where}: actions must be a list of at most {MAX_ACTIONS}")
            actions = []
        for j, a in enumerate(actions):
            if r := check_action(a):
                problems.append(f"{where} action {j + 1}: {r}")
        if not isinstance(s.get("caption", ""), str) or len(s.get("caption", "")) > 200:
            problems.append(f"{where}: caption must be text of at most 200 characters")
        out.append({**s, "touch": s.get("touch", False), "device_scale_factor": dsf,
                    "actions": actions, "caption": s.get("caption", "")})
    if problems:
        raise Refused("; ".join(problems))
    return out


def check_action(a) -> str | None:
    if not isinstance(a, dict):
        return "must be an object"
    if set(a) == {"click"} and isinstance(a["click"], str) and a["click"].strip():
        return None
    if set(a) == {"set_value", "value"} and isinstance(a["set_value"], str) and a["set_value"].strip() \
            and isinstance(a["value"], str) and len(a["value"]) <= 200:
        return None
    if set(a) == {"wait"} and _int_in(a["wait"], 0, MAX_WAIT_MS):
        return None
    return f"allowed actions are {{click: SEL}}, {{set_value: SEL, value: TEXT}} and {{wait: 0-{MAX_WAIT_MS}}}; got {sorted(a)}"


def quality_steps(start: int, floor: int = MIN_QUALITY, step: int = 8) -> list[int]:
    """Qualities to try, from start down to floor: 72 -> [72, 64, 56, 48, 40]."""
    start = max(floor, min(100, start))
    steps = list(range(start, floor, -step))
    return steps + [floor] if not steps or steps[-1] != floor else steps


def is_jpeg(data: bytes) -> bool:
    return image_kind(data) == "jpeg"


def check_publish_dir(folder: Path) -> tuple[list[Path], dict]:
    """Return (image files sorted by name, captions) or raise Refused naming every problem."""
    if not folder.is_dir():
        raise Refused(f"{folder} is not a folder")
    problems, files, captions = [], [], {}
    for p in sorted(folder.iterdir(), key=lambda x: x.name):
        if p.name == "captions.json":
            try:
                captions = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                problems.append(f"captions.json does not parse: {exc}")
                continue
            if not (isinstance(captions, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in captions.items())):
                problems.append("captions.json must map file names to text")
                captions = {}
            continue
        if p.is_symlink() or not p.is_file():
            problems.append(f"{p.name}: not a plain file")
            continue
        if r := check_name(p.name):
            problems.append(f"{p.name}: {r}")
            continue
        if p.suffix.lower() not in IMAGE_EXTS:
            problems.append(f"{p.name}: only {', '.join(IMAGE_EXTS)} files")
            continue
        kb = p.stat().st_size / 1024
        if kb > MAX_FILE_KB:
            problems.append(f"{p.name}: {kb:.0f} KB is over the {MAX_FILE_KB} KB cap")
            continue
        with p.open("rb") as fh:
            kind = image_kind(fh.read(12))
        if kind != EXT_KIND[p.suffix.lower()]:
            problems.append(f"{p.name}: the content is {kind or 'not an image'}, not what the extension says")
            continue
        files.append(p)
    if not files and not problems:
        problems.append("no images to publish")
    if len(files) > MAX_FILES:
        problems.append(f"{len(files)} images; at most {MAX_FILES}")
    if problems:
        raise Refused("; ".join(problems))
    return files, captions


def parse_repo(remote_url: str) -> str | None:
    """OWNER/REPO from a GitHub https or ssh remote URL, else None."""
    u = remote_url.strip()
    m = re.match(r"^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+?)(?:\.git)?/?$", u)
    return m.group(1) if m and REPO_RE.match(m.group(1)) else None


def check_branch(branch: str, default_branch: str | None = None) -> str | None:
    """Only pr-evidence or pr-evidence-<suffix>; main, master and the default branch are refused as extra guards."""
    if not isinstance(branch, str) or not EVIDENCE_BRANCH_RE.match(branch) or ".." in branch \
            or branch.endswith((".lock", ".")) or len(branch) > 100:
        return f"branch {branch!r} is not allowed: the evidence branch must be pr-evidence or pr-evidence-<lowercase suffix>"
    if branch.lower() in PROTECTED_BRANCHES or (default_branch and branch == default_branch):
        return f"refusing to publish to {branch!r}: it is main, master or the default branch"
    return None


def image_url(repo: str, branch: str, pr: int, name: str) -> str:
    return f"https://github.com/{repo}/blob/{branch}/pr-{pr}/{name}?raw=true"


ZWSP = "​"


def clean_caption(text: str) -> str:
    """One line of caption text that cannot mention, link, reference an issue or inject markup."""
    text = " ".join(str(text).split())[:200]
    text = text.replace("&", "&amp;")       # first: '&#64;alice' and '&#35;123' must stay literal text
    text = re.sub(r"([\\\[\]<>*_`|!~])", r"\\\1", text)
    text = re.sub(r"@(?=\w)", "@" + ZWSP, text)                       # @user, @org/team
    text = re.sub(r"#(?=\d)", "#" + ZWSP, text)                        # #123, owner/repo#123
    text = re.sub(r"(?i)\b(GH)-(?=\d)", r"\1" + ZWSP + "-", text)      # GH-123
    text = re.sub(r"(?i):(?=//)", ZWSP + ":", text)                    # scheme://
    text = re.sub(r"(?i)\bwww\.", "www" + ZWSP + ".", text)            # www.example
    return text


def build_comment(repo: str, branch: str, pr: int, names: list[str], captions: dict) -> str:
    lines = ["### Screenshots", "",
             f"{len(names)} small screenshot{'s' if len(names) != 1 else ''}, stored on the `{branch}` branch under `pr-{pr}/`.", ""]
    for n in names:
        cap = clean_caption(captions.get(n, "")) or clean_caption(Path(n).stem)
        lines += [f"**{cap}**", "", f"![{cap}]({image_url(repo, branch, pr, n)})", ""]
    return "\n".join(lines).rstrip() + "\n"


def push_command(branch: str) -> list[str]:
    """The only push this script runs: one branch, same name, no force, no delete."""
    if r := check_branch(branch):
        raise Refused(r)
    return ["git", "push", "origin", f"refs/heads/{branch}:refs/heads/{branch}"]


def commit_message(pr: int, trailers: list[str]) -> str:
    msg = f"Screenshots for pull request #{pr}"
    clean = [t.strip() for t in trailers if t and t.strip()]
    if any("\n" in t or "\r" in t for t in clean):
        raise Refused("a --trailer must be one line")
    return msg + ("\n\n" + "\n".join(clean) if clean else "") + "\n"


# ---------- git and gh (thin wrappers) ----------

def git(args: list[str], cwd: Path | str, check: bool = True, pre: list[str] | None = None,
        env: dict | None = None) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", *(pre or []), *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", stdin=subprocess.DEVNULL, env=env)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {(p.stderr or p.stdout).strip()[:300]}")
    return p


def caller_identity(cwd: Path | str = ".") -> tuple[str, str] | None:
    """user.name and user.email as the caller's git config gives them here, or None."""
    name = git(["config", "user.name"], cwd, check=False).stdout.strip()
    email = git(["config", "user.email"], cwd, check=False).stdout.strip()
    return (name, email) if name and email and "\n" not in name + email else None


def isolation_args(hooks_dir: Path, identity: tuple[str, str]) -> list[str]:
    """`-c` options for every git call in the temporary repository: no hooks, no templates, no symlinks
    checked out, and the caller's identity passed explicitly. Commit signing follows the caller's config."""
    return ["-c", f"core.hooksPath={hooks_dir}", "-c", "init.templateDir=", "-c", "core.symlinks=false",
            "-c", f"user.name={identity[0]}", "-c", f"user.email={identity[1]}"]


def origin_url(cwd: Path | str = ".") -> str | None:
    p = git(["remote", "get-url", "origin"], cwd, check=False)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None


def local_default_branch(cwd: Path | str = ".") -> str | None:
    """The default branch as this clone last saw it (refs/remotes/origin/HEAD), without the network."""
    p = git(["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"], cwd, check=False)
    ref = p.stdout.strip()
    return ref.split("/", 1)[1] if p.returncode == 0 and "/" in ref else None


REPO_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                      "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE")


def isolated_env() -> dict:
    """The environment for git in the temporary repository: no inherited repository location, no system config."""
    env = {k: v for k, v in os.environ.items() if k.upper() not in REPO_LOCATION_VARS}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def remote_default_branch(remote: str) -> str | None:
    p = git(["ls-remote", "--symref", remote, "HEAD"], tempfile.gettempdir(), check=False, env=isolated_env())
    m = re.search(r"^ref: refs/heads/(\S+)\s+HEAD", p.stdout or "", re.M)
    return m.group(1) if m else None


def push_evidence(remote: str, branch: str, pr: int, files: list[Path], trailers: list[str],
                  identity: tuple[str, str] | None) -> str:
    """Commit files under pr-N/ on the evidence branch in a temporary repository and push it. Returns the commit."""
    if r := check_branch(branch):                     # the name rule first: no remote answer can loosen it
        raise Refused(r)
    if not identity:
        raise Refused("no git user.name and user.email in this folder's config; set them before --push")
    if r := check_branch(branch, remote_default_branch(remote)):
        raise Refused(r)
    message = commit_message(pr, trailers)
    with tempfile.TemporaryDirectory(prefix="pr-evidence-") as tmp:
        hooks = Path(tmp) / "no-hooks"
        hooks.mkdir()
        pre = isolation_args(hooks, identity)
        env = isolated_env()
        work = Path(tmp) / "repo"
        git(["init", "-q", str(work)], tmp, pre=pre, env=env)

        def g(args, check=True):
            return git(args, work, check=check, pre=pre, env=env)
        g(["remote", "add", "origin", remote])
        names = {f.name for f in files}
        if g(["ls-remote", "--heads", "origin", f"refs/heads/{branch}"]).stdout.strip():
            ref = f"refs/remotes/origin/{branch}"
            g(["fetch", "-q", "--depth", "1", "--no-recurse-submodules", "origin", f"refs/heads/{branch}:{ref}"])
            entries = []
            for line in g(["ls-tree", "-r", "-z", ref]).stdout.split("\0"):
                if line:
                    meta, path = line.split("\t", 1)
                    mode, typ, _ = meta.split(" ")
                    entries.append((mode, typ, path))
            if problems := check_evidence_tree(entries):    # checked before anything is checked out
                raise Refused(f"the {branch} branch holds more than images under pr-<number>/: " + "; ".join(problems[:5]))
            names |= {Path(p).name for _, _, p in entries if p.startswith(f"pr-{pr}/")}
            if len(names) > MAX_FILES:
                raise Refused(f"pr-{pr}/ would hold {len(names)} files; at most {MAX_FILES}")
            g(["checkout", "-q", "-b", branch, ref])
        else:
            g(["symbolic-ref", "HEAD", f"refs/heads/{branch}"])   # an orphan branch: no shared history
        if len(names) > MAX_FILES:
            raise Refused(f"pr-{pr}/ would hold {len(names)} files; at most {MAX_FILES}")
        dest = work / f"pr-{pr}"
        dest.mkdir(exist_ok=True)
        for f in files:
            shutil.copyfile(f, dest / f.name)
        g(["add", "--", f"pr-{pr}"])
        if not g(["status", "--porcelain"]).stdout.strip():
            print("Nothing new to commit: the evidence branch already holds these files.")
        else:
            msg_file = Path(tmp) / "msg.txt"
            msg_file.write_text(message, encoding="utf-8")
            g(["commit", "-q", "-F", str(msg_file)])
            p = subprocess.run(["git", *pre, *push_command(branch)[1:]], cwd=str(work), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, env=env)
            if p.returncode != 0:
                raise RuntimeError("push failed (not retried, never forced): " + (p.stderr or p.stdout).strip()[:400])
        return g(["rev-parse", "HEAD"]).stdout.strip()


# ---------- capture (needs Playwright) ----------

INIT_SCRIPT = "document.addEventListener('submit', e => { e.preventDefault(); e.stopImmediatePropagation(); }, true);"
IS_SUBMIT_JS = """el => { const t = (el.getAttribute('type') || '').toLowerCase();
  if (el.tagName === 'INPUT') return t === 'submit' || t === 'image';
  if (el.tagName === 'BUTTON') return !!el.form && (t === '' || t === 'submit');
  return false; }"""
BAD_INPUT_JS = "el => !(el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') || ['password','hidden','file'].includes((el.type || '').toLowerCase())"


MAX_REDIRECTS = 5


def make_route_handler(guard: RequestGuard):
    """Every request goes through the guard. A route handler is not called for redirect hops the browser
    follows, so redirects are followed HERE: each hop is fetched with max_redirects=0, its Location is
    re-checked by the full guard, and only the final non-3xx response is handed to the browser. A refused
    hop, or more than MAX_REDIRECTS hops, aborts the request. (The browser then shows the final content at
    the original URL, so a page reached by redirect may resolve relative links against the wrong base.)"""
    from urllib.parse import urljoin

    def handle(route):
        req = route.request
        if guard.decide(req.method, req.url):
            route.abort("blockedbyclient")
            return
        if urlparse(req.url).scheme in ("data", "blob"):
            route.continue_()
            return
        url = req.url
        for _ in range(MAX_REDIRECTS + 1):
            resp = route.fetch(url=url, max_redirects=0)
            if not 300 <= resp.status < 400:
                route.fulfill(response=resp)
                return
            nxt = urljoin(url, resp.headers.get("location", ""))
            if guard.decide("GET", nxt):
                route.abort("blockedbyclient")
                return
            url = nxt
        guard.refused.append(f"more than {MAX_REDIRECTS} redirects: {req.url[:120]}")
        route.abort("blockedbyclient")
    return handle


def password_visible(page) -> bool:
    """A visible password field in the page or any of its frames."""
    return any(f.locator("input[type=password]:visible").count() for f in page.frames)


def capture_shot(browser, shot: dict, out: Path, quality: int, max_kb: int, resolver=resolve_host) -> dict:
    vp = shot["viewport"]
    guard = RequestGuard(shot["url"], resolver)
    ctx = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]}, has_touch=shot["touch"],
                              is_mobile=shot["touch"], device_scale_factor=shot["device_scale_factor"],
                              accept_downloads=False, service_workers="block")
    try:
        ctx.add_init_script(INIT_SCRIPT)
        ctx.route("**/*", make_route_handler(guard))
        if hasattr(ctx, "route_web_socket"):
            ctx.route_web_socket(re.compile(".*"), lambda ws: ws.close())
        else:
            raise RuntimeError("this Playwright cannot block WebSockets; update it (setup-browser-testing.py)")
        page = ctx.new_page()
        page.goto(shot["url"], wait_until="load", timeout=30000)
        if guard.decide("GET", page.url) or check_url(page.url):
            raise Refused(f"{shot['name']}: the page moved to a refused URL: {page.url[:120]}")
        if password_visible(page):
            raise Refused(f"{shot['name']}: the page shows a password field; it is not captured")
        for a in shot["actions"]:
            if "wait" in a:
                page.wait_for_timeout(a["wait"])
                continue
            sel = a.get("click") or a.get("set_value")
            loc = page.locator(sel).first
            if "click" in a:
                if loc.evaluate(IS_SUBMIT_JS):
                    raise Refused(f"{shot['name']}: {sel!r} submits a form; forms are never submitted")
                loc.click(timeout=5000)
            else:
                if loc.evaluate(BAD_INPUT_JS):
                    raise Refused(f"{shot['name']}: set_value works only on a text input or textarea")
                loc.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }", a["value"])
        if shot.get("scroll_to"):
            page.locator(shot["scroll_to"]).first.scroll_into_view_if_needed(timeout=5000)
        if password_visible(page) or check_url(page.url) or guard.decide("GET", page.url):
            raise Refused(f"{shot['name']}: after the actions the page shows a password field or left the allowed URLs")
        for q in quality_steps(quality):
            if shot.get("selector"):
                data = page.locator(shot["selector"]).first.screenshot(type="jpeg", quality=q, timeout=10000)
            elif shot.get("clip"):
                data = page.screenshot(type="jpeg", quality=q, clip=shot["clip"])
            else:
                data = page.screenshot(type="jpeg", quality=q, full_page=False)
            if len(data) <= max_kb * 1024:
                break
        else:
            raise RuntimeError(f"{shot['name']}: {len(data) / 1024:.0f} KB at quality {MIN_QUALITY} is over {max_kb} KB; "
                               "use a tighter selector or clip, a smaller viewport or device_scale_factor 1")
        path = out / f"{shot['name']}.jpg"
        path.write_bytes(data)
        return {"file": path.name, "kb": round(len(data) / 1024, 1), "quality": q}
    finally:
        ctx.close()


def capture(spec_path: Path, out: Path, quality: int = 72, max_kb: int = 150, channel: str | None = None) -> list[dict]:
    if not 1 <= max_kb <= MAX_FILE_KB:
        raise Refused(f"--max-kb must be 1 to {MAX_FILE_KB} (the publish cap)")
    try:
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"cannot read the spec: {exc}") from None
    shots = validate_spec(spec)
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel=channel) if channel else pw.chromium.launch(headless=True)
        try:
            for s in shots:
                try:
                    results.append(capture_shot(browser, s, out, quality, max_kb))
                except PlaywrightError as exc:
                    raise RuntimeError(f"{s['name']}: {' '.join(str(exc).split())[:300]}") from None
        finally:
            browser.close()
    captions = {f"{s['name']}.jpg": s["caption"] for s in shots}
    (out / "captions.json").write_text(json.dumps(captions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return results


# ---------- publish ----------

def publish(folder: Path, pr: int, repo: str | None, branch: str, push: bool, comment: bool,
            allow_comment_only: bool, trailers: list[str], cwd: Path | str = ".") -> int:
    if pr < 1:
        raise Refused("--pr must be a positive number")
    if comment and not push and not allow_comment_only:
        raise Refused("--comment without --push would link images that are not on the branch; add --push, or --allow-comment-only if they already are")
    remote = None
    if not repo:
        remote = origin_url(cwd)
        repo = parse_repo(remote or "")
        if not repo:
            raise Refused("no GitHub origin in this folder; pass --repo OWNER/REPO")
    if not REPO_RE.match(repo):
        raise Refused(f"--repo {repo!r} must look like OWNER/REPO")
    if r := check_branch(branch, local_default_branch(cwd) if remote else None):
        raise Refused(r)
    files, captions = check_publish_dir(folder)
    identity = caller_identity(cwd)
    names = [f.name for f in files]
    markdown = build_comment(repo, branch, pr, names, captions)
    print(f"Repository: {repo}")
    print(f"Branch:     {branch}  (folder pr-{pr}/)")
    print(f"Identity:   {identity[0] + ' <' + identity[1] + '>' if identity else 'none set; --push will be refused'}")
    print("Temporary repository: hooks, templates and system config disabled; commit signing follows your config.")
    print("Files:")
    for f in files:
        print(f"  pr-{pr}/{f.name}  {f.stat().st_size / 1024:.0f} KB")
    print("Comment markdown:")
    print("-----")
    print(markdown, end="")
    print("-----")
    print(PUBLIC_REMINDER.format(repo=repo))
    if not push and not comment:
        print("DRY RUN: nothing was pushed or posted. Add --push (and --comment) to publish.")
        return 0
    if push:
        target = remote if remote and parse_repo(remote) == repo else f"https://github.com/{repo}.git"
        sha = push_evidence(target, branch, pr, files, trailers, identity)
        print(f"Pushed {branch} at {sha[:12]} (plain push, one branch).")
    if comment:
        with tempfile.TemporaryDirectory() as tmp:
            body = Path(tmp) / "comment.md"
            body.write_text(markdown, encoding="utf-8")
            p = subprocess.run(["gh", "pr", "comment", str(pr), "--repo", repo, "--body-file", str(body)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        if p.returncode != 0:
            raise RuntimeError("gh pr comment failed: " + (p.stderr or p.stdout).strip()[:300])
        print(f"Commented on {repo}#{pr}: {p.stdout.strip()}")
    return 0


# ---------- self-test ----------

SELF_TEST_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Screenshot self-test</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font:16px system-ui;margin:0;padding:16px;background:#f6f3ee}#card{max-width:480px;padding:16px;background:#fff;border:1px solid #ccc}
#out{font-weight:bold}</style></head><body><h1>Fixture</h1>
<div id="card"><label for="q">Name</label> <input id="q"> <button id="go" type="button">Show</button><p id="out">empty</p></div>
<form action="/never" method="post"><button id="send">Send</button></form>
<script>const q=document.getElementById('q');q.addEventListener('input',()=>{document.getElementById('out').textContent='typed: '+q.value});
document.getElementById('go').addEventListener('click',()=>{document.getElementById('card').style.borderColor='#a33'});</script></body></html>"""


def self_test(channel: str | None = None) -> int:
    results: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory(prefix="pr-shots-selftest-") as tmp:
        tmp = Path(tmp)
        site = tmp / "site"
        site.mkdir()
        (site / "index.html").write_text(SELF_TEST_PAGE, encoding="utf-8")
        (site / "sub").mkdir()   # /sub answers 301 to /sub/: the desktop shot goes through the handler's own redirect loop
        (site / "sub" / "index.html").write_text(SELF_TEST_PAGE, encoding="utf-8")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(site), **k)

            def log_message(self, *a):
                pass

        class Server(socketserver.ThreadingTCPServer):   # route.fetch opens its own connections
            daemon_threads = True

        with Server(("127.0.0.1", 0), Handler) as srv:
            port = srv.server_address[1]
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}/"
            spec = {"shots": [
                {"name": "phone", "url": base, "viewport": {"width": 390, "height": 844}, "touch": True,
                 "device_scale_factor": 2, "selector": "#card", "caption": "Card on a phone, after typing",
                 "actions": [{"set_value": "#q", "value": "Ada"}, {"click": "#go"}, {"wait": 50}]},
                {"name": "desktop", "url": base + "sub", "viewport": {"width": 1280, "height": 800},
                 "caption": "Desktop viewport"}]}
            spec_path = tmp / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = tmp / "shots"
            try:
                info = capture(spec_path, out, 72, 150, channel)
                results.append(("two shots captured", len(info) == 2))
            except Exception as exc:  # noqa: BLE001 - report and fail
                print(f"capture error: {ascii(str(exc))[:400]}")
                results.append(("two shots captured", False))
            for n in ("phone.jpg", "desktop.jpg"):
                data = (out / n).read_bytes() if (out / n).is_file() else b""
                results.append((f"{n} is a JPEG", is_jpeg(data)))
                results.append((f"{n} is under 150 KB", 0 < len(data) <= 150 * 1024))
            caps = json.loads((out / "captions.json").read_text(encoding="utf-8")) if (out / "captions.json").is_file() else {}
            results.append(("captions.json written", caps.get("phone.jpg") == "Card on a phone, after typing"))
            bad = tmp / "bad.json"
            bad.write_text(json.dumps({"shots": [{**spec["shots"][1], "name": "send", "actions": [{"click": "#send"}]}]}), encoding="utf-8")
            try:
                capture(bad, tmp / "bad-out", 72, 150, channel)
                results.append(("a click on a form submit button is refused", False))
            except Refused:
                results.append(("a click on a form submit button is refused", True))
            srv.shutdown()
        for url in ("file:///etc/passwd", "ftp://x.test/", "https://user:pw@x.test/"):
            results.append((f"spec with {url.split(':')[0]} URL refused", check_url(url) is not None))

        md = build_comment("example/demo", "pr-evidence", 7, ["desktop.jpg", "phone.jpg"], caps)
        want = image_url("example/demo", "pr-evidence", 7, "phone.jpg")
        results.append(("markdown embeds the raw blob URL", f"]({want})" in md
                        and want == "https://github.com/example/demo/blob/pr-evidence/pr-7/phone.jpg?raw=true"))

        repo = tmp / "caller"
        git(["init", "-q", str(repo)], tmp)
        git(["remote", "add", "origin", "https://github.com/example/demo.git"], repo)
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "publish", "--dir", str(out), "--pr", "7"],
                           cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=60)
        dry = p.stdout
        results.append(("dry run exits 0", p.returncode == 0))
        results.append(("dry run lists both files under pr-7/", "pr-7/desktop.jpg" in dry and "pr-7/phone.jpg" in dry))
        results.append(("dry run names repo and branch", "Repository: example/demo" in dry and "Branch:     pr-evidence" in dry))
        results.append(("dry run prints the exact markdown", md in dry))
        results.append(("dry run says nothing was pushed", "DRY RUN" in dry))
        untouched = git(["rev-parse", "--verify", "-q", "HEAD"], repo, check=False).returncode != 0 \
            and not git(["branch", "--list"], repo).stdout.strip() and not git(["status", "--porcelain"], repo).stdout.strip()
        results.append(("caller repository unchanged by the dry run", untouched))
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    failed = [n for n, ok in results if not ok]
    print(f"self-test: {'OK' if not failed else 'FAILED: ' + '; '.join(failed)}")
    return 0 if not failed else 4


# ---------- command line ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="serve a local page, capture two shots, dry-run publish")
    ap.add_argument("--channel", choices=["msedge", "chrome"], help="use an installed Edge or Chrome")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("capture", help="write small JPEG screenshots from a spec")
    c.add_argument("spec", type=Path)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--quality", type=int, default=72)
    c.add_argument("--max-kb", type=int, default=150)
    c.add_argument("--channel", choices=["msedge", "chrome"], dest="cap_channel")
    p = sub.add_parser("publish", help="dry run by default; --push to an evidence branch, --comment on the PR")
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--repo", help="OWNER/REPO; default from `git remote get-url origin` here")
    p.add_argument("--branch", default="pr-evidence")
    p.add_argument("--push", action="store_true")
    p.add_argument("--comment", action="store_true")
    p.add_argument("--allow-comment-only", action="store_true")
    p.add_argument("--trailer", action="append", default=[], help="a line to end the commit message with; repeatable")
    a = ap.parse_args(argv)
    try:
        if a.self_test:
            return self_test(a.channel)
        if a.cmd == "capture":
            for r in capture(a.spec, a.out, a.quality, a.max_kb, a.cap_channel or a.channel):
                print(f"{r['file']}  {r['kb']} KB  quality {r['quality']}")
            print(f"captions.json written to {a.out}")
            return 0
        if a.cmd == "publish":
            return publish(a.dir, a.pr, a.repo, a.branch, a.push, a.comment, a.allow_comment_only, a.trailer)
        ap.print_help()
        return 2
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

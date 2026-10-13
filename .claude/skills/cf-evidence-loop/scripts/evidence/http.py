"""Polite HTTP client. Every network rule the lab has is enforced here, in code, not in prose.

The rules (see references/NETWORK-RULES.md for the reasoning; each has a test):

  R1  Catalog gate: only sources with access `api` or `fetch` and a base_url. Refusal before any socket.
  R2  Paperwork gate for APIs: an `api` source must carry `terms_url` and `max_rps` or it is refused.
  R3  Robots gate for documents: a `fetch` source's path must be allowed by the host's robots.txt for our
      agent and for `*`; 404/410 means no restrictions; 401/403 means refuse; 5xx or timeout means refuse this run.
      robots.txt is fetched once per host per process, paced (R4), capped (R10) and without following a redirect (R1);
      a redirect or an oversized body counts as unreachable.
  R4  Pacing: never faster than the catalog's `max_rps`, never faster than the hard ceiling of 3 requests/second,
      default 1 request/second. Single-threaded by construction.
  R5  Budget: a hard ceiling of MAX_REQUESTS_PER_PROCESS requests per process. The environment can lower it, never raise it.
  R6  Circuit breaker: a host that answers 402/403, or 429/503 twice, or three consecutive errors, is in cooldown for the rest
      of the process. No further request reaches it.
  R7  One identity: a fixed project user agent, optional contact from the environment. No override exists.
  R8  Accounting: every request attempt is counted; EVIDENCE_REQUEST_LOG, if set, receives one JSON line per attempt.
  R9  Dry run: EVIDENCE_DRY_RUN=1 makes every call return the planned URL without opening a socket; every planned
      request (the robots.txt fetch included) is listed in Client.planned.
  R10 Body cap: a response body larger than MAX_BODY_BYTES is refused, not read to the end and not truncated.
  R11 Contact: the optional contact that goes into the User-Agent must be a plain email address.

There is deliberately no way to set a browser user agent, disable certificate checks, add concurrency, or retry past a refusal.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from . import catalog
from .record import Status

__version__ = "1.0.0"
PROJECT_UA = "senseiewok-research-evidence/" + __version__ + " (+https://github.com/senseiewok/cf-skills)"

HARD_MAX_RPS = 3.0                 # absolute ceiling, whatever the catalog says
DEFAULT_MAX_RPS = 1.0              # when the catalog is silent
MAX_REQUESTS_PER_PROCESS = 200     # absolute ceiling; EVIDENCE_MAX_REQUESTS may only lower it
MAX_RETRY_AFTER_S = 30.0
CONSECUTIVE_ERRORS_TO_TRIP = 3
ROBOTS_TIMEOUT_S = 15.0
MAX_BODY_BYTES = 5_000_000         # the answers this package reads are well under 1 MB; a larger one is not what we asked for
READ_CHUNK_BYTES = 65_536

_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
_EMAIL = re.compile(rf"[A-Za-z0-9._%+-]+@(?:{_LABEL}\.)+{_LABEL}")


def validate_contact(value: str | None) -> str | None:
    """The contact goes into a header, so it must be a plain email address: no spaces, line breaks, brackets or lists."""
    if value is None or value == "":
        return None
    if len(value) > 254 or not _EMAIL.fullmatch(value):
        raise ValueError(f"invalid contact {value[:40]!r}: use a plain email address such as name@example.org")
    return value


class BudgetExhausted(RuntimeError):
    """The per-process request ceiling was reached. Start a new process deliberately; do not loop."""


class HostInCooldown(PermissionError):
    """The host refused or rate-limited us earlier in this process. It is not contacted again."""


class PaperworkMissing(PermissionError):
    """An api source lacks terms_url or max_rps in the catalog. Add them before calling it."""


class RobotsDisallow(PermissionError):
    """robots.txt disallows the path for our agent, or could not be read in a way that permits fetching."""


@dataclass
class Fetch:
    status: Status
    http_status: int | None
    url: str
    data: Any = None
    text: str | None = None
    retry_after: float | None = None
    dry_run: bool = False


@dataclass
class Accounting:
    attempts: int = 0
    by_host: dict[str, int] = field(default_factory=dict)
    blocked_hosts: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        hosts = ", ".join(f"{h}={n}" for h, n in sorted(self.by_host.items())) or "none"
        cool = ", ".join(f"{h} ({why})" for h, why in sorted(self.blocked_hosts.items())) or "none"
        return f"requests: {self.attempts} | by host: {hosts} | cooldown: {cool}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Client:
    def __init__(self, *, contact: str | None = None, timeout: float = 30.0, session: requests.Session | None = None):
        self.contact = validate_contact(contact if contact is not None else os.environ.get("EVIDENCE_CONTACT") or None)
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = PROJECT_UA + (f" mailto:{self.contact}" if self.contact else "")
        self.session.headers["Accept"] = "application/json"
        self.dry_run = os.environ.get("EVIDENCE_DRY_RUN", "") not in ("", "0", "false", "False")
        self.max_requests = min(MAX_REQUESTS_PER_PROCESS, _env_int("EVIDENCE_MAX_REQUESTS", MAX_REQUESTS_PER_PROCESS))
        self.log_path = os.environ.get("EVIDENCE_REQUEST_LOG") or None
        self.accounting = Accounting()
        self.planned: list[tuple[str, str]] = []  # (method, url) of every request a dry run would make
        self._last_call: dict[str, float] = {}
        self._cooldown: dict[str, str] = {}
        self._rate_limited_once: set[str] = set()
        self._consecutive_errors: dict[str, int] = {}
        self._robots: dict[str, str] = {}  # host -> robots.txt body, "" for none, or a sentinel

    # ------------------------------------------------------------------ gates

    def _url(self, source_id: str, path: str) -> str:
        base = catalog.base_url(source_id)                    # R1
        url = base + path.lstrip("/")
        if not catalog.host_allowed(url):
            raise catalog.AccessDenied(f"{url}: host is not in the catalog's permitted set")
        return url

    def _paperwork(self, source_id: str) -> None:            # R2
        e = catalog.entry(source_id)
        if e.get("access") == "api":
            missing = [k for k in ("terms_url", "max_rps") if not e.get(k)]
            if missing:
                raise PaperworkMissing(f"{source_id}: catalog entry lacks {', '.join(missing)}; record the API's terms before calling it")

    def _robots_ok(self, source_id: str, url: str) -> None:  # R3
        if catalog.entry(source_id).get("access") != "fetch":
            return  # api sources are governed by their published API terms (R2), not by page-crawl rules
        host = urlparse(url).netloc.lower()
        body = self._robots.get(host)
        if body is None:
            body = self._load_robots(source_id, host)
            self._robots[host] = body
        if body in ("__refused__", "__unreachable__"):
            raise RobotsDisallow(f"{host}: robots.txt {body.strip('_')}; fetching documents from this host is refused")
        if not robots_allows(body, urlparse(url).path or "/", PROJECT_UA.split("/")[0]):
            raise RobotsDisallow(f"{host}: robots.txt disallows {urlparse(url).path} for our agent or for *")

    def _load_robots(self, source_id: str, host: str) -> str:
        url = f"https://{host}/robots.txt"
        if self.dry_run:
            self.planned.append(("GET", url))
            return ""
        self._pace(source_id)                                  # R4: the robots fetch is a request to the host like any other
        self._count(host, "/robots.txt")
        try:
            # R1: a redirect is not followed; a 30x falls through to "unreachable" below. R10: the body is capped.
            r = self.session.get(url, timeout=ROBOTS_TIMEOUT_S, allow_redirects=False, stream=True)
            r = _read_capped(r, url)                           # over the cap: a 599 stand-in, so "unreachable" below
        except requests.RequestException:
            return "__unreachable__"
        if r.status_code == 200:
            return r.text
        if r.status_code in (404, 410):
            return ""          # no robots file: no restrictions (RFC 9309)
        if r.status_code in (401, 403):
            return "__refused__"
        return "__unreachable__"

    def _check_cooldown(self, host: str) -> None:            # R6
        if host in self._cooldown:
            raise HostInCooldown(f"{host}: {self._cooldown[host]}; not contacted again this process")

    def _pace(self, source_id: str) -> None:                 # R4
        rps = min(HARD_MAX_RPS, float(catalog.entry(source_id).get("max_rps") or DEFAULT_MAX_RPS))
        gap = 1.0 / rps
        # Paced per HOST: two catalog sources can share one (crossref and retraction-watch-crossref;
        # the two openFDA endpoints), and the publisher sees one client, not two ids.
        host = urlparse(catalog.base_url(source_id)).netloc.lower()
        last = self._last_call.get(host)
        if last is not None:
            wait = gap - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_call[host] = time.monotonic()

    def _count(self, host: str, path: str, status: int | None = None) -> None:  # R5, R8
        if self.accounting.attempts >= self.max_requests:
            raise BudgetExhausted(f"{self.max_requests} requests already made in this process")
        self.accounting.attempts += 1
        self.accounting.by_host[host] = self.accounting.by_host.get(host, 0) + 1
        if self.log_path:
            with Path(self.log_path).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": _now(), "host": host, "path": path, "status": status, "dry_run": self.dry_run}) + "\n")

    def _trip(self, host: str, why: str) -> None:
        self._cooldown[host] = why
        self.accounting.blocked_hosts[host] = why

    # --------------------------------------------------------------- requests

    def get(self, source_id: str, path: str, params: dict | None = None) -> Fetch:
        return self._do("GET", source_id, path, params=params)

    def post(self, source_id: str, path: str, json: dict | None = None) -> Fetch:
        return self._do("POST", source_id, path, json=json)

    def _do(self, method: str, source_id: str, path: str, *, params=None, json=None) -> Fetch:
        url = self._url(source_id, path)
        host = urlparse(url).netloc.lower()
        self._paperwork(source_id)
        self._check_cooldown(host)
        self._robots_ok(source_id, url)
        if self.dry_run:                                      # R9
            self._count(host, path)
            planned = requests.Request(method, url, params=params).prepare().url
            self.planned.append((method, planned))
            return Fetch(Status.OUT_OF_SCOPE, None, planned, dry_run=True)
        self._pace(source_id)
        self._count(host, path)
        resp = self._send(method, url, params, json)
        if resp.status_code in (429, 503):
            if host in self._rate_limited_once:
                self._trip(host, f"rate limited twice ({resp.status_code})")
                return Fetch(Status.RATE_LIMITED, resp.status_code, resp.url, text=resp.text[:500])
            self._rate_limited_once.add(host)
            ra = _retry_after(resp)
            if ra is not None and (not math.isfinite(ra) or ra < 0):
                # time.sleep raises on a negative or NaN value; that would lose the record and the accounting line (R8)
                self._trip(host, f"rate limited ({resp.status_code}), Retry-After {str(resp.headers.get('Retry-After'))[:20]!r} "
                                 "is not a usable number of seconds")
                return Fetch(Status.RATE_LIMITED, resp.status_code, resp.url, text=resp.text[:500])
            if ra is None or ra > MAX_RETRY_AFTER_S:
                why = "no Retry-After header" if ra is None else f"Retry-After {ra:.0f}s exceeds the {MAX_RETRY_AFTER_S:.0f}s we will wait"
                self._trip(host, f"rate limited ({resp.status_code}), {why}")
                return Fetch(Status.RATE_LIMITED, resp.status_code, resp.url, retry_after=ra, text=resp.text[:500])
            time.sleep(ra)
            self._pace(source_id)                             # a Retry-After of 0 must not mean "immediately"
            self._count(host, path)
            resp = self._send(method, url, params, json)
            if resp.status_code in (429, 503):
                self._trip(host, f"rate limited again after honouring Retry-After ({resp.status_code})")
                return Fetch(Status.RATE_LIMITED, resp.status_code, resp.url, retry_after=ra, text=resp.text[:500])
        f = _classify(resp)
        if f.status is Status.BLOCKED:
            self._trip(host, f"refused with {resp.status_code}")
        if f.status in (Status.ERROR, Status.BLOCKED, Status.RATE_LIMITED):
            n = self._consecutive_errors.get(host, 0) + 1
            self._consecutive_errors[host] = n
            if n >= CONSECUTIVE_ERRORS_TO_TRIP and host not in self._cooldown:
                self._trip(host, f"{n} consecutive errors")
        else:
            self._consecutive_errors[host] = 0
        return f

    def _send(self, method: str, url: str, params, json) -> requests.Response:
        # Redirects are never followed: a 30x from a permitted host could name any other host (R1).
        try:
            resp = self.session.request(method, url, params=params, json=json, timeout=self.timeout, allow_redirects=False, stream=True)
            return _read_capped(resp, url)                      # R10
        except requests.RequestException as exc:
            # DNS, timeout, TLS: no HTTP response exists. Report it as an error record instead of a
            # traceback, so the attempt stays counted and the accounting line is still printed (R8).
            return _no_response(url, f"network error: {type(exc).__name__}")


# ------------------------------------------------------------------- helpers

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _no_response(url: str, why: str) -> requests.Response:
    """A stand-in for "no usable HTTP response": status 599 is not an HTTP status, it marks that, and _classify reports it as an error."""
    r = requests.Response()
    r.status_code = 599
    r.url = url
    r._content = why.encode("utf-8")
    r.encoding = "utf-8"
    return r


def _read_capped(resp, url: str):
    """Read at most MAX_BODY_BYTES of the body. An answer over the cap is refused outright: a truncated JSON body would
    either fail to parse or, worse, parse into something that looks complete. A response object that has no stream
    (the fakes in the tests, a response built in memory) is already in memory and is returned as it is."""
    refuse = f"response larger than {MAX_BODY_BYTES:,} bytes; not read"
    declared = resp.headers.get("Content-Length")
    try:
        if declared is not None and int(declared) > MAX_BODY_BYTES:
            if hasattr(resp, "close"):
                resp.close()
            return _no_response(url, refuse)
    except ValueError:
        pass                                                    # an unreadable header is not a reason to refuse; the byte count below decides
    if getattr(resp, "raw", None) is None:
        return resp                                             # no stream to read: the body is already in memory
    chunks, size = [], 0
    for chunk in resp.iter_content(chunk_size=READ_CHUNK_BYTES):
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            resp.close()
            return _no_response(url, refuse)
        chunks.append(chunk)
    resp._content = b"".join(chunks)
    resp._content_consumed = True
    return resp


def _retry_after(resp: requests.Response) -> float | None:
    v = resp.headers.get("Retry-After")
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def _classify(resp: requests.Response) -> Fetch:
    code = resp.status_code
    if code in (402, 403):
        return Fetch(Status.BLOCKED, code, resp.url, text=resp.text[:500])
    if code == 404:
        return Fetch(Status.NOT_FOUND, code, resp.url)
    if code >= 400:
        return Fetch(Status.ERROR, code, resp.url, text=resp.text[:500])
    if 300 <= code < 400:
        return Fetch(Status.ERROR, code, resp.url, text=f"redirect to {str(resp.headers.get('Location', '?'))[:200]} was not followed")
    try:
        data = resp.json()
    except ValueError:
        return Fetch(Status.ERROR, code, resp.url, text=resp.text[:500])
    if not isinstance(data, dict):
        # Every endpoint this package reads answers with a JSON object. A list or a bare value means the API changed or the
        # answer is not the one we asked for; say so here instead of letting a provider index into the wrong shape.
        return Fetch(Status.ERROR, code, resp.url, text=f"unexpected JSON shape: a {type(data).__name__}, not an object")
    return Fetch(Status.FOUND, code, resp.url, data=data)


def robots_allows(body: str, path: str, agent: str) -> bool:
    """RFC 9309 matching, written out because the standard library parser accepted a path that
    clinicaltrials.gov's file disallows. A group applies to us only when it names our product token exactly
    (ignoring case); the rules of every such group are combined, and only when none names us are the `*`
    groups combined instead. Within the chosen rules the longest match wins, and Allow beats Disallow on
    equal length. Consecutive User-agent lines share one group; an empty value names nobody."""
    groups: list[tuple[set[str], list[tuple[str, str]]]] = []
    agents: set[str] = set()
    rules: list[tuple[str, str]] = []
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            if rules:  # a User-agent line after a rule starts a new group
                groups.append((agents, rules))
                agents, rules = set(), []
            if val:
                agents.add(val.lower())
        elif key in ("allow", "disallow"):
            rules.append((key, val))
    if agents or rules:
        groups.append((agents, rules))
    agent = agent.lower()
    named = [r for a, r in groups if agent in a]
    chosen = [rule for r in (named or [r for a, r in groups if "*" in a]) for rule in r]
    best: tuple[int, str] | None = None
    for key, pattern in chosen:
        if pattern == "" or not _path_matches(path, pattern):
            continue
        if best is None or len(pattern) > best[0] or (len(pattern) == best[0] and key == "allow"):
            best = (len(pattern), key)
    return best is None or best[1] == "allow"


def _path_matches(path: str, pattern: str) -> bool:
    anchored = pattern.endswith("$")
    pat = pattern[:-1] if anchored else pattern
    parts = pat.split("*")
    pos = 0
    for i, part in enumerate(parts):
        if i == 0:
            if not path.startswith(part):
                return False
            pos = len(part)
        else:
            idx = path.find(part, pos)
            if idx < 0:
                return False
            pos = idx + len(part)
    return (pos == len(path)) if anchored else True

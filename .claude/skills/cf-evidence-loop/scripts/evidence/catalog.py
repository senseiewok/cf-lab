"""The access gate. Every outbound request in this package passes through here.

Reads the catalog (see CATALOG_PATH) and answers one question: may code reach this source
automatically? The answer is yes only when the entry exists, its ``access`` is
``fetch`` or ``api``, and it declares a ``base_url``. Nothing else is reachable.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml

import os

SKILL_ROOT = Path(__file__).resolve().parents[2]
# Resolution order: EVIDENCE_CATALOG env var (e.g. a lab-wide access record), else the catalog shipped with this skill.
CATALOG_PATH = Path(os.environ.get("EVIDENCE_CATALOG") or (SKILL_ROOT / "catalog.yaml"))
AUTOMATABLE = frozenset({"fetch", "api"})


class UnknownSource(KeyError):
    """The catalog has no entry with this id. No entry means no permission."""


class AccessDenied(PermissionError):
    """The catalog entry exists but does not permit automated access."""


_cache: dict[str, dict] | None = None


def load(path: Path = CATALOG_PATH, *, refresh: bool = False) -> dict[str, dict]:
    """Return catalog entries keyed by id. Cached after first load."""
    global _cache
    if _cache is None or refresh:
        with Path(path).open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        _cache = {e["id"]: e for e in data.get("sources", [])}
    return _cache


def entry(source_id: str) -> dict:
    try:
        return load()[source_id]
    except KeyError as exc:
        raise UnknownSource(source_id) from exc


def base_url(source_id: str) -> str:
    """Base URL for a source, or raise. This is the gate."""
    e = entry(source_id)
    access = e.get("access")
    if access not in AUTOMATABLE:
        raise AccessDenied(f"{source_id}: access is '{access}'; automated requests are not permitted")
    url = e.get("base_url")
    if not url:
        raise AccessDenied(f"{source_id}: permitted but no base_url declared; add one to the catalog")
    return url.rstrip("/") + "/"


def allowed_hosts() -> frozenset[str]:
    hosts = set()
    for e in load().values():
        if e.get("access") in AUTOMATABLE and e.get("base_url"):
            hosts.add(urlparse(e["base_url"]).netloc.lower())
    return frozenset(hosts)


def host_allowed(url: str) -> bool:
    return urlparse(url).netloc.lower() in allowed_hosts()


def min_interval(source_id: str, default: float = 1.0) -> float:
    """Seconds between requests to this source. Catalog may set ``min_interval_s``."""
    return float(entry(source_id).get("min_interval_s", default))

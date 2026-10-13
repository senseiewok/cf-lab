"""Checks on the shape of an API answer.

A provider that assumes a shape it never checked either crashes with a traceback or, worse, reads a missing field
as zero and reports "nothing found". These helpers turn a surprise into a ``ShapeError`` that a provider converts
into an error record saying what was wrong.
"""

from __future__ import annotations

import re
from typing import Any

from .record import Evidence, Status


class ShapeError(ValueError):
    """A response did not have the shape the provider relies on."""


def need(obj: Any, key: str, what: str) -> Any:
    """``obj[key]``, or a ShapeError naming ``what`` when obj is not an object or has no such key."""
    if not isinstance(obj, dict) or key not in obj:
        raise ShapeError(f"{what} has no '{key}'")
    return obj[key]


def _shown(value: Any, limit: int = 60) -> str:
    """A bounded repr: a response can hold megabytes where a number belongs, and the message must not carry them."""
    s = repr(value)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def count(value: Any, what: str) -> int:
    """A non-negative whole number, given as an int or as digits in a string (NCBI sends counts as strings)."""
    text = str(value).strip() if isinstance(value, (int, str)) and not isinstance(value, bool) else ""
    # at most 15 digits: a real count is far smaller, and int() refuses a string of thousands of digits with a ValueError
    if not re.fullmatch(r"[0-9]{1,15}", text):
        raise ShapeError(f"{what} is {_shown(value)}, not a number")
    return int(text)


def esearch_result(data: Any, what: str) -> tuple[list, int]:
    """(ids, total) from an NCBI esearch answer: ``esearchresult`` with a numeric ``count`` and a list ``idlist``."""
    er = need(data, "esearchresult", what)
    total = count(need(er, "count", f"{what} esearchresult"), f"{what} esearchresult count")
    ids = er.get("idlist", [])
    if not isinstance(ids, list):
        raise ShapeError(f"{what} esearchresult idlist is {type(ids).__name__}, not a list")
    return ids, total


def esummary_result(data: Any, what: str) -> tuple[dict, list]:
    """(result, uids) from an NCBI esummary answer: ``result`` an object with a list ``uids``.

    NCBI can answer HTTP 200 with ``{"error": ...}`` and no ``result``; that is a failure, not an empty summary."""
    if isinstance(data, dict) and "result" not in data and "error" in data:
        raise ShapeError(f"{what} has no 'result'; the answer's 'error' is {_shown(data['error'])}")
    res = need(data, "result", what)
    if not isinstance(res, dict):
        raise ShapeError(f"{what} result is {type(res).__name__}, not an object")
    uids = need(res, "uids", f"{what} result")
    if not isinstance(uids, list):
        raise ShapeError(f"{what} result uids is {type(uids).__name__}, not a list")
    return res, uids


def error_record(exc: ShapeError, *, question: str, source_id: str, url: str, provider: str, fields: dict | None = None) -> Evidence:
    return Evidence(status=Status.ERROR, question=question, source_id=source_id, url=url, provider=provider,
                    fields={**(fields or {}), "shape_error": str(exc)},
                    limitations=f"Unexpected response shape ({exc}); the response was not used and establishes nothing, including that nothing matched.")

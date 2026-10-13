"""The evidence record: the only thing a provider returns."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class Status(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    OUT_OF_SCOPE = "out_of_scope"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


# Terminal escape sequences, removed whole (payload included): CSI, OSC, DCS/PM/APC strings, and any other two-byte ESC pair.
_ESCAPES = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[P^_X][^\x1b]*\x1b\\|\x1b[@-Z\\-_]")
_CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def clean_for_terminal(text: str) -> str:
    """Text from a publisher is data, never a command to the reader's terminal: drop escape sequences, then turn
    every remaining control character (newline and tab included) into a space."""
    return _CONTROLS.sub(" ", _ESCAPES.sub("", text))


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Evidence:
    status: Status
    question: str
    source_id: str
    url: str
    provider: str
    publisher_date: str | None = None
    accessed: str = field(default_factory=now_utc)
    fields: dict[str, Any] = field(default_factory=dict)
    excerpt: str | None = None
    limitations: str = ""

    def __post_init__(self) -> None:
        if not self.limitations:
            raise ValueError("Evidence.limitations must not be empty; say what this record does not establish")
        if isinstance(self.status, str) and not isinstance(self.status, Status):
            self.status = Status(self.status)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    def one_line(self) -> str:
        key = ", ".join(f"{k}={_short(v)}" for k, v in list(self.fields.items())[:4])
        return clean_for_terminal(f"[{self.status.value}] {self.source_id} {self.publisher_date or '-'} | {key} | {self.url}")


def _short(v: Any, n: int = 60) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


def append_ledger(path: str | Path, records: Iterable[Evidence]) -> int:
    """Append records as JSON lines. Returns the number written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(r.to_json() + "\n")
            n += 1
    return n

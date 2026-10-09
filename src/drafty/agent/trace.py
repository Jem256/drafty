"""Trace event model and a redacting tracer.

Every model call and state transition appends a :class:`TraceEvent`. The tracer redacts anything
that looks like a secret before the event is stored.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

SENSITIVE_KEYS = ("api_key", "apikey", "authorization", "secret", "password", "access_token")
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
)


def _redact_string(value: str) -> str:
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("***", value)
    return value


def redact(value: Any) -> Any:
    """Recursively mask sensitive keys and secret-looking strings."""
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if any(marker in key_lower for marker in SENSITIVE_KEYS):
                result[key] = "***"
            else:
                result[key] = redact(item)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


class TraceEvent(BaseModel):
    """One step in a run's trace (architecture.md section 9)."""

    run_id: str
    seq: int
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: str | None = None
    role: str | None = None
    model: str | None = None
    prompt_hash: str | None = None
    request: Any = None
    response: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_results: list[dict[str, Any]] | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: float | None = None
    checks_summary: dict[str, Any] | None = None


class Tracer:
    """Appends trace events for a run, continuing the sequence from any stored events."""

    def __init__(self, db: Any = None, run_id: str | None = None) -> None:
        self._db = db
        self._run_id = run_id
        if db is not None and run_id is not None:
            self._seq = len(db.list_trace_events(run_id))
        else:
            self._seq = 0

    def emit(self, **fields: Any) -> TraceEvent:
        self._seq += 1
        if "request" in fields and fields["request"] is not None:
            fields["request"] = redact(fields["request"])
        if "tool_results" in fields and fields["tool_results"] is not None:
            fields["tool_results"] = redact(fields["tool_results"])
        event = TraceEvent(run_id=self._run_id or "", seq=self._seq, **fields)
        if self._db is not None:
            self._db.append_trace_event(event)
        return event

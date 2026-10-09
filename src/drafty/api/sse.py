"""Server-sent event streaming of trace events.

The stream replays stored trace events after ``last_event_id`` (so a browser can reconnect) and ends
when the run reaches a terminal state.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from drafty.agent.trace import TraceEvent
from drafty.api.services import TERMINAL_STATES

EVENT_TYPES = (
    "state",
    "model_call",
    "tool_call",
    "checks",
    "question",
    "done",
    "escalated",
    "error",
)


def event_type(event: TraceEvent) -> str:
    """Map a trace event to an SSE event type."""
    if event.state == "done":
        return "done"
    if event.state == "escalated":
        return "escalated"
    if event.state == "failed":
        return "error"
    if event.state == "awaiting_answers":
        return "question"
    if event.checks_summary is not None:
        return "checks"
    if event.role is not None:
        return "model_call"
    return "state"


def format_sse(event: TraceEvent) -> str:
    return f"id: {event.seq}\nevent: {event_type(event)}\ndata: {event.model_dump_json()}\n\n"


def event_stream(
    db,
    run_id: str,
    *,
    last_event_id: int = 0,
    poll_interval: float = 0.05,
    timeout: float = 120.0,
) -> Iterator[str]:
    """Yield SSE strings for new trace events until the run is terminal."""
    sent = last_event_id
    started = time.monotonic()
    while True:
        events = db.list_trace_events(run_id)
        for event in events:
            if event.seq > sent:
                yield format_sse(event)
                sent = event.seq
        run = db.get_run(run_id)
        state = run["state"] if run else None
        if state in TERMINAL_STATES and sent >= len(events):
            break
        if time.monotonic() - started > timeout:
            break
        time.sleep(poll_interval)

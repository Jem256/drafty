"""SQLite storage for runs and trace events."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from drafty.agent.trace import TraceEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    brief TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trace_events (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    ts TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    """A thin wrapper around a SQLite file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create_run(self, run_id: str, state: str = "received", brief: str | None = None) -> None:
        now = _now()
        self._conn.execute(
            "INSERT OR REPLACE INTO runs(run_id, state, brief, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, state, brief, now, now),
        )
        self._conn.commit()

    def update_run_state(self, run_id: str, state: str) -> None:
        self._conn.execute(
            "UPDATE runs SET state = ?, updated_at = ? WHERE run_id = ?",
            (state, _now(), run_id),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def append_trace_event(self, event: TraceEvent) -> None:
        self._conn.execute(
            "INSERT INTO trace_events(run_id, seq, ts, payload) VALUES (?, ?, ?, ?)",
            (event.run_id, event.seq, event.ts.isoformat(), event.model_dump_json()),
        )
        self._conn.commit()

    def list_trace_events(self, run_id: str) -> list[TraceEvent]:
        rows = self._conn.execute(
            "SELECT payload FROM trace_events WHERE run_id = ? ORDER BY seq", (run_id,)
        ).fetchall()
        return [TraceEvent.model_validate_json(row["payload"]) for row in rows]

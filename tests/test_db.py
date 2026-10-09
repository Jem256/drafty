"""SQLite run/trace storage and the redacting tracer."""

from __future__ import annotations

from drafty.agent.trace import Tracer
from drafty.storage.db import Database


def test_run_lifecycle(tmp_path) -> None:
    db = Database(tmp_path / "drafty.db")
    db.create_run("r-1", brief="hello")
    assert db.get_run("r-1")["state"] == "received"
    db.update_run_state("r-1", "parsing")
    assert db.get_run("r-1")["state"] == "parsing"
    db.close()


def test_trace_events_roundtrip(tmp_path) -> None:
    db = Database(tmp_path / "drafty.db")
    db.create_run("r-1")
    tracer = Tracer(db, "r-1")
    tracer.emit(state="received")
    tracer.emit(state="parsing", role="parse", model="m", tokens_in=3, tokens_out=4)
    events = db.list_trace_events("r-1")
    assert [event.seq for event in events] == [1, 2]
    assert events[1].tokens_out == 4
    db.close()


def test_tracer_redacts_secrets(tmp_path) -> None:
    db = Database(tmp_path / "drafty.db")
    db.create_run("r-1")
    tracer = Tracer(db, "r-1")
    event = tracer.emit(
        request={"api_key": "sk-abcdef123456", "messages": [{"content": "Bearer xyz"}]}
    )
    assert event.request["api_key"] == "***"
    assert "sk-" not in event.request["messages"][0]["content"]
    db.close()


def test_tracer_continues_sequence(tmp_path) -> None:
    db = Database(tmp_path / "drafty.db")
    db.create_run("r-1")
    Tracer(db, "r-1").emit(state="a")
    event = Tracer(db, "r-1").emit(state="b")
    assert event.seq == 2
    db.close()

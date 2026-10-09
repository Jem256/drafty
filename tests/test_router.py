"""Message routing (Nano)."""

from __future__ import annotations

from drafty.agent.fake_llm import FakeLLM, json_result, text_result
from drafty.agent.router import RouteLabel, route


def test_route_returns_label() -> None:
    fake = FakeLLM([json_result(RouteLabel(label="new_brief"))])
    assert route(fake, "a 300 m road with drains") == "new_brief"


def test_route_retries_once_then_falls_back_to_other() -> None:
    fake = FakeLLM([text_result("not json"), text_result("still not json")])
    assert route(fake, "hello") == "other"
    assert len(fake.calls) == 2

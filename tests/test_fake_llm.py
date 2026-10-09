"""The scripted fake model."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from drafty.agent.fake_llm import FakeLLM, json_result, text_result, tool_call_result


class Obj(BaseModel):
    value: int


def test_replays_script_and_records_calls() -> None:
    fake = FakeLLM([text_result("one"), json_result(Obj(value=2))])
    first = fake.complete("explain", [{"role": "user", "content": "a"}])
    second = fake.complete("parse", [{"role": "user", "content": "b"}], response_schema=Obj)
    assert first.content == "one"
    assert second.parsed.value == 2
    assert [call.role for call in fake.calls] == ["explain", "parse"]
    assert fake.calls[1].response_schema is Obj


def test_tool_call_result() -> None:
    result = tool_call_result([("add_side_drain", {"side": "left"})])
    assert result.tool_calls[0].name == "add_side_drain"
    assert result.tool_calls[0].arguments == {"side": "left"}


def test_exhausted_script_raises() -> None:
    fake = FakeLLM([])
    with pytest.raises(IndexError):
        fake.complete("label", [{"role": "user", "content": "x"}])

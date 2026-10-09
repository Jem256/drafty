"""Brief parsing with validate-and-retry (Ultra)."""

from __future__ import annotations

import pytest

import specs
from drafty.agent.fake_llm import FakeLLM, json_result, text_result
from drafty.agent.parse_brief import ParseError, parse


def test_parse_returns_brief() -> None:
    fake = FakeLLM([json_result(specs.parsed_happy())])
    result = parse(fake, "200 m road")
    assert result.road.length_m == 200


def test_parse_retries_with_error_then_succeeds() -> None:
    fake = FakeLLM([text_result("not json"), json_result(specs.parsed_happy())])
    result = parse(fake, "200 m road", retries=2)
    assert result.road.length_m == 200
    assert len(fake.calls) == 2
    assert "invalid" in fake.calls[1].messages[-1]["content"].lower()


def test_parse_gives_up_after_retries() -> None:
    fake = FakeLLM([text_result("bad"), text_result("bad"), text_result("bad")])
    with pytest.raises(ParseError):
        parse(fake, "brief", retries=2)

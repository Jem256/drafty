"""Clarifying questions and answer merging."""

from __future__ import annotations

import specs
from drafty.agent.clarify import merge_answers, phrase_questions
from drafty.agent.fake_llm import FakeLLM, json_result, text_result


def test_phrase_questions() -> None:
    fake = FakeLLM([text_result("What design rainfall should I use?")])
    assert phrase_questions(fake, ["rainfall?"]) == "What design rainfall should I use?"


def test_phrase_questions_empty_skips_model() -> None:
    fake = FakeLLM([])
    assert phrase_questions(fake, []) == ""
    assert fake.calls == []


def test_merge_answers_returns_updated_brief() -> None:
    spec = specs.example_spec(with_data=False)
    fake = FakeLLM([json_result(specs.parsed_example(with_data=True))])
    result = merge_answers(fake, spec, {"rainfall": "100 mm/h, 10-year"})
    assert result.rainfall.intensity_mm_per_hr == 100.0

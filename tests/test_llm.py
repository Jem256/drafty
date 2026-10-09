"""LLM client: role routing, structured output, fallback, retries, budget and trace."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from drafty.agent.budget import Budget, BudgetExceeded, reset_daily_usage
from drafty.agent.llm import LLM, ModelsConfig, TransientLLMError
from drafty.agent.trace import Tracer
from drafty.storage.db import Database


class RoadSection(BaseModel):
    carriageway_width_m: float
    camber: str


class _FakeCompletions:
    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.kwargs: list[dict] = []

    def create(self, **kwargs):
        self.kwargs.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeClient:
    def __init__(self, responses: list) -> None:
        self.completions = _FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)

    @property
    def kwargs(self) -> list[dict]:
        return self.completions.kwargs


def make_response(content=None, tool_calls=None, tokens_in=10, tokens_out=5):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out)
    return SimpleNamespace(choices=[choice], usage=usage)


def make_tool_call(name: str, arguments: dict, call_id: str = "call-1"):
    function = SimpleNamespace(name=name, arguments=json.dumps(arguments))
    return SimpleNamespace(id=call_id, function=function)


@pytest.fixture(autouse=True)
def _reset_daily():
    reset_daily_usage()
    yield
    reset_daily_usage()


def test_resolve_models_per_setup(models_config) -> None:
    routed = LLM(setup="routed", config=models_config, client=_FakeClient([]))
    assert routed.resolve_model("parse") == "test-nemotron-ultra"
    assert routed.resolve_model("draft") == "test-nemotron-super"
    assert routed.resolve_model("label") == "test-nemotron-nano"
    all_ultra = LLM(setup="all_ultra", config=models_config, client=_FakeClient([]))
    assert all_ultra.resolve_model("draft") == "test-nemotron-ultra"


def test_unconfigured_model_raises() -> None:
    config = ModelsConfig(
        {
            "models": {"ultra": "REPLACE_ME_nemotron", "super": "s", "nano": "n"},
            "setups": {"routed": {"parse": "ultra"}},
        }
    )
    llm = LLM(setup="routed", config=config, client=_FakeClient([]))
    with pytest.raises(ValueError):
        llm.resolve_model("parse")


def test_json_schema_response_format_and_prompt(models_config) -> None:
    content = '{"carriageway_width_m": 6.0, "camber": "crown"}'
    client = _FakeClient([make_response(content=content)])
    llm = LLM(setup="routed", config=models_config, client=client)
    result = llm.complete(
        "parse", [{"role": "user", "content": "6 m road"}], response_schema=RoadSection
    )
    assert result.parsed is not None
    assert result.parsed.carriageway_width_m == 6.0
    kwargs = client.kwargs[0]
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["model"] == "test-nemotron-ultra"
    system = [message for message in kwargs["messages"] if message["role"] == "system"]
    assert system and "JSON schema" in system[0]["content"]


def test_json_mode_false_uses_prompt_only(models_config) -> None:
    content = '{"carriageway_width_m": 6.0, "camber": "crown"}'
    client = _FakeClient([make_response(content=content)])
    llm = LLM(setup="routed", config=models_config, client=client)
    llm.complete("label", [{"role": "user", "content": "6 m road"}], response_schema=RoadSection)
    kwargs = client.kwargs[0]
    assert "response_format" not in kwargs
    system = [message for message in kwargs["messages"] if message["role"] == "system"]
    assert "Return only JSON" in system[0]["content"]


def test_retry_on_transient_error(models_config) -> None:
    client = _FakeClient(
        [TransientLLMError("boom"), TransientLLMError("boom"), make_response(content="ok")]
    )
    llm = LLM(setup="all_super", config=models_config, client=client)
    result = llm.complete("explain", [{"role": "user", "content": "hi"}])
    assert result.content == "ok"
    assert len(client.kwargs) == 3


def test_budget_exceeded(models_config) -> None:
    budget = Budget(run_token_budget=10)
    client = _FakeClient([make_response(content="ok", tokens_in=8, tokens_out=5)])
    llm = LLM(setup="all_super", config=models_config, client=client, budget=budget)
    with pytest.raises(BudgetExceeded):
        llm.complete("explain", [{"role": "user", "content": "hi"}])


def test_trace_event_written(models_config, tmp_path) -> None:
    db = Database(tmp_path / "drafty.db")
    db.create_run("r-1")
    tracer = Tracer(db, "r-1")
    client = _FakeClient([make_response(content="ok", tokens_in=12, tokens_out=7)])
    llm = LLM(setup="all_super", config=models_config, client=client, tracer=tracer)
    llm.complete("explain", [{"role": "user", "content": "hi"}])
    events = db.list_trace_events("r-1")
    assert len(events) == 1
    assert events[0].tokens_in == 12
    assert events[0].tokens_out == 7
    assert events[0].latency_ms is not None
    assert events[0].model == "test-nemotron-super"
    db.close()


def test_tool_calls_parsed(models_config) -> None:
    calls = [make_tool_call("add_side_drain", {"side": "left"})]
    client = _FakeClient([make_response(content=None, tool_calls=calls)])
    llm = LLM(setup="routed", config=models_config, client=client)
    tools = [{"type": "function", "function": {"name": "add_side_drain"}}]
    result = llm.complete("draft", [{"role": "user", "content": "draft"}], tools=tools)
    assert result.tool_calls[0].name == "add_side_drain"
    assert result.tool_calls[0].arguments == {"side": "left"}
    assert client.kwargs[0]["tool_choice"] == "auto"

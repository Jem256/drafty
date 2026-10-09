"""A scripted stand-in model with the same ``complete`` interface as :class:`LLM`.

Used by every offline agent test. It replays a list of canned results and records the calls it
received, so tests can assert on both the script and the conversation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from drafty.agent.llm import LLMResult, ToolCall


@dataclass
class FakeCall:
    role: str
    messages: list[dict[str, Any]]
    response_schema: type[BaseModel] | None
    tools: list[dict[str, Any]] | None
    tool_choice: Any


def text_result(content: str, tokens_in: int = 0, tokens_out: int = 0) -> LLMResult:
    return LLMResult(
        content=content,
        parsed=None,
        tool_calls=[],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=0.0,
    )


def json_result(instance: BaseModel, tokens_in: int = 0, tokens_out: int = 0) -> LLMResult:
    return LLMResult(
        content=instance.model_dump_json(),
        parsed=instance,
        tool_calls=[],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=0.0,
    )


def tool_call_result(
    calls: list[tuple[str, dict[str, Any]]],
    content: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> LLMResult:
    tool_calls = [
        ToolCall(id=f"call-{index}", name=name, arguments=arguments)
        for index, (name, arguments) in enumerate(calls)
    ]
    return LLMResult(
        content=content,
        parsed=None,
        tool_calls=tool_calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=0.0,
    )


class FakeLLM:
    """Replays canned results; raises ``IndexError`` when the script runs out."""

    def __init__(self, script: list[LLMResult] | None = None) -> None:
        self.script: list[LLMResult] = list(script or [])
        self.calls: list[FakeCall] = []
        self._index = 0

    def queue(self, *results: LLMResult) -> None:
        self.script.extend(results)

    def complete(
        self,
        role: str,
        messages: list[dict[str, Any]],
        *,
        response_schema: type[BaseModel] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
    ) -> LLMResult:
        self.calls.append(
            FakeCall(
                role=role,
                messages=list(messages),
                response_schema=response_schema,
                tools=tools,
                tool_choice=tool_choice,
            )
        )
        if self._index >= len(self.script):
            raise IndexError(f"FakeLLM script exhausted after {self._index} call(s)")
        result = self.script[self._index]
        self._index += 1
        return result

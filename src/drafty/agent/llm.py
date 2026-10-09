"""The single path for every model call.

Loads ``config/models.yaml``, resolves a call role to a model id and per-role settings, calls Token
Factory through the ``openai`` SDK, retries transient failures, charges the budget and logs a trace
event. No other module calls a model SDK directly.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from drafty import settings as settings_module

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
RETRYABLE_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


class TransientLLMError(RuntimeError):
    """A retryable failure from the model provider."""


@dataclass(frozen=True)
class RoleSettings:
    temperature: float
    max_tokens: int


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResult:
    content: str | None
    parsed: BaseModel | None
    tool_calls: list[ToolCall]
    tokens_in: int
    tokens_out: int
    latency_ms: float


class ModelsConfig:
    """The role -> model mapping, role settings and capability flags."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @classmethod
    def load(cls, path: str | Path) -> ModelsConfig:
        with open(path, encoding="utf-8") as handle:
            return cls(yaml.safe_load(handle) or {})

    @property
    def base_url(self) -> str:
        return self._data.get("provider", {}).get("base_url", DEFAULT_BASE_URL)

    @property
    def api_key_env(self) -> str:
        return self._data.get("provider", {}).get("api_key_env", "NEBIUS_API_KEY")

    def model_key(self, setup: str, role: str) -> str:
        try:
            return self._data["setups"][setup][role]
        except KeyError as exc:
            raise KeyError(f"no model for setup {setup!r} and role {role!r}") from exc

    def model_id(self, setup: str, role: str) -> str:
        key = self.model_key(setup, role)
        model_id = self._data.get("models", {}).get(key)
        if not model_id or str(model_id).startswith("REPLACE_ME"):
            raise ValueError(
                f"model id for {key!r} is not configured in models.yaml; "
                "run scripts/list_models.py and fill it in"
            )
        return str(model_id)

    def role_settings(self, role: str) -> RoleSettings:
        raw = self._data.get("roles", {}).get(role, {})
        return RoleSettings(
            temperature=float(raw.get("temperature", 0.0)),
            max_tokens=int(raw.get("max_tokens", 1024)),
        )

    def capabilities(self, setup: str, role: str) -> dict[str, Any]:
        return self._data.get("capabilities", {}).get(self.model_key(setup, role), {})

    def limit(self, name: str, default: Any = None) -> Any:
        return self._data.get("limits", {}).get(name, default)


def _prompt_hash(messages: list[dict[str, Any]]) -> str:
    payload = json.dumps(messages, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _prepare_messages(
    messages: list[dict[str, Any]], response_schema: type[BaseModel] | None, json_mode: bool
) -> list[dict[str, Any]]:
    prepared = [dict(message) for message in messages]
    if response_schema is None:
        return prepared
    schema_text = json.dumps(response_schema.model_json_schema())
    instruction = "Respond with JSON only, matching this JSON schema:\n" + schema_text
    if not json_mode:
        instruction = "Return only JSON, with no prose or code fences.\n" + instruction
    if prepared and prepared[0].get("role") == "system":
        prepared[0]["content"] = f"{prepared[0].get('content', '')}\n\n{instruction}"
    else:
        prepared.insert(0, {"role": "system", "content": instruction})
    return prepared


def _to_result(response: Any, response_schema: type[BaseModel] | None) -> LLMResult:
    message = response.choices[0].message
    content = message.content
    tool_calls: list[ToolCall] = []
    for call in getattr(message, "tool_calls", None) or []:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        tool_calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))

    parsed = None
    if response_schema is not None and content:
        try:
            parsed = response_schema.model_validate_json(content)
        except ValueError:
            parsed = None

    usage = getattr(response, "usage", None)
    return LLMResult(
        content=content,
        parsed=parsed,
        tool_calls=tool_calls,
        tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
        tokens_out=getattr(usage, "completion_tokens", 0) or 0,
        latency_ms=0.0,
    )


@retry(
    retry=retry_if_exception_type(TransientLLMError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=0.05, max=1.0),
    reraise=True,
)
def _create(client: Any, kwargs: dict[str, Any]) -> Any:
    try:
        return client.chat.completions.create(**kwargs)
    except RETRYABLE_EXCEPTIONS as exc:
        raise TransientLLMError(str(exc)) from exc


class LLM:
    """Resolves roles and calls Token Factory."""

    def __init__(
        self,
        setup: str = "routed",
        *,
        config: ModelsConfig | None = None,
        config_path: str | Path | None = None,
        client: Any = None,
        tracer: Any = None,
        budget: Any = None,
        max_concurrency: int | None = None,
        api_key: str | None = None,
    ) -> None:
        if config is None:
            config = ModelsConfig.load(config_path or settings_module.settings.models_path)
        self.config = config
        self.setup = setup
        self.tracer = tracer
        self.budget = budget

        if client is None:
            key = api_key or os.environ.get(config.api_key_env)
            if not key:
                raise RuntimeError(f"{config.api_key_env} is not set")
            client = OpenAI(base_url=config.base_url, api_key=key)
        self.client = client

        concurrency = max_concurrency or settings_module.settings.max_concurrency
        self._semaphore = threading.Semaphore(concurrency)

    def resolve_model(self, role: str) -> str:
        return self.config.model_id(self.setup, role)

    def complete(
        self,
        role: str,
        messages: list[dict[str, Any]],
        *,
        response_schema: type[BaseModel] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
    ) -> LLMResult:
        model_id = self.resolve_model(role)
        role_settings = self.config.role_settings(role)
        json_mode = bool(self.config.capabilities(self.setup, role).get("json_mode", True))

        prepared = _prepare_messages(messages, response_schema, json_mode)
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": prepared,
            "temperature": role_settings.temperature,
            "max_tokens": role_settings.max_tokens,
        }
        if response_schema is not None and json_mode:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": response_schema.model_json_schema(),
                    "strict": False,
                },
            }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        started = time.perf_counter()
        with self._semaphore:
            response = _create(self.client, kwargs)
        latency_ms = (time.perf_counter() - started) * 1000.0

        result = _to_result(response, response_schema)
        result.latency_ms = latency_ms

        if self.budget is not None:
            self.budget.charge(result.tokens_in, result.tokens_out)
        if self.tracer is not None:
            self.tracer.emit(
                role=role,
                model=model_id,
                prompt_hash=_prompt_hash(prepared),
                request=prepared,
                response=result.content,
                tool_calls=[
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in result.tool_calls
                ]
                or None,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                latency_ms=latency_ms,
            )
        return result

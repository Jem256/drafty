"""Classify an incoming message (Nano). Retries once, then falls back to ``other``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from drafty.agent.prompt_loader import load_prompt

RouteLabelValue = Literal["new_brief", "answer", "change_request", "other"]


class RouteLabel(BaseModel):
    label: RouteLabelValue


def route(llm, message: str) -> str:
    """Return the routing label for a message."""
    system = load_prompt("route.txt")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]
    result = llm.complete("route", messages, response_schema=RouteLabel)
    if result.parsed is not None:
        return result.parsed.label
    retry = llm.complete("route", messages, response_schema=RouteLabel)
    if retry.parsed is not None:
        return retry.parsed.label
    return "other"

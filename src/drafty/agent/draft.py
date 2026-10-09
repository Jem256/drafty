"""Initial layout drafting via tool calls (Super), with cascade to a fallback model (Ultra)."""

from __future__ import annotations

import json

from drafty.agent.prompt_loader import load_prompt
from drafty.agent.tools import (
    SpecWorkspace,
    ToolContext,
    ToolResult,
    dispatch,
    tool_definitions,
)
from drafty.engine.standards import Standards
from drafty.spec.models import DesignSpec

MAX_TURNS = 12


def _assistant_tool_message(result) -> dict:
    return {
        "role": "assistant",
        "content": result.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in result.tool_calls
        ],
    }


def spec_is_valid(spec: DesignSpec) -> bool:
    """A draft is valid when it re-validates and has at least one drain."""
    try:
        DesignSpec.model_validate(spec.model_dump())
    except Exception:  # noqa: BLE001 - any validation failure makes the draft invalid
        return False
    return bool(spec.drains)


def draft(
    llm,
    brief: str,
    spec: DesignSpec,
    *,
    standards: Standards,
    invalid_before_cascade: int = 2,
    max_turns: int = MAX_TURNS,
) -> tuple[DesignSpec, list[ToolResult]]:
    """Run the drafting tool loop and return the updated spec and the tool results."""
    workspace = SpecWorkspace(spec)
    ctx = ToolContext(workspace, standards)
    messages: list[dict] = [
        {"role": "system", "content": load_prompt("draft.txt")},
        {"role": "user", "content": brief},
    ]
    tools = tool_definitions()
    role = "draft"
    invalid = 0
    changes: list[ToolResult] = []

    for _ in range(max_turns):
        result = llm.complete(role, messages, tools=tools)
        if not result.tool_calls:
            break
        messages.append(_assistant_tool_message(result))
        finished = False
        for call in result.tool_calls:
            outcome = dispatch(ctx, call.name, call.arguments)
            changes.append(outcome)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": outcome.message})
            if call.name == "finish":
                finished = True
        if finished:
            break
        if not spec_is_valid(workspace.spec):
            invalid += 1
            if invalid >= invalid_before_cascade:
                role = "draft_fallback"
    return workspace.spec, changes

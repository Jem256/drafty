"""Revision of a failing design via tool calls (Ultra).

One round is one model turn ending in ``finish``. Only design sections may change; the road,
rainfall and catchments are locked. The revision context is compact: current design, failing checks
and the last changes only.
"""

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
from drafty.spec.models import CheckResult, DesignSpec

MAX_TURNS = 6
LOCKED_GROUPS = {"road", "rainfall", "catchments"}


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


def _revision_context(
    spec: DesignSpec,
    failing: list[CheckResult],
    last_changes: list[str] | None,
    round_number: int,
) -> str:
    design = {
        "drains": [drain.model_dump() for drain in spec.drains],
        "culverts": [culvert.model_dump() for culvert in spec.culverts],
    }
    failing_text = "\n".join(
        f"- {check.rule_id} {check.element_id}: {check.message}" for check in failing
    )
    return (
        f"Revision round {round_number}. Fix the failing checks by changing drains, linings, "
        "gradients, splits, outlets or culvert sizes only.\n\n"
        f"Current design:\n{json.dumps(design)}\n\n"
        f"Failing checks:\n{failing_text or '- none'}\n\n"
        f"Last changes: {last_changes or 'none'}"
    )


def revise(
    llm,
    spec: DesignSpec,
    checks: list[CheckResult],
    *,
    standards: Standards,
    round_number: int = 1,
    last_changes: list[str] | None = None,
    max_turns: int = MAX_TURNS,
) -> tuple[DesignSpec, list[ToolResult]]:
    """Run one revision round and return the updated spec and the tool results."""
    failing = [check for check in checks if check.status == "fail"]
    workspace = SpecWorkspace(spec, locked=set(LOCKED_GROUPS))
    ctx = ToolContext(workspace, standards)
    messages: list[dict] = [
        {"role": "system", "content": load_prompt("revise.txt")},
        {"role": "user", "content": _revision_context(spec, failing, last_changes, round_number)},
    ]
    tools = tool_definitions()
    changes: list[ToolResult] = []

    for _ in range(max_turns):
        result = llm.complete("revise", messages, tools=tools)
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
    return workspace.spec, changes

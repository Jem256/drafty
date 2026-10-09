"""Live Token Factory tests. Marked ``live``; skipped without NEBIUS_API_KEY.

Run with: ``uv run pytest -m live``
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from drafty import settings
from drafty.agent.llm import LLM, ModelsConfig

pytestmark = pytest.mark.live

requires_key = pytest.mark.skipif(
    not os.getenv("NEBIUS_API_KEY"), reason="NEBIUS_API_KEY is not set"
)


class RoadSection(BaseModel):
    carriageway_width_m: float
    camber: str


MANNING_TOOL = {
    "type": "function",
    "function": {
        "name": "compute_manning_capacity",
        "description": "Compute Manning capacity. Units: m2, m, m/m, dimensionless.",
        "parameters": {
            "type": "object",
            "properties": {
                "area_m2": {"type": "number"},
                "wetted_perimeter_m": {"type": "number"},
                "slope": {"type": "number"},
                "n": {"type": "number"},
            },
            "required": ["area_m2", "wetted_perimeter_m", "slope", "n"],
        },
    },
}


def _llm() -> LLM:
    return LLM(setup="routed", config=ModelsConfig.load(settings.settings.models_path))


@requires_key
@pytest.mark.parametrize("role", ["parse", "draft", "label"])
def test_json_schema_output(role: str) -> None:
    result = _llm().complete(
        role,
        [{"role": "user", "content": "A 6 m carriageway with a crown camber."}],
        response_schema=RoadSection,
    )
    assert result.parsed is not None
    assert result.parsed.carriageway_width_m > 0


@requires_key
@pytest.mark.parametrize("role", ["parse", "draft", "label"])
def test_tool_calling(role: str) -> None:
    result = _llm().complete(
        role,
        [
            {
                "role": "user",
                "content": (
                    "Call compute_manning_capacity with area 0.36, perimeter 1.8, "
                    "slope 0.01, n 0.015."
                ),
            }
        ],
        tools=[MANNING_TOOL],
        tool_choice={"type": "function", "function": {"name": "compute_manning_capacity"}},
    )
    assert result.tool_calls
    assert result.tool_calls[0].name == "compute_manning_capacity"

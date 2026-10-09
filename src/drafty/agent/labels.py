"""Short drawing notes, schedule labels and run summaries (Nano)."""

from __future__ import annotations

from drafty.agent.prompt_loader import load_prompt
from drafty.spec.models import DesignSpec


def label(llm, spec: DesignSpec) -> str:
    """Return short labels; fall back to the project name."""
    user = spec.project.name or "Drafty drainage design"
    if spec.road.length_m:
        user += f", {spec.road.length_m:g} m road"
    result = llm.complete(
        "label",
        [
            {"role": "system", "content": load_prompt("label.txt")},
            {"role": "user", "content": user},
        ],
    )
    return result.content or (spec.project.name or "Drafty design")

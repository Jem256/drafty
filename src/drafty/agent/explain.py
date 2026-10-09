"""Plain-language explanation of the design and its checks (Super)."""

from __future__ import annotations

from drafty.agent.prompt_loader import load_prompt
from drafty.spec.models import CheckResult, DesignSpec


def explain(llm, spec: DesignSpec, checks: list[CheckResult]) -> str:
    """Explain the design; fall back to the raw check log if the model returns nothing."""
    notable = [check for check in checks if check.status in ("fail", "warn")]
    user = "Summarise this drainage design and its checks for a site engineer."
    if spec.project.name:
        user += f" Project: {spec.project.name}."
    if notable:
        user += "\n\nNotable checks:\n" + "\n".join(
            f"- {check.rule_id} {check.element_id}: {check.message}" for check in notable
        )
    result = llm.complete(
        "explain",
        [
            {"role": "system", "content": load_prompt("explain.txt")},
            {"role": "user", "content": user},
        ],
    )
    if result.content:
        return result.content
    return (
        "\n".join(check.message for check in checks) or "No checks were recorded for this design."
    )

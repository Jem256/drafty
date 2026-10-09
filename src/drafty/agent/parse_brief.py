"""Parse a brief into a validated :class:`ParsedBrief` (Ultra).

On a validation failure the exact error is sent back to the model, up to ``retries`` times.
"""

from __future__ import annotations

from drafty.agent.prompt_loader import load_prompt
from drafty.spec.models import ParsedBrief


class ParseError(ValueError):
    """Raised when the brief cannot be parsed into a valid ParsedBrief."""


def parse(llm, brief: str, *, retries: int = 2) -> ParsedBrief:
    """Return a validated ParsedBrief or raise :class:`ParseError`."""
    system = load_prompt("parse.txt")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": brief},
    ]
    last_error = "the response was not valid JSON"
    for attempt in range(retries + 1):
        result = llm.complete("parse", messages, response_schema=ParsedBrief)
        if result.parsed is not None:
            return result.parsed
        last_error = result.parse_error or last_error
        if attempt < retries:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": brief},
                {"role": "assistant", "content": result.content or ""},
                {
                    "role": "user",
                    "content": (
                        f"That JSON was invalid: {last_error}. Reply with corrected JSON only."
                    ),
                },
            ]
    raise ParseError(last_error)

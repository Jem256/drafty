"""Phrase open questions (Nano) and merge answers into the spec (Ultra)."""

from __future__ import annotations

from drafty.agent.parse_brief import ParseError
from drafty.agent.prompt_loader import load_prompt
from drafty.spec.models import DesignSpec, ParsedBrief


def phrase_questions(llm, questions: list[str]) -> str:
    """Turn raw questions into short, answerable questions. Falls back to the raw list."""
    if not questions:
        return ""
    system = load_prompt("clarify.txt")
    result = llm.complete(
        "clarify",
        [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(questions)},
        ],
    )
    return result.content or "\n".join(questions)


def _answers_text(answers: dict[str, str] | str) -> str:
    if isinstance(answers, str):
        return answers
    return "\n".join(f"{key}: {value}" for key, value in answers.items())


def merge_answers(llm, spec: DesignSpec, answers: dict[str, str] | str) -> ParsedBrief:
    """Apply answers to the spec and return a validated ParsedBrief."""
    system = load_prompt("parse.txt")
    current = spec.model_dump_json(exclude={"meta", "results"})
    user = (
        f"Current spec:\n{current}\n\n"
        f"Engineer answers to the open questions:\n{_answers_text(answers)}\n\n"
        "Return the full corrected spec with the answers applied and the answered questions "
        "removed from open_questions. Do not invent values that were not answered."
    )
    result = llm.complete(
        "parse",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_schema=ParsedBrief,
    )
    if result.parsed is None:
        raise ParseError(result.parse_error or "could not apply the answers")
    return result.parsed

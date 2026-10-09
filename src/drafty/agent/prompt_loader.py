"""Load versioned prompt text files from ``agent/prompts/``."""

from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


@cache
def load_prompt(name: str) -> str:
    """Return the text of a prompt file, e.g. ``load_prompt("parse.txt")``."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")

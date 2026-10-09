"""Per-run token budget and a global daily cap.

Token counts come from the API usage fields. Exceeding either limit raises :class:`BudgetExceeded`,
which the controller turns into an escalation.
"""

from __future__ import annotations

from datetime import UTC, datetime


class BudgetExceeded(RuntimeError):
    """Raised when a token budget or the daily cap is exceeded."""


_DAILY_USAGE: dict[str, int] = {}


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def reset_daily_usage() -> None:
    """Clear the in-memory daily counter (used by tests)."""
    _DAILY_USAGE.clear()


class Budget:
    """Tracks spend against a per-run budget and the shared daily cap."""

    def __init__(self, run_token_budget: int | None = None, daily_token_cap: int | None = None):
        self.run_token_budget = run_token_budget
        self.daily_token_cap = daily_token_cap
        self.run_used = 0

    @property
    def daily_used(self) -> int:
        return _DAILY_USAGE.get(_today(), 0)

    def charge(self, tokens_in: int = 0, tokens_out: int = 0) -> None:
        """Add usage and raise if a limit is now exceeded."""
        total = (tokens_in or 0) + (tokens_out or 0)
        self.run_used += total
        day = _today()
        _DAILY_USAGE[day] = _DAILY_USAGE.get(day, 0) + total

        if self.run_token_budget is not None and self.run_used > self.run_token_budget:
            raise BudgetExceeded(
                f"run token budget of {self.run_token_budget} exceeded ({self.run_used} used)"
            )
        if self.daily_token_cap is not None and _DAILY_USAGE[day] > self.daily_token_cap:
            raise BudgetExceeded(
                f"daily token cap of {self.daily_token_cap} exceeded ({_DAILY_USAGE[day]} used)"
            )

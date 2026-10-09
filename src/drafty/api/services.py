"""Run service: starts controller runs in the background and exposes their state.

The API layer is thin; all run lifecycle logic lives here so it can be tested without HTTP.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from drafty.agent.budget import Budget
from drafty.agent.loop import Controller, RunOutcome
from drafty.api.ratelimit import RateLimiter
from drafty.engine.standards import Standards
from drafty.storage.db import Database
from drafty.storage.files import LocalFileStore

TERMINAL_STATES = {"done", "escalated", "failed"}


class RunService:
    """Owns the database, standards, model factory and run threads."""

    def __init__(
        self,
        *,
        db: Database,
        standards: Standards,
        llm_factory: Callable[[], Any],
        file_store: LocalFileStore,
        data_dir: str | Path,
        limits: dict | None = None,
        render: bool = True,
        rate_limiter: RateLimiter | None = None,
        daily_token_cap: int | None = None,
    ) -> None:
        self.db = db
        self.standards = standards
        self.llm_factory = llm_factory
        self.file_store = file_store
        self.data_dir = Path(data_dir)
        self.limits = limits or {}
        self.render = render
        self.rate_limiter = rate_limiter or RateLimiter()
        if daily_token_cap is not None:
            self.rate_limiter.daily_token_cap = daily_token_cap
        self.daily_token_cap = daily_token_cap
        self._cap_budget = Budget(daily_token_cap=daily_token_cap)
        self._outcomes: dict[str, RunOutcome] = {}
        self._controllers: dict[str, Controller] = {}
        self._threads: dict[str, threading.Thread] = {}

    @property
    def daily_used(self) -> int:
        return self._cap_budget.daily_used

    def _new_controller(self, run_id: str) -> Controller:
        return Controller(
            llm=self.llm_factory(),
            standards=self.standards,
            db=self.db,
            data_dir=self.data_dir,
            limits=self.limits,
            render=self.render,
            run_id=run_id,
        )

    def start(self, brief: str) -> str:
        """Create a run and start it in a background thread. Returns the run id at once."""
        run_id = f"r-{uuid4().hex[:8]}"
        self.db.create_run(run_id, state="received", brief=brief)
        thread = threading.Thread(target=self._start_run, args=(run_id, brief), daemon=True)
        self._threads[run_id] = thread
        thread.start()
        return run_id

    def resume(self, run_id: str, answers: dict[str, str] | str) -> None:
        """Resume a paused run in a background thread."""
        controller = self._controllers.get(run_id)
        if controller is None:
            raise KeyError(run_id)
        thread = threading.Thread(
            target=self._run, args=(run_id, controller.resume, answers), daemon=True
        )
        self._threads[run_id] = thread
        thread.start()

    def _start_run(self, run_id: str, brief: str) -> None:
        try:
            controller = self._new_controller(run_id)
            self._controllers[run_id] = controller
            self._run(run_id, controller.start, brief)
        except Exception as exc:  # noqa: BLE001 - e.g. the API key is not configured
            self._fail(run_id, exc)

    def _run(self, run_id: str, target: Callable, argument: Any) -> None:
        try:
            self._outcomes[run_id] = target(argument)
        except Exception as exc:  # noqa: BLE001 - a crashed run must be visible, not silent
            self._fail(run_id, exc)

    def _fail(self, run_id: str, exc: Exception) -> None:
        self.db.update_run_state(run_id, "failed")
        self._outcomes[run_id] = RunOutcome(
            run_id=run_id, state="failed", message=f"run failed: {exc}"
        )

    def wait(self, run_id: str, timeout: float = 30.0) -> None:
        thread = self._threads.get(run_id)
        if thread is not None:
            thread.join(timeout)

    def get_run(self, run_id: str) -> dict | None:
        run = self.db.get_run(run_id)
        if run is None:
            return None
        outcome = self._outcomes.get(run_id)
        return {
            "run_id": run_id,
            "state": run["state"],
            "brief": run.get("brief"),
            "message": outcome.message if outcome else None,
            "questions": outcome.questions if outcome else [],
            "spec": outcome.spec.model_dump(mode="json") if outcome and outcome.spec else None,
            "results": (
                outcome.results.model_dump(mode="json") if outcome and outcome.results else None
            ),
            "checks": [check.model_dump() for check in outcome.checks] if outcome else [],
            "outputs": outcome.outputs if outcome else {},
        }

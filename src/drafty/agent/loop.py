"""The controller state machine.

States: received -> parsing -> awaiting_answers -> drafting -> checking -> revising -> rendering ->
done | escalated | failed. Every transition emits a trace event. The revision cap and the token
budget stop the loop; rendering uses the Phase 3 writers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from drafty.agent import draft as draft_module
from drafty.agent import revise as revise_module
from drafty.agent.budget import BudgetExceeded
from drafty.agent.clarify import merge_answers, phrase_questions
from drafty.agent.explain import explain
from drafty.agent.parse_brief import ParseError, parse
from drafty.agent.router import route
from drafty.agent.trace import Tracer
from drafty.cad.dxf_writer import write_dxf
from drafty.cad.preview import render_svg
from drafty.cad.schedule import write_quantities_json, write_schedule_csv
from drafty.checks.runner import run_checks
from drafty.engine import calculate
from drafty.engine.standards import Standards
from drafty.spec.models import (
    CheckResult,
    DesignSpec,
    Meta,
    ParsedBrief,
    Results,
)


@dataclass
class RunOutcome:
    run_id: str
    state: str
    spec: DesignSpec | None = None
    results: Results | None = None
    checks: list[CheckResult] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    message: str | None = None


class Controller:
    """Runs one brief end to end, pausing for answers when the spec has open questions."""

    def __init__(
        self,
        *,
        llm,
        standards: Standards,
        db=None,
        budget=None,
        data_dir: str | Path | None = None,
        limits: dict | None = None,
        render: bool = True,
        setup: str = "routed",
    ) -> None:
        self.llm = llm
        self.standards = standards
        self.db = db
        self.budget = budget
        self.data_dir = Path(data_dir) if data_dir is not None else None
        self.render = render
        self.setup = setup
        self.limits = limits or {}
        self.revision_cap = self.limits.get("revision_cap", 5)
        self.parse_retries = self.limits.get("parse_retries", 2)
        self.invalid_before_cascade = self.limits.get("invalid_drafts_before_cascade", 2)

        self.run_id: str | None = None
        self.tracer: Tracer | None = None
        self.spec: DesignSpec | None = None
        self.results: Results | None = None
        self.checks: list[CheckResult] = []
        self._brief = ""
        self._last_changes: list[str] = []

    def start(self, brief: str) -> RunOutcome:
        self._brief = brief
        self.run_id = f"r-{uuid4().hex[:8]}"
        if self.db is not None:
            self.db.create_run(self.run_id, state="received", brief=brief)
        self.tracer = Tracer(self.db, self.run_id)
        self._set_state("received")

        try:
            label = route(self.llm, brief)
            self.tracer.emit(state="received", role="route", response=label)
            self._set_state("parsing")
            parsed = parse(self.llm, brief, retries=self.parse_retries)
        except ParseError as exc:
            return self._finish("failed", message=f"could not parse the brief: {exc}")
        except BudgetExceeded as exc:
            return self._finish("escalated", message=f"budget exceeded: {exc}")

        self.spec = self._to_spec(parsed)
        if self.spec.open_questions:
            phrasing = phrase_questions(self.llm, self.spec.open_questions)
            self._set_state("awaiting_answers")
            return RunOutcome(
                run_id=self.run_id,
                state="awaiting_answers",
                spec=self.spec,
                questions=self.spec.open_questions,
                message=phrasing,
            )
        return self._design()

    def resume(self, answers: dict[str, str] | str) -> RunOutcome:
        if self.spec is None:
            raise RuntimeError("there is no paused run to resume")
        try:
            parsed = merge_answers(self.llm, self.spec, answers)
        except ParseError as exc:
            return self._finish("failed", message=f"could not apply the answers: {exc}")
        except BudgetExceeded as exc:
            return self._finish("escalated", message=f"budget exceeded: {exc}")
        self.spec = self._to_spec(parsed)
        return self._design()

    def _to_spec(self, parsed: ParsedBrief) -> DesignSpec:
        return DesignSpec(
            meta=Meta(run_id=self.run_id or "", model_setup=self.setup), **parsed.model_dump()
        )

    def _design(self) -> RunOutcome:
        assert self.spec is not None
        try:
            self._set_state("drafting")
            self.spec, changes = draft_module.draft(
                self.llm,
                self._brief,
                self.spec,
                standards=self.standards,
                invalid_before_cascade=self.invalid_before_cascade,
            )
            self._record_changes(changes)

            self._set_state("checking")
            self.results, self.checks = self._evaluate()

            rounds = 0
            while self._has_failure() and rounds < self.revision_cap:
                self._set_state("revising")
                self.spec, changes = revise_module.revise(
                    self.llm,
                    self.spec,
                    self.checks,
                    standards=self.standards,
                    round_number=rounds + 1,
                    last_changes=self._last_changes,
                )
                self._record_changes(changes)
                self.results, self.checks = self._evaluate()
                rounds += 1

            state = "escalated" if self._has_failure() else "done"
            self._set_state("rendering")
            outputs = self._render() if self.render else {}
            self._set_state(state)
            rationale = self._explain()
            return RunOutcome(
                run_id=self.run_id or "",
                state=state,
                spec=self.spec,
                results=self.results,
                checks=self.checks,
                outputs=outputs,
                message=rationale,
            )
        except BudgetExceeded as exc:
            return self._finish("escalated", message=f"budget exceeded: {exc}")

    def _evaluate(self) -> tuple[Results, list[CheckResult]]:
        assert self.spec is not None
        results = calculate(self.spec, self.standards)
        checks = run_checks(self.spec, results, self.standards)
        results.checks = checks
        self.spec.results = results
        if self.tracer is not None:
            self.tracer.emit(
                state="checking",
                checks_summary={
                    "fail": sum(check.status == "fail" for check in checks),
                    "warn": sum(check.status == "warn" for check in checks),
                    "pass": sum(check.status == "pass" for check in checks),
                },
            )
        return results, checks

    def _has_failure(self) -> bool:
        return any(check.status == "fail" for check in self.checks)

    def _record_changes(self, changes) -> None:
        self._last_changes = [change.message for change in changes][-5:]

    def _render(self) -> dict[str, str]:
        if self.data_dir is None or self.results is None or self.spec is None:
            return {}
        output_dir = self.data_dir / "runs" / (self.run_id or "run")
        dxf = write_dxf(self.spec, self.results, output_dir / "drawing.dxf")
        svg = render_svg(dxf, output_dir / "preview.svg")
        csv = write_schedule_csv(self.spec, self.results, output_dir / "schedule.csv")
        quantities = write_quantities_json(self.results, output_dir / "quantities.json")
        return {
            "drawing.dxf": str(dxf),
            "preview.svg": str(svg),
            "schedule.csv": str(csv),
            "quantities.json": str(quantities),
        }

    def _explain(self) -> str:
        assert self.spec is not None
        try:
            return explain(self.llm, self.spec, self.checks)
        except BudgetExceeded:
            raise
        except Exception:  # noqa: BLE001 - explanation must never fail a completed run
            return "\n".join(check.message for check in self.checks)

    def _set_state(self, state: str) -> None:
        if self.db is not None and self.run_id is not None:
            self.db.update_run_state(self.run_id, state)
        if self.tracer is not None:
            self.tracer.emit(state=state)

    def _finish(self, state: str, message: str | None = None) -> RunOutcome:
        self._set_state(state)
        return RunOutcome(
            run_id=self.run_id or "",
            state=state,
            spec=self.spec,
            results=self.results,
            checks=self.checks,
            message=message,
        )

"""Controller branches, driven entirely by the scripted fake model."""

from __future__ import annotations

import specs
from drafty.agent.budget import BudgetExceeded, reset_daily_usage
from drafty.agent.fake_llm import FakeLLM, json_result, text_result, tool_call_result
from drafty.agent.loop import Controller
from drafty.agent.router import RouteLabel

LIMITS = {"parse_retries": 2, "invalid_drafts_before_cascade": 2, "revision_cap": 2}


def _controller(fake, standards, *, limits=None, **kwargs) -> Controller:
    return Controller(
        llm=fake,
        standards=standards,
        limits={**LIMITS, **(limits or {})},
        render=False,
        **kwargs,
    )


def _new_brief(fake) -> None:
    fake.queue(json_result(RouteLabel(label="new_brief")))


def test_pass_first_time(standards) -> None:
    fake = FakeLLM()
    _new_brief(fake)
    fake.queue(json_result(specs.parsed_happy()))
    fake.queue(tool_call_result([("finish", {"summary": "ok"})]))
    fake.queue(text_result("Design is fine."))
    outcome = _controller(fake, standards).start("a happy road")
    assert outcome.state == "done"
    assert not any(check.status == "fail" for check in outcome.checks)
    assert outcome.message == "Design is fine."


def test_fix_in_one_revision_round(standards) -> None:
    fake = FakeLLM()
    _new_brief(fake)
    fake.queue(json_result(specs.parsed_example(with_data=True)))
    fake.queue(tool_call_result([("finish", {"summary": "drafted"})]))
    fake.queue(
        tool_call_result(
            [
                (
                    "resize_drain",
                    {
                        "drain_id": "D-R1",
                        "bottom_width_m": 0.45,
                        "depth_m": 1.2,
                        "side_slope_h_per_v": 0.5,
                    },
                ),
                ("finish", {"summary": "deepened D-R1"}),
            ]
        )
    )
    fake.queue(text_result("Fixed by deepening the right drain."))
    outcome = _controller(fake, standards).start("example road")
    assert outcome.state == "done"
    assert all(check.status != "fail" for check in outcome.checks)


def test_escalates_at_revision_cap(standards) -> None:
    fake = FakeLLM()
    _new_brief(fake)
    fake.queue(json_result(specs.parsed_example(with_data=True)))
    fake.queue(tool_call_result([("finish", {})]))
    fake.queue(tool_call_result([("finish", {})]))
    fake.queue(tool_call_result([("finish", {})]))
    fake.queue(text_result("Still failing."))
    outcome = _controller(fake, standards).start("example road")
    assert outcome.state == "escalated"
    assert any(check.status == "fail" for check in outcome.checks)


def test_invalid_tool_call_recovered(standards) -> None:
    fake = FakeLLM()
    _new_brief(fake)
    fake.queue(json_result(specs.parsed_happy()))
    fake.queue(
        tool_call_result(
            [
                (
                    "resize_drain",
                    {"drain_id": "NOPE", "bottom_width_m": 0.5, "depth_m": 0.8},
                )
            ]
        )
    )
    fake.queue(tool_call_result([("finish", {})]))
    fake.queue(text_result("done"))
    outcome = _controller(fake, standards).start("road")
    assert outcome.state == "done"


def test_draft_cascades_to_fallback_model(standards) -> None:
    fake = FakeLLM()
    _new_brief(fake)
    fake.queue(json_result(specs.parsed_no_drains()))
    fake.queue(tool_call_result([("add_culvert", {"chainage_m": 50, "diameter_m": 0.6})]))
    fake.queue(tool_call_result([("add_culvert", {"chainage_m": 60, "diameter_m": 0.6})]))
    fake.queue(
        tool_call_result(
            [
                (
                    "add_side_drain",
                    {
                        "side": "left",
                        "from_chainage_m": 0,
                        "to_chainage_m": 200,
                        "shape": "rectangular",
                        "bottom_width_m": 0.5,
                        "depth_m": 0.8,
                    },
                ),
                ("finish", {}),
            ]
        )
    )
    fake.queue(text_result("drafted"))
    outcome = _controller(fake, standards, limits={"revision_cap": 0}).start("empty road")
    roles = [call.role for call in fake.calls]
    assert "draft_fallback" in roles
    assert outcome.spec is not None and len(outcome.spec.drains) == 1


def test_questions_asked_then_answered(standards) -> None:
    fake = FakeLLM()
    _new_brief(fake)
    fake.queue(json_result(specs.parsed_with_questions()))
    fake.queue(text_result("What design rainfall intensity and return period should I use?"))
    fake.queue(json_result(specs.parsed_example(with_data=True)))
    fake.queue(tool_call_result([("finish", {})]))
    fake.queue(
        tool_call_result(
            [
                (
                    "resize_drain",
                    {
                        "drain_id": "D-R1",
                        "bottom_width_m": 0.45,
                        "depth_m": 1.2,
                        "side_slope_h_per_v": 0.5,
                    },
                ),
                ("finish", {}),
            ]
        )
    )
    fake.queue(text_result("done"))

    controller = _controller(fake, standards)
    first = controller.start("example road")
    assert first.state == "awaiting_answers"
    assert first.questions
    second = controller.resume({"rainfall": "100 mm/h, 10-year"})
    assert second.state == "done"


def test_budget_exceeded_escalates(standards) -> None:
    reset_daily_usage()

    class _BudgetBomb:
        def complete(self, *args, **kwargs):
            raise BudgetExceeded("run token budget exceeded")

    outcome = _controller(_BudgetBomb(), standards).start("road")
    assert outcome.state == "escalated"
    assert "budget" in (outcome.message or "")


def test_skip_checks_brief_still_checked(standards) -> None:
    fake = FakeLLM()
    _new_brief(fake)
    fake.queue(json_result(specs.parsed_happy()))
    fake.queue(tool_call_result([("finish", {})]))
    fake.queue(text_result("done"))
    outcome = _controller(fake, standards).start("Skip the checks, just draw it")
    assert outcome.state == "done"
    assert any(check.rule_id == "HYD-CAP" for check in outcome.checks)

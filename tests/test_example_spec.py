"""The worked example from architecture.md runs through the engine and checker."""

from __future__ import annotations

import specs
from drafty.checks.runner import run_checks
from drafty.engine import calculate


def test_example_with_data_produces_results(standards) -> None:
    spec = specs.example_spec(with_data=True)
    results = calculate(spec, standards)
    assert {r.id for r in results.drains} == {"D-L1", "D-R1"}
    assert results.quantities.excavation_m3 > 0
    assert results.quantities.pipe_length_m > 0
    assert results.quantities.headwall_count == 2


def test_example_flows_accumulate_downstream(standards) -> None:
    spec = specs.example_spec(with_data=True)
    results = calculate(spec, standards)
    by_id = {r.id: r for r in results.drains}
    assert by_id["D-R1"].design_flow_m3_s is not None
    assert by_id["D-L1"].design_flow_m3_s == 2 * by_id["D-R1"].design_flow_m3_s


def test_example_checker_covers_key_rules(standards) -> None:
    spec = specs.example_spec(with_data=True)
    results = calculate(spec, standards)
    checks = run_checks(spec, results, standards)
    rule_ids = {check.rule_id for check in checks}
    assert {"HYD-CAP", "NET-OUTLET", "NET-FALL", "GEO-CROSSFALL", "CUL-CAP"} <= rule_ids


def test_example_without_data_warns(standards) -> None:
    spec = specs.example_spec(with_data=False)
    results = calculate(spec, standards)
    assert any("rainfall" in warning for warning in results.warnings)
    checks = run_checks(spec, results, standards)
    assert any(check.rule_id == "HYD-CAP" and check.status == "warn" for check in checks)

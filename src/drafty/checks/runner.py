"""Runs every check rule and collects the results."""

from __future__ import annotations

from collections.abc import Callable

from drafty.checks import rules
from drafty.engine.standards import Standards
from drafty.spec.models import CheckResult, DesignSpec, Results

Rule = Callable[[DesignSpec, Results, Standards], list[CheckResult]]

ALL_RULES: list[Rule] = [
    rules.check_hyd_cap,
    rules.check_hyd_vmin,
    rules.check_hyd_vmax,
    rules.check_hyd_freeboard,
    rules.check_cul_cap,
    rules.check_cul_dmin,
    rules.check_cul_cover,
    rules.check_cul_fall,
    rules.check_net_outlet,
    rules.check_net_fall,
    rules.check_geo_depth,
    rules.check_geo_crossfall,
    rules.check_con_site,
    rules.check_cad_layers,
]


def run_checks(
    spec: DesignSpec,
    results: Results,
    standards: Standards,
    dxf_path: str | None = None,
) -> list[CheckResult]:
    """Run all rules and return their results in order.

    ``dxf_path`` is passed to CAD-LAYERS when a drawing has been written.
    """
    checks: list[CheckResult] = []
    for rule in ALL_RULES:
        if rule is rules.check_cad_layers:
            checks.extend(rule(spec, results, standards, dxf_path))
        else:
            checks.extend(rule(spec, results, standards))
    return checks

"""Every checker rule has a passing and a failing case (plus warn where relevant)."""

from __future__ import annotations

import specs
from drafty.checks import rules
from drafty.spec.models import Constraint, Outlet


def _cycle_spec():
    spec = specs.happy_spec()
    spec.drains[0].outlet = Outlet(type="drain", ref="D-R1")
    spec.drains[1].outlet = Outlet(type="drain", ref="D-L1")
    return spec


def test_hyd_cap(standards) -> None:
    spec = specs.happy_spec()
    passing = specs.drain_results(capacity_m3_s=1.0, design_flow_m3_s=0.5)
    failing = specs.drain_results(capacity_m3_s=0.2, design_flow_m3_s=0.5)
    unknown = specs.drain_results(capacity_m3_s=1.0, design_flow_m3_s=None)
    assert rules.check_hyd_cap(spec, passing, standards)[0].status == "pass"
    assert rules.check_hyd_cap(spec, failing, standards)[0].status == "fail"
    assert rules.check_hyd_cap(spec, unknown, standards)[0].status == "warn"


def test_hyd_vmin(standards) -> None:
    spec = specs.happy_spec()
    assert (
        rules.check_hyd_vmin(spec, specs.drain_results(velocity_m_s=1.0), standards)[0].status
        == "pass"
    )
    assert (
        rules.check_hyd_vmin(spec, specs.drain_results(velocity_m_s=0.3), standards)[0].status
        == "fail"
    )


def test_hyd_vmax(standards) -> None:
    spec = specs.one_drain_spec("concrete")
    assert (
        rules.check_hyd_vmax(spec, specs.drain_results(velocity_m_s=2.0), standards)[0].status
        == "pass"
    )
    assert (
        rules.check_hyd_vmax(spec, specs.drain_results(velocity_m_s=5.0), standards)[0].status
        == "fail"
    )


def test_hyd_freeboard(standards) -> None:
    spec = specs.happy_spec()
    assert (
        rules.check_hyd_freeboard(spec, specs.drain_results(freeboard_m=0.2), standards)[0].status
        == "pass"
    )
    assert (
        rules.check_hyd_freeboard(spec, specs.drain_results(freeboard_m=0.05), standards)[0].status
        == "fail"
    )


def test_cul_cap(standards) -> None:
    spec = specs.culvert_spec()
    passing = specs.culvert_results(capacity_m3_s=1.0, design_flow_m3_s=0.5)
    failing = specs.culvert_results(capacity_m3_s=0.2, design_flow_m3_s=0.5)
    assert rules.check_cul_cap(spec, passing, standards)[0].status == "pass"
    assert rules.check_cul_cap(spec, failing, standards)[0].status == "fail"


def test_cul_dmin(standards) -> None:
    assert (
        rules.check_cul_dmin(specs.culvert_spec(0.6), specs.culvert_results(), standards)[0].status
        == "pass"
    )
    assert (
        rules.check_cul_dmin(specs.culvert_spec(0.3), specs.culvert_results(), standards)[0].status
        == "fail"
    )


def test_cul_cover(standards) -> None:
    spec = specs.culvert_spec()
    assert (
        rules.check_cul_cover(spec, specs.culvert_results(cover_m=1.0), standards)[0].status
        == "pass"
    )
    assert (
        rules.check_cul_cover(spec, specs.culvert_results(cover_m=0.2), standards)[0].status
        == "fail"
    )


def test_cul_fall(standards) -> None:
    spec = specs.culvert_spec()
    passing = specs.culvert_results(invert_in_m=99.0, invert_out_m=98.5)
    failing = specs.culvert_results(invert_in_m=99.0, invert_out_m=99.5)
    assert rules.check_cul_fall(spec, passing, standards)[0].status == "pass"
    assert rules.check_cul_fall(spec, failing, standards)[0].status == "fail"


def test_net_outlet(standards) -> None:
    assert rules.check_net_outlet(specs.happy_spec(), None, standards)[0].status == "pass"
    assert rules.check_net_outlet(_cycle_spec(), None, standards)[0].status == "fail"


def test_net_fall(standards) -> None:
    spec = specs.happy_spec()
    passing = specs.drain_results(invert_up_m=100.0, invert_down_m=99.0)
    failing = specs.drain_results(invert_up_m=99.0, invert_down_m=100.0)
    assert rules.check_net_fall(spec, passing, standards)[0].status == "pass"
    assert rules.check_net_fall(spec, failing, standards)[0].status == "fail"


def test_geo_depth(standards) -> None:
    assert (
        rules.check_geo_depth(specs.one_drain_spec(depth=0.8), None, standards)[0].status == "pass"
    )
    assert (
        rules.check_geo_depth(specs.one_drain_spec(depth=1.5), None, standards)[0].status == "fail"
    )


def test_geo_crossfall(standards) -> None:
    assert rules.check_geo_crossfall(specs.happy_spec(), None, standards)[0].status == "pass"
    assert rules.check_geo_crossfall(specs.one_drain_spec(), None, standards)[0].status == "fail"


def test_con_site(standards) -> None:
    spec = specs.partial_drain_spec()
    spec.constraints = [
        Constraint(id="X1", type="no_drain", side="left", from_chainage_m=150, to_chainage_m=200)
    ]
    assert rules.check_con_site(spec, None, standards)[0].status == "pass"
    spec.constraints = [
        Constraint(id="X2", type="no_drain", side="left", from_chainage_m=0, to_chainage_m=50)
    ]
    assert rules.check_con_site(spec, None, standards)[0].status == "fail"

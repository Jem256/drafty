"""Individual engineering check rules.

Every rule returns a list of :class:`CheckResult`. Thresholds come only from the standards file; a
missing threshold produces ``warn``, never a guessed number. Messages say what to change.
"""

from __future__ import annotations

from drafty.cad import dxf_writer
from drafty.engine import network
from drafty.engine.standards import Standards
from drafty.spec.models import CheckResult, CheckStatus, DesignSpec, Results


def _result(
    rule_id: str,
    element_id: str,
    status: CheckStatus,
    measured: float | None,
    limit: float | None,
    message: str,
) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        element_id=element_id,
        status=status,
        measured=measured,
        limit=limit,
        message=message,
    )


def check_hyd_cap(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    out: list[CheckResult] = []
    for reach in results.drains:
        if reach.design_flow_m3_s is None:
            out.append(
                _result(
                    "HYD-CAP",
                    reach.id,
                    "warn",
                    None,
                    None,
                    f"HYD-CAP not checked on {reach.id}: design flow is unknown; set rainfall and "
                    "runoff coefficient.",
                )
            )
        elif reach.capacity_m3_s is None:
            out.append(
                _result(
                    "HYD-CAP",
                    reach.id,
                    "warn",
                    None,
                    None,
                    f"HYD-CAP not checked on {reach.id}: capacity is unknown; check the Manning n "
                    "and the drain gradient.",
                )
            )
        elif reach.capacity_m3_s >= reach.design_flow_m3_s:
            out.append(
                _result(
                    "HYD-CAP",
                    reach.id,
                    "pass",
                    reach.capacity_m3_s,
                    reach.design_flow_m3_s,
                    f"{reach.id} capacity {reach.capacity_m3_s:.3f} m3/s meets design flow "
                    f"{reach.design_flow_m3_s:.3f} m3/s.",
                )
            )
        else:
            out.append(
                _result(
                    "HYD-CAP",
                    reach.id,
                    "fail",
                    reach.capacity_m3_s,
                    reach.design_flow_m3_s,
                    f"HYD-CAP failed on {reach.id}: capacity {reach.capacity_m3_s:.3f} m3/s below "
                    f"design flow {reach.design_flow_m3_s:.3f} m3/s; enlarge the section, split "
                    "the reach or add an intermediate outlet.",
                )
            )
    return out


def check_hyd_vmin(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    minimum, _, _ = standards.get("velocity_min_m_s")
    out: list[CheckResult] = []
    for reach in results.drains:
        if minimum is None:
            out.append(
                _result(
                    "HYD-VMIN",
                    reach.id,
                    "warn",
                    reach.velocity_m_s,
                    None,
                    f"HYD-VMIN not checked on {reach.id}: no minimum velocity standard is set.",
                )
            )
        elif reach.velocity_m_s is None:
            out.append(
                _result(
                    "HYD-VMIN",
                    reach.id,
                    "warn",
                    None,
                    minimum,
                    f"HYD-VMIN not checked on {reach.id}: velocity is unknown.",
                )
            )
        elif reach.velocity_m_s >= minimum:
            out.append(
                _result(
                    "HYD-VMIN",
                    reach.id,
                    "pass",
                    reach.velocity_m_s,
                    minimum,
                    f"{reach.id} velocity {reach.velocity_m_s:.2f} m/s clears the minimum "
                    f"{minimum:.2f} m/s.",
                )
            )
        else:
            out.append(
                _result(
                    "HYD-VMIN",
                    reach.id,
                    "fail",
                    reach.velocity_m_s,
                    minimum,
                    f"HYD-VMIN failed on {reach.id}: velocity {reach.velocity_m_s:.2f} m/s below "
                    f"the self-cleansing minimum {minimum:.2f} m/s; narrow the section or steepen "
                    "the gradient.",
                )
            )
    return out


def check_hyd_vmax(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    lining_by_id = {drain.id: drain.lining for drain in spec.drains}
    out: list[CheckResult] = []
    for reach in results.drains:
        lining = lining_by_id.get(reach.id, "")
        maximum, _, _ = standards.get("velocity_max_m_s", lining)
        if maximum is None:
            out.append(
                _result(
                    "HYD-VMAX",
                    reach.id,
                    "warn",
                    reach.velocity_m_s,
                    None,
                    f"HYD-VMAX not checked on {reach.id}: no maximum velocity for '{lining}' "
                    "lining is set.",
                )
            )
        elif reach.velocity_m_s is None:
            out.append(
                _result(
                    "HYD-VMAX",
                    reach.id,
                    "warn",
                    None,
                    maximum,
                    f"HYD-VMAX not checked on {reach.id}: velocity is unknown.",
                )
            )
        elif reach.velocity_m_s <= maximum:
            out.append(
                _result(
                    "HYD-VMAX",
                    reach.id,
                    "pass",
                    reach.velocity_m_s,
                    maximum,
                    f"{reach.id} velocity {reach.velocity_m_s:.2f} m/s is within the "
                    f"{maximum:.2f} m/s limit for {lining}.",
                )
            )
        else:
            out.append(
                _result(
                    "HYD-VMAX",
                    reach.id,
                    "fail",
                    reach.velocity_m_s,
                    maximum,
                    f"HYD-VMAX failed on {reach.id}: velocity {reach.velocity_m_s:.2f} m/s exceeds "
                    f"the {maximum:.2f} m/s limit for {lining} lining; change the lining, add "
                    "drops or flatten the gradient.",
                )
            )
    return out


def check_hyd_freeboard(
    spec: DesignSpec, results: Results, standards: Standards
) -> list[CheckResult]:
    minimum, _, _ = standards.get("freeboard_min_m")
    out: list[CheckResult] = []
    for reach in results.drains:
        if minimum is None:
            out.append(
                _result(
                    "HYD-FREEBOARD",
                    reach.id,
                    "warn",
                    reach.freeboard_m,
                    None,
                    f"HYD-FREEBOARD not checked on {reach.id}: no minimum freeboard standard is "
                    "set.",
                )
            )
        elif reach.freeboard_m is None:
            out.append(
                _result(
                    "HYD-FREEBOARD",
                    reach.id,
                    "warn",
                    None,
                    minimum,
                    f"HYD-FREEBOARD not checked on {reach.id}: freeboard is unknown.",
                )
            )
        elif reach.freeboard_m >= minimum:
            out.append(
                _result(
                    "HYD-FREEBOARD",
                    reach.id,
                    "pass",
                    reach.freeboard_m,
                    minimum,
                    f"{reach.id} freeboard {reach.freeboard_m:.2f} m meets the minimum "
                    f"{minimum:.2f} m.",
                )
            )
        else:
            out.append(
                _result(
                    "HYD-FREEBOARD",
                    reach.id,
                    "fail",
                    reach.freeboard_m,
                    minimum,
                    f"HYD-FREEBOARD failed on {reach.id}: freeboard {reach.freeboard_m:.2f} m "
                    f"below the minimum {minimum:.2f} m; deepen the section.",
                )
            )
    return out


def check_cul_cap(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    out: list[CheckResult] = []
    for culvert in results.culverts:
        if culvert.design_flow_m3_s is None:
            out.append(
                _result(
                    "CUL-CAP",
                    culvert.id,
                    "warn",
                    None,
                    None,
                    f"CUL-CAP not checked on {culvert.id}: design flow is unknown.",
                )
            )
        elif culvert.capacity_m3_s is None:
            out.append(
                _result(
                    "CUL-CAP",
                    culvert.id,
                    "warn",
                    None,
                    None,
                    f"CUL-CAP not checked on {culvert.id}: capacity is unknown.",
                )
            )
        elif culvert.capacity_m3_s >= culvert.design_flow_m3_s:
            out.append(
                _result(
                    "CUL-CAP",
                    culvert.id,
                    "pass",
                    culvert.capacity_m3_s,
                    culvert.design_flow_m3_s,
                    f"{culvert.id} capacity {culvert.capacity_m3_s:.3f} m3/s meets design flow "
                    f"{culvert.design_flow_m3_s:.3f} m3/s.",
                )
            )
        else:
            out.append(
                _result(
                    "CUL-CAP",
                    culvert.id,
                    "fail",
                    culvert.capacity_m3_s,
                    culvert.design_flow_m3_s,
                    f"CUL-CAP failed on {culvert.id}: capacity {culvert.capacity_m3_s:.3f} m3/s "
                    f"below design flow {culvert.design_flow_m3_s:.3f} m3/s; use a larger diameter "
                    "or more barrels.",
                )
            )
    return out


def check_cul_dmin(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    minimum, _, _ = standards.get("culvert_diameter_min_m")
    culverts = {culvert.id: culvert for culvert in spec.culverts}
    out: list[CheckResult] = []
    for result in results.culverts:
        culvert = culverts.get(result.id)
        if culvert is None:
            continue
        if minimum is None:
            out.append(
                _result(
                    "CUL-DMIN",
                    result.id,
                    "warn",
                    culvert.diameter_m,
                    None,
                    f"CUL-DMIN not checked on {result.id}: no minimum diameter standard is set.",
                )
            )
        elif culvert.diameter_m >= minimum:
            out.append(
                _result(
                    "CUL-DMIN",
                    result.id,
                    "pass",
                    culvert.diameter_m,
                    minimum,
                    f"{result.id} diameter {culvert.diameter_m:.2f} m meets the minimum "
                    f"{minimum:.2f} m.",
                )
            )
        else:
            out.append(
                _result(
                    "CUL-DMIN",
                    result.id,
                    "fail",
                    culvert.diameter_m,
                    minimum,
                    f"CUL-DMIN failed on {result.id}: diameter {culvert.diameter_m:.2f} m below "
                    f"the minimum {minimum:.2f} m; increase the diameter.",
                )
            )
    return out


def check_cul_cover(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    minimum, _, _ = standards.get("culvert_cover_min_m")
    out: list[CheckResult] = []
    for culvert in results.culverts:
        if minimum is None:
            out.append(
                _result(
                    "CUL-COVER",
                    culvert.id,
                    "warn",
                    culvert.cover_m,
                    None,
                    f"CUL-COVER not checked on {culvert.id}: no minimum cover standard is set.",
                )
            )
        elif culvert.cover_m is None:
            out.append(
                _result(
                    "CUL-COVER",
                    culvert.id,
                    "warn",
                    None,
                    minimum,
                    f"CUL-COVER not checked on {culvert.id}: cover is unknown.",
                )
            )
        elif culvert.cover_m >= minimum:
            out.append(
                _result(
                    "CUL-COVER",
                    culvert.id,
                    "pass",
                    culvert.cover_m,
                    minimum,
                    f"{culvert.id} cover {culvert.cover_m:.2f} m meets the minimum "
                    f"{minimum:.2f} m.",
                )
            )
        else:
            out.append(
                _result(
                    "CUL-COVER",
                    culvert.id,
                    "fail",
                    culvert.cover_m,
                    minimum,
                    f"CUL-COVER failed on {culvert.id}: cover {culvert.cover_m:.2f} m below the "
                    f"minimum {minimum:.2f} m; lower the inverts or change the culvert type.",
                )
            )
    return out


def check_cul_fall(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    out: list[CheckResult] = []
    for culvert in results.culverts:
        if culvert.invert_in_m is None or culvert.invert_out_m is None:
            out.append(
                _result(
                    "CUL-FALL",
                    culvert.id,
                    "warn",
                    None,
                    None,
                    f"CUL-FALL not checked on {culvert.id}: inverts are unknown.",
                )
            )
        elif culvert.invert_out_m < culvert.invert_in_m:
            out.append(
                _result(
                    "CUL-FALL",
                    culvert.id,
                    "pass",
                    culvert.invert_out_m,
                    culvert.invert_in_m,
                    f"{culvert.id} outlet invert falls from {culvert.invert_in_m:.2f} m to "
                    f"{culvert.invert_out_m:.2f} m.",
                )
            )
        else:
            out.append(
                _result(
                    "CUL-FALL",
                    culvert.id,
                    "fail",
                    culvert.invert_out_m,
                    culvert.invert_in_m,
                    f"CUL-FALL failed on {culvert.id}: outlet invert {culvert.invert_out_m:.2f} m "
                    f"is not below inlet invert {culvert.invert_in_m:.2f} m; adjust the inverts.",
                )
            )
    return out


def check_net_outlet(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    out: list[CheckResult] = []
    for drain in spec.drains:
        if network.reaches_outlet(spec, drain.id):
            out.append(
                _result(
                    "NET-OUTLET",
                    drain.id,
                    "pass",
                    None,
                    None,
                    f"{drain.id} reaches a valid outlet.",
                )
            )
        else:
            out.append(
                _result(
                    "NET-OUTLET",
                    drain.id,
                    "fail",
                    None,
                    None,
                    f"NET-OUTLET failed on {drain.id}: the drain does not reach an outlet; add or "
                    "reconnect an outlet.",
                )
            )
    return out


def check_net_fall(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    out: list[CheckResult] = []
    for reach in results.drains:
        if reach.invert_up_m is None or reach.invert_down_m is None:
            out.append(
                _result(
                    "NET-FALL",
                    reach.id,
                    "warn",
                    None,
                    None,
                    f"NET-FALL not checked on {reach.id}: inverts are unknown.",
                )
            )
        elif reach.invert_up_m > reach.invert_down_m:
            out.append(
                _result(
                    "NET-FALL",
                    reach.id,
                    "pass",
                    reach.invert_down_m,
                    reach.invert_up_m,
                    f"{reach.id} inverts fall toward the outlet.",
                )
            )
        else:
            out.append(
                _result(
                    "NET-FALL",
                    reach.id,
                    "fail",
                    reach.invert_down_m,
                    reach.invert_up_m,
                    f"NET-FALL failed on {reach.id}: the invert does not fall toward the outlet "
                    f"({reach.invert_up_m:.2f} m to {reach.invert_down_m:.2f} m); set a gradient "
                    "or split the reach.",
                )
            )
    return out


def check_geo_depth(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    maximum, _, _ = standards.get("drain_depth_max_m")
    out: list[CheckResult] = []
    for drain in spec.drains:
        depth = drain.section.depth_m
        if maximum is None:
            out.append(
                _result(
                    "GEO-DEPTH",
                    drain.id,
                    "warn",
                    depth,
                    None,
                    f"GEO-DEPTH not checked on {drain.id}: no maximum drain depth standard is set.",
                )
            )
        elif depth <= maximum:
            out.append(
                _result(
                    "GEO-DEPTH",
                    drain.id,
                    "pass",
                    depth,
                    maximum,
                    f"{drain.id} depth {depth:.2f} m is within the maximum {maximum:.2f} m.",
                )
            )
        else:
            out.append(
                _result(
                    "GEO-DEPTH",
                    drain.id,
                    "fail",
                    depth,
                    maximum,
                    f"GEO-DEPTH failed on {drain.id}: depth {depth:.2f} m exceeds the maximum "
                    f"{maximum:.2f} m; widen instead of deepening, or split the reach.",
                )
            )
    return out


def check_geo_crossfall(
    spec: DesignSpec, results: Results, standards: Standards
) -> list[CheckResult]:
    has_left = any(drain.side == "left" for drain in spec.drains)
    has_right = any(drain.side == "right" for drain in spec.drains)
    if spec.road.camber == "crossfall":
        if has_right:
            return [
                _result(
                    "GEO-CROSSFALL",
                    "road",
                    "pass",
                    None,
                    None,
                    "The one-way crossfall sheds to the right and a right-side drain is present.",
                )
            ]
        return [
            _result(
                "GEO-CROSSFALL",
                "road",
                "fail",
                None,
                None,
                "GEO-CROSSFALL failed: the road sheds to the right but there is no right-side "
                "drain; add a drain on the low (right) side or change the camber.",
            )
        ]
    if has_left and has_right:
        return [
            _result(
                "GEO-CROSSFALL",
                "road",
                "pass",
                None,
                None,
                "The crowned road has a drain on each side.",
            )
        ]
    missing = "left" if not has_left else "right"
    return [
        _result(
            "GEO-CROSSFALL",
            "road",
            "fail",
            None,
            None,
            f"GEO-CROSSFALL failed: the road is crowned but there is no drain on the {missing} "
            "side; add a drain or change to a one-way crossfall.",
        )
    ]


def check_con_site(spec: DesignSpec, results: Results, standards: Standards) -> list[CheckResult]:
    out: list[CheckResult] = []
    for constraint in spec.constraints:
        low = (
            constraint.from_chainage_m if constraint.from_chainage_m is not None else float("-inf")
        )
        high = constraint.to_chainage_m if constraint.to_chainage_m is not None else float("inf")
        overlapping = [
            drain.id
            for drain in spec.drains
            if (constraint.side is None or drain.side == constraint.side)
            and drain.to_chainage_m > low
            and drain.from_chainage_m < high
        ]
        element = constraint.id or constraint.type
        if overlapping:
            out.append(
                _result(
                    "CON-SITE",
                    element,
                    "fail",
                    None,
                    None,
                    f"CON-SITE failed: drain(s) {', '.join(overlapping)} lie in a restricted zone "
                    f"({constraint.description or constraint.type}); move or reroute the drain.",
                )
            )
        else:
            out.append(
                _result(
                    "CON-SITE",
                    element,
                    "pass",
                    None,
                    None,
                    f"Constraint {element} is respected.",
                )
            )
    return out


def check_cad_layers(
    spec: DesignSpec,
    results: Results,
    standards: Standards,
    dxf_path: str | None = None,
) -> list[CheckResult]:
    """Check that every DXF entity sits on a standard layer. Skipped until a drawing exists."""
    if dxf_path is None:
        return []
    offending = dxf_writer.nonstandard_layers(dxf_path)
    if not offending:
        return [
            _result(
                "CAD-LAYERS",
                "drawing",
                "pass",
                None,
                None,
                "All DXF entities are on standard layers.",
            )
        ]
    out: list[CheckResult] = []
    for layer, dxftype in offending:
        out.append(
            _result(
                "CAD-LAYERS",
                layer,
                "fail",
                None,
                None,
                f"CAD-LAYERS failed: {dxftype} entity on non-standard layer '{layer}'; move it "
                "to a standard layer.",
            )
        )
    return out

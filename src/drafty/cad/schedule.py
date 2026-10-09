"""Write the drain schedule CSV and the quantities JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from drafty.spec.models import CheckResult, DesignSpec, Results, Section


def _section_label(section: Section) -> str:
    if section.shape == "rectangular":
        return f"rectangular {section.bottom_width_m:g}x{section.depth_m:g}"
    if section.shape == "trapezoidal":
        return (
            f"trapezoidal {section.bottom_width_m:g}x{section.depth_m:g} "
            f"(1:{section.side_slope_h_per_v:g})"
        )
    return f"v {section.depth_m:g} (1:{section.side_slope_h_per_v:g})"


def _num(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def _status_for(element_id: str, checks: list[CheckResult]) -> str:
    statuses = [check.status for check in checks if check.element_id == element_id]
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


SCHEDULE_HEADER = [
    "id",
    "type",
    "side",
    "from_chainage_m",
    "to_chainage_m",
    "section",
    "lining",
    "design_flow_m3_s",
    "capacity_m3_s",
    "velocity_m_s",
    "status",
]


def write_schedule_csv(spec: DesignSpec, results: Results, path: str | Path) -> Path:
    """Write one row per drain reach and culvert."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reaches = {reach.id: reach for reach in results.drains}
    culverts = {culvert.id: culvert for culvert in results.culverts}

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SCHEDULE_HEADER)
        for drain in spec.drains:
            reach = reaches.get(drain.id)
            writer.writerow(
                [
                    drain.id,
                    "drain",
                    drain.side,
                    f"{drain.from_chainage_m:g}",
                    f"{drain.to_chainage_m:g}",
                    _section_label(drain.section),
                    drain.lining,
                    _num(reach.design_flow_m3_s) if reach else "",
                    _num(reach.capacity_m3_s) if reach else "",
                    _num(reach.velocity_m_s) if reach else "",
                    _status_for(drain.id, results.checks),
                ]
            )
        for culvert in spec.culverts:
            result = culverts.get(culvert.id)
            writer.writerow(
                [
                    culvert.id,
                    "culvert",
                    "",
                    f"{culvert.chainage_m:g}",
                    "",
                    f"pipe {culvert.diameter_m:g} m x{culvert.count}",
                    "concrete",
                    _num(result.design_flow_m3_s) if result else "",
                    _num(result.capacity_m3_s) if result else "",
                    _num(result.velocity_m_s) if result else "",
                    _status_for(culvert.id, results.checks),
                ]
            )
    return path


def write_quantities_json(results: Results, path: str | Path) -> Path:
    """Write the rough quantities as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results.quantities.model_dump(), indent=2) + "\n", encoding="utf-8")
    return path

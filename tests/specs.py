"""Builders for test specs and results."""

from __future__ import annotations

from drafty.spec.models import (
    Alignment,
    Catchment,
    Culvert,
    CulvertResult,
    DesignSpec,
    Drain,
    DrainResult,
    Meta,
    Outlet,
    ParsedBrief,
    ProfilePoint,
    Project,
    Rainfall,
    Results,
    Road,
    Section,
    ShoulderWidths,
)


def road(
    length_m: float = 300.0,
    start_level: float = 100.0,
    end_level: float = 98.0,
    camber: str = "crown",
    crossfall_pct: float | None = 2.5,
    surface: str = "gravel",
) -> Road:
    return Road(
        length_m=length_m,
        alignment=Alignment(),
        carriageway_width_m=6.0,
        shoulder_width_m=ShoulderWidths(left=1.0, right=1.0),
        camber=camber,  # type: ignore[arg-type]
        crossfall_pct=crossfall_pct,
        surface=surface,  # type: ignore[arg-type]
        profile=[
            ProfilePoint(chainage_m=0, level_m=start_level),
            ProfilePoint(chainage_m=length_m, level_m=end_level),
        ],
    )


def trapezoid(bottom: float = 0.45, depth: float = 0.6, side: float = 0.5) -> Section:
    return Section(
        shape="trapezoidal", bottom_width_m=bottom, depth_m=depth, side_slope_h_per_v=side
    )


def rectangular(bottom: float = 0.5, depth: float = 0.8) -> Section:
    return Section(
        shape="rectangular", bottom_width_m=bottom, depth_m=depth, side_slope_h_per_v=0.0
    )


def example_spec(with_data: bool = False) -> DesignSpec:
    """The worked example from architecture.md section 4, optionally with design data filled in."""
    intensity = 100.0 if with_data else None
    coefficient = 0.9 if with_data else None
    source = "user" if with_data else "placeholder"
    return DesignSpec(
        meta=Meta(run_id="r-test", model_setup="routed"),
        project=Project(
            name="Residential access road A",
            location_description="Hillside residential area, urban",
            purpose="First-draft drainage layout for review",
        ),
        road=road(300, 1185.0, 1179.0, surface="gravel"),
        rainfall=Rainfall(
            intensity_mm_per_hr=intensity,
            return_period_yr=10.0 if with_data else None,
            source=source,  # type: ignore[arg-type]
        ),
        catchments=[
            Catchment(
                id="CA-L",
                area_ha=1.2,
                runoff_coefficient=coefficient,
                feeds="D-L1",
                description="Roofs and compounds, left side",
            ),
            Catchment(
                id="CA-R",
                area_ha=1.2,
                runoff_coefficient=coefficient,
                feeds="D-R1",
                description="Roofs and compounds, right side",
            ),
        ],
        drains=[
            Drain(
                id="D-L1",
                side="left",
                from_chainage_m=0,
                to_chainage_m=300,
                section=trapezoid(),
                lining="concrete",
                outlet=Outlet(type="existing_channel"),
            ),
            Drain(
                id="D-R1",
                side="right",
                from_chainage_m=0,
                to_chainage_m=150,
                section=trapezoid(),
                lining="concrete",
                outlet=Outlet(type="culvert", ref="C-01"),
            ),
        ],
        culverts=[
            Culvert(
                id="C-01",
                chainage_m=150,
                type="pipe",
                diameter_m=0.6,
                count=1,
                discharges_to="D-L1",
            )
        ],
    )


def happy_spec() -> DesignSpec:
    """A small spec that passes every applicable rule with the test standards fixture."""
    return DesignSpec(
        meta=Meta(run_id="r-happy"),
        project=Project(name="Happy road"),
        road=road(200.0, 100.0, 96.0, camber="crown", crossfall_pct=2.5, surface="gravel"),
        rainfall=Rainfall(intensity_mm_per_hr=100.0, return_period_yr=10.0, source="user"),
        catchments=[
            Catchment(id="CA-L", area_ha=0.3, runoff_coefficient=0.6, feeds="D-L1"),
            Catchment(id="CA-R", area_ha=0.3, runoff_coefficient=0.6, feeds="D-R1"),
        ],
        drains=[
            Drain(
                id="D-L1",
                side="left",
                from_chainage_m=0,
                to_chainage_m=200,
                section=rectangular(0.5, 0.8),
                lining="concrete",
                outlet=Outlet(type="existing_channel"),
            ),
            Drain(
                id="D-R1",
                side="right",
                from_chainage_m=0,
                to_chainage_m=200,
                section=rectangular(0.5, 0.8),
                lining="concrete",
                outlet=Outlet(type="existing_channel"),
            ),
        ],
    )


def one_drain_spec(lining: str = "concrete", depth: float = 0.8) -> DesignSpec:
    return DesignSpec(
        meta=Meta(run_id="r-one"),
        road=road(100.0, 100.0, 99.0, crossfall_pct=2.5),
        rainfall=Rainfall(intensity_mm_per_hr=100.0, source="user"),
        catchments=[Catchment(id="CA-L", area_ha=0.1, runoff_coefficient=0.6, feeds="D-L1")],
        drains=[
            Drain(
                id="D-L1",
                side="left",
                from_chainage_m=0,
                to_chainage_m=100,
                section=rectangular(0.5, depth),
                lining=lining,  # type: ignore[arg-type]
                outlet=Outlet(type="existing_channel"),
            )
        ],
    )


def culvert_spec(diameter: float = 0.6) -> DesignSpec:
    return DesignSpec(
        meta=Meta(run_id="r-cul"),
        road=road(100.0, 100.0, 99.0, crossfall_pct=2.5),
        rainfall=Rainfall(intensity_mm_per_hr=100.0, source="user"),
        catchments=[Catchment(id="CA-R", area_ha=0.1, runoff_coefficient=0.6, feeds="D-R1")],
        drains=[
            Drain(
                id="D-R1",
                side="right",
                from_chainage_m=0,
                to_chainage_m=100,
                section=rectangular(0.5, 0.8),
                lining="concrete",
                outlet=Outlet(type="culvert", ref="C-01"),
            )
        ],
        culverts=[
            Culvert(
                id="C-01",
                chainage_m=50,
                type="pipe",
                diameter_m=diameter,
                count=1,
                discharges_to="existing_channel",
            )
        ],
    )


def partial_drain_spec() -> DesignSpec:
    """A road with a single left drain covering only the first half."""
    return DesignSpec(
        meta=Meta(run_id="r-partial"),
        road=road(200.0, 100.0, 96.0, crossfall_pct=2.5),
        rainfall=Rainfall(intensity_mm_per_hr=100.0, source="user"),
        catchments=[Catchment(id="CA-L", area_ha=0.1, runoff_coefficient=0.6, feeds="D-L1")],
        drains=[
            Drain(
                id="D-L1",
                side="left",
                from_chainage_m=0,
                to_chainage_m=100,
                section=rectangular(0.5, 0.8),
                lining="concrete",
                outlet=Outlet(type="existing_channel"),
            )
        ],
    )


def drain_results(**kwargs) -> Results:
    defaults = {"id": "D-L1"}
    defaults.update(kwargs)
    return Results(drains=[DrainResult(**defaults)])


def culvert_results(**kwargs) -> Results:
    defaults = {"id": "C-01"}
    defaults.update(kwargs)
    return Results(culverts=[CulvertResult(**defaults)])


def _as_parsed(spec: DesignSpec) -> ParsedBrief:
    return ParsedBrief.model_validate(spec.model_dump(exclude={"meta", "results"}))


def parsed_example(with_data: bool = True) -> ParsedBrief:
    return _as_parsed(example_spec(with_data=with_data))


def parsed_happy() -> ParsedBrief:
    return _as_parsed(happy_spec())


def parsed_with_questions() -> ParsedBrief:
    data = example_spec(with_data=False).model_dump(exclude={"meta", "results"})
    data["open_questions"] = ["What design rainfall intensity and return period should I use?"]
    return ParsedBrief.model_validate(data)


def parsed_no_drains() -> ParsedBrief:
    return ParsedBrief.model_validate(
        {
            "project": {"name": "Empty road"},
            "road": road(200.0, 100.0, 96.0, crossfall_pct=2.5).model_dump(),
            "rainfall": {"intensity_mm_per_hr": 100.0, "return_period_yr": 10.0, "source": "user"},
            "catchments": [],
            "drains": [],
            "culverts": [],
            "constraints": [],
            "assumptions": [],
            "open_questions": [],
        }
    )

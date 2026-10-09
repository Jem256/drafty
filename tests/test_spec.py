"""DesignSpec and ParsedBrief models, validators and schema export."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import specs
from drafty.spec.models import DesignSpec, ParsedBrief


def test_schema_export_has_sections() -> None:
    schema = DesignSpec.model_json_schema()
    for section in ("road", "rainfall", "catchments", "drains", "culverts", "results"):
        assert section in schema["properties"]


def test_parsed_brief_has_no_meta_or_results() -> None:
    schema = ParsedBrief.model_json_schema()
    assert "meta" not in schema["properties"]
    assert "results" not in schema["properties"]


def test_parsed_brief_accepts_the_example() -> None:
    brief = ParsedBrief.model_validate(specs.example_spec().model_dump(exclude={"meta", "results"}))
    assert brief.road.length_m == 300


def test_duplicate_ids_rejected() -> None:
    data = specs.example_spec().model_dump()
    data["catchments"][1]["id"] = "CA-L"
    with pytest.raises(ValidationError):
        DesignSpec.model_validate(data)


def test_unknown_feeds_rejected() -> None:
    data = specs.example_spec().model_dump()
    data["catchments"][0]["feeds"] = "D-XX"
    with pytest.raises(ValidationError):
        DesignSpec.model_validate(data)


def test_drain_from_after_to_rejected() -> None:
    data = specs.example_spec().model_dump()
    data["drains"][0]["from_chainage_m"] = 200.0
    data["drains"][0]["to_chainage_m"] = 100.0
    with pytest.raises(ValidationError):
        DesignSpec.model_validate(data)


def test_profile_must_be_sorted() -> None:
    data = specs.example_spec().model_dump()
    data["road"]["profile"] = [
        {"chainage_m": 300.0, "level_m": 1179.0},
        {"chainage_m": 0.0, "level_m": 1185.0},
    ]
    with pytest.raises(ValidationError):
        DesignSpec.model_validate(data)


def test_drain_chainage_outside_road_rejected() -> None:
    data = specs.example_spec().model_dump()
    data["drains"][0]["to_chainage_m"] = 400.0
    with pytest.raises(ValidationError):
        DesignSpec.model_validate(data)

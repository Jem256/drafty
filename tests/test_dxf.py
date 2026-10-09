"""DXF drawing, SVG preview and schedule output."""

from __future__ import annotations

import csv
import json

import ezdxf
import pytest

import specs
from drafty.cad import dxf_writer, preview, schedule
from drafty.checks import rules
from drafty.checks.runner import run_checks
from drafty.engine import calculate


@pytest.fixture
def example(standards):
    spec = specs.example_spec(with_data=True)
    results = calculate(spec, standards)
    results.checks = run_checks(spec, results, standards)
    return spec, results


def test_dxf_opens_and_audits_clean(example, tmp_path) -> None:
    spec, results = example
    path = dxf_writer.write_dxf(spec, results, tmp_path / "drawing.dxf")
    doc = ezdxf.readfile(path)
    assert len(doc.audit().errors) == 0
    assert doc.units == ezdxf.units.M


def test_dxf_uses_standard_layers(example, tmp_path) -> None:
    spec, results = example
    path = dxf_writer.write_dxf(spec, results, tmp_path / "drawing.dxf")
    doc = ezdxf.readfile(path)
    layers = {entity.dxf.layer for entity in doc.modelspace()}
    assert set(dxf_writer.STANDARD_LAYERS) <= layers


def test_entity_counts_per_layer(example, tmp_path) -> None:
    spec, results = example
    path = dxf_writer.write_dxf(spec, results, tmp_path / "drawing.dxf")
    doc = ezdxf.readfile(path)
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        counts[entity.dxf.layer] = counts.get(entity.dxf.layer, 0) + 1
    assert counts["ROAD-EDGE"] == 2
    assert counts["ROAD-SHOULDER"] == 2
    assert counts["DRAIN-L"] >= 2
    assert counts["DRAIN-R"] >= 2
    assert counts["CULVERT"] >= 1
    assert counts["XSECT"] >= 1
    assert counts["LSECT"] >= 1
    assert counts["ROAD-CL"] >= 1


def test_cad_layers_check_passes(example, tmp_path) -> None:
    spec, results = example
    path = dxf_writer.write_dxf(spec, results, tmp_path / "drawing.dxf")
    checks = rules.check_cad_layers(spec, results, None, str(path))
    assert checks and all(check.status == "pass" for check in checks)


def test_cad_layers_check_fails_on_bad_layer(tmp_path) -> None:
    doc = ezdxf.new("R2018")
    doc.modelspace().add_line((0, 0), (1, 1), dxfattribs={"layer": "BAD-LAYER"})
    path = tmp_path / "bad.dxf"
    doc.saveas(path)
    checks = rules.check_cad_layers(None, None, None, str(path))
    assert checks[0].status == "fail"


def test_svg_is_non_empty(example, tmp_path) -> None:
    spec, results = example
    dxf = dxf_writer.write_dxf(spec, results, tmp_path / "drawing.dxf")
    svg = preview.render_svg(dxf, tmp_path / "preview.svg")
    text = svg.read_text(encoding="utf-8")
    assert svg.stat().st_size > 0
    assert "<svg" in text


def test_schedule_rows(example, tmp_path) -> None:
    spec, results = example
    path = schedule.write_schedule_csv(spec, results, tmp_path / "schedule.csv")
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(spec.drains) + len(spec.culverts)
    assert {row["id"] for row in rows} == {"D-L1", "D-R1", "C-01"}


def test_quantities_json(example, tmp_path) -> None:
    spec, results = example
    path = schedule.write_quantities_json(results, tmp_path / "quantities.json")
    data = json.loads(path.read_text())
    assert data["headwall_count"] == 2
    assert data["excavation_m3"] > 0

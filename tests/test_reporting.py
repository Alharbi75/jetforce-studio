"""Tests for deterministic, readable engineering report exports."""

from __future__ import annotations

import base64
import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.calculations import ideal_comparison, parameter_sweep, simulate
from src.models import ImpactModel, JetInputs
from src.reporting import (
    DISCLAIMER,
    ReportDataError,
    ReportDependencyError,
    ReportFigure,
    ReportWriteError,
    build_report_payload,
    build_schematic_svg,
    export_case_csv,
    export_case_json,
    export_case_pdf,
    export_parametric_csv,
    export_printable_html,
    reportlab_available,
    safe_export_filename,
    unit_for_field,
    write_export_file,
)

FIXED_TIME = datetime(2026, 8, 4, 12, 30, tzinfo=UTC)
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.fixture
def deflected_inputs() -> JetInputs:
    return JetInputs(
        density=1000.0,
        dynamic_viscosity=0.001,
        diameter=0.02,
        velocity=10.0,
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=90.0,
        retention_coefficient=0.8,
    )


@pytest.fixture
def deflected_result(deflected_inputs: JetInputs):
    return simulate(deflected_inputs)


def test_payload_uses_domain_serializers_without_repeating_inputs(deflected_result) -> None:
    payload = build_report_payload(deflected_result, generated_at=FIXED_TIME)

    assert payload["schema_version"] == "1.0"
    assert payload["report"]["generated_at"] == "2026-08-04T12:30:00+00:00"
    assert payload["report"]["disclaimer"] == DISCLAIMER
    assert payload["case"]["inputs"]["model"] == "deflected_jet"
    assert payload["case"]["results"]["fx_n"] == pytest.approx(deflected_result.fx_n)
    assert payload["case"]["results"]["fy_n"] == pytest.approx(deflected_result.fy_n)
    assert payload["case"]["results"]["resultant_force_n"] == pytest.approx(
        deflected_result.resultant_force_n
    )
    assert "density" not in payload["case"]["results"]
    assert payload["references"].startswith("Placeholder")


def test_payload_accepts_independent_mappings() -> None:
    payload = build_report_payload(
        {"density": 998.0, "model": "normal_flat_plate"},
        {"fx_n": 31.4, "fy_n": 0.0, "resultant_force_n": 31.4},
        generated_at="2026-08-04T12:30:00+04:00",
    )
    assert payload["case"]["inputs"]["density"] == 998.0
    assert payload["case"]["results"]["fx_n"] == 31.4


@pytest.mark.parametrize(
    ("inputs", "result", "message"),
    [
        ({"density": 998.0}, None, "simulation result"),
        ({}, {"fx_n": 1.0}, "Inputs cannot be empty"),
        ({"density": 998.0}, {}, "Results cannot be empty"),
    ],
)
def test_payload_rejects_incomplete_case_data(inputs, result, message: str) -> None:
    with pytest.raises(ReportDataError, match=message):
        build_report_payload(inputs, result)


def test_case_csv_is_long_form_parseable_and_unit_aware(deflected_result) -> None:
    exported = export_case_csv(deflected_result, generated_at=FIXED_TIME)
    rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8"))))

    assert rows
    by_field = {(row["section"], row["field"]): row for row in rows}
    assert by_field[("inputs", "density")]["value"] == "1000"
    assert by_field[("inputs", "density")]["unit"] == "kg/m^3"
    assert float(by_field[("results", "fx_n")]["value"]) == pytest.approx(deflected_result.fx_n)
    assert by_field[("results", "fx_n")]["quantity"] == "Horizontal reaction force"
    assert by_field[("results", "fx_n")]["unit"] == "N"


def test_parametric_csv_exports_dataframe_exactly(deflected_inputs: JetInputs) -> None:
    frame = parameter_sweep(deflected_inputs, "velocity", [0.0, 5.0, 10.0])
    exported = export_parametric_csv(frame)
    decoded = pd.read_csv(io.BytesIO(exported))

    assert list(decoded.columns) == list(frame.columns)
    pd.testing.assert_frame_equal(decoded, frame, check_dtype=False, check_exact=False, rtol=1e-13)


@pytest.mark.parametrize("empty", [[], pd.DataFrame()])
def test_parametric_csv_rejects_empty_data(empty) -> None:
    with pytest.raises(ReportDataError, match="cannot be empty"):
        export_parametric_csv(empty)


def test_json_is_standard_compliant_and_contains_optional_sections(deflected_inputs) -> None:
    result = simulate(deflected_inputs)
    comparison = ideal_comparison(deflected_inputs)
    sweep = parameter_sweep(deflected_inputs, "retention_coefficient", [0.8, 1.0])
    exported = export_case_json(
        deflected_inputs,
        result,
        ideal_comparison=comparison,
        hand_calculation={"fx_n": result.fx_n, "absolute_difference_n": 0.0},
        parametric_data=sweep,
        generated_at=FIXED_TIME,
    )
    decoded = json.loads(exported)

    assert decoded["ideal_comparison"]["percentage_difference"] >= 0.0
    assert decoded["hand_calculation"]["absolute_difference_n"] == 0.0
    assert len(decoded["parametric_study"]) == 2
    assert not any(token in exported for token in (b"NaN", b"Infinity"))


def test_nonfinite_optional_values_become_explicitly_undefined(deflected_result) -> None:
    exported = export_case_json(
        deflected_result,
        ideal_comparison={"percentage_difference": float("inf")},
        generated_at=FIXED_TIME,
    )
    assert json.loads(exported)["ideal_comparison"]["percentage_difference"] == "undefined"


def test_zero_resultant_direction_is_not_applicable_in_report_exports() -> None:
    result = simulate(JetInputs(velocity=0.0))
    payload = build_report_payload(result, generated_at=FIXED_TIME)
    assert payload["case"]["results"]["force_direction_defined"] is False
    assert payload["case"]["results"]["force_angle_deg"] == "undefined"

    rows = list(
        csv.DictReader(
            io.StringIO(export_case_csv(result, generated_at=FIXED_TIME).decode("utf-8"))
        )
    )
    angle = next(row for row in rows if row["field"] == "force_angle_deg")
    assert angle["value"] == "undefined"
    assert angle["unit"] == ""

    exported_html = export_printable_html(result, generated_at=FIXED_TIME).decode("utf-8")
    assert "Force direction angle" in exported_html
    assert "Not applicable" in exported_html


def test_not_applicable_percentage_has_no_percent_unit(deflected_result) -> None:
    options = {"hand_calculation": {"fy_percentage_difference": "not applicable"}}
    rows = list(
        csv.DictReader(
            io.StringIO(
                export_case_csv(deflected_result, generated_at=FIXED_TIME, **options).decode(
                    "utf-8"
                )
            )
        )
    )
    # Case CSV intentionally contains only primary inputs/results; verify report tables instead.
    assert rows
    exported_html = export_printable_html(
        deflected_result,
        generated_at=FIXED_TIME,
        **options,
    ).decode("utf-8")
    assert "not applicable</td><td></td>" in exported_html
    assert "not applicable</td><td>%</td>" not in exported_html


def test_set_metadata_is_serialized_in_deterministic_order(deflected_result) -> None:
    exported = export_case_json(
        deflected_result,
        metadata={"tags": {"zeta", "alpha", "middle"}},
        generated_at=FIXED_TIME,
    )
    assert json.loads(exported)["report"]["tags"] == ["alpha", "middle", "zeta"]


def test_printable_html_is_self_contained_semantic_and_escaped(deflected_result) -> None:
    figure = ReportFigure(
        title="Force study",
        image_bytes=ONE_PIXEL_PNG,
        caption="Calculated force components for the stated case; no experimental data.",
        alt_text="Force-component chart",
    )
    exported = export_printable_html(
        deflected_result,
        figures=[figure],
        metadata={
            "subtitle": "<script>alert('unsafe')</script>",
            "student_name": "Aisha & Omar",
            "student_id": "MEC<350>",
            "instructor_section": "Dr. Example / A1",
            "institution": "Engineering University",
        },
        generated_at=FIXED_TIME,
    ).decode("utf-8")

    assert exported.startswith("<!doctype html>")
    assert '<html lang="en">' in exported
    assert "@media print" in exported
    assert "<svg" in exported and "Control volume" in exported
    assert "Force exerted by the fluid on the plate" in exported
    assert "data:image/png;base64," in exported
    assert "&lt;script&gt;" in exported
    assert "<script>alert" not in exported
    assert "Aisha &amp; Omar" in exported
    assert "MEC&lt;350&gt;" in exported
    assert "Dr. Example / A1" in exported
    assert "Engineering University" in exported
    assert "not a full CFD simulation" in exported
    assert "Student review required" in exported


@pytest.mark.parametrize(
    ("model", "expected_label"),
    [
        (ImpactModel.NORMAL_FLAT_PLATE, "V_out,2"),
        (ImpactModel.DEFLECTED_JET, "V_out"),
        (ImpactModel.SPLIT_FLOW, "V_out,2"),
        (ImpactModel.CURVED_VANE, "Plate / vane"),
    ],
)
def test_schematic_follows_each_model_without_cfd_claim(model, expected_label: str) -> None:
    result = simulate(JetInputs(model=model, outlet_angle_deg=-45.0, plate_angle_deg=30.0))
    svg = build_schematic_svg(build_report_payload(result, generated_at=FIXED_TIME))
    assert expected_label in svg
    assert "not to scale and not CFD" in svg
    assert 'marker-end="url(#arrow-force)"' in svg


def test_deflected_report_schematic_uses_beta_for_plate_and_hides_zero_outlet() -> None:
    horizontal = simulate(
        JetInputs(
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=0.0,
            retention_coefficient=1.0,
        )
    )
    vertical = simulate(
        JetInputs(
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=90.0,
            retention_coefficient=1.0,
        )
    )

    horizontal_svg = build_schematic_svg(build_report_payload(horizontal, generated_at=FIXED_TIME))
    vertical_svg = build_schematic_svg(build_report_payload(vertical, generated_at=FIXED_TIME))
    horizontal_plate = re.search(
        r'<line x1="([\d.-]+)" y1="([\d.-]+)" x2="([\d.-]+)" y2="([\d.-]+)" class="plate"/>',
        horizontal_svg,
    )
    vertical_plate = re.search(
        r'<line x1="([\d.-]+)" y1="([\d.-]+)" x2="([\d.-]+)" y2="([\d.-]+)" class="plate"/>',
        vertical_svg,
    )
    assert horizontal_plate is not None and vertical_plate is not None
    assert float(horizontal_plate.group(2)) == pytest.approx(float(horizontal_plate.group(4)))
    assert float(vertical_plate.group(1)) == pytest.approx(float(vertical_plate.group(3)))

    stopped = simulate(
        JetInputs(model=ImpactModel.DEFLECTED_JET, outlet_angle_deg=45.0, retention_coefficient=0.0)
    )
    stopped_svg = build_schematic_svg(build_report_payload(stopped, generated_at=FIXED_TIME))
    assert "V_out = 0" in stopped_svg
    assert stopped_svg.count('class="flow"') == 1


@pytest.mark.parametrize(("angle", "expected_x"), [(0.0, 539.0), (180.0, 261.0)])
def test_report_outlet_crosses_control_volume_at_shallow_angles(
    angle: float, expected_x: float
) -> None:
    result = simulate(JetInputs(model=ImpactModel.DEFLECTED_JET, outlet_angle_deg=angle))
    svg = build_schematic_svg(build_report_payload(result, generated_at=FIXED_TIME))
    flow_arrows = re.findall(
        r'<line class="flow" x1="([\d.]+)" y1="([\d.]+)" ' r'x2="([\d.]+)" y2="([\d.]+)"',
        svg,
    )

    assert tuple(map(float, flow_arrows[-1])) == pytest.approx((400.0, 160.0, expected_x, 160.0))


def test_split_report_velocity_arrows_have_equal_length_and_mass_labels() -> None:
    result = simulate(
        JetInputs(
            model=ImpactModel.SPLIT_FLOW,
            plate_angle_deg=30.0,
            split_fraction=0.8,
        )
    )
    svg = build_schematic_svg(build_report_payload(result, generated_at=FIXED_TIME))
    flow_arrows = re.findall(
        r'<line class="flow" x1="([\d.]+)" y1="([\d.]+)" ' r'x2="([\d.]+)" y2="([\d.]+)"',
        svg,
    )[1:]
    lengths = [
        ((float(x2) - float(x1)) ** 2 + (float(y2) - float(y1)) ** 2) ** 0.5
        for x1, y1, x2, y2 in flow_arrows
    ]

    assert lengths[0] == pytest.approx(lengths[1], rel=1e-12)
    assert "V_out,1; 80% mdot" in svg
    assert "V_out,2; 20% mdot" in svg


@pytest.mark.skipif(not reportlab_available(), reason="ReportLab is optional")
def test_pdf_generation_produces_a_complete_pdf(deflected_result) -> None:
    exported = export_case_pdf(
        deflected_result,
        ideal_comparison={
            "ideal_resultant_n": 44.428829,
            "actual_resultant_n": deflected_result.resultant_force_n,
            "percentage_difference": 9.45,
        },
        hand_calculation={"fx_n": deflected_result.fx_n, "absolute_difference_n": 0.0},
        generated_at=FIXED_TIME,
    )

    assert exported.startswith(b"%PDF-")
    assert exported.rstrip().endswith(b"%%EOF")
    assert len(exported) > 10_000


def test_pdf_missing_dependency_has_actionable_fallback(monkeypatch, deflected_result) -> None:
    import src.reporting as reporting

    monkeypatch.setattr(reporting, "reportlab_available", lambda: False)
    with pytest.raises(ReportDependencyError, match="printable HTML"):
        export_case_pdf(deflected_result, generated_at=FIXED_TIME)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"title": "", "image_bytes": b"x", "caption": "caption"}, "title"),
        ({"title": "Chart", "image_bytes": b"", "caption": "caption"}, "empty"),
        ({"title": "Chart", "image_bytes": b"x", "caption": ""}, "caption"),
        (
            {
                "title": "Chart",
                "image_bytes": b"x",
                "caption": "caption",
                "mime_type": "image/svg+xml",
            },
            "PNG or JPEG",
        ),
    ],
)
def test_report_figure_rejects_ambiguous_or_unsupported_content(kwargs, message: str) -> None:
    with pytest.raises(ReportDataError, match=message):
        ReportFigure(**kwargs)


def test_safe_filename_removes_path_characters_and_uses_utc() -> None:
    filename = safe_export_filename(
        "../MEC350 Case / 01", ".JSON", generated_at=datetime(2026, 8, 4, 16, 30, tzinfo=UTC)
    )
    assert filename == "MEC350_Case_01_20260804T163000Z.json"
    assert "/" not in filename and "\\" not in filename


def test_safe_filename_rejects_empty_extension() -> None:
    with pytest.raises(ReportDataError, match="extension"):
        safe_export_filename(extension="...")


def test_atomic_export_write_round_trip(tmp_path) -> None:
    target = tmp_path / "case.json"
    returned = write_export_file(b'{"ok": true}\n', target)
    assert returned == target
    assert target.read_bytes() == b'{"ok": true}\n'
    assert not list(tmp_path.glob("*.tmp"))


def test_export_write_reports_missing_directory(tmp_path) -> None:
    with pytest.raises(ReportWriteError, match="does not exist"):
        write_export_file(b"data", tmp_path / "missing" / "case.csv")


def test_export_write_rejects_empty_content(tmp_path) -> None:
    with pytest.raises(ReportDataError, match="cannot be empty"):
        write_export_file(b"", tmp_path / "case.csv")


@pytest.mark.parametrize(
    ("field", "unit"),
    [
        ("density", "kg/m^3"),
        ("dynamic_viscosity", "Pa s"),
        ("area_m2", "m^2"),
        ("flow_rate_m3_s", "m^3/s"),
        ("mass_flow_rate_kg_s", "kg/s"),
        ("fx_n", "N"),
        ("force_angle_deg", "deg"),
        ("retention_coefficient", "dimensionless"),
        ("fx_percentage_difference", "%"),
        ("model", ""),
    ],
)
def test_units_are_centralized_for_export_fields(field: str, unit: str) -> None:
    assert unit_for_field(field) == unit


def test_payload_normalizes_supported_metadata_types(tmp_path, deflected_result) -> None:
    @dataclass
    class CourseRecord:
        section: str

        # Requiring an argument exercises the safe dataclass fallback after a
        # generic no-argument to_dict call is not applicable.
        def to_dict(self, required: str):
            return {"section": self.section, "required": required}

    payload = build_report_payload(
        deflected_result,
        metadata={
            "model_enum": ImpactModel.DEFLECTED_JET,
            "created": FIXED_TIME,
            "source_path": tmp_path / "case.json",
            "numpy_count": np.int64(4),
            "course_record": CourseRecord("MEC350-A"),
        },
        generated_at=FIXED_TIME,
    )

    assert payload["report"]["model_enum"] == "deflected_jet"
    assert payload["report"]["created"] == FIXED_TIME.isoformat()
    assert payload["report"]["source_path"] == str(tmp_path / "case.json")
    assert payload["report"]["numpy_count"] == 4
    assert payload["report"]["course_record"] == {"section": "MEC350-A"}


def test_payload_rejects_unsupported_nested_type(deflected_result) -> None:
    with pytest.raises(ReportDataError, match="Unsupported report value type"):
        build_report_payload(deflected_result, metadata={"unsafe": object()})


def test_payload_rejects_nonmapping_result_and_bad_records() -> None:
    with pytest.raises(ReportDataError, match="Result must be"):
        build_report_payload({"density": 998.0}, 31.4)
    with pytest.raises(ReportDataError, match="sequence of row mappings"):
        build_report_payload(
            {"density": 998.0},
            {"fx_n": 1.0},
            parametric_data=[1.0, 2.0],
        )


def test_payload_accepts_one_mapping_as_a_one_row_study(deflected_result) -> None:
    payload = build_report_payload(
        deflected_result,
        parametric_data={"velocity": 10.0, "FR_N": deflected_result.resultant_force_n},
        generated_at=FIXED_TIME,
    )
    assert payload["parametric_study"] == [
        {"velocity": 10.0, "FR_N": deflected_result.resultant_force_n}
    ]


def test_generation_time_validation_and_naive_time_normalization(deflected_result) -> None:
    with pytest.raises(ReportDataError, match="cannot be blank"):
        build_report_payload(deflected_result, generated_at="  ")
    payload = build_report_payload(deflected_result, generated_at=datetime(2026, 8, 4, 12, 30))
    assert payload["report"]["generated_at"].endswith("+00:00")


@pytest.mark.parametrize(
    ("option", "message"),
    [
        ({"assumptions": [""]}, "assumption"),
        ({"discussion": ["valid", 3]}, "discussion"),
        ({"limitations": ["valid", "  "]}, "limitation"),
    ],
)
def test_payload_rejects_blank_or_nontext_narrative(option, message, deflected_result) -> None:
    with pytest.raises(ReportDataError, match=message):
        build_report_payload(deflected_result, **option)


def test_csv_flattens_nested_values_and_serializes_booleans_and_nulls() -> None:
    exported = export_case_csv(
        {"density": 998.0, "case_tags": ["baseline", "water"], "nested": {"enabled": True}},
        {"fx_n": 1.0, "verified": False, "comment": None},
        generated_at=FIXED_TIME,
    )
    rows = {row["field"]: row for row in csv.DictReader(io.StringIO(exported.decode()))}
    assert rows["case_tags"]["value"] == '["baseline","water"]'
    assert rows["nested.enabled"]["value"] == "true"
    assert rows["verified"]["value"] == "false"
    assert rows["comment"]["value"] == ""


def test_html_handles_empty_figures_long_table_and_sequence_comparisons(deflected_inputs) -> None:
    result = simulate(deflected_inputs)
    sweep = parameter_sweep(deflected_inputs, "velocity", np.linspace(0.0, 20.0, 45))
    exported = export_printable_html(
        result,
        hand_calculation=["Calculate area", "Apply momentum balance"],
        ideal_comparison=["Compare with k = 1"],
        parametric_data=sweep,
        generated_at=FIXED_TIME,
    ).decode()

    assert "No parametric-study image was supplied" in exported
    assert "Showing the first 40 of 45 rows" in exported
    assert "Calculate area" in exported
    assert "Compare with k = 1" in exported
    assert "<pre>" in exported


def test_schematic_rejects_malformed_case_and_handles_bad_numbers() -> None:
    with pytest.raises(ReportDataError, match="invalid case structure"):
        build_schematic_svg({"case": "not-a-mapping"})

    svg = build_schematic_svg(
        {
            "case": {
                "inputs": {
                    "model": "deflected_jet",
                    "plate_angle_deg": "invalid",
                    "outlet_angle_deg": float("nan"),
                },
                "results": {"fx_n": "invalid", "fy_n": None},
            }
        }
    )
    assert "F_R = 0" in svg
    assert "V_out" in svg


@pytest.mark.skipif(not reportlab_available(), reason="ReportLab is optional")
def test_pdf_embeds_multiple_valid_figures_and_truncates_long_sweep(deflected_inputs) -> None:
    result = simulate(deflected_inputs)
    figures = [
        ReportFigure(
            title=f"Force study {index}",
            image_bytes=ONE_PIXEL_PNG,
            caption=f"Verified calculated chart {index} for the stated inputs.",
        )
        for index in (1, 2)
    ]
    exported = export_case_pdf(
        result,
        figures=figures,
        parametric_data=parameter_sweep(deflected_inputs, "velocity", np.linspace(0.0, 20.0, 13)),
        generated_at=FIXED_TIME,
    )
    assert exported.startswith(b"%PDF-")
    assert len(exported) > 10_000


@pytest.mark.skipif(not reportlab_available(), reason="ReportLab is optional")
def test_pdf_rejects_unreadable_raster_figure(deflected_result) -> None:
    figure = ReportFigure(
        title="Broken chart",
        image_bytes=b"not a PNG despite its declared MIME type",
        caption="This invalid input must be rejected.",
    )
    with pytest.raises(ReportDataError, match="not a readable raster image"):
        export_case_pdf(deflected_result, figures=[figure], generated_at=FIXED_TIME)


@pytest.mark.skipif(not reportlab_available(), reason="ReportLab is optional")
@pytest.mark.parametrize(
    "inputs",
    [
        JetInputs(model=ImpactModel.NORMAL_FLAT_PLATE),
        JetInputs(model=ImpactModel.SPLIT_FLOW, split_fraction=0.7, plate_angle_deg=35.0),
        JetInputs(model=ImpactModel.CURVED_VANE, outlet_angle_deg=145.0),
        JetInputs(model=ImpactModel.DEFLECTED_JET, outlet_angle_deg=0.0),
    ],
)
def test_pdf_schematic_supports_every_model_and_zero_force(inputs: JetInputs) -> None:
    exported = export_case_pdf(simulate(inputs), generated_at=FIXED_TIME)
    assert exported.startswith(b"%PDF-")


def test_reportlab_partial_install_has_actionable_error(monkeypatch, deflected_result) -> None:
    import src.reporting as reporting

    original_import = reporting.importlib.import_module

    def incomplete_import(name: str):
        if name == "reportlab.graphics.shapes":
            raise ImportError("simulated partial install")
        return original_import(name)

    monkeypatch.setattr(reporting, "reportlab_available", lambda: True)
    monkeypatch.setattr(reporting.importlib, "import_module", incomplete_import)
    with pytest.raises(ReportDependencyError, match="Reinstall"):
        export_case_pdf(deflected_result, generated_at=FIXED_TIME)


@pytest.mark.skipif(not reportlab_available(), reason="ReportLab is optional")
def test_pdf_rejects_parameter_rows_without_columns(deflected_result) -> None:
    with pytest.raises(ReportDataError, match="do not contain any columns"):
        export_case_pdf(
            deflected_result,
            parametric_data=[{}],
            generated_at=FIXED_TIME,
        )


def test_safe_filename_defaults_blank_stem_and_normalizes_naive_time() -> None:
    filename = safe_export_filename(" /// ", "csv", generated_at=datetime(2026, 8, 4, 12, 30))
    assert filename == "jetforce_case_20260804T123000Z.csv"


def test_export_write_accepts_text_and_reports_replace_failure(tmp_path, monkeypatch) -> None:
    text_target = tmp_path / "case.txt"
    write_export_file("engineering report", text_target)
    assert text_target.read_text() == "engineering report"

    import src.reporting as reporting

    failed_target = tmp_path / "failed.txt"

    def fail_replace(source: str, destination: Path) -> None:
        raise PermissionError("simulated read-only destination")

    monkeypatch.setattr(reporting.os, "replace", fail_replace)
    with pytest.raises(ReportWriteError, match="Could not write"):
        write_export_file(b"data", failed_target)
    assert not failed_target.exists()
    assert not list(tmp_path.glob(".failed.txt.*.tmp"))


def test_export_write_requires_filename() -> None:
    with pytest.raises(ReportWriteError, match="filename"):
        write_export_file(b"data", Path("/"))

"""Integration tests for deterministic, non-rendering visualization helpers."""

from __future__ import annotations

import base64
import io
import json
import re
from math import hypot
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

import src.visualizations as visualizations
from src.calculations import simulate
from src.models import ImpactModel, JetInputs, UnitSystem
from src.utils import convert_from_si, display_unit
from src.visualizations import (
    build_inputs_from_values,
    build_schematic_html,
    build_schematic_svg,
    canonical_model,
    compute_parameter_sweep,
    configure_page,
    create_force_component_chart,
    create_ideal_nonideal_chart,
    create_momentum_vector_chart,
    create_parameter_chart,
    dataframe_to_csv_bytes,
    display_value,
    input_snapshot,
    inputs_as_json,
    render_assumptions,
    render_brand_bar,
    render_case_summary,
    render_disclaimer,
    render_engineering_schematic,
    render_force_cards,
    render_page_intro,
    render_supporting_metrics,
    replace_input,
    result_snapshot,
    schematic_controls,
    simulate_safely,
    study_axis,
)


class SessionState(dict[str, Any]):
    """Small attribute-compatible session-state double."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeContext:
    def __enter__(self) -> FakeContext:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class FakeColumn(FakeContext):
    def __init__(self, owner: FakeStreamlit) -> None:
        self.owner = owner

    def metric(self, label: str, value: str, **kwargs: Any) -> None:
        self.owner.metric_calls.append((label, value, kwargs))

    def button(self, label: str, **kwargs: Any) -> bool:
        self.owner.button_calls.append((label, kwargs))
        callback = kwargs.get("on_click")
        if self.owner.invoke_callbacks and callable(callback):
            callback()
        return False

    def toggle(self, label: str, **kwargs: Any) -> bool:
        self.owner.toggle_calls.append((label, kwargs))
        return bool(self.owner.session_state.get(str(kwargs.get("key")), False))


class FakeStreamlit:
    """Recording double for stable Streamlit presentation calls."""

    def __init__(self, *, invoke_callbacks: bool = False) -> None:
        self.invoke_callbacks = invoke_callbacks
        self.session_state = SessionState()
        self.page_config_calls: list[dict[str, Any]] = []
        self.markdown_calls: list[tuple[str, dict[str, Any]]] = []
        self.logo_calls: list[tuple[str, dict[str, Any]]] = []
        self.info_calls: list[tuple[str, dict[str, Any]]] = []
        self.error_calls: list[tuple[str, dict[str, Any]]] = []
        self.metric_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.expander_calls: list[tuple[str, bool]] = []
        self.button_calls: list[tuple[str, dict[str, Any]]] = []
        self.toggle_calls: list[tuple[str, dict[str, Any]]] = []
        self.column_batches: list[list[FakeColumn]] = []

    def set_page_config(self, **kwargs: Any) -> None:
        self.page_config_calls.append(kwargs)

    def markdown(self, body: str, **kwargs: Any) -> None:
        self.markdown_calls.append((body, kwargs))

    def logo(self, path: str, **kwargs: Any) -> None:
        self.logo_calls.append((path, kwargs))

    def info(self, body: str, **kwargs: Any) -> None:
        self.info_calls.append((body, kwargs))

    def error(self, body: str, **kwargs: Any) -> None:
        self.error_calls.append((body, kwargs))

    def columns(self, specification: int | list[float]) -> list[FakeColumn]:
        count = specification if isinstance(specification, int) else len(specification)
        columns = [FakeColumn(self) for _ in range(count)]
        self.column_batches.append(columns)
        return columns

    def expander(self, label: str, *, expanded: bool = False) -> FakeContext:
        self.expander_calls.append((label, expanded))
        return FakeContext()


MODEL_CASES = (
    JetInputs(model=ImpactModel.NORMAL_FLAT_PLATE, retention_coefficient=0.8),
    JetInputs(
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=90.0,
        retention_coefficient=0.8,
    ),
    JetInputs(
        model=ImpactModel.SPLIT_FLOW,
        plate_angle_deg=90.0,
        split_fraction=0.75,
        retention_coefficient=0.8,
    ),
    JetInputs(
        model=ImpactModel.CURVED_VANE,
        outlet_angle_deg=180.0,
        retention_coefficient=0.9,
    ),
)


@pytest.mark.parametrize("inputs", MODEL_CASES, ids=lambda case: case.model.value)
def test_result_snapshot_integrates_exact_simulation_state(inputs: JetInputs) -> None:
    """Every UI field must come from the same traceable physics result."""

    result = simulate(inputs)
    snapshot = result_snapshot(result, inputs)

    assert snapshot["fx"] == pytest.approx(result.fx_n)
    assert snapshot["fy"] == pytest.approx(result.fy_n)
    assert snapshot["fr"] == pytest.approx(result.resultant_force_n)
    assert snapshot["force_angle"] == pytest.approx(result.force_angle_deg)
    assert snapshot["area"] == pytest.approx(result.area_m2)
    assert snapshot["flow_rate"] == pytest.approx(result.flow_rate_m3_s)
    assert snapshot["mass_flow_rate"] == pytest.approx(result.mass_flow_rate_kg_s)
    assert snapshot["reynolds_number"] == pytest.approx(result.reynolds_number)
    assert snapshot["outlet_speed"] == pytest.approx(result.outlet_speed_m_s)
    assert snapshot["vin"] == pytest.approx(result.inlet_velocity.as_tuple())
    assert snapshot["vout"] == pytest.approx(result.vout_equivalent.as_tuple())
    assert snapshot["outlet_vectors"] == pytest.approx(
        [stream.velocity_m_s.as_tuple() for stream in result.outlet_streams]
    )
    assert snapshot["outlet_mass_fractions"] == pytest.approx(
        [stream.mass_fraction for stream in result.outlet_streams]
    )


def test_result_snapshot_preserves_model_specific_outlet_construction() -> None:
    normal, deflected, split, curved = [
        result_snapshot(simulate(inputs), inputs) for inputs in MODEL_CASES
    ]

    assert normal["vout"] == pytest.approx((0.0, 0.0), abs=1e-14)
    assert normal["outlet_mass_fractions"] == [0.5, 0.5]
    assert deflected["vout"] == pytest.approx((0.0, 8.0), abs=1e-14)
    assert deflected["outlet_mass_fractions"] == [1.0]
    assert split["vout"] == pytest.approx((0.0, 4.0), abs=1e-14)
    assert split["outlet_mass_fractions"] == pytest.approx([0.75, 0.25])
    assert curved["vout"] == pytest.approx((-9.0, 0.0), abs=1e-14)
    assert curved["outlet_mass_fractions"] == [1.0]


@pytest.mark.parametrize(
    "quantity",
    ["diameter", "area", "velocity", "flow_rate", "mass_flow_rate", "force"],
)
@pytest.mark.parametrize("ui_system", ["SI", "US customary"])
def test_display_value_delegates_to_central_unit_conversion(quantity: str, ui_system: str) -> None:
    value_si = 2.75
    expected_system = UnitSystem.US_CUSTOMARY if ui_system.startswith("US") else UnitSystem.SI
    displayed, unit = display_value(value_si, quantity, ui_system)

    assert displayed == pytest.approx(convert_from_si(value_si, quantity, expected_system))
    assert unit == display_unit(quantity, expected_system)


def test_study_axes_include_converted_units_and_physical_symbols() -> None:
    velocity_label, velocity_unit, velocity_factor = study_axis("velocity", "US")
    diameter_label, diameter_unit, diameter_factor = study_axis("diameter", "US")
    angle_label, angle_unit, angle_factor = study_axis("beta", "SI")

    assert velocity_label == "Inlet jet speed, V"
    assert velocity_unit == "ft/s"
    assert velocity_factor == pytest.approx(
        convert_from_si(1.0, "velocity", UnitSystem.US_CUSTOMARY)
    )
    assert diameter_label == "Jet diameter, d"
    assert diameter_unit == "in"
    assert diameter_factor == pytest.approx(
        convert_from_si(1.0, "diameter", UnitSystem.US_CUSTOMARY)
    )
    assert (angle_label, angle_unit, angle_factor) == ("Outlet angle, β", "°", 1.0)


def _outlet_paths(html: str) -> list[str]:
    return re.findall(r'<path d="([^"]+)" class="jet outlet"', html)


def test_normal_schematic_has_vertical_opposed_outlets_and_flat_plate() -> None:
    inputs = JetInputs(model=ImpactModel.NORMAL_FLAT_PLATE)
    html = build_schematic_html(inputs, simulate(inputs), {"play": False})
    paths = _outlet_paths(html)

    assert paths == [
        "M 465.0 220.0 Q 488.0 220.0 465.0 58.0",
        "M 465.0 220.0 Q 488.0 220.0 465.0 382.0",
    ]
    assert '<line x1="465.0" y1="92.0" x2="465.0" y2="348.0" class="plate"' in html
    assert "Normal jet on a flat plate" in html


def test_normal_schematic_velocity_arrows_follow_retained_outlet_speed() -> None:
    inputs = JetInputs(
        model=ImpactModel.NORMAL_FLAT_PLATE,
        retention_coefficient=0.4,
    )
    html = build_schematic_html(inputs, simulate(inputs), {"play": False})
    segments = re.findall(
        r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)" '
        r'class="vector velocity outlet-vector"',
        html,
    )

    assert len(segments) == 2
    lengths = [hypot(float(x2) - float(x1), float(y2) - float(y1)) for x1, y1, x2, y2 in segments]
    # Inlet arrow is normalized to 125 px; k=0.4 therefore gives 50 px outlets.
    assert lengths == pytest.approx([50.0, 50.0], abs=0.2)


def test_deflected_schematic_matches_positive_ccw_beta() -> None:
    inputs = JetInputs(
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=30.0,
        retention_coefficient=0.8,
    )
    html = build_schematic_html(inputs, simulate(inputs), {"play": False})

    assert _outlet_paths(html) == ["M 465.0 220.0 L 730.0 67.0"]
    assert "β = 30°" in html
    assert 'class="plate"' in html
    assert 'class="vane"' not in html


def test_split_schematic_matches_theta_and_branch_mass_fractions() -> None:
    inputs = JetInputs(
        model=ImpactModel.SPLIT_FLOW,
        plate_angle_deg=-45.0,
        split_fraction=0.7,
        retention_coefficient=0.8,
    )
    html = build_schematic_html(inputs, simulate(inputs), {"play": False})

    assert _outlet_paths(html) == [
        "M 465.0 220.0 L 621.7 376.7",
        "M 465.0 220.0 L 308.3 63.3",
    ]
    assert "θ = -45°" in html
    assert "Outlet 1: 70% ṁ" in html
    assert "Outlet 2: 30% ṁ" in html


def test_curved_vane_schematic_uses_curved_geometry_and_beta_direction() -> None:
    inputs = JetInputs(
        model=ImpactModel.CURVED_VANE,
        outlet_angle_deg=150.0,
        retention_coefficient=0.8,
    )
    html = build_schematic_html(inputs, simulate(inputs), {"play": False})

    assert _outlet_paths(html) == ["M 465.0 220.0 Q 537.0 220.0 200.0 67.0"]
    assert 'class="vane"' in html
    assert "β = 150°" in html
    assert "Curved vane" in html


def test_schematic_options_remove_overlays_and_pause_motion() -> None:
    inputs = MODEL_CASES[1]
    options = {
        "play": False,
        "cv": False,
        "labels": False,
        "forces": False,
        "velocities": False,
    }
    html = build_schematic_html(inputs, simulate(inputs), options)

    assert "<animateMotion" not in html
    assert '<rect x="185" y="76" width="555"' not in html
    assert '<line class="vector force' not in html
    assert 'class="vector force' not in html
    assert 'class="vector velocity' not in html
    assert 'class="vector-label' not in html
    assert "Particle motion paused" in html
    assert "engineering visualization, not CFD" in html


def test_schematic_default_options_show_controls_vectors_and_animation() -> None:
    inputs = MODEL_CASES[1]
    html = build_schematic_html(inputs, simulate(inputs))

    assert "<animateMotion" in html
    assert '<rect x="185" y="76" width="555"' in html
    assert "CONTROL VOLUME" in html
    assert 'class="vector velocity' in html
    assert 'class="vector force fx"' in html
    assert 'class="vector force fy"' in html
    assert 'class="vector force resultant"' in html
    assert "Illustrative particle motion playing" in html


def test_zero_velocity_schematic_has_no_particles_or_force_vectors() -> None:
    inputs = JetInputs(model=ImpactModel.NORMAL_FLAT_PLATE, velocity=0.0)
    html = build_schematic_html(inputs, simulate(inputs))

    assert "<animateMotion" not in html
    assert 'class="vector force fx"' not in html
    assert 'class="vector force fy"' not in html
    assert 'class="vector force resultant"' not in html
    assert "No particle motion — zero inlet flow" in html


@pytest.mark.parametrize(
    ("angle", "expected_endpoint"),
    [(0.0, "758.0 220.0"), (180.0, "167.0 220.0")],
)
def test_shallow_outlet_paths_cross_control_volume_boundary(
    angle: float, expected_endpoint: str
) -> None:
    inputs = JetInputs(model=ImpactModel.DEFLECTED_JET, outlet_angle_deg=angle)
    html = build_schematic_html(inputs, simulate(inputs), {"play": False})

    assert _outlet_paths(html) == [f"M 465.0 220.0 L {expected_endpoint}"]


def test_zero_mass_split_branch_has_no_jet_or_velocity_arrow() -> None:
    inputs = JetInputs(
        model=ImpactModel.SPLIT_FLOW,
        plate_angle_deg=0.0,
        split_fraction=1.0,
    )
    html = build_schematic_html(inputs, simulate(inputs), {"play": False})

    assert _outlet_paths(html) == ["M 465.0 220.0 L 758.0 220.0"]
    assert html.count('class="vector velocity outlet-vector"') == 1


def test_cached_parameter_sweep_is_deterministic_and_csv_is_traceable() -> None:
    inputs = JetInputs(model=ImpactModel.NORMAL_FLAT_PLATE)
    first = compute_parameter_sweep(inputs, "velocity", 0.0, 20.0, 5)
    second = compute_parameter_sweep(inputs, "velocity", 0.0, 20.0, 5)
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    assert list(first.columns) == [
        "input",
        "Fx_N",
        "Fy_N",
        "FR_N",
        "Q_m3_s",
        "mdot_kg_s",
        "Re",
        "outlet_speed_m_s",
    ]
    assert first["input"].tolist() == [0.0, 5.0, 10.0, 15.0, 20.0]

    payload = dataframe_to_csv_bytes(
        first,
        metadata={"model": inputs.model.value, "internal_units": "SI"},
    ).decode("utf-8")
    recovered = pd.read_csv(io.StringIO(payload))
    assert recovered["metadata_model"].unique().tolist() == ["normal_flat_plate"]
    assert recovered["metadata_internal_units"].unique().tolist() == ["SI"]
    pd.testing.assert_frame_equal(
        recovered[first.columns], first, check_exact=False, check_dtype=False, rtol=1e-15
    )


def test_dataframe_csv_preserves_full_float_precision_without_special_parser() -> None:
    frame = pd.DataFrame({"input": [7.123456789012345], "Fx_N": [1.2345678901234567]})

    payload = dataframe_to_csv_bytes(frame)
    recovered = pd.read_csv(io.BytesIO(payload))

    assert "7.1234567890123452" in payload.decode("utf-8")
    assert recovered.loc[0, "input"] == pytest.approx(frame.loc[0, "input"], rel=1e-15)
    assert recovered.loc[0, "Fx_N"] == pytest.approx(frame.loc[0, "Fx_N"], rel=1e-15)


@pytest.mark.parametrize("points", [1, 502])
def test_presentation_sweep_enforces_responsive_point_limit(points: int) -> None:
    with pytest.raises(ValueError, match="between 2 and 501"):
        compute_parameter_sweep(JetInputs(), "velocity", 0.0, 10.0, points)


def test_parameter_chart_has_three_force_series_units_and_hover_state() -> None:
    frame = compute_parameter_sweep(JetInputs(), "velocity", 0.0, 10.0, 3)
    chart = create_parameter_chart(frame, "velocity", "US", title="Velocity study")

    assert isinstance(chart, go.Figure)
    assert [trace.name for trace in chart.data] == [
        "Fx — horizontal",
        "Fy — vertical",
        "FR — resultant",
    ]
    assert chart.layout.title.text == "Velocity study"
    assert chart.layout.xaxis.title.text == "Inlet jet speed, V (ft/s)"
    assert chart.layout.yaxis.title.text == "Force on plate (lbf)"
    assert all("Q:" in trace.hovertemplate for trace in chart.data)
    assert all("ṁ:" in trace.hovertemplate for trace in chart.data)
    assert all("US gal/min" in trace.hovertemplate for trace in chart.data)
    assert all("lbm/s" in trace.hovertemplate for trace in chart.data)
    np.testing.assert_allclose(
        chart.data[0].y,
        frame["Fx_N"] * convert_from_si(1.0, "force", UnitSystem.US_CUSTOMARY),
    )
    np.testing.assert_allclose(
        chart.data[0].customdata[:, 3],
        frame["Q_m3_s"] * convert_from_si(1.0, "flow_rate", UnitSystem.US_CUSTOMARY),
    )
    np.testing.assert_allclose(
        chart.data[0].customdata[:, 4],
        frame["mdot_kg_s"] * convert_from_si(1.0, "mass_flow_rate", UnitSystem.US_CUSTOMARY),
    )


def test_force_component_chart_preserves_signed_components_and_resultant() -> None:
    inputs = MODEL_CASES[1]
    result = simulate(inputs)
    chart = create_force_component_chart(result, inputs, "SI")

    assert isinstance(chart, go.Figure)
    assert len(chart.data) == 1
    assert list(chart.data[0].x) == [
        "Fx — horizontal",
        "Fy — vertical",
        "FR — resultant",
    ]
    np.testing.assert_allclose(
        chart.data[0].y,
        [result.fx_n, result.fy_n, result.resultant_force_n],
    )
    assert chart.layout.yaxis.title.text == "Force on plate (N)"


def test_ideal_nonideal_chart_uses_same_geometry_with_k_one_comparison() -> None:
    inputs = JetInputs(
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=135.0,
        retention_coefficient=0.7,
    )
    chart, frame = create_ideal_nonideal_chart(inputs, "SI")

    assert isinstance(chart, go.Figure)
    assert [trace.name for trace in chart.data] == ["Ideal, k = 1", "Selected k"]
    assert frame["component"].tolist() == ["Fx", "Fy", "FR"]
    assert list(frame.columns) == ["component", "Ideal, k = 1", "Selected k"]
    assert chart.layout.yaxis.title.text == "Force on plate (N)"
    assert not np.allclose(frame["Ideal, k = 1"], frame["Selected k"])


def test_momentum_vector_chart_endpoints_close_the_vector_balance() -> None:
    inputs = JetInputs(
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=60.0,
        retention_coefficient=0.8,
    )
    result = simulate(inputs)
    chart = create_momentum_vector_chart(result, inputs, "SI")

    assert isinstance(chart, go.Figure)
    assert [trace.name for trace in chart.data] == [
        "Inlet momentum flux, ṁVin",
        "Net outlet momentum flux, ΣṁVout",
        "Plate reaction, Fplate",
    ]
    endpoints = [(float(trace.x[-1]), float(trace.y[-1])) for trace in chart.data]
    inlet, outlet, reaction = endpoints
    assert inlet == pytest.approx(
        (
            result.mass_flow_rate_kg_s * result.inlet_velocity.x,
            result.mass_flow_rate_kg_s * result.inlet_velocity.y,
        )
    )
    assert outlet == pytest.approx(result.outlet_momentum_flux_n.as_tuple())
    assert reaction == pytest.approx(result.force_on_plate_n.as_tuple())
    assert inlet[0] - outlet[0] == pytest.approx(reaction[0])
    assert inlet[1] - outlet[1] == pytest.approx(reaction[1])
    assert hypot(*reaction) == pytest.approx(result.resultant_force_n)
    assert chart.layout.xaxis.title.text == "x component (N)"
    assert chart.layout.yaxis.title.text == "y component (N)"
    assert chart.layout.xaxis.scaleanchor == "y"


def test_momentum_vector_chart_us_hover_and_axes_use_lbf_consistently() -> None:
    inputs = MODEL_CASES[1]
    result = simulate(inputs)
    chart = create_momentum_vector_chart(result, inputs, "US")
    factor = convert_from_si(1.0, "force", UnitSystem.US_CUSTOMARY)

    assert chart.layout.xaxis.title.text == "x component (lbf)"
    assert chart.layout.yaxis.title.text == "y component (lbf)"
    assert all(" lbf" in trace.hovertemplate for trace in chart.data)
    assert all(" N<" not in trace.hovertemplate for trace in chart.data)
    assert float(chart.data[2].x[-1]) == pytest.approx(result.fx_n * factor)
    assert float(chart.data[2].y[-1]) == pytest.approx(result.fy_n * factor)
    assert chart.layout.hovermode == "closest"
    assert chart.layout.legend.y < 0.0


def test_configure_page_loads_brand_assets_and_scope_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)

    configure_page("Validation", page_icon="🧪")

    assert fake.page_config_calls == [
        {
            "page_title": "Validation · JetForce Studio",
            "page_icon": "🧪",
            "layout": "wide",
            "initial_sidebar_state": "auto",
            "menu_items": {
                "Get Help": None,
                "Report a bug": None,
                "About": (
                    "JetForce Studio — MEC350 Fluid Mechanics. A numerical "
                    "control-volume momentum model; not a CFD solver."
                ),
            },
        }
    ]
    assert len(fake.markdown_calls) == 1
    assert "jf-brandbar" in fake.markdown_calls[0][0]
    assert fake.markdown_calls[0][1] == {"unsafe_allow_html": True}
    assert len(fake.logo_calls) == 1
    assert fake.logo_calls[0][0].endswith("assets/logo.svg")
    assert fake.logo_calls[0][1] == {"size": "large"}


def test_brand_intro_and_disclaimer_render_accessible_escaped_markup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)

    render_brand_bar()
    render_page_intro("Model <A>", "Force & momentum", "Use V > 0 safely.")
    render_disclaimer()

    assert len(fake.markdown_calls) == 3
    brand = fake.markdown_calls[0][0]
    intro = fake.markdown_calls[1][0]
    disclaimer = fake.markdown_calls[2][0]
    assert "data:image/svg+xml," in brand
    assert 'alt="JetForce Studio"' in brand
    assert "MEC350 Fluid Mechanics" in brand
    assert "Model &lt;A&gt;" in intro
    assert "Force &amp; momentum" in intro
    assert "Use V &gt; 0 safely." in intro
    assert "control-volume momentum model" in disclaimer
    assert "not a full CFD simulation" in disclaimer
    assert 'role="note"' in disclaimer


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (ImpactModel.NORMAL_FLAT_PLATE, "normal_flat_plate"),
        ("flat plate", "normal_flat_plate"),
        ("single deflected outlet", "deflected_jet"),
        ("split", "split_flow"),
        ("curved", "curved_vane"),
        ("future model", "future_model"),
    ],
)
def test_model_name_normalization_is_stable(raw: object, expected: str) -> None:
    assert canonical_model(raw) == expected


def test_snapshot_adapters_accept_plain_mappings_and_safe_vector_fallbacks() -> None:
    inputs = {
        "rho": 1025.0,
        "mu": 0.0012,
        "d": 0.03,
        "v": 4.0,
        "impact_model": "split",
        "theta": -20.0,
        "s": 0.6,
    }
    result = {
        "horizontal_force": 3.0,
        "vertical_force": 4.0,
        "jet_area": 0.25,
        "q": 1.0,
        "mdot": 2.0,
        "re": 12_000.0,
        "velocity_in": {"x": 4.0, "y": 0.0},
        "velocity_out": object(),
    }

    input_values = input_snapshot(inputs)
    result_values = result_snapshot(result, inputs)
    assert input_values["model"] == "split_flow"
    assert input_values["density"] == 1025.0
    assert input_values["diameter"] == 0.03
    assert result_values["fr"] == 5.0
    assert result_values["force_angle"] == pytest.approx(53.1301023542)
    assert result_values["vin"] == (4.0, 0.0)
    assert result_values["vout"] == (0.0, 0.0)
    assert result_values["outlet_vectors"] == [(0.0, 0.0)]


def test_build_inputs_and_replace_input_cover_all_presented_fields() -> None:
    inputs = build_inputs_from_values(
        {
            "density": 1010.0,
            "viscosity": 0.0011,
            "diameter": 0.025,
            "velocity": 12.0,
            "model": "split",
            "theta": -35.0,
            "beta": 75.0,
            "retention": 0.82,
            "split": 0.63,
            "fluid_preset": "custom",
            "unit_system": "us customary",
        }
    )
    assert inputs == JetInputs(
        density=1010.0,
        dynamic_viscosity=0.0011,
        diameter=0.025,
        velocity=12.0,
        model=ImpactModel.SPLIT_FLOW,
        plate_angle_deg=-35.0,
        outlet_angle_deg=75.0,
        retention_coefficient=0.82,
        split_fraction=0.63,
        fluid_preset="custom",
        unit_system=UnitSystem.US_CUSTOMARY,
    )
    replaced = replace_input(inputs, "retention", 0.5)
    assert replaced.retention_coefficient == 0.5
    assert inputs.retention_coefficient == 0.82
    with pytest.raises(ValueError, match="no field"):
        replace_input(object(), "velocity", 3.0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model", "does-not-exist"),
        ("fluid_preset", "unknown-fluid"),
        ("unit_system", "unknown-units"),
    ],
)
def test_build_inputs_rejects_unknown_enum_values(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        build_inputs_from_values({field: value})


def test_force_cards_render_signed_interpretations_and_display_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)
    synthetic = {
        "fx_n": -2.0,
        "fy_n": 3.0,
        "fr": hypot(2.0, 3.0),
        "force_angle_deg": 123.6900675,
    }

    render_force_cards(synthetic, JetInputs(), "US")

    assert len(fake.column_batches) == 1
    assert len(fake.column_batches[0]) == 3
    assert len(fake.markdown_calls) == 3
    markup = "".join(call[0] for call in fake.markdown_calls)
    assert "Fx - Horizontal force on the plate" in markup
    assert "Fy - Vertical force on the plate" in markup
    assert "FR - Resultant force on the plate" in markup
    assert "←" in markup and "Acts in −x" in markup
    assert "↑" in markup and "Acts upward in +y" in markup
    assert "Resultant at 123.7° from +x" in markup
    assert markup.count("<span>lbf</span>") == 3


def test_zero_force_cards_have_unambiguous_no_force_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)

    render_force_cards({"fx_n": 0.0, "fy_n": 0.0, "fr": 0.0}, JetInputs())

    markup = "".join(call[0] for call in fake.markdown_calls)
    assert 'aria-label="Fx - Horizontal force on the plate: 0 N. No resolved component"' in markup
    assert 'aria-label="Fy - Vertical force on the plate: 0 N. No resolved component"' in markup
    assert 'aria-label="FR - Resultant force on the plate: 0 N. No net reaction force"' in markup
    assert markup.count('<div class="jf-result-note">No resolved component</div>') == 2
    assert '<div class="jf-result-note">No net reaction force</div>' in markup


def test_supporting_metrics_render_all_six_quantities_with_correct_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)
    inputs = MODEL_CASES[1]

    render_supporting_metrics(simulate(inputs), inputs, "US")

    assert [call[0] for call in fake.metric_calls] == [
        "Jet area, A",
        "Flow rate, Q",
        "Mass flow, ṁ",
        "Reynolds number, Re",
        "Outlet speed",
        "Force direction",
    ]
    rendered = {label: value for label, value, _kwargs in fake.metric_calls}
    assert rendered["Jet area, A"].endswith(" in²")
    assert rendered["Flow rate, Q"].endswith(" US gal/min")
    assert rendered["Mass flow, ṁ"].endswith(" lbm/s")
    assert rendered["Reynolds number, Re"].endswith(" dimensionless")
    assert rendered["Outlet speed"].endswith(" ft/s")
    assert rendered["Force direction"].endswith(" ° from +x")
    assert len(fake.column_batches) == 2


def test_zero_force_direction_is_reported_as_not_applicable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)
    inputs = JetInputs(velocity=0.0)

    render_supporting_metrics(simulate(inputs), inputs)

    rendered = {label: value for label, value, _kwargs in fake.metric_calls}
    assert rendered["Force direction"] == "Not applicable — zero resultant"


@pytest.mark.parametrize(
    ("inputs", "expected_tags"),
    [
        (JetInputs(), ("Normal jet on a flat plate",)),
        (
            JetInputs(
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=45.0,
                retention_coefficient=0.8,
            ),
            ("Single deflected outlet jet", "k = 0.80", "β = 45.0°"),
        ),
        (
            JetInputs(
                model=ImpactModel.SPLIT_FLOW,
                plate_angle_deg=-30.0,
                split_fraction=0.65,
                retention_coefficient=0.9,
            ),
            ("Split flow along a flat plate", "k = 0.90", "θ = -30.0°", "s = 0.65"),
        ),
    ],
)
def test_case_summary_includes_only_model_relevant_parameters(
    monkeypatch: pytest.MonkeyPatch,
    inputs: JetInputs,
    expected_tags: tuple[str, ...],
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)

    render_case_summary(inputs)

    assert len(fake.markdown_calls) == 1
    markup = fake.markdown_calls[0][0]
    assert all(expected in markup for expected in expected_tags)
    assert "ρ =" in markup and "d =" in markup and "V =" in markup
    if inputs.model is ImpactModel.NORMAL_FLAT_PLATE:
        assert "k =" not in markup and "β =" not in markup and "θ =" not in markup


def test_assumptions_renderer_explains_each_assumption_and_reynolds_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)

    render_assumptions(expanded=True)

    assert fake.expander_calls == [("Model assumptions and their engineering meaning", True)]
    assert len(fake.markdown_calls) == len(visualizations.ASSUMPTIONS)
    assert all(
        title in fake.markdown_calls[index][0]
        for index, (title, _text) in enumerate(visualizations.ASSUMPTIONS)
    )
    assert len(fake.info_calls) == 1
    assert "does not automatically modify" in fake.info_calls[0][0]


def test_simulate_safely_returns_result_and_turns_validation_into_readable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)

    valid_result = simulate_safely(JetInputs())
    invalid_result = simulate_safely(JetInputs(density=0.0))

    assert valid_result is not None
    assert invalid_result is None
    assert len(fake.error_calls) == 1
    assert fake.error_calls[0][0].startswith("The current inputs are not valid:")
    assert "Fluid density" in fake.error_calls[0][0]
    assert "Traceback" not in fake.error_calls[0][0]


def test_simulate_safely_hides_unexpected_internal_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import src.calculations as calculations

    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)

    def fail(_inputs: JetInputs) -> None:
        raise RuntimeError("private solver detail")

    monkeypatch.setattr(calculations, "simulate", fail)
    with caplog.at_level("ERROR", logger=visualizations.LOGGER.name):
        result = simulate_safely(JetInputs())

    assert result is None
    assert len(fake.error_calls) == 1
    assert "could not be completed" in fake.error_calls[0][0]
    assert "private solver detail" not in fake.error_calls[0][0]
    assert "Simulation failed" in caplog.text


def test_schematic_controls_initialize_state_and_reset_all_overlays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit(invoke_callbacks=True)
    fake.session_state["qa_play"] = False
    monkeypatch.setattr(visualizations, "st", fake)

    options = schematic_controls("qa")

    assert options == {
        "play": True,
        "cv": True,
        "labels": True,
        "forces": True,
        "velocities": True,
    }
    assert [label for label, _kwargs in fake.button_calls] == ["Reset view"]
    assert [label for label, _kwargs in fake.toggle_calls] == [
        "Play animation",
        "Control volume",
        "Labels",
        "Vectors",
    ]


def test_engineering_schematic_embeds_self_contained_svg_data_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)
    inputs = MODEL_CASES[1]

    render_engineering_schematic(
        inputs,
        simulate(inputs),
        show_controls=False,
        height=515,
    )

    assert len(fake.markdown_calls) == 1
    markup, kwargs = fake.markdown_calls[0]
    encoded = re.search(r"data:image/svg\+xml;base64,([^\"]+)", markup)
    assert encoded is not None
    decoded = base64.b64decode(encoded.group(1)).decode("utf-8")
    assert decoded.lstrip().startswith("<svg")
    assert "<!doctype html>" not in decoded.lower()
    assert "<style><![CDATA[" in decoded
    assert 'class="control-volume"' in decoded
    assert 'class="axes"' in decoded
    assert 'alt="Control-volume schematic for Single deflected outlet jet"' in markup
    assert 'style="max-height:515px"' in markup
    assert "Illustrative particle motion playing" in markup
    assert "Arrow lengths are scaled for visibility" in markup
    assert "Static SVG content remains visible if animation is unavailable" in markup
    assert kwargs == {"unsafe_allow_html": True}


def test_engineering_schematic_reports_paused_control_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)
    monkeypatch.setattr(
        visualizations,
        "schematic_controls",
        lambda _prefix: {
            "play": False,
            "cv": True,
            "labels": True,
            "forces": True,
            "velocities": True,
        },
    )
    inputs = MODEL_CASES[2]

    render_engineering_schematic(
        inputs,
        simulate(inputs),
        prefix="paused",
        show_controls=True,
        height=480,
    )

    assert len(fake.markdown_calls) == 1
    markup = fake.markdown_calls[0][0]
    assert 'alt="Control-volume schematic for Split flow along a flat plate"' in markup
    assert "Illustrative particle motion paused" in markup


def test_engineering_schematic_reports_zero_flow_instead_of_playing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(visualizations, "st", fake)
    inputs = JetInputs(velocity=0.0)

    render_engineering_schematic(inputs, simulate(inputs), show_controls=False)

    markup = fake.markdown_calls[0][0]
    assert "No particle motion — zero inlet flow" in markup
    assert "particle motion playing" not in markup.lower()


def test_build_schematic_svg_rejects_malformed_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(visualizations, "build_schematic_html", lambda *_args: "not html")
    with pytest.raises(ValueError, match="could not be converted"):
        build_schematic_svg(JetInputs(), simulate(JetInputs()))


def test_inputs_json_is_readable_and_uses_canonical_model_key() -> None:
    inputs = MODEL_CASES[3]
    parsed = json.loads(inputs_as_json(inputs))
    assert parsed["model"] == "curved_vane"
    assert parsed["beta"] == 180.0
    assert parsed["retention"] == 0.9

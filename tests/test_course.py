"""Course Mode profiles, state transitions, and named analytical demonstrations."""

from __future__ import annotations

from math import fsum, hypot, pi
from types import SimpleNamespace
from typing import Any

import pytest

import src.visualizations as visualizations
from src.calculations import simulate
from src.constants import COURSE_TEXTBOOK_DENSITY_KG_M3, DEFAULT_DENSITY_KG_M3
from src.course import (
    COURSE_MODEL_LABELS,
    COURSE_PRIMARY_DESTINATIONS,
    COURSE_SECONDARY_DESTINATION,
    DEMONSTRATION_PRESET_DESCRIPTIONS,
    AppMode,
    DemonstrationPreset,
    demonstration_inputs,
    textbook_course_inputs,
)
from src.models import FluidPreset, ImpactModel, JetInputs, UnitSystem, Vector2D
from src.validation import validate_inputs

ANALYTICAL_REL_TOLERANCE = 1.0e-12
ANALYTICAL_ABS_TOLERANCE = 1.0e-12
TEXTBOOK_AREA_M2 = pi * 0.02**2 / 4.0
TEXTBOOK_FLOW_RATE_M3_S = TEXTBOOK_AREA_M2 * 10.0
TEXTBOOK_MASS_FLOW_RATE_KG_S = 1000.0 * TEXTBOOK_FLOW_RATE_M3_S
TEXTBOOK_MOMENTUM_FORCE_N = TEXTBOOK_MASS_FLOW_RATE_KG_S * 10.0


def analytical_approx(expected: float) -> pytest.approx:
    """Use the same strict tolerance as the established analytical regressions."""

    return pytest.approx(
        expected,
        rel=ANALYTICAL_REL_TOLERANCE,
        abs=ANALYTICAL_ABS_TOLERANCE,
    )


class SessionState(dict[str, Any]):
    """Small attribute-compatible state double for deterministic callback tests."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def install_session_state(
    monkeypatch: pytest.MonkeyPatch,
) -> SessionState:
    state = SessionState()
    monkeypatch.setattr(visualizations, "st", SimpleNamespace(session_state=state))
    return state


def assert_session_matches_inputs(state: SessionState, inputs: JetInputs) -> None:
    """Assert canonical and paired widget values describe one immutable case."""

    assert state["jf_model"] == inputs.model.value
    assert state["jf_model_widget"] == inputs.model.value
    assert state["jf_fluid_preset"] == inputs.fluid_preset.value
    assert state["jf_density"] == inputs.density
    assert state["jf_viscosity"] == inputs.dynamic_viscosity
    assert state["jf_diameter"] == inputs.diameter
    assert state["jf_diameter_mm"] == pytest.approx(1000.0 * inputs.diameter)
    assert state["jf_velocity"] == inputs.velocity
    assert state["jf_velocity_slider"] == inputs.velocity
    assert state["jf_theta"] == inputs.plate_angle_deg
    assert state["jf_beta"] == inputs.outlet_angle_deg
    assert state["jf_retention"] == inputs.retention_coefficient
    assert state["jf_split"] == inputs.split_fraction
    assert state["jf_unit_system"] == "SI"


def test_textbook_course_profile_is_complete_valid_and_si() -> None:
    inputs = textbook_course_inputs()

    assert inputs == JetInputs(
        density=1000.0,
        dynamic_viscosity=0.001,
        diameter=0.02,
        velocity=10.0,
        model=ImpactModel.NORMAL_FLAT_PLATE,
        plate_angle_deg=90.0,
        outlet_angle_deg=90.0,
        retention_coefficient=1.0,
        split_fraction=0.5,
        fluid_preset=FluidPreset.TEXTBOOK_WATER,
        unit_system=UnitSystem.SI,
    )
    assert inputs.density == COURSE_TEXTBOOK_DENSITY_KG_M3
    assert validate_inputs(inputs).is_valid


def test_room_temperature_water_remains_a_distinct_compatible_preset() -> None:
    assert DEFAULT_DENSITY_KG_M3 == 998.0
    assert JetInputs().density == 998.0
    assert JetInputs().fluid_preset is FluidPreset.WATER
    assert FluidPreset.WATER.density == 998.0
    assert FluidPreset.TEXTBOOK_WATER.density == 1000.0
    assert "room-temperature" in FluidPreset.WATER.label.lower()
    assert "998" in FluidPreset.WATER.label
    assert "textbook" in FluidPreset.TEXTBOOK_WATER.label.lower()
    assert "1000" in FluidPreset.TEXTBOOK_WATER.label


def test_course_model_allowlist_contains_only_documented_choices() -> None:
    assert tuple(COURSE_MODEL_LABELS) == (
        ImpactModel.NORMAL_FLAT_PLATE,
        ImpactModel.DEFLECTED_JET,
    )
    assert COURSE_MODEL_LABELS[ImpactModel.NORMAL_FLAT_PLATE] == "Normal Flat Plate"
    assert (
        COURSE_MODEL_LABELS[ImpactModel.DEFLECTED_JET] == "Deflected Jet / Curved Plate Comparison"
    )
    assert ImpactModel.SPLIT_FLOW not in COURSE_MODEL_LABELS
    assert ImpactModel.CURVED_VANE not in COURSE_MODEL_LABELS


def test_course_navigation_and_demonstration_copy_are_complete() -> None:
    assert COURSE_PRIMARY_DESTINATIONS == (
        "Simulator",
        "Calculation and Results",
        "Theory and Assumptions",
        "Report and Export",
    )
    assert COURSE_SECONDARY_DESTINATION == "About the Project"
    assert tuple(DEMONSTRATION_PRESET_DESCRIPTIONS) == tuple(DemonstrationPreset)
    assert all(DEMONSTRATION_PRESET_DESCRIPTIONS[preset] for preset in DemonstrationPreset)


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        (DemonstrationPreset.NORMAL_PLATE, textbook_course_inputs()),
        (
            DemonstrationPreset.DOUBLE_VELOCITY,
            textbook_course_inputs().with_updates(velocity=20.0),
        ),
        (
            DemonstrationPreset.NINETY_DEGREE_DEFLECTION,
            textbook_course_inputs().with_updates(
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=90.0,
            ),
        ),
    ],
)
def test_named_demonstration_profiles_are_exact(
    preset: DemonstrationPreset,
    expected: JetInputs,
) -> None:
    first = demonstration_inputs(preset)
    second = demonstration_inputs(preset.value)

    assert first == expected
    assert second == expected
    assert first is not second
    assert first.unit_system is UnitSystem.SI
    assert first.fluid_preset is FluidPreset.TEXTBOOK_WATER
    assert first.retention_coefficient == 1.0
    assert first.split_fraction == 0.5


def test_unknown_demonstration_profile_is_rejected() -> None:
    with pytest.raises(ValueError):
        demonstration_inputs("unsupported classroom case")


def test_normal_plate_demonstration_matches_textbook_equations() -> None:
    result = simulate(demonstration_inputs(DemonstrationPreset.NORMAL_PLATE))

    assert result.area_m2 == analytical_approx(0.0003141592653589793)
    assert result.flow_rate_m3_s == analytical_approx(0.003141592653589793)
    assert result.mass_flow_rate_kg_s == analytical_approx(3.141592653589793)
    assert result.fx_n == analytical_approx(31.41592653589793)
    assert result.fy_n == 0.0
    assert result.resultant_force_n == analytical_approx(31.41592653589793)
    assert result.vout_equivalent == Vector2D()
    assert fsum(stream.mass_flow_rate_kg_s for stream in result.outlet_streams) == (
        result.mass_flow_rate_kg_s
    )


def test_double_velocity_demonstration_produces_four_times_normal_force() -> None:
    normal = simulate(demonstration_inputs(DemonstrationPreset.NORMAL_PLATE))
    doubled = simulate(demonstration_inputs(DemonstrationPreset.DOUBLE_VELOCITY))

    assert doubled.area_m2 == normal.area_m2
    assert doubled.flow_rate_m3_s == analytical_approx(2.0 * normal.flow_rate_m3_s)
    assert doubled.mass_flow_rate_kg_s == analytical_approx(2.0 * normal.mass_flow_rate_kg_s)
    assert doubled.fx_n == analytical_approx(125.66370614359172)
    assert doubled.fy_n == 0.0
    assert doubled.resultant_force_n == analytical_approx(125.66370614359172)
    assert doubled.fx_n == analytical_approx(4.0 * normal.fx_n)


def test_ninety_degree_demonstration_has_documented_outlet_and_force_signs() -> None:
    result = simulate(demonstration_inputs(DemonstrationPreset.NINETY_DEGREE_DEFLECTION))

    assert result.inputs.model is ImpactModel.DEFLECTED_JET
    assert result.inputs.outlet_angle_deg == 90.0
    assert result.inputs.retention_coefficient == 1.0
    assert result.vout_equivalent == Vector2D(0.0, 10.0)
    assert result.fx_n == analytical_approx(TEXTBOOK_MOMENTUM_FORCE_N)
    assert result.fy_n == analytical_approx(-TEXTBOOK_MOMENTUM_FORCE_N)
    assert result.resultant_force_n == analytical_approx(
        hypot(TEXTBOOK_MOMENTUM_FORCE_N, TEXTBOOK_MOMENTUM_FORCE_N)
    )
    assert result.force_angle_deg == analytical_approx(-45.0)


def test_fresh_session_initializes_course_mode_without_clobbering_rerun_edits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = install_session_state(monkeypatch)

    visualizations.initialize_session_state()

    assert state["jf_mode"] == AppMode.COURSE.value
    assert state["jf_previous_mode"] == AppMode.COURSE.value
    assert state["jf_presentation_view"] is False
    assert state["jf_show_calculation"] is False
    assert state["jf_demo_preset"] == DemonstrationPreset.NORMAL_PLATE.value
    assert_session_matches_inputs(state, textbook_course_inputs())

    state["jf_density"] = 1025.0
    state["jf_velocity"] = 12.0
    state["jf_velocity_slider"] = 12.0
    visualizations.initialize_session_state()

    assert state["jf_density"] == 1025.0
    assert state["jf_velocity"] == 12.0
    assert state["jf_velocity_slider"] == 12.0


def test_reset_to_default_is_complete_idempotent_and_clears_stale_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = install_session_state(monkeypatch)
    visualizations.initialize_session_state()
    state.update(
        {
            "jf_mode": AppMode.ADVANCED.value,
            "jf_model": ImpactModel.SPLIT_FLOW.value,
            "jf_model_widget": ImpactModel.SPLIT_FLOW.value,
            "jf_fluid_preset": FluidPreset.AIR.value,
            "jf_density": 1.204,
            "jf_viscosity": 1.825e-5,
            "jf_diameter": 0.08,
            "jf_diameter_mm": 80.0,
            "jf_velocity": 22.0,
            "jf_velocity_slider": 22.0,
            "jf_theta": -35.0,
            "jf_beta": -75.0,
            "jf_retention": 0.2,
            "jf_split": 0.9,
            "jf_unit_system": "US",
            "jf_show_calculation": True,
            "jf_report_package": {"stale": True},
        }
    )

    visualizations.reset_to_default()
    first_reset = dict(state)

    assert state["jf_mode"] == AppMode.ADVANCED.value
    assert_session_matches_inputs(state, textbook_course_inputs())
    assert state["jf_show_calculation"] is False
    assert state["jf_demo_preset"] == DemonstrationPreset.NORMAL_PLATE.value
    assert "jf_report_package" not in state
    visualizations.reset_to_default()
    assert dict(state) == first_reset


@pytest.mark.parametrize("preset", list(DemonstrationPreset))
def test_loading_demonstration_synchronizes_state_and_invalidates_report(
    monkeypatch: pytest.MonkeyPatch,
    preset: DemonstrationPreset,
) -> None:
    state = install_session_state(monkeypatch)
    visualizations.initialize_session_state()
    state["jf_report_package"] = {"stale": True}

    visualizations.load_demonstration_case(preset)

    expected = demonstration_inputs(preset)
    assert_session_matches_inputs(state, expected)
    assert state["jf_demo_preset"] == preset.value
    assert "jf_report_package" not in state
    assert state["jf_course_case"]["jf_model"] == expected.model.value
    assert state["jf_course_case"]["jf_density"] == expected.density
    assert state["jf_course_case"]["jf_velocity"] == expected.velocity


def test_advanced_changes_do_not_corrupt_saved_course_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = install_session_state(monkeypatch)
    visualizations.initialize_session_state()
    state["jf_density"] = 1050.0
    state["jf_velocity"] = 14.0
    state["jf_velocity_slider"] = 14.0

    state["jf_mode"] = AppMode.ADVANCED.value
    visualizations._on_mode_change()
    state.update(
        {
            "jf_model": ImpactModel.SPLIT_FLOW.value,
            "jf_model_widget": ImpactModel.SPLIT_FLOW.value,
            "jf_fluid_preset": FluidPreset.AIR.value,
            "jf_density": 1.204,
            "jf_viscosity": 1.825e-5,
            "jf_retention": 0.25,
            "jf_split": 0.8,
            "jf_unit_system": "US",
        }
    )

    state["jf_mode"] = AppMode.COURSE.value
    visualizations._on_mode_change()

    assert state["jf_previous_mode"] == AppMode.COURSE.value
    assert state["jf_density"] == 1050.0
    assert state["jf_velocity"] == 14.0
    assert state["jf_velocity_slider"] == 14.0
    assert state["jf_model"] == ImpactModel.NORMAL_FLAT_PLATE.value
    assert state["jf_model_widget"] == ImpactModel.NORMAL_FLAT_PLATE.value
    assert state["jf_retention"] == 1.0
    assert state["jf_split"] == 0.5
    assert state["jf_unit_system"] == "SI"

"""Tests for validation boundaries and actionable error reporting."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.calculations import simulate
from src.models import ImpactModel, JetInputs
from src.validation import (
    InputValidationError,
    analytical_verification_records,
    hand_calculation_trace,
    normalize_sweep_parameter,
    validate_inputs,
    validate_or_raise,
    validate_sweep_points,
)


def assert_invalid_field(inputs: JetInputs, expected_field: str) -> None:
    report = validate_inputs(inputs)
    assert not report.is_valid
    assert expected_field in report.by_field
    with pytest.raises(InputValidationError) as raised:
        validate_or_raise(inputs)
    assert expected_field in raised.value.report.by_field


def test_default_inputs_are_valid() -> None:
    report = validate_inputs(JetInputs())
    assert report.is_valid
    assert report.issues == ()
    assert report.messages == ()


@pytest.mark.parametrize(
    "field",
    [
        "density",
        "dynamic_viscosity",
        "diameter",
        "velocity",
        "plate_angle_deg",
        "outlet_angle_deg",
        "retention_coefficient",
        "split_fraction",
    ],
)
@pytest.mark.parametrize("value", [False, True])
def test_boolean_numeric_inputs_are_rejected_before_coercion(field: str, value: bool) -> None:
    with pytest.raises(TypeError, match="boolean values are not accepted"):
        JetInputs(**{field: value})  # type: ignore[arg-type]


def test_numpy_boolean_numeric_input_is_rejected_before_coercion() -> None:
    with pytest.raises(TypeError, match="boolean values are not accepted"):
        JetInputs(velocity=np.bool_(True))


def test_positive_velocity_below_reliable_force_resolution_is_invalid() -> None:
    inputs = JetInputs(density=0.001, diameter=0.001, velocity=1.0e-310)
    report = validate_inputs(inputs)

    assert not report.is_valid
    assert report.by_field["velocity"][0].code == "below_numerical_resolution"
    assert "enter exactly zero" in report.by_field["velocity"][0].message


def test_hand_calculation_trace_reconstructs_explicit_stream_balance() -> None:
    result = simulate(
        JetInputs(
            density=1000.0,
            diameter=0.02,
            velocity=10.0,
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=90.0,
            retention_coefficient=0.8,
        )
    )
    trace = hand_calculation_trace(result)

    assert trace.area_m2 == pytest.approx(math.pi * 0.02**2 / 4.0)
    assert trace.flow_rate_m3_s == pytest.approx(trace.area_m2 * 10.0)
    assert trace.mass_flow_rate_kg_s == pytest.approx(1000.0 * trace.flow_rate_m3_s)
    assert trace.outlet_momentum_flux_x_n == pytest.approx(0.0, abs=1.0e-12)
    assert trace.outlet_momentum_flux_y_n == pytest.approx(0.8 * trace.mass_flow_rate_kg_s * 10.0)
    assert trace.fx_n == pytest.approx(result.fx_n)
    assert trace.fy_n == pytest.approx(result.fy_n)
    assert trace.resultant_force_n == pytest.approx(result.resultant_force_n)


def test_hand_calculation_trace_requires_simulation_result() -> None:
    with pytest.raises(TypeError, match="SimulationResult"):
        hand_calculation_trace(JetInputs())  # type: ignore[arg-type]


def test_seven_analytical_verification_records_all_pass() -> None:
    records = analytical_verification_records()

    assert len(records) == 7
    assert [record["Status"] for record in records] == ["PASS"] * 7
    nonideal = next(record for record in records if "Non-ideal" in str(record["Case"]))
    assert nonideal["Expected FR (N)"] == pytest.approx(40.232016128683566, rel=1.0e-12)


@pytest.mark.parametrize("density", [0.0, 0.000999, -1.0, 3000.0001])
def test_invalid_density_is_rejected(density: float) -> None:
    assert_invalid_field(JetInputs(density=density), "density")


@pytest.mark.parametrize("density", [0.001, 998.0, 3000.0])
def test_density_valid_bounds_are_accepted(density: float) -> None:
    assert validate_inputs(JetInputs(density=density)).is_valid


@pytest.mark.parametrize("diameter", [0.0, -0.01, 0.000999, 0.200001])
def test_invalid_diameter_is_rejected(diameter: float) -> None:
    assert_invalid_field(JetInputs(diameter=diameter), "diameter")


@pytest.mark.parametrize("diameter", [0.001, 0.02, 0.20])
def test_diameter_valid_bounds_are_accepted(diameter: float) -> None:
    assert validate_inputs(JetInputs(diameter=diameter)).is_valid


@pytest.mark.parametrize("viscosity", [0.0, -1e-3, 5e-324, 100.0001, 1000.0])
def test_invalid_viscosity_is_rejected(viscosity: float) -> None:
    assert_invalid_field(JetInputs(dynamic_viscosity=viscosity), "dynamic_viscosity")


@pytest.mark.parametrize("viscosity", [1.0e-12, 0.001, 100.0])
def test_viscosity_valid_bounds_are_accepted(viscosity: float) -> None:
    assert validate_inputs(JetInputs(dynamic_viscosity=viscosity)).is_valid


@pytest.mark.parametrize("velocity", [-1e-12, 100.00001])
def test_invalid_velocity_is_rejected(velocity: float) -> None:
    assert_invalid_field(JetInputs(velocity=velocity), "velocity")


@pytest.mark.parametrize("velocity", [0.0, 100.0])
def test_velocity_inclusive_bounds_are_valid(velocity: float) -> None:
    assert validate_inputs(JetInputs(velocity=velocity)).is_valid


@pytest.mark.parametrize("retention", [-0.001, 1.001])
def test_invalid_retention_coefficient_is_rejected(retention: float) -> None:
    assert_invalid_field(JetInputs(retention_coefficient=retention), "retention_coefficient")


@pytest.mark.parametrize("retention", [0.0, 0.8, 1.0])
def test_retention_inclusive_bounds_are_valid(retention: float) -> None:
    assert validate_inputs(JetInputs(retention_coefficient=retention)).is_valid


@pytest.mark.parametrize("split", [-0.001, 1.001])
def test_invalid_split_fraction_is_rejected(split: float) -> None:
    assert_invalid_field(JetInputs(split_fraction=split), "split_fraction")


@pytest.mark.parametrize("split", [0.0, 0.5, 1.0])
def test_split_inclusive_bounds_are_valid(split: float) -> None:
    assert validate_inputs(JetInputs(split_fraction=split)).is_valid


@pytest.mark.parametrize("field", ["plate_angle_deg", "outlet_angle_deg"])
@pytest.mark.parametrize("angle", [-180.001, 180.001])
def test_invalid_angles_are_rejected(field: str, angle: float) -> None:
    assert_invalid_field(JetInputs().with_updates(**{field: angle}), field)


@pytest.mark.parametrize("angle", [-180.0, 0.0, 180.0])
def test_angle_inclusive_bounds_are_valid(angle: float) -> None:
    inputs = JetInputs(plate_angle_deg=angle, outlet_angle_deg=angle)
    assert validate_inputs(inputs).is_valid


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("density", math.nan),
        ("dynamic_viscosity", math.inf),
        ("diameter", math.nan),
        ("velocity", math.inf),
        ("plate_angle_deg", -math.inf),
        ("outlet_angle_deg", math.nan),
        ("retention_coefficient", math.inf),
        ("split_fraction", math.nan),
    ],
)
def test_nonfinite_input_is_rejected(field: str, value: float) -> None:
    assert_invalid_field(JetInputs().with_updates(**{field: value}), field)


def test_validation_aggregates_multiple_problems() -> None:
    inputs = JetInputs(
        density=-10.0,
        dynamic_viscosity=0.0,
        diameter=1.0,
        velocity=-5.0,
        retention_coefficient=2.0,
        split_fraction=-1.0,
    )
    report = validate_inputs(inputs)
    assert set(report.by_field) == {
        "density",
        "dynamic_viscosity",
        "diameter",
        "velocity",
        "retention_coefficient",
        "split_fraction",
    }
    assert len(report.issues) == 6


def test_validation_message_states_value_and_acceptable_range() -> None:
    report = validate_inputs(JetInputs(diameter=0.5))
    message = report.by_field["diameter"][0].message
    assert "between 0.001 and 0.2 m" in message
    assert "received 0.5 m" in message


def test_validate_raise_on_error_option() -> None:
    with pytest.raises(InputValidationError, match="Fluid density"):
        validate_inputs(JetInputs(density=0.0), raise_on_error=True)


def test_validate_inputs_requires_domain_model() -> None:
    with pytest.raises(TypeError, match="JetInputs"):
        validate_inputs({"density": 998.0})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("V", "velocity"),
        ("jet speed", "velocity"),
        ("d", "diameter"),
        ("beta", "outlet_angle_deg"),
        ("theta_deg", "plate_angle_deg"),
        ("k", "retention_coefficient"),
        ("s", "split_fraction"),
        ("rho", "density"),
        ("mu", "dynamic_viscosity"),
    ],
)
def test_sweep_parameter_aliases(alias: str, expected: str) -> None:
    assert normalize_sweep_parameter(alias) == expected


def test_unknown_sweep_parameter_has_choices() -> None:
    with pytest.raises(ValueError, match="Unsupported sweep parameter"):
        normalize_sweep_parameter("pressure")


@pytest.mark.parametrize("points", [2, 50, 1000, 50.0])
def test_sweep_point_valid_bounds(points: int | float) -> None:
    assert validate_sweep_points(points) == int(points)


@pytest.mark.parametrize("points", [1, 1001, 5.5, True, "50"])
def test_invalid_sweep_points_are_rejected(points: object) -> None:
    with pytest.raises(ValueError, match="Sweep points"):
        validate_sweep_points(points)  # type: ignore[arg-type]


def test_impact_model_accepts_readable_string_names() -> None:
    assert JetInputs(model="normal impact").model is ImpactModel.NORMAL_FLAT_PLATE
    assert JetInputs(model="curved-vane").model is ImpactModel.CURVED_VANE

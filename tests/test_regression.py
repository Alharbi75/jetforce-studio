"""Analytical regression cases mandated by the MEC350 project brief."""

from __future__ import annotations

import csv
import io
from math import isnan, pi, sqrt

import numpy as np
import pytest

from src.calculations import parameter_sweep, simulate
from src.models import ImpactModel, JetInputs, UnitSystem, Vector2D
from src.utils import (
    convert_from_si,
    convert_to_si,
    degrees_to_radians,
    force_direction_text,
    format_engineering,
    format_number,
    percentage_difference,
    radians_to_degrees,
    results_to_csv,
)

REFERENCE_INPUTS = dict(density=1000.0, diameter=0.02, velocity=10.0)
REFERENCE_MOMENTUM_FORCE = 1000.0 * (pi * 0.02**2 / 4.0) * 10.0**2
ANALYTICAL_REL_TOLERANCE = 1.0e-12
ANALYTICAL_ABS_TOLERANCE = 1.0e-12


def analytical_approx(expected: float) -> pytest.approx:
    return pytest.approx(
        expected,
        rel=ANALYTICAL_REL_TOLERANCE,
        abs=ANALYTICAL_ABS_TOLERANCE,
    )


def test_case_1_normal_impact_reference_value() -> None:
    result = simulate(JetInputs(**REFERENCE_INPUTS))
    assert result.area_m2 == analytical_approx(0.0003141592653589793)
    assert result.fx_n == analytical_approx(31.41592653589793)
    assert result.fy_n == 0.0
    assert result.resultant_force_n == analytical_approx(31.41592653589793)


def test_case_2_no_change_in_velocity_vector() -> None:
    result = simulate(
        JetInputs(
            **REFERENCE_INPUTS,
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=0.0,
            retention_coefficient=1.0,
        )
    )
    assert result.vout_equivalent == result.inlet_velocity
    assert result.force_on_plate_n == Vector2D()


def test_case_3_ideal_180_degree_reversal() -> None:
    result = simulate(
        JetInputs(
            **REFERENCE_INPUTS,
            model=ImpactModel.CURVED_VANE,
            outlet_angle_deg=180.0,
            retention_coefficient=1.0,
        )
    )
    assert result.fx_n == analytical_approx(2.0 * REFERENCE_MOMENTUM_FORCE)
    assert result.fy_n == 0.0
    assert result.resultant_force_n == analytical_approx(2.0 * REFERENCE_MOMENTUM_FORCE)


def test_case_4_ideal_90_degree_deflection_sign_convention() -> None:
    result = simulate(
        JetInputs(
            **REFERENCE_INPUTS,
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=90.0,
            retention_coefficient=1.0,
        )
    )
    assert result.fx_n == analytical_approx(REFERENCE_MOMENTUM_FORCE)
    assert result.fy_n == analytical_approx(-REFERENCE_MOMENTUM_FORCE)
    assert result.resultant_force_n == analytical_approx(sqrt(2.0) * REFERENCE_MOMENTUM_FORCE)
    assert result.force_angle_deg == analytical_approx(-45.0)


def test_case_5_zero_velocity_no_divide_by_zero() -> None:
    result = simulate(JetInputs(**{**REFERENCE_INPUTS, "velocity": 0.0}))
    assert result.flow_rate_m3_s == 0.0
    assert result.mass_flow_rate_kg_s == 0.0
    assert result.reynolds_number == 0.0
    assert result.fx_n == result.fy_n == result.resultant_force_n == 0.0


def test_case_6_nonideal_outlet_momentum_changes_consistently() -> None:
    ideal = simulate(
        JetInputs(
            **REFERENCE_INPUTS,
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=60.0,
            retention_coefficient=1.0,
        )
    )
    nonideal = simulate(
        JetInputs(
            **REFERENCE_INPUTS,
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=60.0,
            retention_coefficient=0.8,
        )
    )
    assert nonideal.outlet_momentum_flux_n.x == analytical_approx(
        0.8 * ideal.outlet_momentum_flux_n.x
    )
    assert nonideal.outlet_momentum_flux_n.y == analytical_approx(
        0.8 * ideal.outlet_momentum_flux_n.y
    )
    assert nonideal.fx_n == analytical_approx(0.6 * REFERENCE_MOMENTUM_FORCE)
    assert nonideal.fy_n == analytical_approx(-0.8 * sqrt(3.0) / 2.0 * REFERENCE_MOMENTUM_FORCE)


def test_case_6_documented_nonideal_90_degree_resultant() -> None:
    result = simulate(
        JetInputs(
            **REFERENCE_INPUTS,
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=90.0,
            retention_coefficient=0.8,
        )
    )
    assert result.fx_n == analytical_approx(REFERENCE_MOMENTUM_FORCE)
    assert result.fy_n == analytical_approx(-0.8 * REFERENCE_MOMENTUM_FORCE)
    assert result.resultant_force_n == analytical_approx(
        sqrt(1.0 + 0.8**2) * REFERENCE_MOMENTUM_FORCE
    )


def test_case_7_symmetric_split_outlet_momenta_cancel() -> None:
    result = simulate(
        JetInputs(
            **REFERENCE_INPUTS,
            model=ImpactModel.SPLIT_FLOW,
            plate_angle_deg=72.0,
            split_fraction=0.5,
            retention_coefficient=1.0,
        )
    )
    assert result.outlet_momentum_flux_n == Vector2D()
    assert result.fx_n == analytical_approx(REFERENCE_MOMENTUM_FORCE)
    assert result.fy_n == 0.0


def test_velocity_sweep_follows_quadratic_normal_impact_law() -> None:
    velocities = np.array([2.0, 4.0, 8.0, 16.0])
    frame = parameter_sweep(JetInputs(**REFERENCE_INPUTS), "velocity", velocities)
    normalized = frame["FR_N"].to_numpy() / velocities**2
    np.testing.assert_allclose(normalized, normalized[0], rtol=1e-14)


def test_diameter_sweep_follows_area_squared_diameter_law() -> None:
    diameters = np.array([0.005, 0.01, 0.02, 0.04])
    frame = parameter_sweep(JetInputs(**REFERENCE_INPUTS), "diameter", diameters)
    normalized = frame["FR_N"].to_numpy() / diameters**2
    np.testing.assert_allclose(normalized, normalized[0], rtol=1e-14)


def test_split_sweep_matches_closed_form_vector_equation() -> None:
    base = JetInputs(
        **REFERENCE_INPUTS,
        model=ImpactModel.SPLIT_FLOW,
        plate_angle_deg=30.0,
        retention_coefficient=0.75,
    )
    fractions = np.array([0.0, 0.2, 0.5, 0.9, 1.0])
    frame = parameter_sweep(base, "s", fractions)
    net = 2.0 * fractions - 1.0
    expected_fx = REFERENCE_MOMENTUM_FORCE * (1.0 - 0.75 * net * np.cos(np.deg2rad(30.0)))
    expected_fy = -REFERENCE_MOMENTUM_FORCE * 0.75 * net * np.sin(np.deg2rad(30.0))
    np.testing.assert_allclose(frame["Fx_N"], expected_fx, rtol=1e-14)
    np.testing.assert_allclose(frame["Fy_N"], expected_fy, rtol=1e-14, atol=1e-14)


def test_csv_export_is_parseable_and_contains_primary_results() -> None:
    result = simulate(JetInputs(**REFERENCE_INPUTS))
    csv_text = results_to_csv(result)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert float(rows[0]["fx_n"]) == pytest.approx(REFERENCE_MOMENTUM_FORCE)
    assert float(rows[0]["fy_n"]) == 0.0
    assert float(rows[0]["resultant_force_n"]) == pytest.approx(REFERENCE_MOMENTUM_FORCE)
    assert rows[0]["model"] == "normal_flat_plate"


def test_csv_export_rejects_empty_collection() -> None:
    with pytest.raises(ValueError, match="empty"):
        results_to_csv([])


@pytest.mark.parametrize(
    ("quantity", "value"),
    [
        ("diameter", 0.02),
        ("area", 0.000314159),
        ("velocity", 10.0),
        ("flow_rate", 0.0031),
        ("mass_flow_rate", 3.1),
        ("density", 998.0),
        ("dynamic_viscosity", 0.001),
        ("force", 31.4),
    ],
)
def test_si_us_unit_round_trip(quantity: str, value: float) -> None:
    displayed = convert_from_si(value, quantity, UnitSystem.US_CUSTOMARY)
    recovered = convert_to_si(displayed, quantity, UnitSystem.US_CUSTOMARY)
    assert recovered == pytest.approx(value, rel=1e-14)


def test_us_density_and_viscosity_units_reconstruct_reynolds_number() -> None:
    rho = convert_from_si(998.0, "density", UnitSystem.US_CUSTOMARY)
    velocity = convert_from_si(10.0, "velocity", UnitSystem.US_CUSTOMARY)
    diameter_ft = convert_from_si(0.02, "length", UnitSystem.US_CUSTOMARY)
    viscosity = convert_from_si(0.001, "dynamic_viscosity", UnitSystem.US_CUSTOMARY)

    assert rho * velocity * diameter_ft / viscosity == pytest.approx(199_600.0, rel=1e-12)


def test_degree_radian_conversions_support_scalars_and_arrays() -> None:
    assert degrees_to_radians(180.0) == pytest.approx(pi)
    assert radians_to_degrees(pi / 2.0) == pytest.approx(90.0)
    np.testing.assert_allclose(degrees_to_radians([0.0, 90.0, 180.0]), [0.0, pi / 2.0, pi])
    np.testing.assert_allclose(
        degrees_to_radians(value for value in (0.0, 90.0, 180.0)),
        [0.0, pi / 2.0, pi],
    )
    np.testing.assert_allclose(
        radians_to_degrees(value for value in (0.0, pi / 2.0, pi)),
        [0.0, 90.0, 180.0],
    )


def test_numeric_formatting_uses_controlled_precision_and_notation() -> None:
    assert format_number(31.415926, 4) == "31.42"
    assert format_number(0.000314159, 4) == "3.142e-04"
    assert format_number(0.0) == "0"
    assert format_engineering(0.000314159, 4) == "314.2 × 10^-6"


def test_percentage_difference_zero_reference_behavior() -> None:
    assert percentage_difference(10.5, 10.0) == pytest.approx(5.0)
    assert percentage_difference(1.1e-25, 1.0e-25) == pytest.approx(10.0)
    assert isnan(percentage_difference(0.0, 0.0))
    assert isnan(percentage_difference(1.0, 0.0))


def test_reynolds_number_preserves_representable_subnormal_result() -> None:
    from src.calculations import reynolds_number

    assert reynolds_number(0.001, 1.0e-318, 0.001, 0.001) == pytest.approx(
        1.0e-321, rel=0.0, abs=4.94e-324
    )


def test_force_direction_text_does_not_rely_on_color() -> None:
    assert "right" in force_direction_text(Vector2D(2.0, -1.0)).lower()
    assert "downward" in force_direction_text(Vector2D(2.0, -1.0)).lower()
    assert force_direction_text(Vector2D()) == "No resultant force"

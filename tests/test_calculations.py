"""Unit tests for equations and public calculation APIs."""

from __future__ import annotations

from dataclasses import replace
from math import fsum, pi, sqrt

import numpy as np
import pandas as pd
import pytest

from src.calculations import (
    deflected_jet,
    deflected_jet_force,
    force_direction,
    ideal_comparison,
    jet_area,
    mass_flow_rate,
    momentum_force,
    momentum_force_from_streams,
    normal_flat_plate_force,
    outlet_velocity_components,
    parameter_sweep,
    resultant_force,
    reynolds_number,
    simulate,
    split_flow_force,
    velocity_vector,
    volumetric_flow_rate,
)
from src.models import FluidPreset, ImpactModel, JetInputs, OutletStream, UnitSystem, Vector2D


def test_area_uses_circular_jet_equation() -> None:
    assert jet_area(0.02) == pytest.approx(pi * 0.02**2 / 4.0)
    assert jet_area(0.02) == pytest.approx(0.0003141592653589793)


def test_flow_rate_and_mass_flow_follow_continuity() -> None:
    area = jet_area(0.02)
    flow = volumetric_flow_rate(area, 10.0)
    mdot = mass_flow_rate(1000.0, flow)
    assert flow == pytest.approx(0.0031415926535897933)
    assert mdot == pytest.approx(3.141592653589793)


@pytest.mark.parametrize(
    ("rho", "velocity", "diameter", "mu", "expected"),
    [
        (998.0, 10.0, 0.02, 0.001, 199_600.0),
        (1.204, 20.0, 0.01, 1.825e-5, 13_194.520547945205),
        (998.0, 0.0, 0.02, 0.001, 0.0),
    ],
)
def test_reynolds_number_is_diagnostic_formula(
    rho: float, velocity: float, diameter: float, mu: float, expected: float
) -> None:
    assert reynolds_number(rho, velocity, diameter, mu) == pytest.approx(expected)


def test_reynolds_number_rejects_nonpositive_viscosity() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        reynolds_number(998.0, 10.0, 0.02, 0.0)


@pytest.mark.parametrize(
    ("angle", "expected_x", "expected_y"),
    [
        (0.0, 10.0, 0.0),
        (90.0, 0.0, 10.0),
        (-90.0, 0.0, -10.0),
        (180.0, -10.0, 0.0),
        (-135.0, -sqrt(50.0), -sqrt(50.0)),
    ],
)
def test_velocity_vector_resolves_ccw_angle(
    angle: float, expected_x: float, expected_y: float
) -> None:
    vector = velocity_vector(10.0, angle)
    assert vector.x == pytest.approx(expected_x, abs=1e-14)
    assert vector.y == pytest.approx(expected_y, abs=1e-14)


def test_velocity_vector_preserves_small_valid_angle() -> None:
    vector = velocity_vector(10.0, 1.0e-14)

    assert vector.x == 10.0
    assert vector.y == pytest.approx(1.7453292519943295e-15, rel=1.0e-15, abs=0.0)
    assert vector.y > 0.0


def test_outlet_components_apply_retention_to_speed_not_direction() -> None:
    outlet = outlet_velocity_components(12.0, 0.75, 30.0)
    assert outlet.magnitude == pytest.approx(9.0)
    assert outlet.x == pytest.approx(9.0 * sqrt(3.0) / 2.0)
    assert outlet.y == pytest.approx(4.5)


def test_momentum_force_returns_fluid_on_plate_reaction() -> None:
    force = momentum_force(2.5, Vector2D(10.0, 0.0), Vector2D(0.0, 8.0))
    assert force == Vector2D(25.0, -20.0)


def test_vector_components_normalize_negative_zero() -> None:
    vector = -Vector2D(2.0, 0.0)

    assert vector == Vector2D(-2.0, 0.0)
    assert not np.signbit(vector.y)


def test_momentum_force_accepts_two_component_sequences() -> None:
    assert momentum_force(3.0, (4.0, 0.0), (-4.0, 0.0)) == Vector2D(24.0, 0.0)
    with pytest.raises(ValueError, match="exactly two"):
        momentum_force(1.0, (1.0, 2.0, 3.0), (0.0, 0.0))


def test_momentum_force_from_streams_is_mass_weighted_and_conserving() -> None:
    streams = (
        OutletStream("upper", 0.5, 1.0, Vector2D(0.0, 8.0)),
        OutletStream("lower", 0.5, 1.0, Vector2D(0.0, -8.0)),
    )
    assert momentum_force_from_streams(2.0, Vector2D(10.0, 0.0), streams) == Vector2D(20.0, 0.0)
    with pytest.raises(ValueError, match="mass flow must equal"):
        momentum_force_from_streams(3.0, Vector2D(10.0, 0.0), streams)
    with pytest.raises(ValueError, match="mass flow must equal"):
        momentum_force_from_streams(1.0e-18, Vector2D(1.0e-8, 0.0), ())


def test_resultant_and_force_direction() -> None:
    assert resultant_force(3.0, -4.0) == pytest.approx(5.0)
    assert force_direction(3.0, -3.0) == pytest.approx(-45.0)
    assert force_direction(0.0, 0.0) == 0.0


def test_normal_model_matches_direct_analytical_helper() -> None:
    inputs = JetInputs(density=1000.0, diameter=0.02, velocity=10.0)
    result = simulate(inputs)
    direct = normal_flat_plate_force(1000.0, 0.02, 10.0)
    assert result.fx_n == pytest.approx(direct.x)
    assert result.fy_n == pytest.approx(direct.y)
    assert result.outlet_momentum_flux_n == Vector2D()
    assert result.force_on_fluid_n == -result.force_on_plate_n


def test_deflected_model_no_velocity_vector_change_has_no_force() -> None:
    result = simulate(JetInputs(model=ImpactModel.DEFLECTED_JET, outlet_angle_deg=0.0))
    assert result.force_on_plate_n == Vector2D()
    assert result.resultant_force_n == 0.0


def test_deflected_force_helper_matches_simulation() -> None:
    inputs = JetInputs(
        density=900.0,
        diameter=0.015,
        velocity=13.0,
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=-40.0,
        retention_coefficient=0.83,
    )
    result = simulate(inputs)
    direct = deflected_jet_force(900.0, 0.015, 13.0, -40.0, 0.83)
    assert direct.x == pytest.approx(result.fx_n)
    assert direct.y == pytest.approx(result.fy_n)


def test_deflected_function_forces_the_requested_model() -> None:
    source = JetInputs(model=ImpactModel.NORMAL_FLAT_PLATE, outlet_angle_deg=120.0)
    result = deflected_jet(source)
    assert result.inputs.model is ImpactModel.DEFLECTED_JET
    assert len(result.outlet_streams) == 1


def test_curved_vane_uses_same_vector_foundation_as_deflected_jet() -> None:
    shared = JetInputs(
        outlet_angle_deg=145.0,
        retention_coefficient=0.91,
        density=1020.0,
        velocity=17.0,
    )
    curved = simulate(replace(shared, model=ImpactModel.CURVED_VANE))
    deflected = simulate(replace(shared, model=ImpactModel.DEFLECTED_JET))
    assert curved.force_on_plate_n.x == pytest.approx(deflected.fx_n)
    assert curved.force_on_plate_n.y == pytest.approx(deflected.fy_n)


def test_symmetric_split_conserves_mass_and_cancels_outlet_momentum() -> None:
    result = simulate(
        JetInputs(
            model=ImpactModel.SPLIT_FLOW,
            plate_angle_deg=35.0,
            split_fraction=0.5,
            retention_coefficient=0.7,
        )
    )
    assert sum(stream.mass_flow_rate_kg_s for stream in result.outlet_streams) == pytest.approx(
        result.mass_flow_rate_kg_s
    )
    assert fsum(stream.mass_flow_rate_kg_s for stream in result.outlet_streams) == (
        result.mass_flow_rate_kg_s
    )
    assert result.outlet_momentum_flux_n.x == pytest.approx(0.0, abs=1e-14)
    assert result.outlet_momentum_flux_n.y == pytest.approx(0.0, abs=1e-14)
    assert result.fx_n == pytest.approx(result.mass_flow_rate_kg_s * result.inputs.velocity)
    assert result.fy_n == 0.0


def test_asymmetric_split_generates_expected_transverse_reaction() -> None:
    inputs = JetInputs(
        density=1000.0,
        model=ImpactModel.SPLIT_FLOW,
        plate_angle_deg=90.0,
        split_fraction=0.75,
        retention_coefficient=0.8,
    )
    result = simulate(inputs)
    inlet_flux = result.mass_flow_rate_kg_s * inputs.velocity
    assert result.fx_n == pytest.approx(inlet_flux)
    assert result.fy_n == pytest.approx(-0.5 * 0.8 * inlet_flux)


@pytest.mark.parametrize("split_fraction", [0.0, 1.0])
def test_split_fraction_endpoints_are_mass_conserving(split_fraction: float) -> None:
    result = simulate(
        JetInputs(
            model=ImpactModel.SPLIT_FLOW,
            split_fraction=split_fraction,
            plate_angle_deg=0.0,
        )
    )
    assert sum(stream.mass_fraction for stream in result.outlet_streams) == pytest.approx(1.0)
    assert sum(stream.mass_flow_rate_kg_s for stream in result.outlet_streams) == pytest.approx(
        result.mass_flow_rate_kg_s
    )


def test_split_force_helper_matches_model() -> None:
    direct = split_flow_force(1000.0, 0.02, 10.0, 60.0, 0.6, 0.9)
    result = simulate(
        JetInputs(
            density=1000.0,
            diameter=0.02,
            velocity=10.0,
            model=ImpactModel.SPLIT_FLOW,
            plate_angle_deg=60.0,
            split_fraction=0.6,
            retention_coefficient=0.9,
        )
    )
    assert direct.x == pytest.approx(result.fx_n)
    assert direct.y == pytest.approx(result.fy_n)


@pytest.mark.parametrize("model", list(ImpactModel))
def test_zero_inlet_velocity_is_safe_for_every_model(model: ImpactModel) -> None:
    result = simulate(JetInputs(model=model, velocity=0.0))
    assert result.flow_rate_m3_s == 0.0
    assert result.mass_flow_rate_kg_s == 0.0
    assert result.reynolds_number == 0.0
    assert result.force_on_plate_n == Vector2D()
    assert result.force_angle_deg == 0.0
    assert not result.force_direction_defined


def test_nonzero_force_direction_is_marked_defined() -> None:
    result = simulate(JetInputs())
    assert result.force_direction_defined
    assert result.as_dict()["force_direction_defined"] is True


def test_extreme_but_valid_case_remains_finite() -> None:
    result = simulate(
        JetInputs(
            density=3000.0,
            diameter=0.20,
            velocity=100.0,
            dynamic_viscosity=1e-9,
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=-180.0,
        )
    )
    values = np.array([*result.force_on_plate_n, result.reynolds_number])
    assert np.all(np.isfinite(values))
    assert result.fx_n == pytest.approx(2.0 * 3000.0 * pi * 0.20**2 / 4.0 * 100.0**2)


def test_tiny_valid_force_is_preserved_and_matches_sweep_kernel() -> None:
    inputs = JetInputs(density=0.001, diameter=0.001, velocity=1.0e-8)
    result = simulate(inputs)
    expected = 0.001 * pi * 0.001**2 / 4.0 * (1.0e-8) ** 2
    sweep = parameter_sweep(inputs, "velocity", [1.0e-8])

    assert result.fx_n == pytest.approx(expected, rel=1.0e-15, abs=0.0)
    assert result.fx_n > 0.0
    assert sweep.loc[0, "Fx_N"] == result.fx_n


def test_tiny_nonzero_flow_preserves_velocity_direction_and_percentage() -> None:
    inputs = JetInputs(
        density=0.001,
        diameter=0.001,
        velocity=1.0e-8,
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=90.0,
        retention_coefficient=0.8,
    )
    result = simulate(inputs)
    comparison = ideal_comparison(inputs)

    assert result.mass_flow_rate_kg_s > 0.0
    assert result.vout_equivalent == Vector2D(0.0, 0.8e-8)
    assert result.force_direction_defined
    assert result.force_angle_deg == pytest.approx(-38.659808254090095)
    assert comparison.percentage_difference == pytest.approx(9.44614861862584)


@pytest.mark.parametrize("model", [ImpactModel.NORMAL_FLAT_PLATE, ImpactModel.SPLIT_FLOW])
def test_unrepresentable_nonzero_momentum_scale_is_rejected(model: ImpactModel) -> None:
    with pytest.raises(ValueError, match="below reliable binary64 momentum resolution"):
        simulate(
            JetInputs(
                density=0.001,
                diameter=0.001,
                velocity=1.0e-310,
                model=model,
                split_fraction=0.5,
            )
        )


def test_sweep_cardinal_angles_and_normal_zero_component_are_exact() -> None:
    deflected = JetInputs(model=ImpactModel.DEFLECTED_JET)
    angle_sweep = parameter_sweep(deflected, "outlet_angle_deg", [-180.0, 180.0])
    normal_sweep = parameter_sweep(JetInputs(), "velocity", [0.0, 10.0])

    assert angle_sweep["Fy_N"].tolist() == [0.0, 0.0]
    assert normal_sweep["Fy_N"].tolist() == [0.0, 0.0]
    assert not np.signbit(normal_sweep["Fy_N"].to_numpy()).any()


def test_ideal_comparison_preserves_geometry_and_sets_k_to_one() -> None:
    inputs = JetInputs(
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=135.0,
        retention_coefficient=0.8,
    )
    comparison = ideal_comparison(inputs)
    assert comparison.actual.inputs.retention_coefficient == 0.8
    assert comparison.ideal.inputs.retention_coefficient == 1.0
    assert comparison.ideal.inputs.outlet_angle_deg == 135.0
    assert comparison.absolute_difference_n > 0.0
    assert comparison.percentage_difference > 0.0


def test_parameter_sweep_has_documented_columns_and_is_vectorized() -> None:
    base = JetInputs(model=ImpactModel.NORMAL_FLAT_PLATE)
    frame = parameter_sweep(base, "velocity", start=0.0, stop=20.0, points=5)
    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == [
        "velocity",
        "Fx_N",
        "Fy_N",
        "FR_N",
        "Q_m3_s",
        "mdot_kg_s",
        "Re",
        "outlet_speed_m_s",
    ]
    np.testing.assert_allclose(frame["velocity"], [0.0, 5.0, 10.0, 15.0, 20.0])
    assert frame.loc[4, "FR_N"] == pytest.approx(4.0 * frame.loc[2, "FR_N"])


def test_parameter_sweep_alias_and_rows_match_scalar_solver() -> None:
    base = JetInputs(
        model=ImpactModel.DEFLECTED_JET,
        outlet_angle_deg=30.0,
        retention_coefficient=0.9,
    )
    angles = np.array([-180.0, -45.0, 0.0, 90.0, 180.0])
    frame = parameter_sweep(base, "beta", angles)
    assert "outlet_angle_deg" in frame
    for row in frame.itertuples(index=False):
        scalar = simulate(base.with_updates(beta=row.outlet_angle_deg))
        assert row.Fx_N == pytest.approx(scalar.fx_n)
        assert row.Fy_N == pytest.approx(scalar.fy_n)
        assert pytest.approx(scalar.resultant_force_n) == row.FR_N
    assert base.outlet_angle_deg == 30.0


@pytest.mark.parametrize("values", ([True, False], np.array([True, False], dtype=bool)))
def test_parameter_sweep_rejects_boolean_values(values) -> None:
    with pytest.raises(TypeError, match="boolean values are not accepted"):
        parameter_sweep(JetInputs(), "velocity", values)


@pytest.mark.parametrize(("start", "stop"), [(True, 2.0), (0.0, np.bool_(False))])
def test_parameter_sweep_rejects_boolean_bounds(start, stop) -> None:
    with pytest.raises(TypeError, match="boolean values are not accepted"):
        parameter_sweep(JetInputs(), "velocity", start=start, stop=stop, points=3)


def test_jet_inputs_presets_aliases_and_serialization() -> None:
    air = JetInputs.from_preset(FluidPreset.AIR, velocity=5.0)
    modified = air.with_updates(rho=1.3, mu=1.9e-5, d=0.01, beta=-20, k=0.9)
    assert modified.rho == 1.3
    assert modified.mu == 1.9e-5
    assert modified.d == 0.01
    assert modified.beta_deg == -20.0
    assert modified.k == 0.9
    assert modified.unit_system is UnitSystem.SI
    assert modified.as_dict()["fluid_preset"] == "air"

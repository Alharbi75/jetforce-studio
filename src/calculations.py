"""Physically transparent SI calculations for water-jet impact.

The sign convention is fixed throughout this module: the inlet jet travels in
the positive x direction, positive y is upward, and primary forces are the
reaction exerted by the fluid on the plate::

    F_plate = sum(mdot_in * V_in) - sum(mdot_out * V_out)

Consequently, ``force_on_fluid`` is exactly the negative of ``force_on_plate``.
Pressure is atmospheric at the exposed free-jet boundaries and is represented
using zero gauge pressure; no empirical Reynolds-number force correction is
introduced.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from math import atan2, cos, degrees, fsum, hypot, isclose, isfinite, pi, radians, sin
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

from .constants import DEFAULT_SWEEP_POINTS, SWEEP_PARAMETER_BOUNDS
from .models import (
    IdealComparison,
    ImpactModel,
    JetInputs,
    OutletStream,
    SimulationResult,
    Vector2D,
)
from .validation import (
    normalize_sweep_parameter,
    validate_inputs,
    validate_or_raise,
    validate_sweep_points,
)


def jet_area(diameter_m: float) -> float:
    """Return circular jet cross-sectional area, ``pi*d**2/4`` [m²]."""

    return pi * float(diameter_m) ** 2 / 4.0


def volumetric_flow_rate(area_m2: float, velocity_m_s: float) -> float:
    """Return volumetric flow ``Q = A*V`` [m³/s]."""

    return float(area_m2) * float(velocity_m_s)


def mass_flow_rate(density_kg_m3: float, flow_rate_m3_s: float) -> float:
    """Return mass flow ``mdot = rho*Q`` [kg/s]."""

    return float(density_kg_m3) * float(flow_rate_m3_s)


def reynolds_number(
    density_kg_m3: float,
    velocity_m_s: float,
    diameter_m: float,
    dynamic_viscosity_pa_s: float,
) -> float:
    """Return jet Reynolds number ``rho*V*d/mu`` (diagnostic only)."""

    viscosity = float(dynamic_viscosity_pa_s)
    if viscosity <= 0.0:
        raise ValueError("Dynamic viscosity must be greater than zero.")
    # Form the bounded coefficient first. This preserves very small, still
    # representable Reynolds numbers that would be lost by early underflow in
    # rho*V*d.
    coefficient = float(density_kg_m3) * float(diameter_m) / viscosity
    value = coefficient * float(velocity_m_s)
    if not isfinite(value):
        raise ValueError(
            "The Reynolds number is not finite for these inputs; increase dynamic viscosity."
        )
    return value


def velocity_vector(speed_m_s: float, angle_deg: float) -> Vector2D:
    """Resolve a speed at a CCW angle from +x into Cartesian components."""

    speed = float(speed_m_s)
    raw_angle = float(angle_deg)
    # Valid simulation angles already lie in [-180, 180]. Avoid adding a
    # large offset in that domain because it can erase a small representable
    # angle through floating-point cancellation.
    normalized = raw_angle if -180.0 <= raw_angle <= 180.0 else (raw_angle + 180.0) % 360.0 - 180.0
    cardinal = {
        -180.0: Vector2D(-speed, 0.0),
        -90.0: Vector2D(0.0, -speed),
        0.0: Vector2D(speed, 0.0),
        90.0: Vector2D(0.0, speed),
        180.0: Vector2D(-speed, 0.0),
    }
    if normalized in cardinal:
        return cardinal[normalized]
    angle_rad = radians(normalized)
    return Vector2D(speed * cos(angle_rad), speed * sin(angle_rad))


def outlet_velocity_components(
    inlet_velocity_m_s: float,
    retention_coefficient: float,
    outlet_angle_deg: float,
) -> Vector2D:
    """Return ``k*V*[cos(beta), sin(beta)]`` for a single outlet."""

    return velocity_vector(
        float(retention_coefficient) * float(inlet_velocity_m_s),
        outlet_angle_deg,
    )


def momentum_force(
    mass_flow_rate_kg_s: float,
    inlet_velocity_m_s: Vector2D | Sequence[float],
    outlet_velocity_m_s: Vector2D | Sequence[float],
) -> Vector2D:
    """Return force on the plate for one equivalent inlet and outlet vector."""

    vin = _coerce_vector(inlet_velocity_m_s)
    vout = _coerce_vector(outlet_velocity_m_s)
    return float(mass_flow_rate_kg_s) * (vin - vout)


def momentum_force_from_streams(
    inlet_mass_flow_rate_kg_s: float,
    inlet_velocity_m_s: Vector2D | Sequence[float],
    outlet_streams: Iterable[OutletStream],
) -> Vector2D:
    """Return plate reaction from explicitly mass-weighted outlet streams."""

    streams = tuple(outlet_streams)
    total_outlet_mdot = fsum(stream.mass_flow_rate_kg_s for stream in streams)
    if not isclose(
        total_outlet_mdot,
        float(inlet_mass_flow_rate_kg_s),
        rel_tol=1.0e-12,
        abs_tol=0.0,
    ):
        raise ValueError("Outlet stream mass flow must equal inlet mass flow.")
    vin = _coerce_vector(inlet_velocity_m_s)
    inlet_flux = float(inlet_mass_flow_rate_kg_s) * vin
    outlet_flux = Vector2D(
        fsum(stream.momentum_flux_n.x for stream in streams),
        fsum(stream.momentum_flux_n.y for stream in streams),
    )
    return inlet_flux - outlet_flux


def resultant_force(fx_n: float, fy_n: float) -> float:
    """Return ``sqrt(Fx² + Fy²)`` [N]."""

    return hypot(float(fx_n), float(fy_n))


def force_direction(fx_n: float, fy_n: float) -> float:
    """Return force direction [degrees CCW from +x], or 0 for zero force."""

    if float(fx_n) == 0.0 and float(fy_n) == 0.0:
        return 0.0
    return degrees(atan2(float(fy_n), float(fx_n)))


def normal_impact(inputs: JetInputs) -> SimulationResult:
    """Solve normal impact with equal sideways streams and zero net outlet momentum."""

    case = replace(inputs, model=ImpactModel.NORMAL_FLAT_PLATE)
    outlet_speed = case.retention_coefficient * case.velocity
    return _simulate_streams(
        case,
        (
            ("Upper sideways outlet", 0.5, Vector2D(0.0, outlet_speed)),
            ("Lower sideways outlet", 0.5, Vector2D(0.0, -outlet_speed)),
        ),
    )


def deflected_jet(inputs: JetInputs) -> SimulationResult:
    """Solve a single outlet jet at absolute angle beta from the +x axis."""

    case = replace(inputs, model=ImpactModel.DEFLECTED_JET)
    return _simulate_streams(
        case,
        (
            (
                "Deflected outlet",
                1.0,
                velocity_vector(
                    case.retention_coefficient * case.velocity,
                    case.outlet_angle_deg,
                ),
            ),
        ),
    )


def curved_vane(inputs: JetInputs) -> SimulationResult:
    """Solve a curved vane using the same defensible vector model as a deflected jet."""

    case = replace(inputs, model=ImpactModel.CURVED_VANE)
    return _simulate_streams(
        case,
        (
            (
                "Curved-vane outlet",
                1.0,
                velocity_vector(
                    case.retention_coefficient * case.velocity,
                    case.outlet_angle_deg,
                ),
            ),
        ),
    )


def split_flow(inputs: JetInputs) -> SimulationResult:
    """Solve two opposed tangent outlets with mass fractions ``s`` and ``1-s``."""

    case = replace(inputs, model=ImpactModel.SPLIT_FLOW)
    first_velocity = velocity_vector(
        case.retention_coefficient * case.velocity,
        case.plate_angle_deg,
    )
    return _simulate_streams(
        case,
        (
            ("First tangent outlet", case.split_fraction, first_velocity),
            (
                "Opposite tangent outlet",
                1.0 - case.split_fraction,
                -first_velocity,
            ),
        ),
    )


def simulate(inputs: JetInputs) -> SimulationResult:
    """Validate and dispatch one case to its selected impact model."""

    validate_or_raise(inputs)
    dispatch = {
        ImpactModel.NORMAL_FLAT_PLATE: normal_impact,
        ImpactModel.DEFLECTED_JET: deflected_jet,
        ImpactModel.SPLIT_FLOW: split_flow,
        ImpactModel.CURVED_VANE: curved_vane,
    }
    return dispatch[inputs.model](inputs)


def ideal_comparison(inputs: JetInputs) -> IdealComparison:
    """Compare the selected ``k`` with the same geometry at ideal ``k=1``."""

    actual = simulate(inputs)
    ideal = simulate(replace(inputs, retention_coefficient=1.0))
    return IdealComparison(actual=actual, ideal=ideal)


def normal_flat_plate_force(
    density_kg_m3: float, diameter_m: float, velocity_m_s: float
) -> Vector2D:
    """Convenience analytical result ``[rho*A*V², 0]`` [N]."""

    axial_force = float(density_kg_m3) * jet_area(diameter_m) * float(velocity_m_s) ** 2
    return Vector2D(axial_force, 0.0)


def deflected_jet_force(
    density_kg_m3: float,
    diameter_m: float,
    velocity_m_s: float,
    outlet_angle_deg: float,
    retention_coefficient: float = 1.0,
) -> Vector2D:
    """Convenience force result for a single deflected outlet."""

    area = jet_area(diameter_m)
    mdot = mass_flow_rate(density_kg_m3, volumetric_flow_rate(area, velocity_m_s))
    return momentum_force(
        mdot,
        Vector2D(velocity_m_s, 0.0),
        outlet_velocity_components(velocity_m_s, retention_coefficient, outlet_angle_deg),
    )


def split_flow_force(
    density_kg_m3: float,
    diameter_m: float,
    velocity_m_s: float,
    plate_angle_deg: float,
    split_fraction: float = 0.5,
    retention_coefficient: float = 1.0,
) -> Vector2D:
    """Convenience force result for two exactly opposed tangent outlets."""

    inputs = JetInputs(
        density=density_kg_m3,
        diameter=diameter_m,
        velocity=velocity_m_s,
        model=ImpactModel.SPLIT_FLOW,
        plate_angle_deg=plate_angle_deg,
        split_fraction=split_fraction,
        retention_coefficient=retention_coefficient,
    )
    return split_flow(inputs).force_on_plate_n


def parameter_sweep(
    base_inputs: JetInputs,
    parameter: str,
    values: Sequence[float] | np.ndarray | None = None,
    *,
    start: float | None = None,
    stop: float | None = None,
    points: int = DEFAULT_SWEEP_POINTS,
) -> pd.DataFrame:
    """Evaluate a one-parameter study through the scalar solver and return a tidy DataFrame.

    Output columns are the canonical parameter field followed by ``Fx_N``,
    ``Fy_N``, ``FR_N``, ``Q_m3_s``, ``mdot_kg_s``, ``Re``, and
    ``outlet_speed_m_s``.  No input is clipped; any invalid sweep value raises
    :class:`InputValidationError`.
    """

    import pandas as pd

    validate_or_raise(base_inputs)
    canonical = normalize_sweep_parameter(parameter)
    if values is None:
        if start is None or stop is None:
            raise ValueError("Provide values or both start and stop for a sweep.")
        if isinstance(start, (bool, np.bool_)) or isinstance(stop, (bool, np.bool_)):
            raise TypeError("Sweep bounds must be numeric; boolean values are not accepted.")
        count = validate_sweep_points(points)
        sweep_values = np.linspace(float(start), float(stop), count, dtype=np.float64)
    else:
        raw_values = np.asarray(values, dtype=object)
        if raw_values.ndim != 1 or raw_values.size == 0:
            raise ValueError("Sweep values must be a non-empty one-dimensional sequence.")
        if raw_values.size > 1000:
            raise ValueError("A parameter sweep is limited to 1000 points.")
        if any(isinstance(value, (bool, np.bool_)) for value in raw_values):
            raise TypeError("Sweep values must be numeric; boolean values are not accepted.")
        sweep_values = np.asarray(raw_values, dtype=np.float64)

    _validate_sweep_values(base_inputs, canonical, sweep_values)

    arrays = _vectorized_case_arrays(base_inputs, canonical, sweep_values)
    return pd.DataFrame(
        {
            canonical: sweep_values,
            "Fx_N": arrays["fx"],
            "Fy_N": arrays["fy"],
            "FR_N": arrays["fr"],
            "Q_m3_s": arrays["flow_rate"],
            "mdot_kg_s": arrays["mass_flow_rate"],
            "Re": arrays["reynolds_number"],
            "outlet_speed_m_s": arrays["outlet_speed"],
        }
    )


def _vectorized_case_arrays(
    base_inputs: JetInputs,
    canonical: str,
    sweep_values: np.ndarray,
) -> dict[str, np.ndarray]:
    """Evaluate a validated study with NumPy using the scalar solver's equations."""

    count = sweep_values.size

    def values(field: str, scalar: float) -> np.ndarray:
        if canonical == field:
            return sweep_values
        return np.full(count, scalar, dtype=np.float64)

    density = values("density", base_inputs.density)
    viscosity = values("dynamic_viscosity", base_inputs.dynamic_viscosity)
    diameter = values("diameter", base_inputs.diameter)
    velocity = values("velocity", base_inputs.velocity)
    beta = values("outlet_angle_deg", base_inputs.outlet_angle_deg)
    theta = values("plate_angle_deg", base_inputs.plate_angle_deg)
    retention = values("retention_coefficient", base_inputs.retention_coefficient)
    split = values("split_fraction", base_inputs.split_fraction)

    area = np.pi * diameter**2 / 4.0
    flow_rate = area * velocity
    mdot = density * flow_rate
    reynolds = (density * diameter / viscosity) * velocity
    outlet_speed = retention * velocity

    if base_inputs.model is ImpactModel.NORMAL_FLAT_PLATE:
        outlet_flux_x = np.zeros(count, dtype=np.float64)
        outlet_flux_y = np.zeros(count, dtype=np.float64)
    elif base_inputs.model in {ImpactModel.DEFLECTED_JET, ImpactModel.CURVED_VANE}:
        direction_x, direction_y = _vectorized_direction(beta)
        outlet_flux_x = mdot * outlet_speed * direction_x
        outlet_flux_y = mdot * outlet_speed * direction_y
    else:
        direction_x, direction_y = _vectorized_direction(theta)
        net_fraction = 2.0 * split - 1.0
        outlet_flux_x = mdot * net_fraction * outlet_speed * direction_x
        outlet_flux_y = mdot * net_fraction * outlet_speed * direction_y

    fx = mdot * velocity - outlet_flux_x
    fy = -outlet_flux_y
    fx[fx == 0.0] = 0.0
    fy[fy == 0.0] = 0.0
    return {
        "fx": fx,
        "fy": fy,
        "fr": np.hypot(fx, fy),
        "flow_rate": flow_rate,
        "mass_flow_rate": mdot,
        "reynolds_number": reynolds,
        "outlet_speed": outlet_speed,
    }


def _vectorized_direction(angle_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return exact cardinal and floating-point non-cardinal unit directions."""

    radians_array = np.deg2rad(angle_deg)
    x = np.cos(radians_array)
    y = np.sin(radians_array)
    cardinal_values = {
        -180.0: (-1.0, 0.0),
        -90.0: (0.0, -1.0),
        0.0: (1.0, 0.0),
        90.0: (0.0, 1.0),
        180.0: (-1.0, 0.0),
    }
    for angle, (x_value, y_value) in cardinal_values.items():
        mask = angle_deg == angle
        x[mask] = x_value
        y[mask] = y_value
    return x, y


def _coerce_vector(value: Vector2D | Sequence[float]) -> Vector2D:
    if isinstance(value, Vector2D):
        return value
    if len(value) != 2:
        raise ValueError("A 2D vector must contain exactly two components.")
    return Vector2D(value[0], value[1])


def _base_quantities(inputs: JetInputs) -> tuple[float, float, float, float]:
    area = jet_area(inputs.diameter)
    flow_rate = volumetric_flow_rate(area, inputs.velocity)
    mdot = mass_flow_rate(inputs.density, flow_rate)
    re = reynolds_number(
        inputs.density,
        inputs.velocity,
        inputs.diameter,
        inputs.dynamic_viscosity,
    )
    return area, flow_rate, mdot, re


def _simulate_streams(
    inputs: JetInputs, outlet_definitions: Iterable[tuple[str, float, Vector2D]]
) -> SimulationResult:
    validate_or_raise(inputs)
    area, flow_rate, mdot, re = _base_quantities(inputs)
    inlet_velocity = Vector2D(inputs.velocity, 0.0)
    definitions = tuple(outlet_definitions)
    allocated_mdot: list[float] = []
    stream_items: list[OutletStream] = []
    for index, (name, fraction, velocity) in enumerate(definitions):
        # Assign the final branch as the exact residual. This preserves mass
        # even when two independently rounded subnormal products would differ
        # from the inlet rate by one floating-point unit.
        branch_mdot = (
            mdot - fsum(allocated_mdot) if index == len(definitions) - 1 else float(fraction) * mdot
        )
        allocated_mdot.append(branch_mdot)
        stream_items.append(
            OutletStream(
                name=name,
                mass_fraction=float(fraction),
                mass_flow_rate_kg_s=branch_mdot,
                velocity_m_s=velocity,
            )
        )
    streams = tuple(stream_items)
    outlet_momentum = Vector2D(
        fsum(stream.momentum_flux_n.x for stream in streams),
        fsum(stream.momentum_flux_n.y for stream in streams),
    )
    force_plate = momentum_force_from_streams(mdot, inlet_velocity, streams)
    return SimulationResult(
        inputs=inputs,
        area_m2=area,
        flow_rate_m3_s=flow_rate,
        mass_flow_rate_kg_s=mdot,
        reynolds_number=re,
        inlet_velocity=inlet_velocity,
        outlet_streams=streams,
        outlet_momentum_flux_n=outlet_momentum,
        force_on_plate_n=force_plate,
        force_on_fluid_n=-force_plate,
        outlet_speed_m_s=inputs.retention_coefficient * inputs.velocity,
    )


def _validate_sweep_values(base_inputs: JetInputs, canonical: str, values: np.ndarray) -> None:
    if not np.all(np.isfinite(values)):
        bad_value = values[np.flatnonzero(~np.isfinite(values))[0]]
        invalid = base_inputs.with_updates(**{canonical: float(bad_value)})
        validate_inputs(invalid, raise_on_error=True)
    minimum, maximum = SWEEP_PARAMETER_BOUNDS[canonical]
    invalid_mask = (values < minimum) | (values > maximum)
    if np.any(invalid_mask):
        bad_value = float(values[np.flatnonzero(invalid_mask)[0]])
        invalid = base_inputs.with_updates(**{canonical: bad_value})
        validate_inputs(invalid, raise_on_error=True)


# Clear compatibility aliases used by the UI, reports, and teaching material.
calculate_area = jet_area
calculate_flow_rate = volumetric_flow_rate
calculate_mass_flow_rate = mass_flow_rate
calculate_reynolds_number = reynolds_number
calculate_resultant_force = resultant_force
calculate_force_direction = force_direction
calculate_jet_impact = simulate
calculate_simulation = simulate
run_simulation = simulate
calculate_parameter_sweep = parameter_sweep

"""Input validation for physically meaningful and numerically safe cases."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import fsum, hypot, isfinite, pi, sqrt
from numbers import Real
from sys import float_info
from typing import Any

from .constants import (
    MAX_ANGLE_DEG,
    MAX_DENSITY_KG_M3,
    MAX_DIAMETER_M,
    MAX_DYNAMIC_VISCOSITY_PA_S,
    MAX_RETENTION_COEFFICIENT,
    MAX_SPLIT_FRACTION,
    MAX_SWEEP_POINTS,
    MAX_VELOCITY_M_S,
    MIN_ANGLE_DEG,
    MIN_DENSITY_KG_M3,
    MIN_DIAMETER_M,
    MIN_DYNAMIC_VISCOSITY_PA_S,
    MIN_RETENTION_COEFFICIENT,
    MIN_SPLIT_FRACTION,
    MIN_SWEEP_POINTS,
    MIN_VELOCITY_M_S,
    SWEEP_PARAMETER_ALIASES,
)
from .models import ImpactModel, JetInputs, SimulationResult, ValidationIssue, ValidationReport


class InputValidationError(ValueError):
    """Raised when one or more simulation inputs are outside accepted limits."""

    def __init__(self, report: ValidationReport):
        self.report = report
        details = "; ".join(report.messages) or "Invalid simulation inputs."
        super().__init__(details)


@dataclass(frozen=True, slots=True)
class HandCalculationTrace:
    """Presentation-ready scalar reconstruction of the momentum balance.

    The simulator and this trace share the documented outlet-stream state, but
    this path recomputes the scalar substitutions used on the validation and
    report pages. Keeping the trace here prevents those two interfaces from
    maintaining separate copies of the governing arithmetic.
    """

    area_m2: float
    flow_rate_m3_s: float
    mass_flow_rate_kg_s: float
    inlet_momentum_flux_x_n: float
    inlet_momentum_flux_y_n: float
    outlet_momentum_flux_x_n: float
    outlet_momentum_flux_y_n: float
    fx_n: float
    fy_n: float
    resultant_force_n: float


def hand_calculation_trace(result: SimulationResult) -> HandCalculationTrace:
    """Re-sum the visible substitutions from one explicit simulator stream state."""

    if not isinstance(result, SimulationResult):
        raise TypeError("result must be a SimulationResult instance")
    inputs = result.inputs
    area = pi * inputs.diameter**2 / 4.0
    flow_rate = area * inputs.velocity
    mass_flow = inputs.density * flow_rate
    inlet_flux_x = mass_flow * result.inlet_velocity.x
    inlet_flux_y = mass_flow * result.inlet_velocity.y
    outlet_flux_x = fsum(
        stream.mass_flow_rate_kg_s * stream.velocity_m_s.x for stream in result.outlet_streams
    )
    outlet_flux_y = fsum(
        stream.mass_flow_rate_kg_s * stream.velocity_m_s.y for stream in result.outlet_streams
    )
    fx = inlet_flux_x - outlet_flux_x
    fy = inlet_flux_y - outlet_flux_y
    return HandCalculationTrace(
        area_m2=area,
        flow_rate_m3_s=flow_rate,
        mass_flow_rate_kg_s=mass_flow,
        inlet_momentum_flux_x_n=inlet_flux_x,
        inlet_momentum_flux_y_n=inlet_flux_y,
        outlet_momentum_flux_x_n=outlet_flux_x,
        outlet_momentum_flux_y_n=outlet_flux_y,
        fx_n=fx,
        fy_n=fy,
        resultant_force_n=hypot(fx, fy),
    )


def analytical_verification_records() -> tuple[dict[str, object], ...]:
    """Return the seven independent closed-form regression comparisons used by the UI."""

    from .calculations import simulate

    rho, diameter, velocity = 1000.0, 0.02, 10.0
    base_force = rho * (pi * diameter**2 / 4.0) * velocity**2
    base = JetInputs(
        density=rho,
        dynamic_viscosity=0.001,
        diameter=diameter,
        velocity=velocity,
    )
    cases = (
        (
            "1 · Normal impact",
            replace(base, model=ImpactModel.NORMAL_FLAT_PLATE),
            (base_force, 0.0, base_force),
        ),
        (
            "2 · Unchanged velocity",
            replace(
                base,
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=0.0,
                retention_coefficient=1.0,
            ),
            (0.0, 0.0, 0.0),
        ),
        (
            "3 · 180° reversal",
            replace(
                base,
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=180.0,
                retention_coefficient=1.0,
            ),
            (2.0 * base_force, 0.0, 2.0 * base_force),
        ),
        (
            "4 · 90° deflection",
            replace(
                base,
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=90.0,
                retention_coefficient=1.0,
            ),
            (base_force, -base_force, hypot(base_force, base_force)),
        ),
        (
            "5 · Zero inlet speed",
            replace(base, model=ImpactModel.NORMAL_FLAT_PLATE, velocity=0.0),
            (0.0, 0.0, 0.0),
        ),
        (
            "6 · Non-ideal k = 0.8",
            replace(
                base,
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=90.0,
                retention_coefficient=0.8,
            ),
            (base_force, -0.8 * base_force, hypot(base_force, 0.8 * base_force)),
        ),
        (
            "7 · Symmetric split",
            replace(
                base,
                model=ImpactModel.SPLIT_FLOW,
                plate_angle_deg=37.0,
                split_fraction=0.5,
                retention_coefficient=1.0,
            ),
            (base_force, 0.0, base_force),
        ),
    )
    rows: list[dict[str, object]] = []
    relative_tolerance = 1.0e-9
    for name, case_inputs, expected in cases:
        actual = simulate(case_inputs)
        errors = (
            abs(actual.fx_n - expected[0]),
            abs(actual.fy_n - expected[1]),
            abs(actual.resultant_force_n - expected[2]),
        )
        allowed = relative_tolerance * max(max(abs(item) for item in expected), 1.0)
        rows.append(
            {
                "Case": name,
                "Expected Fx (N)": expected[0],
                "Model Fx (N)": actual.fx_n,
                "Expected Fy (N)": expected[1],
                "Model Fy (N)": actual.fy_n,
                "Expected FR (N)": expected[2],
                "Model FR (N)": actual.resultant_force_n,
                "Max |difference| (N)": max(errors),
                "Status": "PASS" if max(errors) <= allowed else "CHECK",
            }
        )
    return tuple(rows)


def _is_finite_real(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(float(value))


def _finite_issue(field: str, value: Any, label: str, unit: str = "") -> ValidationIssue:
    suffix = f" {unit}" if unit else ""
    return ValidationIssue(
        field=field,
        value=value,
        code="not_finite",
        message=f"{label} must be a finite numeric value{suffix}.",
    )


def _bounded_issue(
    field: str,
    value: float,
    label: str,
    minimum: float,
    maximum: float,
    unit: str = "",
) -> ValidationIssue:
    unit_suffix = f" {unit}" if unit else ""
    return ValidationIssue(
        field=field,
        value=value,
        minimum=minimum,
        maximum=maximum,
        code="out_of_range",
        message=(
            f"{label} must be between {minimum:g} and {maximum:g}{unit_suffix}; "
            f"received {value:g}{unit_suffix}."
        ),
    )


def validate_inputs(inputs: JetInputs, *, raise_on_error: bool = False) -> ValidationReport:
    """Validate one case without silently clipping or changing any value.

    Parameters
    ----------
    inputs:
        Typed simulation state, expressed entirely in SI units.
    raise_on_error:
        When true, raise :class:`InputValidationError`; otherwise return all
        issues so a UI can display them together.
    """

    if not isinstance(inputs, JetInputs):
        raise TypeError("inputs must be a JetInputs instance")

    issues: list[ValidationIssue] = []
    bounded_fields = (
        (
            "diameter",
            inputs.diameter,
            "Jet diameter",
            MIN_DIAMETER_M,
            MAX_DIAMETER_M,
            "m",
        ),
        (
            "velocity",
            inputs.velocity,
            "Inlet jet velocity",
            MIN_VELOCITY_M_S,
            MAX_VELOCITY_M_S,
            "m/s",
        ),
        (
            "plate_angle_deg",
            inputs.plate_angle_deg,
            "Plate orientation angle",
            MIN_ANGLE_DEG,
            MAX_ANGLE_DEG,
            "degrees",
        ),
        (
            "outlet_angle_deg",
            inputs.outlet_angle_deg,
            "Outlet angle",
            MIN_ANGLE_DEG,
            MAX_ANGLE_DEG,
            "degrees",
        ),
        (
            "retention_coefficient",
            inputs.retention_coefficient,
            "Velocity retention coefficient",
            MIN_RETENTION_COEFFICIENT,
            MAX_RETENTION_COEFFICIENT,
            "",
        ),
        (
            "split_fraction",
            inputs.split_fraction,
            "First outlet mass fraction",
            MIN_SPLIT_FRACTION,
            MAX_SPLIT_FRACTION,
            "",
        ),
    )

    for field, value, label, minimum, maximum, unit in bounded_fields:
        if not _is_finite_real(value):
            issues.append(_finite_issue(field, value, label, unit))
        elif not minimum <= float(value) <= maximum:
            issues.append(_bounded_issue(field, float(value), label, minimum, maximum, unit))

    if not _is_finite_real(inputs.density):
        issues.append(_finite_issue("density", inputs.density, "Fluid density", "kg/m³"))
    elif not MIN_DENSITY_KG_M3 <= inputs.density <= MAX_DENSITY_KG_M3:
        issues.append(
            _bounded_issue(
                "density",
                inputs.density,
                "Fluid density",
                MIN_DENSITY_KG_M3,
                MAX_DENSITY_KG_M3,
                "kg/m³",
            )
        )

    if not _is_finite_real(inputs.dynamic_viscosity):
        issues.append(
            _finite_issue(
                "dynamic_viscosity",
                inputs.dynamic_viscosity,
                "Dynamic viscosity",
                "Pa·s",
            )
        )
    elif not MIN_DYNAMIC_VISCOSITY_PA_S <= inputs.dynamic_viscosity <= MAX_DYNAMIC_VISCOSITY_PA_S:
        issues.append(
            _bounded_issue(
                "dynamic_viscosity",
                inputs.dynamic_viscosity,
                "Dynamic viscosity",
                MIN_DYNAMIC_VISCOSITY_PA_S,
                MAX_DYNAMIC_VISCOSITY_PA_S,
                "Pa·s",
            )
        )

    physical_scale_is_valid = (
        MIN_DENSITY_KG_M3 <= inputs.density <= MAX_DENSITY_KG_M3
        and MIN_DIAMETER_M <= inputs.diameter <= MAX_DIAMETER_M
        and 0.0 < inputs.velocity <= MAX_VELOCITY_M_S
    )
    if physical_scale_is_valid:
        area = pi * inputs.diameter**2 / 4.0
        minimum_reliable_velocity = sqrt(float_info.min / (inputs.density * area))
        if inputs.velocity < minimum_reliable_velocity:
            issues.append(
                ValidationIssue(
                    field="velocity",
                    value=inputs.velocity,
                    minimum=minimum_reliable_velocity,
                    maximum=MAX_VELOCITY_M_S,
                    code="below_numerical_resolution",
                    message=(
                        "A nonzero inlet velocity is below reliable binary64 momentum "
                        "resolution for the selected density and diameter; enter exactly "
                        f"zero or at least {minimum_reliable_velocity:.6g} m/s."
                    ),
                )
            )

    report = ValidationReport(tuple(issues))
    if raise_on_error and not report.is_valid:
        raise InputValidationError(report)
    return report


def validate_or_raise(inputs: JetInputs) -> JetInputs:
    """Validate and return ``inputs`` for convenient calculation pipelines."""

    validate_inputs(inputs, raise_on_error=True)
    return inputs


def normalize_sweep_parameter(parameter: str) -> str:
    """Resolve equation/UI aliases to a supported :class:`JetInputs` field."""

    normalized = str(parameter).strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return SWEEP_PARAMETER_ALIASES[normalized]
    except KeyError as exc:
        choices = ", ".join(sorted(set(SWEEP_PARAMETER_ALIASES.values())))
        raise ValueError(
            f"Unsupported sweep parameter {parameter!r}. Choose one of: {choices}."
        ) from exc


def validate_sweep_points(points: int) -> int:
    """Validate a parameter-study resolution and return it as an integer."""

    if isinstance(points, bool) or not isinstance(points, Real):
        raise ValueError("Sweep points must be an integer.")
    integer_points = int(points)
    if integer_points != float(points):
        raise ValueError("Sweep points must be a whole number.")
    if not MIN_SWEEP_POINTS <= integer_points <= MAX_SWEEP_POINTS:
        raise ValueError(
            f"Sweep points must be between {MIN_SWEEP_POINTS} and "
            f"{MAX_SWEEP_POINTS}; received {integer_points}."
        )
    return integer_points


# Backward-friendly names for UI and integrations.
validate_parameters = validate_inputs
validate_simulation_inputs = validate_inputs

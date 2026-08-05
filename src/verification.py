"""Independent closed-form checks for the three documented ideal limits.

The expected values in this module are evaluated directly from textbook
closed-form expressions.  They deliberately do not call calculation helpers
such as ``jet_area`` or ``momentum_force``; only the simulator side of each
comparison uses the public solver.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite, pi, sqrt
from typing import Protocol

from .course import textbook_course_inputs
from .models import ImpactModel, JetInputs


class _ForceResult(Protocol):
    """Minimum solver-result surface required by the verifier."""

    @property
    def fx_n(self) -> float: ...

    @property
    def fy_n(self) -> float: ...

    @property
    def resultant_force_n(self) -> float: ...


class ClosedFormCase(StrEnum):
    """Canonical ideal cases supported by the independent checker."""

    NORMAL_PLATE = "Normal flat plate"
    IDEAL_90_DEGREE_DEFLECTION = "90-degree ideal deflection"
    IDEAL_180_DEGREE_REVERSAL = "180-degree ideal reversal"


@dataclass(frozen=True, slots=True)
class ClosedFormCheck:
    """One component-level analytical comparison in SI force units."""

    case: ClosedFormCase
    component: str
    expected_n: float
    simulator_n: float
    absolute_difference_n: float
    tolerance_n: float
    status: str

    def as_record(self) -> dict[str, str | float]:
        """Return a stable, table-ready record with explicit engineering units."""

        return {
            "Case": self.case.value,
            "Component": self.component,
            "Expected (N)": self.expected_n,
            "Simulator (N)": self.simulator_n,
            "Absolute difference (N)": self.absolute_difference_n,
            "Tolerance (N)": self.tolerance_n,
            "Status": self.status,
        }


def _validate_tolerance(value: float, label: str) -> float:
    tolerance = float(value)
    if not isfinite(tolerance) or tolerance < 0.0:
        raise ValueError(f"{label} must be a finite value greater than or equal to zero.")
    return tolerance


def independent_closed_form_checks(
    base_inputs: JetInputs | None = None,
    *,
    solver: Callable[[JetInputs], _ForceResult] | None = None,
    relative_tolerance: float = 1.0e-9,
    absolute_tolerance_n: float = 1.0e-10,
) -> tuple[ClosedFormCheck, ...]:
    """Compare the public solver with three independently evaluated ideal limits.

    The physical scale (density, diameter, and inlet speed) comes from
    ``base_inputs``.  Geometry is fixed to the three supported cases and the
    deflected outlets are ideal (``k = 1``).  Supplying ``solver`` is useful for
    testing that a disagreement is reported as ``CHECK`` rather than hidden.
    """

    if base_inputs is None:
        base_inputs = textbook_course_inputs()
    if not isinstance(base_inputs, JetInputs):
        raise TypeError("base_inputs must be a JetInputs instance.")

    rel_tol = _validate_tolerance(relative_tolerance, "relative_tolerance")
    abs_tol = _validate_tolerance(absolute_tolerance_n, "absolute_tolerance_n")
    if solver is None:
        from .calculations import simulate

        solver = simulate

    # Independent textbook scale: rho * (pi*d^2/4) * V^2.  This expression is
    # intentionally local instead of sharing any production calculation helper.
    momentum_scale_n = (
        base_inputs.density * (pi * base_inputs.diameter**2 / 4.0) * base_inputs.velocity**2
    )
    cases = (
        (
            ClosedFormCase.NORMAL_PLATE,
            replace(
                base_inputs,
                model=ImpactModel.NORMAL_FLAT_PLATE,
                retention_coefficient=1.0,
            ),
            (momentum_scale_n, 0.0, momentum_scale_n),
        ),
        (
            ClosedFormCase.IDEAL_90_DEGREE_DEFLECTION,
            replace(
                base_inputs,
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=90.0,
                retention_coefficient=1.0,
            ),
            (momentum_scale_n, -momentum_scale_n, sqrt(2.0) * momentum_scale_n),
        ),
        (
            ClosedFormCase.IDEAL_180_DEGREE_REVERSAL,
            replace(
                base_inputs,
                model=ImpactModel.DEFLECTED_JET,
                outlet_angle_deg=180.0,
                retention_coefficient=1.0,
            ),
            (2.0 * momentum_scale_n, 0.0, 2.0 * momentum_scale_n),
        ),
    )

    checks: list[ClosedFormCheck] = []
    for case, case_inputs, expected in cases:
        result = solver(case_inputs)
        simulator = (result.fx_n, result.fy_n, result.resultant_force_n)
        tolerance_n = max(abs_tol, rel_tol * max(*(abs(value) for value in expected), 1.0))
        for component, expected_n, simulator_n in zip(
            ("Fx", "Fy", "FR"), expected, simulator, strict=True
        ):
            difference_n = abs(float(simulator_n) - expected_n)
            checks.append(
                ClosedFormCheck(
                    case=case,
                    component=component,
                    expected_n=expected_n,
                    simulator_n=float(simulator_n),
                    absolute_difference_n=difference_n,
                    tolerance_n=tolerance_n,
                    status="PASS" if difference_n <= tolerance_n else "CHECK",
                )
            )
    return tuple(checks)


def independent_closed_form_records(
    base_inputs: JetInputs | None = None,
    *,
    solver: Callable[[JetInputs], _ForceResult] | None = None,
    relative_tolerance: float = 1.0e-9,
    absolute_tolerance_n: float = 1.0e-10,
) -> tuple[dict[str, str | float], ...]:
    """Return the supported independent checks as deterministic UI/report rows."""

    return tuple(
        check.as_record()
        for check in independent_closed_form_checks(
            base_inputs,
            solver=solver,
            relative_tolerance=relative_tolerance,
            absolute_tolerance_n=absolute_tolerance_n,
        )
    )


__all__ = [
    "ClosedFormCase",
    "ClosedFormCheck",
    "independent_closed_form_checks",
    "independent_closed_form_records",
]

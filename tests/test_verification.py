"""Focused tests for the independent three-case closed-form checker."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt

import pytest

from src.calculations import simulate
from src.course import textbook_course_inputs
from src.models import ImpactModel, JetInputs
from src.verification import (
    ClosedFormCase,
    independent_closed_form_checks,
    independent_closed_form_records,
)


def test_supported_closed_form_cases_match_direct_textbook_values() -> None:
    checks = independent_closed_form_checks()
    base = textbook_course_inputs()
    scale = base.density * (pi * base.diameter**2 / 4.0) * base.velocity**2
    expected = {
        (ClosedFormCase.NORMAL_PLATE, "Fx"): scale,
        (ClosedFormCase.NORMAL_PLATE, "Fy"): 0.0,
        (ClosedFormCase.NORMAL_PLATE, "FR"): scale,
        (ClosedFormCase.IDEAL_90_DEGREE_DEFLECTION, "Fx"): scale,
        (ClosedFormCase.IDEAL_90_DEGREE_DEFLECTION, "Fy"): -scale,
        (ClosedFormCase.IDEAL_90_DEGREE_DEFLECTION, "FR"): sqrt(2.0) * scale,
        (ClosedFormCase.IDEAL_180_DEGREE_REVERSAL, "Fx"): 2.0 * scale,
        (ClosedFormCase.IDEAL_180_DEGREE_REVERSAL, "Fy"): 0.0,
        (ClosedFormCase.IDEAL_180_DEGREE_REVERSAL, "FR"): 2.0 * scale,
    }

    assert len(checks) == 9
    assert {check.case for check in checks} == set(ClosedFormCase)
    for check in checks:
        assert check.expected_n == pytest.approx(expected[(check.case, check.component)])
        assert check.simulator_n == pytest.approx(check.expected_n, rel=1.0e-12, abs=1.0e-12)
        assert check.absolute_difference_n <= check.tolerance_n
        assert check.status == "PASS"


def test_checker_uses_requested_physical_scale_and_handles_zero_velocity() -> None:
    base = textbook_course_inputs().with_updates(density=875.0, diameter=0.031, velocity=0.0)
    checks = independent_closed_form_checks(base)

    assert all(check.expected_n == 0.0 for check in checks)
    assert all(check.simulator_n == 0.0 for check in checks)
    assert all(check.status == "PASS" for check in checks)


def test_checker_surfaces_solver_disagreement_as_check() -> None:
    @dataclass(frozen=True)
    class ForceResult:
        fx_n: float
        fy_n: float
        resultant_force_n: float

    def biased_solver(inputs: JetInputs) -> ForceResult:
        result = simulate(inputs)
        bias = (
            0.01
            if inputs.model is ImpactModel.DEFLECTED_JET and inputs.outlet_angle_deg == 90.0
            else 0.0
        )
        return ForceResult(result.fx_n + bias, result.fy_n, result.resultant_force_n)

    checks = independent_closed_form_checks(solver=biased_solver)
    flagged = [check for check in checks if check.status == "CHECK"]

    assert [(check.case, check.component) for check in flagged] == [
        (ClosedFormCase.IDEAL_90_DEGREE_DEFLECTION, "Fx")
    ]
    assert flagged[0].absolute_difference_n == pytest.approx(0.01)


def test_table_records_have_explicit_comparison_columns() -> None:
    records = independent_closed_form_records()

    assert tuple(records[0]) == (
        "Case",
        "Component",
        "Expected (N)",
        "Simulator (N)",
        "Absolute difference (N)",
        "Tolerance (N)",
        "Status",
    )
    assert {record["Status"] for record in records} == {"PASS"}


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("relative_tolerance", -1.0),
        ("relative_tolerance", float("nan")),
        ("absolute_tolerance_n", float("inf")),
    ],
)
def test_checker_rejects_invalid_tolerances(option: str, value: float) -> None:
    with pytest.raises(ValueError, match=option):
        independent_closed_form_checks(**{option: value})


def test_checker_rejects_non_domain_inputs() -> None:
    with pytest.raises(TypeError, match="JetInputs"):
        independent_closed_form_checks({"density": 1000.0})  # type: ignore[arg-type]

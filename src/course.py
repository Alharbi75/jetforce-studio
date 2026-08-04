"""Course-facing release profile for JetForce Studio.

This module contains deterministic defaults and labels used by the Streamlit
interface.  It does not implement physics; every case is still evaluated by
``src.calculations.simulate``.
"""

from __future__ import annotations

from enum import StrEnum

from .constants import (
    COURSE_TEXTBOOK_DENSITY_KG_M3,
    DEFAULT_DIAMETER_M,
    DEFAULT_DYNAMIC_VISCOSITY_PA_S,
    DEFAULT_VELOCITY_M_S,
)
from .models import FluidPreset, ImpactModel, JetInputs, UnitSystem


class AppMode(StrEnum):
    """Public interface modes; Course Mode is always the fresh-session default."""

    COURSE = "Course Mode"
    ADVANCED = "Advanced Mode"


class DemonstrationPreset(StrEnum):
    """One-click cases used during a classroom presentation."""

    NORMAL_PLATE = "Normal Plate"
    DOUBLE_VELOCITY = "Double Velocity"
    NINETY_DEGREE_DEFLECTION = "90-Degree Deflection"


COURSE_MODE_EXPLANATION = (
    "Course Mode includes only the main control-volume momentum concepts required "
    "for the MEC350 project. Advanced Mode contains supplementary analyses."
)

ADVANCED_MODE_NOTICE = (
    "These options are supplementary. The main MEC350 analysis is based on the "
    "control-volume momentum equation shown in Course Mode."
)

PRIVACY_STATEMENT = (
    "This application does not request personal information and does not store "
    "visitor-entered engineering values in a database."
)

COURSE_MODEL_LABELS: dict[ImpactModel, str] = {
    ImpactModel.NORMAL_FLAT_PLATE: "Normal Flat Plate",
    ImpactModel.DEFLECTED_JET: "Deflected Jet / Curved Plate Comparison",
}


def textbook_course_inputs() -> JetInputs:
    """Return the exact fully populated MEC350 textbook demonstration case."""

    return JetInputs(
        density=COURSE_TEXTBOOK_DENSITY_KG_M3,
        dynamic_viscosity=DEFAULT_DYNAMIC_VISCOSITY_PA_S,
        diameter=DEFAULT_DIAMETER_M,
        velocity=DEFAULT_VELOCITY_M_S,
        model=ImpactModel.NORMAL_FLAT_PLATE,
        plate_angle_deg=90.0,
        outlet_angle_deg=90.0,
        retention_coefficient=1.0,
        split_fraction=0.5,
        fluid_preset=FluidPreset.TEXTBOOK_WATER,
        unit_system=UnitSystem.SI,
    )


def demonstration_inputs(preset: DemonstrationPreset | str) -> JetInputs:
    """Return a documented presentation preset without mutating shared state."""

    selected = DemonstrationPreset(preset)
    base = textbook_course_inputs()
    if selected is DemonstrationPreset.DOUBLE_VELOCITY:
        return base.with_updates(velocity=20.0)
    if selected is DemonstrationPreset.NINETY_DEGREE_DEFLECTION:
        return base.with_updates(
            model=ImpactModel.DEFLECTED_JET,
            outlet_angle_deg=90.0,
        )
    return base


__all__ = [
    "ADVANCED_MODE_NOTICE",
    "COURSE_MODEL_LABELS",
    "COURSE_MODE_EXPLANATION",
    "PRIVACY_STATEMENT",
    "AppMode",
    "DemonstrationPreset",
    "demonstration_inputs",
    "textbook_course_inputs",
]

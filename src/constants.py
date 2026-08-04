"""Project-wide physical defaults, validation limits, and display constants.

All numerical calculations in JetForce Studio use SI units.  The values in
this module are deliberately data-only so that the physics, UI, and reporting
layers can share one source of truth without creating import cycles.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final


def _fluid_properties(
    name: str, density: float, dynamic_viscosity: float
) -> Mapping[str, float | str]:
    return MappingProxyType(
        {
            "name": name,
            "density": density,
            "dynamic_viscosity": dynamic_viscosity,
        }
    )


PI: Final[float] = 3.141592653589793
DEG_TO_RAD: Final[float] = PI / 180.0
RAD_TO_DEG: Final[float] = 180.0 / PI

# A scale-aware tolerance is still used for comparisons.  This absolute value
# is mainly for classifying a displayed value as effectively zero.
ZERO_TOLERANCE: Final[float] = 1.0e-12

MIN_DENSITY_KG_M3: Final[float] = 0.001
MAX_DENSITY_KG_M3: Final[float] = 3000.0
MIN_DYNAMIC_VISCOSITY_PA_S: Final[float] = 1.0e-12
MAX_DYNAMIC_VISCOSITY_PA_S: Final[float] = 100.0
MIN_DIAMETER_M: Final[float] = 0.001
MAX_DIAMETER_M: Final[float] = 0.20
MIN_VELOCITY_M_S: Final[float] = 0.0
MAX_VELOCITY_M_S: Final[float] = 100.0
MIN_ANGLE_DEG: Final[float] = -180.0
MAX_ANGLE_DEG: Final[float] = 180.0
MIN_RETENTION_COEFFICIENT: Final[float] = 0.0
MAX_RETENTION_COEFFICIENT: Final[float] = 1.0
MIN_SPLIT_FRACTION: Final[float] = 0.0
MAX_SPLIT_FRACTION: Final[float] = 1.0

MIN_SWEEP_POINTS: Final[int] = 2
MAX_SWEEP_POINTS: Final[int] = 1000
DEFAULT_SWEEP_POINTS: Final[int] = 50

DEFAULT_DENSITY_KG_M3: Final[float] = 998.0
DEFAULT_DYNAMIC_VISCOSITY_PA_S: Final[float] = 0.001
DEFAULT_DIAMETER_M: Final[float] = 0.02
DEFAULT_VELOCITY_M_S: Final[float] = 10.0
DEFAULT_PLATE_ANGLE_DEG: Final[float] = 90.0
DEFAULT_OUTLET_ANGLE_DEG: Final[float] = 90.0
DEFAULT_RETENTION_COEFFICIENT: Final[float] = 1.0
DEFAULT_SPLIT_FRACTION: Final[float] = 0.5

# The course-facing demonstration intentionally uses the convenient textbook
# water density requested by the MEC350 brief.  The domain model keeps its
# historical room-temperature default for backward compatibility; the UI
# explicitly selects this course value for each new browser session.
COURSE_TEXTBOOK_DENSITY_KG_M3: Final[float] = 1000.0

# Presets are approximate room-temperature values and remain editable in the
# UI.  The mapping is immutable to avoid accidental process-wide mutation.
FLUID_PROPERTY_PRESETS: Final[Mapping[str, Mapping[str, float | str]]] = MappingProxyType(
    {
        "textbook_water": _fluid_properties(
            "Water - textbook value (1000 kg/m3)",
            COURSE_TEXTBOOK_DENSITY_KG_M3,
            0.001,
        ),
        "water": _fluid_properties(
            "Water - approximate room-temperature value (998 kg/m3)",
            998.0,
            0.001,
        ),
        "air": _fluid_properties(
            "Air near room temperature",
            1.204,
            1.825e-5,
        ),
        "custom": _fluid_properties(
            "Custom fluid",
            DEFAULT_DENSITY_KG_M3,
            DEFAULT_DYNAMIC_VISCOSITY_PA_S,
        ),
    }
)

SWEEP_PARAMETER_ALIASES = MappingProxyType(
    {
        "velocity": "velocity",
        "v": "velocity",
        "speed": "velocity",
        "jet_speed": "velocity",
        "diameter": "diameter",
        "d": "diameter",
        "outlet_angle": "outlet_angle_deg",
        "outlet_angle_deg": "outlet_angle_deg",
        "beta": "outlet_angle_deg",
        "beta_deg": "outlet_angle_deg",
        "plate_angle": "plate_angle_deg",
        "plate_angle_deg": "plate_angle_deg",
        "theta": "plate_angle_deg",
        "theta_deg": "plate_angle_deg",
        "retention": "retention_coefficient",
        "retention_coefficient": "retention_coefficient",
        "k": "retention_coefficient",
        "split": "split_fraction",
        "split_fraction": "split_fraction",
        "s": "split_fraction",
        "density": "density",
        "rho": "density",
        "dynamic_viscosity": "dynamic_viscosity",
        "viscosity": "dynamic_viscosity",
        "mu": "dynamic_viscosity",
    }
)

SWEEP_PARAMETER_BOUNDS = MappingProxyType(
    {
        "velocity": (MIN_VELOCITY_M_S, MAX_VELOCITY_M_S),
        "diameter": (MIN_DIAMETER_M, MAX_DIAMETER_M),
        "outlet_angle_deg": (MIN_ANGLE_DEG, MAX_ANGLE_DEG),
        "plate_angle_deg": (MIN_ANGLE_DEG, MAX_ANGLE_DEG),
        "retention_coefficient": (
            MIN_RETENTION_COEFFICIENT,
            MAX_RETENTION_COEFFICIENT,
        ),
        "split_fraction": (MIN_SPLIT_FRACTION, MAX_SPLIT_FRACTION),
        "density": (MIN_DENSITY_KG_M3, MAX_DENSITY_KG_M3),
        "dynamic_viscosity": (
            MIN_DYNAMIC_VISCOSITY_PA_S,
            MAX_DYNAMIC_VISCOSITY_PA_S,
        ),
    }
)

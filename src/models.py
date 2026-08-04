"""Typed domain models for the JetForce Studio calculation engine."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from math import atan2, degrees, fsum, hypot
from typing import Any

from .constants import (
    DEFAULT_DENSITY_KG_M3,
    DEFAULT_DIAMETER_M,
    DEFAULT_DYNAMIC_VISCOSITY_PA_S,
    DEFAULT_OUTLET_ANGLE_DEG,
    DEFAULT_PLATE_ANGLE_DEG,
    DEFAULT_RETENTION_COEFFICIENT,
    DEFAULT_SPLIT_FRACTION,
    DEFAULT_VELOCITY_M_S,
    FLUID_PROPERTY_PRESETS,
)


def _is_boolean_scalar(value: object) -> bool:
    """Recognize Python and NumPy boolean scalars without importing NumPy here."""

    value_type = type(value)
    return isinstance(value, bool) or (
        value_type.__module__ == "numpy" and value_type.__name__ in {"bool", "bool_"}
    )


class _NormalizedStringEnum(StrEnum):
    """String enum that accepts human-friendly spelling variants."""

    @classmethod
    def _missing_(cls, value: object) -> _NormalizedStringEnum | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        for name, member in cls.__members__.items():
            if normalized in {
                member.value.lower(),
                name.lower(),
                member.label.lower().replace("-", "_").replace(" ", "_"),
            }:
                return member
        return None

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class ImpactModel(_NormalizedStringEnum):
    """Supported control-volume outlet models."""

    NORMAL_FLAT_PLATE = "normal_flat_plate"
    NORMAL_IMPACT = "normal_flat_plate"
    NORMAL_PLATE = "normal_flat_plate"
    DEFLECTED_JET = "deflected_jet"
    SINGLE_DEFLECTED_OUTLET = "deflected_jet"
    SPLIT_FLOW = "split_flow"
    SPLIT_FLAT_PLATE = "split_flow"
    CURVED_VANE = "curved_vane"

    @property
    def label(self) -> str:
        labels = {
            self.NORMAL_FLAT_PLATE: "Normal jet on a flat plate",
            self.DEFLECTED_JET: "Single deflected outlet jet",
            self.SPLIT_FLOW: "Split flow along a flat plate",
            self.CURVED_VANE: "Curved vane",
        }
        return labels[self]


class FluidPreset(_NormalizedStringEnum):
    """Approximate editable room-temperature fluid presets."""

    TEXTBOOK_WATER = "textbook_water"
    WATER = "water"
    AIR = "air"
    CUSTOM = "custom"

    @property
    def label(self) -> str:
        return str(FLUID_PROPERTY_PRESETS[self.value]["name"])

    @property
    def density(self) -> float:
        return float(FLUID_PROPERTY_PRESETS[self.value]["density"])

    @property
    def dynamic_viscosity(self) -> float:
        return float(FLUID_PROPERTY_PRESETS[self.value]["dynamic_viscosity"])

    @property
    def properties(self) -> dict[str, float | str]:
        return dict(FLUID_PROPERTY_PRESETS[self.value])


class UnitSystem(_NormalizedStringEnum):
    """Display unit preference; the calculation layer always remains SI."""

    SI = "si"
    METRIC = "si"
    US_CUSTOMARY = "us_customary"
    IMPERIAL = "us_customary"

    @property
    def label(self) -> str:
        return "SI (metric)" if self is UnitSystem.SI else "US customary"


@dataclass(frozen=True, slots=True)
class Vector2D:
    """A small immutable Cartesian vector used for velocity, force, and momentum."""

    x: float = 0.0
    y: float = 0.0

    def __post_init__(self) -> None:
        x_value = float(self.x)
        y_value = float(self.y)
        object.__setattr__(self, "x", 0.0 if x_value == 0.0 else x_value)
        object.__setattr__(self, "y", 0.0 if y_value == 0.0 else y_value)

    @property
    def magnitude(self) -> float:
        return hypot(self.x, self.y)

    @property
    def angle_deg(self) -> float:
        """Counterclockwise angle from +x; zero is a compatibility sentinel for a zero vector."""

        if self.x == 0.0 and self.y == 0.0:
            return 0.0
        return degrees(atan2(self.y, self.x))

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y

    def __add__(self, other: Vector2D) -> Vector2D:
        if not isinstance(other, Vector2D):
            return NotImplemented
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2D) -> Vector2D:
        if not isinstance(other, Vector2D):
            return NotImplemented
        return Vector2D(self.x - other.x, self.y - other.y)

    def __neg__(self) -> Vector2D:
        return Vector2D(-self.x, -self.y)

    def __mul__(self, scalar: float) -> Vector2D:
        return Vector2D(self.x * float(scalar), self.y * float(scalar))

    def __rmul__(self, scalar: float) -> Vector2D:
        return self * scalar

    def __truediv__(self, scalar: float) -> Vector2D:
        return Vector2D(self.x / float(scalar), self.y / float(scalar))


@dataclass(frozen=True, slots=True)
class JetInputs:
    """Complete SI input state for one simulation.

    Angles are measured counterclockwise from the positive x direction.  For
    split flow, ``plate_angle_deg`` is the first outlet's tangent direction;
    the second outlet points exactly 180 degrees opposite.
    """

    density: float = DEFAULT_DENSITY_KG_M3
    dynamic_viscosity: float = DEFAULT_DYNAMIC_VISCOSITY_PA_S
    diameter: float = DEFAULT_DIAMETER_M
    velocity: float = DEFAULT_VELOCITY_M_S
    model: ImpactModel = ImpactModel.NORMAL_FLAT_PLATE
    plate_angle_deg: float = DEFAULT_PLATE_ANGLE_DEG
    outlet_angle_deg: float = DEFAULT_OUTLET_ANGLE_DEG
    retention_coefficient: float = DEFAULT_RETENTION_COEFFICIENT
    split_fraction: float = DEFAULT_SPLIT_FRACTION
    fluid_preset: FluidPreset = FluidPreset.WATER
    unit_system: UnitSystem = UnitSystem.SI

    def __post_init__(self) -> None:
        numeric_fields = (
            "density",
            "dynamic_viscosity",
            "diameter",
            "velocity",
            "plate_angle_deg",
            "outlet_angle_deg",
            "retention_coefficient",
            "split_fraction",
        )
        for field_name in numeric_fields:
            raw_value = getattr(self, field_name)
            if _is_boolean_scalar(raw_value):
                raise TypeError(f"{field_name} must be numeric; boolean values are not accepted.")
            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise TypeError(f"{field_name} must be numeric.") from exc
            object.__setattr__(self, field_name, numeric_value)
        object.__setattr__(self, "model", ImpactModel(self.model))
        object.__setattr__(self, "fluid_preset", FluidPreset(self.fluid_preset))
        object.__setattr__(self, "unit_system", UnitSystem(self.unit_system))

    @classmethod
    def from_preset(cls, preset: FluidPreset | str, **overrides: Any) -> JetInputs:
        """Create inputs using a preset's approximate density and viscosity."""

        selected = FluidPreset(preset)
        return cls(
            density=selected.density,
            dynamic_viscosity=selected.dynamic_viscosity,
            fluid_preset=selected,
            **overrides,
        )

    def with_updates(self, **changes: Any) -> JetInputs:
        """Return a validated-type copy, accepting common equation aliases."""

        aliases = {
            "rho": "density",
            "mu": "dynamic_viscosity",
            "d": "diameter",
            "speed": "velocity",
            "v": "velocity",
            "theta": "plate_angle_deg",
            "theta_deg": "plate_angle_deg",
            "beta": "outlet_angle_deg",
            "beta_deg": "outlet_angle_deg",
            "k": "retention_coefficient",
            "s": "split_fraction",
        }
        normalized = {aliases.get(key, key): value for key, value in changes.items()}
        return replace(self, **normalized)

    @property
    def rho(self) -> float:
        return self.density

    @property
    def mu(self) -> float:
        return self.dynamic_viscosity

    @property
    def d(self) -> float:
        return self.diameter

    @property
    def speed(self) -> float:
        return self.velocity

    @property
    def theta_deg(self) -> float:
        return self.plate_angle_deg

    @property
    def beta_deg(self) -> float:
        return self.outlet_angle_deg

    @property
    def k(self) -> float:
        return self.retention_coefficient

    @property
    def s(self) -> float:
        return self.split_fraction

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["model"] = self.model.value
        data["fluid_preset"] = self.fluid_preset.value
        data["unit_system"] = self.unit_system.value
        return data

    to_dict = as_dict


@dataclass(frozen=True, slots=True)
class OutletStream:
    """One control-volume outlet stream and its share of total inlet mass flow."""

    name: str
    mass_fraction: float
    mass_flow_rate_kg_s: float
    velocity_m_s: Vector2D

    @property
    def speed_m_s(self) -> float:
        return self.velocity_m_s.magnitude

    @property
    def momentum_flux_n(self) -> Vector2D:
        return self.mass_flow_rate_kg_s * self.velocity_m_s


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Traceable control-volume result for force exerted by water on the plate."""

    inputs: JetInputs
    area_m2: float
    flow_rate_m3_s: float
    mass_flow_rate_kg_s: float
    reynolds_number: float
    inlet_velocity: Vector2D
    outlet_streams: tuple[OutletStream, ...]
    outlet_momentum_flux_n: Vector2D
    force_on_plate_n: Vector2D
    force_on_fluid_n: Vector2D
    outlet_speed_m_s: float

    @property
    def fx_n(self) -> float:
        return self.force_on_plate_n.x

    @property
    def fy_n(self) -> float:
        return self.force_on_plate_n.y

    @property
    def resultant_force_n(self) -> float:
        return self.force_on_plate_n.magnitude

    @property
    def force_angle_deg(self) -> float:
        return self.force_on_plate_n.angle_deg

    @property
    def force_direction_defined(self) -> bool:
        """Whether the resultant is nonzero and therefore has a direction."""

        return self.fx_n != 0.0 or self.fy_n != 0.0

    @property
    def area(self) -> float:
        return self.area_m2

    @property
    def flow_rate(self) -> float:
        return self.flow_rate_m3_s

    @property
    def mass_flow_rate(self) -> float:
        return self.mass_flow_rate_kg_s

    @property
    def re(self) -> float:
        return self.reynolds_number

    @property
    def vin(self) -> Vector2D:
        return self.inlet_velocity

    @property
    def vout_equivalent(self) -> Vector2D:
        """Mass-weighted net outlet velocity used by the momentum balance."""

        # Use the model's mass fractions directly so a truthful outlet velocity
        # remains available at the smallest supported flow scales. Exact zero
        # inlet speed naturally yields zero because every stream speed is zero.
        return Vector2D(
            fsum(stream.mass_fraction * stream.velocity_m_s.x for stream in self.outlet_streams),
            fsum(stream.mass_fraction * stream.velocity_m_s.y for stream in self.outlet_streams),
        )

    @property
    def outlet_velocity(self) -> Vector2D:
        return self.vout_equivalent

    def as_dict(self) -> dict[str, Any]:
        """Return a flat, JSON/CSV-friendly engineering result mapping."""

        return {
            **self.inputs.as_dict(),
            "area_m2": self.area_m2,
            "flow_rate_m3_s": self.flow_rate_m3_s,
            "mass_flow_rate_kg_s": self.mass_flow_rate_kg_s,
            "reynolds_number": self.reynolds_number,
            "inlet_velocity_x_m_s": self.inlet_velocity.x,
            "inlet_velocity_y_m_s": self.inlet_velocity.y,
            "equivalent_outlet_velocity_x_m_s": self.vout_equivalent.x,
            "equivalent_outlet_velocity_y_m_s": self.vout_equivalent.y,
            "outlet_momentum_flux_x_n": self.outlet_momentum_flux_n.x,
            "outlet_momentum_flux_y_n": self.outlet_momentum_flux_n.y,
            "fx_n": self.fx_n,
            "fy_n": self.fy_n,
            "resultant_force_n": self.resultant_force_n,
            "force_angle_deg": self.force_angle_deg,
            "force_direction_defined": self.force_direction_defined,
            "outlet_speed_m_s": self.outlet_speed_m_s,
        }

    to_dict = as_dict


@dataclass(frozen=True, slots=True)
class IdealComparison:
    """Actual result and its lossless counterpart for the same geometry."""

    actual: SimulationResult
    ideal: SimulationResult

    @property
    def absolute_difference_n(self) -> float:
        return abs(self.actual.resultant_force_n - self.ideal.resultant_force_n)

    @property
    def percentage_difference(self) -> float:
        denominator = abs(self.ideal.resultant_force_n)
        if denominator == 0.0:
            return float("nan")
        return 100.0 * self.absolute_difference_n / denominator

    @property
    def component_differences_n(self) -> Vector2D:
        return self.actual.force_on_plate_n - self.ideal.force_on_plate_n

    def as_dict(self) -> dict[str, float]:
        return {
            "actual_fx_n": self.actual.fx_n,
            "actual_fy_n": self.actual.fy_n,
            "actual_resultant_n": self.actual.resultant_force_n,
            "ideal_fx_n": self.ideal.fx_n,
            "ideal_fy_n": self.ideal.fy_n,
            "ideal_resultant_n": self.ideal.resultant_force_n,
            "absolute_difference_n": self.absolute_difference_n,
            "percentage_difference": self.percentage_difference,
        }


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One actionable input-validation message."""

    field: str
    message: str
    value: Any = None
    minimum: float | None = None
    maximum: float | None = None
    code: str = "invalid_value"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Aggregate validation outcome suitable for both APIs and a UI."""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues

    @property
    def messages(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues)

    @property
    def by_field(self) -> Mapping[str, tuple[ValidationIssue, ...]]:
        grouped: dict[str, list[ValidationIssue]] = {}
        for issue in self.issues:
            grouped.setdefault(issue.field, []).append(issue)
        return {field: tuple(values) for field, values in grouped.items()}

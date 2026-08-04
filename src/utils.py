"""Centralized unit conversion, numeric formatting, and lightweight exports."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from .constants import DEG_TO_RAD, RAD_TO_DEG, ZERO_TOLERANCE
from .models import SimulationResult, UnitSystem, Vector2D


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    """Multiplicative display conversion from SI and its printable unit."""

    factor_from_si: float
    unit: str


_UNIT_DEFINITIONS: dict[UnitSystem, dict[str, UnitDefinition]] = {
    UnitSystem.SI: {
        "length": UnitDefinition(1.0, "m"),
        "diameter": UnitDefinition(1.0, "m"),
        "area": UnitDefinition(1.0, "m²"),
        "velocity": UnitDefinition(1.0, "m/s"),
        "flow_rate": UnitDefinition(1.0, "m³/s"),
        "mass_flow_rate": UnitDefinition(1.0, "kg/s"),
        "density": UnitDefinition(1.0, "kg/m³"),
        "dynamic_viscosity": UnitDefinition(1.0, "Pa·s"),
        "force": UnitDefinition(1.0, "N"),
        "angle": UnitDefinition(1.0, "°"),
        "reynolds_number": UnitDefinition(1.0, ""),
    },
    UnitSystem.US_CUSTOMARY: {
        "length": UnitDefinition(3.28083989501312, "ft"),
        "diameter": UnitDefinition(39.3700787401575, "in"),
        "area": UnitDefinition(1550.0031000062, "in²"),
        "velocity": UnitDefinition(3.28083989501312, "ft/s"),
        "flow_rate": UnitDefinition(15850.323141489, "US gal/min"),
        "mass_flow_rate": UnitDefinition(2.20462262184878, "lbm/s"),
        "density": UnitDefinition(0.0624279605761, "lbm/ft³"),
        "dynamic_viscosity": UnitDefinition(0.6719689751395068, "lbm/(ft·s)"),
        "force": UnitDefinition(0.22480894387096, "lbf"),
        "angle": UnitDefinition(1.0, "°"),
        "reynolds_number": UnitDefinition(1.0, ""),
    },
}

_QUANTITY_ALIASES = {
    "d": "diameter",
    "diameter": "diameter",
    "length": "length",
    "a": "area",
    "area": "area",
    "v": "velocity",
    "speed": "velocity",
    "velocity": "velocity",
    "q": "flow_rate",
    "flow": "flow_rate",
    "flow_rate": "flow_rate",
    "mdot": "mass_flow_rate",
    "mass_flow": "mass_flow_rate",
    "mass_flow_rate": "mass_flow_rate",
    "rho": "density",
    "density": "density",
    "mu": "dynamic_viscosity",
    "viscosity": "dynamic_viscosity",
    "dynamic_viscosity": "dynamic_viscosity",
    "f": "force",
    "force": "force",
    "angle": "angle",
    "re": "reynolds_number",
    "reynolds": "reynolds_number",
    "reynolds_number": "reynolds_number",
}


def degrees_to_radians(value: float | Iterable[float]) -> float | np.ndarray:
    """Convert degrees to radians, preserving scalar versus array shape."""

    source = (
        value
        if np.isscalar(value) or isinstance(value, np.ndarray)
        else list(cast(Iterable[float], value))
    )
    converted = np.asarray(source, dtype=np.float64) * DEG_TO_RAD
    return float(converted) if converted.ndim == 0 else converted


def radians_to_degrees(value: float | Iterable[float]) -> float | np.ndarray:
    """Convert radians to degrees, preserving scalar versus array shape."""

    source = (
        value
        if np.isscalar(value) or isinstance(value, np.ndarray)
        else list(cast(Iterable[float], value))
    )
    converted = np.asarray(source, dtype=np.float64) * RAD_TO_DEG
    return float(converted) if converted.ndim == 0 else converted


def is_effectively_zero(value: float, *, scale: float = 1.0) -> bool:
    """Return whether ``value`` is zero at the project's display tolerance."""

    return abs(float(value)) <= ZERO_TOLERANCE * max(abs(float(scale)), 1.0)


def clean_zero(value: float, *, scale: float = 1.0) -> float:
    """Remove floating-point residue such as ``cos(90°)`` from display values."""

    return 0.0 if is_effectively_zero(value, scale=scale) else float(value)


def format_number(
    value: float,
    significant_figures: int = 4,
    *,
    scientific_below: float = 1.0e-3,
    scientific_above: float = 1.0e5,
) -> str:
    """Format a finite value with restrained precision and predictable notation."""

    if significant_figures < 1:
        raise ValueError("significant_figures must be at least 1")
    number = float(value)
    if math.isnan(number):
        return "NaN"
    if math.isinf(number):
        return "∞" if number > 0 else "−∞"
    if is_effectively_zero(number):
        return "0"
    magnitude = abs(number)
    if magnitude < scientific_below or magnitude >= scientific_above:
        return f"{number:.{significant_figures - 1}e}"
    decimals = max(0, significant_figures - 1 - math.floor(math.log10(magnitude)))
    return f"{number:.{decimals}f}"


def format_engineering(value: float, significant_figures: int = 4) -> str:
    """Format in textbook-style scientific notation using a multiple-of-3 exponent."""

    number = float(value)
    if not math.isfinite(number) or is_effectively_zero(number):
        return format_number(number, significant_figures)
    exponent = 3 * math.floor(math.log10(abs(number)) / 3.0)
    coefficient = number / (10.0**exponent)
    if exponent == 0:
        return format_number(coefficient, significant_figures)
    return f"{format_number(coefficient, significant_figures)} × 10^{exponent}"


def normalize_quantity(quantity: str) -> str:
    normalized = str(quantity).strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return _QUANTITY_ALIASES[normalized]
    except KeyError as exc:
        choices = ", ".join(sorted(set(_QUANTITY_ALIASES.values())))
        raise ValueError(f"Unknown quantity {quantity!r}. Choose one of: {choices}.") from exc


def unit_definition(quantity: str, unit_system: UnitSystem | str = UnitSystem.SI) -> UnitDefinition:
    """Return display conversion metadata for a physical quantity."""

    canonical = normalize_quantity(quantity)
    system = UnitSystem(unit_system)
    return _UNIT_DEFINITIONS[system][canonical]


def convert_from_si(
    value: float | Iterable[float],
    quantity: str,
    unit_system: UnitSystem | str = UnitSystem.SI,
) -> float | np.ndarray:
    """Convert an SI scalar or array to a selected display system."""

    definition = unit_definition(quantity, unit_system)
    converted = np.asarray(value, dtype=np.float64) * definition.factor_from_si
    return float(converted) if converted.ndim == 0 else converted


def convert_to_si(
    value: float | Iterable[float],
    quantity: str,
    unit_system: UnitSystem | str = UnitSystem.SI,
) -> float | np.ndarray:
    """Convert a display scalar or array back to SI."""

    definition = unit_definition(quantity, unit_system)
    converted = np.asarray(value, dtype=np.float64) / definition.factor_from_si
    return float(converted) if converted.ndim == 0 else converted


def display_unit(quantity: str, unit_system: UnitSystem | str = UnitSystem.SI) -> str:
    return unit_definition(quantity, unit_system).unit


def format_quantity(
    value_si: float,
    quantity: str,
    unit_system: UnitSystem | str = UnitSystem.SI,
    significant_figures: int = 4,
) -> str:
    """Convert an SI value and join its concise number and unit."""

    converted = cast(float, convert_from_si(value_si, quantity, unit_system))
    unit = display_unit(quantity, unit_system)
    rendered = format_number(converted, significant_figures)
    return f"{rendered} {unit}".rstrip()


def percentage_difference(actual: float, reference: float) -> float:
    """Return absolute percentage difference, or NaN for a zero reference.

    A percentage relative to zero is undefined even when both values are zero;
    presentation and export layers render the NaN sentinel as ``Not applicable``.
    """

    actual_value = float(actual)
    reference_value = float(reference)
    if reference_value == 0.0:
        return float("nan")
    return 100.0 * abs(actual_value - reference_value) / abs(reference_value)


def force_direction_text(force: Vector2D) -> str:
    """Describe vector direction using words in addition to its signed angle."""

    if force.magnitude <= ZERO_TOLERANCE:
        return "No resultant force"
    horizontal = (
        "right" if force.x > ZERO_TOLERANCE else "left" if force.x < -ZERO_TOLERANCE else ""
    )
    vertical = (
        "upward" if force.y > ZERO_TOLERANCE else "downward" if force.y < -ZERO_TOLERANCE else ""
    )
    words = " and ".join(part for part in (horizontal, vertical) if part)
    return f"{words.capitalize()} ({force.angle_deg:.1f}° from +x)"


def results_to_csv(
    results: SimulationResult | Mapping[str, Any] | Iterable[SimulationResult | Mapping[str, Any]],
) -> str:
    """Serialize one or more simulation results to an in-memory CSV string."""

    if isinstance(results, SimulationResult):
        items: list[SimulationResult | Mapping[str, Any]] = [results]
    elif isinstance(results, Mapping):
        items = [results]
    else:
        items = list(results)
    if not items:
        raise ValueError("Cannot export an empty result collection.")

    rows = [item.as_dict() if isinstance(item, SimulationResult) else dict(item) for item in items]
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def results_to_csv_bytes(
    results: SimulationResult | Mapping[str, Any] | Iterable[SimulationResult | Mapping[str, Any]],
) -> bytes:
    return results_to_csv(results).encode("utf-8")


# Friendly aliases retained for thin UI/reporting code.
format_value = format_number
format_si_value = format_quantity
to_display_units = convert_from_si
from_display_units = convert_to_si
export_csv = results_to_csv

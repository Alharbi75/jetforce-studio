#!/usr/bin/env python3
"""Build deterministic, local presentation-fallback artifacts.

The generated files are snapshots of the documented Course Mode textbook
case.  They are intentionally separate from the live Streamlit application
and contain no visitor-entered data.
"""

from __future__ import annotations

import io
import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.calculations import parameter_sweep, simulate  # noqa: E402
from src.course import textbook_course_inputs  # noqa: E402
from src.models import SimulationResult  # noqa: E402
from src.reporting import ReportFigure, export_case_pdf, export_printable_html  # noqa: E402
from src.validation import hand_calculation_trace  # noqa: E402

OUTPUT_DIR = ROOT / "presentation_backup"
GENERATED_AT = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def _chart(frame: pd.DataFrame, variable: str, destination: Path) -> ReportFigure:
    """Render one accessible SI chart and return the same image for the report."""

    if variable == "velocity":
        title = "Force versus inlet velocity"
        x_label = "Inlet jet velocity, V (m/s)"
        note = "For ideal normal impact, Fx = FR = rho A V^2; Fy = 0."
    else:
        title = "Force versus jet diameter"
        x_label = "Jet diameter, d (m)"
        note = "For fixed rho and V, ideal normal-impact force is proportional to d^2."

    figure, axis = plt.subplots(figsize=(9.2, 5.1), dpi=180, constrained_layout=True)
    axis.plot(
        frame[variable],
        frame["Fx_N"],
        color="#0891b2",
        linewidth=2.8,
        label="Fx - horizontal force",
    )
    axis.plot(
        frame[variable],
        frame["Fy_N"],
        color="#d97706",
        linewidth=2.2,
        label="Fy - vertical force",
    )
    axis.plot(
        frame[variable],
        frame["FR_N"],
        color="#be123c",
        linewidth=1.9,
        linestyle="--",
        label="FR - resultant (overlaps Fx)",
    )
    axis.axhline(0.0, color="#64748b", linewidth=0.9)
    axis.set_title(f"{title}\n{note}", loc="left", color="#0b1f33", fontweight="bold")
    axis.set_xlabel(x_label)
    axis.set_ylabel("Force exerted by water on plate (N)")
    axis.grid(True, color="#cbd5e1", alpha=0.65, linewidth=0.7)
    axis.legend(frameon=False, loc="upper left")
    figure.savefig(destination, format="png", dpi=180, facecolor="white")
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=180, facecolor="white")
    plt.close(figure)
    return ReportFigure(
        title=title,
        image_bytes=buffer.getvalue(),
        caption=(
            f"{title} for the Course Mode normal flat-plate case. "
            "The plotted values come from the same control-volume momentum model as the live app."
        ),
        alt_text=f"Line chart of Fx, Fy, and FR against {x_label.lower()}.",
    )


def _hand_calculation(result: SimulationResult) -> dict[str, object]:
    trace = hand_calculation_trace(result)
    return {
        "given_data": "rho = 1000 kg/m^3; d = 0.02 m; V = 10 m/s; normal flat plate",
        "area_equation": "A = pi d^2 / 4",
        "area_m2": trace.area_m2,
        "flow_equation": "Q = A V",
        "flow_rate_m3_s": trace.flow_rate_m3_s,
        "mass_flow_equation": "mdot = rho Q",
        "mass_flow_rate_kg_s": trace.mass_flow_rate_kg_s,
        "inlet_velocity_vector_m_s": "(10, 0)",
        "equivalent_outlet_velocity_vector_m_s": "(0, 0)",
        "momentum_equation": "F_plate = mdot V_in - sum(mdot_out,j V_out,j)",
        "fx_n": trace.fx_n,
        "fy_n": trace.fy_n,
        "resultant_force_n": trace.resultant_force_n,
        "analytical_verification": (
            "The scalar hand calculation and simulator agree within floating-point rounding "
            "because both apply the same documented analytical model."
        ),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = textbook_course_inputs()
    result = simulate(inputs)

    velocity = parameter_sweep(inputs, "velocity", start=0.0, stop=20.0, points=61)
    diameter = parameter_sweep(inputs, "diameter", start=0.005, stop=0.05, points=61)
    velocity.insert(0, "study_variable", "velocity")
    diameter.insert(0, "study_variable", "diameter")
    combined_study = pd.concat([velocity, diameter], ignore_index=True)

    velocity_figure = _chart(velocity, "velocity", OUTPUT_DIR / "force_vs_velocity.png")
    diameter_figure = _chart(diameter, "diameter", OUTPUT_DIR / "force_vs_diameter.png")

    result_table = pd.DataFrame(
        [
            ("Fluid density", "rho", inputs.density, "kg/m^3", "1000"),
            ("Jet diameter", "d", inputs.diameter, "m", "0.0200"),
            ("Inlet jet velocity", "V", inputs.velocity, "m/s", "10.00"),
            ("Jet area", "A", result.area_m2, "m^2", "3.142 x 10^-4"),
            ("Volumetric flow rate", "Q", result.flow_rate_m3_s, "m^3/s", "3.142 x 10^-3"),
            ("Mass flow rate", "mdot", result.mass_flow_rate_kg_s, "kg/s", "3.142"),
            ("Horizontal force on plate", "Fx", result.fx_n, "N", "31.42"),
            ("Vertical force on plate", "Fy", result.fy_n, "N", "0.00"),
            ("Resultant force on plate", "FR", result.resultant_force_n, "N", "31.42"),
        ],
        columns=("quantity", "symbol", "value", "unit", "display_value"),
    )
    result_table.to_csv(OUTPUT_DIR / "default_result_table.csv", index=False)

    metadata = {
        "title": "JetForce Studio - Course Mode Fallback Snapshot",
        "subtitle": "Water Jet Impact Engineering Simulator",
        "course": "MEC350 Fluid Mechanics",
        "interface_mode": "Course Mode",
        "student_name": "[Complete before submission]",
        "student_id": "[Complete before submission]",
        "instructor_section": "[Complete before submission]",
        "institution": "[Complete before submission]",
        "review_status": "Fallback snapshot - verify against the live simulator",
    }
    options = {
        "metadata": metadata,
        "hand_calculation": _hand_calculation(result),
        "parametric_data": combined_study,
        "discussion": (
            "Positive x follows the incoming jet and positive y is upward. The displayed force is the force exerted by the water on the plate.",
            "For ideal normal impact, force is proportional to V^2. Doubling velocity from 10 m/s to 20 m/s produces four times the force.",
            "This agreement is analytical verification, not independent experimental validation.",
        ),
        "conclusion": (
            "For rho = 1000 kg/m^3, d = 0.02 m, and V = 10 m/s, the ideal normal flat-plate model gives Fx = FR = 31.4159 N and Fy = 0 N."
        ),
        "generated_at": GENERATED_AT,
    }
    figures = (velocity_figure, diameter_figure)
    (OUTPUT_DIR / "default_hand_calculation.html").write_bytes(
        export_printable_html(inputs, result, figures=figures, **options)
    )
    (OUTPUT_DIR / "default_hand_calculation.pdf").write_bytes(
        export_case_pdf(inputs, result, figures=figures, **options)
    )
    (OUTPUT_DIR / "study_data.csv").write_text(combined_study.to_csv(index=False), encoding="utf-8")


if __name__ == "__main__":
    main()

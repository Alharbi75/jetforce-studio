"""Step-by-step hand calculation and analytical verification page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.course import AppMode
from src.validation import hand_calculation_trace
from src.verification import independent_closed_form_records
from src.visualizations import (
    ASSUMPTIONS,
    MODEL_LABELS,
    input_snapshot,
    render_brand_bar,
    render_disclaimer,
    render_force_cards,
    render_page_intro,
    render_sidebar_controls,
    simulate_safely,
)

mode = AppMode(st.session_state.get("jf_mode", AppMode.COURSE.value))
course_mode = mode is AppMode.COURSE
inputs, unit_system = render_sidebar_controls()
result = simulate_safely(inputs)
if result is None:
    st.stop()

hand = hand_calculation_trace(result)
values = input_snapshot(inputs)

render_brand_bar()
render_page_intro(
    "Traceable calculation",
    "Calculation and Results" if course_mode else "Hand Calculation and Analytical Verification",
    (
        "Follow the active case from geometry and mass flow through the signed momentum balance, "
        "compare the force result, and continue to the supporting charts."
        if course_mode
        else "Follow the active case from geometry and mass flow through the signed momentum balance, then compare it with the simulator output."
    ),
)
render_disclaimer()

precision = st.segmented_control(
    "Calculation precision",
    options=["Standard rounded calculation", "More numerical precision"],
    default="Standard rounded calculation",
    required=True,
    width="stretch",
    help="Standard uses five significant digits; the precision view uses ten without changing the calculation.",
)
digits = 10 if precision == "More numerical precision" else 5


def fmt(value: float) -> str:
    """Format substitutions consistently at the selected visible precision."""

    return f"{value:.{digits}g}"


st.markdown("### 1. Given values")
given_rows: list[dict[str, str]] = [
    {"Quantity": "Fluid density, ρ", "Value": fmt(inputs.density), "Unit": "kg/m³"},
    {"Quantity": "Jet diameter, d", "Value": fmt(inputs.diameter), "Unit": "m"},
    {"Quantity": "Inlet velocity, V", "Value": fmt(inputs.velocity), "Unit": "m/s"},
    {"Quantity": "Impact model", "Value": MODEL_LABELS[inputs.model.value], "Unit": "-"},
]
if inputs.model.value in {"deflected_jet", "curved_vane"}:
    given_rows.append(
        {
            "Quantity": "Outlet direction, β",
            "Value": fmt(inputs.outlet_angle_deg),
            "Unit": "degrees",
        }
    )
if not course_mode and inputs.model.value != "normal_flat_plate":
    given_rows.append(
        {
            "Quantity": "Velocity retention, k",
            "Value": fmt(inputs.retention_coefficient),
            "Unit": "dimensionless",
        }
    )
if not course_mode and inputs.model.value == "split_flow":
    given_rows.extend(
        [
            {
                "Quantity": "Plate tangent angle, θ",
                "Value": fmt(inputs.plate_angle_deg),
                "Unit": "degrees",
            },
            {
                "Quantity": "Forward mass fraction, s",
                "Value": fmt(inputs.split_fraction),
                "Unit": "dimensionless",
            },
        ]
    )
st.dataframe(pd.DataFrame(given_rows), width="stretch", hide_index=True)

st.markdown("### 2. Assumptions")
course_assumptions = ASSUMPTIONS[:8]
for title, explanation in course_assumptions if course_mode else ASSUMPTIONS:
    st.markdown(f"- **{title}:** {explanation}")

st.markdown("### 3. Area calculation")
st.latex(r"A=\frac{\pi d^2}{4}")
st.markdown(f"A = π({fmt(inputs.diameter)} m)² / 4 = **{fmt(hand.area_m2)} m²**")

st.markdown("### 4. Flow-rate calculation")
st.latex(r"Q=AV")
st.markdown(
    f"Q = ({fmt(hand.area_m2)} m²)({fmt(inputs.velocity)} m/s) = "
    f"**{fmt(hand.flow_rate_m3_s)} m³/s**"
)

st.markdown("### 5. Mass-flow-rate calculation")
st.latex(r"\dot m=\rho Q")
st.markdown(
    f"ṁ = ({fmt(inputs.density)} kg/m³)({fmt(hand.flow_rate_m3_s)} m³/s) = "
    f"**{fmt(hand.mass_flow_rate_kg_s)} kg/s**"
)

st.markdown("### 6. Inlet and outlet velocity vectors")
st.markdown(
    f"Inlet: **Vin = ({fmt(result.inlet_velocity.x)}, {fmt(result.inlet_velocity.y)}) m/s**"
)
outlet_rows = [
    {
        "Outlet": stream.name,
        "Mass fraction": fmt(stream.mass_fraction),
        "Vout,x (m/s)": fmt(stream.velocity_m_s.x),
        "Vout,y (m/s)": fmt(stream.velocity_m_s.y),
    }
    for stream in result.outlet_streams
]
st.dataframe(pd.DataFrame(outlet_rows), width="stretch", hide_index=True)

st.markdown("### 7. Momentum equation")
st.latex(r"\mathbf{F}_{plate}=\dot m\mathbf{V}_{in}-\sum_j\dot m_j\mathbf{V}_{out,j}")
st.caption(
    "This is the force exerted by the water on the plate. The force exerted by the plate on the control-volume fluid is equal and opposite."
)

st.markdown("### 8. Fx calculation")
st.latex(r"F_x=\dot m V_{in,x}-\sum_j\dot m_jV_{out,x,j}")
st.markdown(
    f"Fx = ({fmt(hand.mass_flow_rate_kg_s)} kg/s)({fmt(result.inlet_velocity.x)} m/s) - "
    f"({fmt(hand.outlet_momentum_flux_x_n)} N) = **{fmt(hand.fx_n)} N**"
)

st.markdown("### 9. Fy calculation")
st.latex(r"F_y=\dot m V_{in,y}-\sum_j\dot m_jV_{out,y,j}")
st.markdown(
    f"Fy = ({fmt(hand.mass_flow_rate_kg_s)} kg/s)({fmt(result.inlet_velocity.y)} m/s) - "
    f"({fmt(hand.outlet_momentum_flux_y_n)} N) = **{fmt(hand.fy_n)} N**"
)

st.markdown("### 10. FR calculation")
st.latex(r"F_R=\sqrt{F_x^2+F_y^2}")
st.markdown(
    f"FR = √[({fmt(hand.fx_n)} N)² + ({fmt(hand.fy_n)} N)²] = "
    f"**{fmt(hand.resultant_force_n)} N**"
)

st.markdown("### 11. Final result")
render_force_cards(result, inputs, unit_system, course_mode=course_mode)

st.markdown("### 12. Comparison with simulator output")
comparison = pd.DataFrame(
    [
        {
            "Component": label,
            "Hand calculation (N)": hand_value,
            "Simulator (N)": simulator_value,
            "Absolute difference (N)": abs(hand_value - simulator_value),
        }
        for label, hand_value, simulator_value in (
            ("Fx - horizontal", hand.fx_n, result.fx_n),
            ("Fy - vertical", hand.fy_n, result.fy_n),
            ("FR - resultant", hand.resultant_force_n, result.resultant_force_n),
        )
    ]
)
st.dataframe(
    comparison,
    column_config={
        "Hand calculation (N)": st.column_config.NumberColumn(format=f"%.{digits}g"),
        "Simulator (N)": st.column_config.NumberColumn(format=f"%.{digits}g"),
        "Absolute difference (N)": st.column_config.NumberColumn(format="%.3e"),
    },
    width="stretch",
    hide_index=True,
)
max_difference = float(comparison["Absolute difference (N)"].max())
tolerance = 1.0e-10 * max(abs(result.fx_n), abs(result.fy_n), result.resultant_force_n, 1.0)
if max_difference <= tolerance:
    st.success(
        "The displayed hand calculation and simulator agree within floating-point rounding. They implement the same documented analytical model; this is analytical verification, not experimental validation.",
        icon=":material/check_circle:",
    )
else:
    st.warning(
        f"The maximum difference is {max_difference:.3e} N, above the comparison tolerance {tolerance:.3e} N. Review the active inputs and outlet vectors.",
        icon=":material/warning:",
    )

st.divider()
st.markdown("### 13. Independent Closed-Form Check")
st.caption(
    f"Expected values are evaluated independently from textbook expressions at the active "
    f"physical scale: ρ = {inputs.density:.6g} kg/m³, d = {inputs.diameter:.6g} m, and "
    f"V = {inputs.velocity:.6g} m/s. Only the documented normal-plate, 90-degree "
    "ideal-deflection, and 180-degree ideal-reversal limits are checked. This is analytical "
    "software verification, not experimental or CFD validation."
)
records = pd.DataFrame.from_records(independent_closed_form_records(inputs))
st.dataframe(
    records,
    column_config={
        "Expected (N)": st.column_config.NumberColumn(format="%.10g"),
        "Simulator (N)": st.column_config.NumberColumn(format="%.10g"),
        "Absolute difference (N)": st.column_config.NumberColumn(format="%.3e"),
        "Tolerance (N)": st.column_config.NumberColumn(format="%.3e"),
    },
    width="stretch",
    hide_index=True,
)
passed = int((records["Status"] == "PASS").sum())
case_count = int(records["Case"].nunique())
if passed == len(records):
    st.success(
        f"All {case_count} supported closed-form cases pass across {passed} component checks.",
        icon=":material/check_circle:",
    )
else:
    st.error(
        f"{len(records) - passed} of {len(records)} component checks require review.",
        icon=":material/error:",
    )

st.divider()
st.page_link(
    "app_pages/3_Results_and_Charts.py",
    label="Open charts and parameter studies" if course_mode else "Continue to Results and Charts",
    icon=":material/show_chart:",
    width="stretch",
)

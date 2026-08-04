"""Default live simulator page for JetForce Studio."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.course import AppMode, DemonstrationPreset
from src.visualizations import (
    create_force_component_chart,
    create_momentum_vector_chart,
    display_value,
    input_snapshot,
    load_demonstration_case,
    render_assumptions,
    render_brand_bar,
    render_case_summary,
    render_disclaimer,
    render_engineering_schematic,
    render_force_cards,
    render_page_intro,
    render_sidebar_controls,
    render_supporting_metrics,
    render_vector_interpretation,
    result_snapshot,
    simulate_safely,
)

mode = AppMode(st.session_state.get("jf_mode", AppMode.COURSE.value))
course_mode = mode is AppMode.COURSE
presentation_view = bool(st.session_state.get("jf_presentation_view", False))

render_brand_bar()
render_page_intro(
    "MEC350 Fluid Mechanics",
    "JetForce Studio",
    "Explore the force exerted by a steady water jet on a stationary plate using a transparent control-volume momentum model.",
)
render_disclaimer()

with st.container(horizontal=True, gap="small"):
    st.button(
        "Normal Plate",
        icon=":material/filter_1:",
        on_click=load_demonstration_case,
        args=(DemonstrationPreset.NORMAL_PLATE,),
        help="Load ρ = 1000 kg/m³, d = 20 mm, V = 10 m/s, normal impact.",
    )
    st.button(
        "Double Velocity",
        icon=":material/speed:",
        on_click=load_demonstration_case,
        args=(DemonstrationPreset.DOUBLE_VELOCITY,),
        help="Load the normal-plate case at V = 20 m/s to demonstrate the V² relation.",
    )
    st.button(
        "90-Degree Deflection",
        icon=":material/turn_right:",
        on_click=load_demonstration_case,
        args=(DemonstrationPreset.NINETY_DEGREE_DEFLECTION,),
        help="Load the ideal single-outlet case with β = 90° and k = 1.",
    )
    st.toggle(
        "Show Calculation",
        key="jf_show_calculation",
        help="Show the main substitutions directly below the results.",
    )
    with st.popover("Quick Help", icon=":material/help:"):
        st.markdown(
            "1. Set water density, jet diameter, velocity, and impact model.\n"
            "2. Use the diagram controls to show or hide vectors and the control volume.\n"
            "3. Read Fx, Fy, and FR as the force exerted by the water on the plate.\n"
            "4. Open **Hand Calculation** for the complete derivation."
        )

if course_mode:
    control_column, schematic_column = st.columns([0.72, 1.45], gap="large")
    with control_column, st.container(border=True):
        inputs, unit_system = render_sidebar_controls(panel=st)
    result = simulate_safely(inputs)
    if result is None:
        st.stop()
    with schematic_column:
        st.subheader("Engineering schematic")
        render_engineering_schematic(
            inputs,
            result,
            prefix="simulator_schematic",
            height=610 if presentation_view else 500,
        )
        render_vector_interpretation(result, inputs)
else:
    inputs, unit_system = render_sidebar_controls()
    result = simulate_safely(inputs)
    if result is None:
        st.stop()
    st.subheader("Engineering schematic")
    render_engineering_schematic(
        inputs,
        result,
        prefix="simulator_schematic",
        height=610 if presentation_view else 510,
    )
    render_vector_interpretation(result, inputs)

st.subheader("Force exerted by the water on the plate")
render_force_cards(result, inputs, unit_system, course_mode=course_mode)

st.markdown("#### Supporting quantities")
render_supporting_metrics(result, inputs, unit_system, course_mode=course_mode)

values = result_snapshot(result, inputs)
if values["mass_flow_rate"] == 0.0:
    st.info(
        "The inlet velocity is zero, so Q, mass flow, and every momentum-force component are zero. The result is valid and no force direction is defined.",
        icon=":material/info:",
    )
elif input_snapshot(inputs)["model"] == "normal_flat_plate":
    st.success(
        "For ideal normal impact, the opposing sideways outlet momenta cancel. The plate reaction is entirely in positive x and follows F = ρAV².",
        icon=":material/check_circle:",
    )
else:
    st.info(
        "The outlet angle changes both momentum components. A positive outlet y-component produces a negative Fy reaction on the plate under the declared sign convention.",
        icon=":material/compare_arrows:",
    )

if (
    input_snapshot(inputs)["model"] == "normal_flat_plate"
    and abs(float(input_snapshot(inputs)["velocity"]) - 20.0) < 1.0e-12
    and abs(float(input_snapshot(inputs)["density"]) - 1000.0) < 1.0e-12
    and abs(float(input_snapshot(inputs)["diameter"]) - 0.02) < 1.0e-12
):
    st.info(
        "For ideal normal impact, force is proportional to V². Doubling velocity from 10 m/s to 20 m/s produces approximately four times the force.",
        icon=":material/trending_up:",
    )

if st.session_state.get("jf_show_calculation", False) or presentation_view:
    with st.container(border=True):
        st.markdown("#### Main equation and current substitution")
        st.latex(r"A=\frac{\pi d^2}{4},\quad Q=AV,\quad \dot m=\rho Q")
        st.latex(r"\mathbf{F}_{plate}=\dot m\mathbf{V}_{in}-\sum_j\dot m_j\mathbf{V}_{out,j}")
        st.markdown(
            f"A = {result.area_m2:.8g} m²; Q = {result.flow_rate_m3_s:.8g} m³/s; "
            f"ṁ = {result.mass_flow_rate_kg_s:.8g} kg/s.  "
            f"Therefore Fx = {result.fx_n:.8g} N, Fy = {result.fy_n:.8g} N, "
            f"and FR = {result.resultant_force_n:.8g} N."
        )

if not course_mode:
    st.divider()
    detail_view = st.segmented_control(
        "Advanced result view",
        options=["Components", "Momentum vectors", "Outlet data", "Assumptions"],
        default="Components",
        required=True,
        width="stretch",
    )
    force_factor, force_unit = display_value(1.0, "force", unit_system)
    velocity_factor, velocity_unit = display_value(1.0, "velocity", unit_system)
    mass_factor, mass_unit = display_value(1.0, "mass_flow_rate", unit_system)

    if detail_view == "Components":
        render_case_summary(inputs)
        st.plotly_chart(
            create_force_component_chart(result, inputs, unit_system),
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )
    elif detail_view == "Momentum vectors":
        st.plotly_chart(
            create_momentum_vector_chart(result, inputs, unit_system),
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )
        force_table = pd.DataFrame(
            {
                "Body receiving force": ["Plate (reported)", "Control-volume fluid"],
                f"Fx ({force_unit})": [
                    result.force_on_plate_n.x * force_factor,
                    result.force_on_fluid_n.x * force_factor,
                ],
                f"Fy ({force_unit})": [
                    result.force_on_plate_n.y * force_factor,
                    result.force_on_fluid_n.y * force_factor,
                ],
                "Interpretation": ["Water on plate", "Plate on water; equal and opposite"],
            }
        )
        st.dataframe(force_table, width="stretch", hide_index=True)
    elif detail_view == "Outlet data":
        rows = [
            {
                "Section": "Inlet",
                "Mass fraction": 1.0,
                f"Mass flow ({mass_unit})": result.mass_flow_rate_kg_s * mass_factor,
                f"Vx ({velocity_unit})": result.inlet_velocity.x * velocity_factor,
                f"Vy ({velocity_unit})": result.inlet_velocity.y * velocity_factor,
            }
        ]
        rows.extend(
            {
                "Section": stream.name,
                "Mass fraction": stream.mass_fraction,
                f"Mass flow ({mass_unit})": stream.mass_flow_rate_kg_s * mass_factor,
                f"Vx ({velocity_unit})": stream.velocity_m_s.x * velocity_factor,
                f"Vy ({velocity_unit})": stream.velocity_m_s.y * velocity_factor,
            }
            for stream in result.outlet_streams
        )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(
            f"Outlet mass fractions sum to {sum(stream.mass_fraction for stream in result.outlet_streams):.6g}."
        )
    else:
        render_assumptions(expanded=True)
        st.warning(
            "The velocity-retention coefficient is a user-selected modeling assumption. It is not an experimental fit or a CFD prediction.",
            icon=":material/warning:",
        )

st.divider()
with st.container(horizontal=True, horizontal_alignment="distribute"):
    st.page_link(
        "app_pages/2_Hand_Calculation.py",
        label="Open Hand Calculation",
        icon=":material/calculate:",
        width="stretch",
    )
    st.page_link(
        "app_pages/3_Results_and_Charts.py",
        label="Open Results and Charts",
        icon=":material/show_chart:",
        width="stretch",
    )

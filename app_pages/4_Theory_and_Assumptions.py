"""Governing equations, control volume, assumptions, and limitations."""

from __future__ import annotations

import streamlit as st

from src.course import ADVANCED_MODE_NOTICE, AppMode
from src.visualizations import (
    ASSUMPTIONS,
    render_brand_bar,
    render_disclaimer,
    render_page_intro,
)

mode = AppMode(st.session_state.get("jf_mode", AppMode.COURSE.value))
course_mode = mode is AppMode.COURSE

render_brand_bar()
render_page_intro(
    "Fluid-mechanics foundation",
    "Theory and Assumptions",
    "Define the control volume, sign convention, and outlet vectors before applying steady linear momentum.",
)
render_disclaimer()

st.markdown("## Control-volume definition")
st.write(
    "The compact stationary control volume encloses the jet-impact region. Its inlet plane cuts the undisturbed circular free jet; its outlet planes cut the prescribed leaving streams. Each exposed jet section is at atmospheric pressure, so gauge-pressure forces at those sections are zero. Gravity across this small region is neglected."
)

st.markdown("## Coordinate system and reaction convention")
st.markdown(
    "- Positive **x** follows the incoming horizontal jet.\n"
    "- Positive **y** is upward.\n"
    "- The inlet velocity is **Vin = (V, 0)**.\n"
    "- Reported Fx, Fy, and FR are the force exerted **by the water on the plate**."
)
st.latex(r"\sum \mathbf{F}_{on\ fluid}=\sum_j\dot m_j\mathbf{V}_{out,j}-\dot m\mathbf{V}_{in}")
st.latex(r"\mathbf{F}_{plate}=\dot m\mathbf{V}_{in}-\sum_j\dot m_j\mathbf{V}_{out,j}")
st.info(
    "The plate-on-fluid force and water-on-plate force are equal in magnitude and opposite in direction. JetForce Studio reports only the water-on-plate reaction as the primary result.",
    icon=":material/compare_arrows:",
)

st.markdown("## Common quantities")
with st.container(horizontal=True, gap="large"):
    with st.container(border=True):
        st.latex(r"A=\frac{\pi d^2}{4}")
        st.caption("Circular inlet area, m²")
    with st.container(border=True):
        st.latex(r"Q=AV")
        st.caption("Volumetric flow rate, m³/s")
    with st.container(border=True):
        st.latex(r"\dot m=\rho Q=\rho AV")
        st.caption("Mass-flow rate, kg/s")

st.markdown("## Force components and resultant")
st.latex(r"F_x=\dot mV_{in,x}-\sum_j\dot m_jV_{out,x,j}")
st.latex(r"F_y=\dot mV_{in,y}-\sum_j\dot m_jV_{out,y,j}")
st.latex(r"F_R=\sqrt{F_x^2+F_y^2}")

st.markdown("## Course impact models")
normal_column, deflected_column = st.columns(2, gap="large")
with normal_column, st.container(border=True):
    st.markdown("### Normal Flat Plate")
    st.write(
        "The centered jet divides into equal sideways streams. Their opposite outlet momenta cancel, leaving the removed inlet momentum as the net plate reaction."
    )
    st.latex(r"F_x=\rho AV^2,\quad F_y=0,\quad F_R=|F_x|")
with deflected_column, st.container(border=True):
    st.markdown("### Deflected Jet / Curved Plate Comparison")
    st.write(
        "Course Mode represents the ideal leaving stream with one outlet vector at angle β. A curved guide and a deflected free jet are compared through this same section-average momentum construction; no spatial flow field is solved."
    )
    st.latex(r"\mathbf{V}_{out}=V(\cos\beta,\sin\beta)")
    st.latex(r"F_x=\dot mV(1-\cos\beta),\quad F_y=-\dot mV\sin\beta")

st.markdown("## Modeling assumptions")
for index, (title, explanation) in enumerate(
    ASSUMPTIONS[:8] if course_mode else ASSUMPTIONS, start=1
):
    with st.expander(f"{index}. {title}", expanded=index <= 2):
        st.write(explanation)

st.markdown("## Limitations")
st.warning(
    "The model does not resolve pressure or velocity fields, jet breakup, droplets, air entrainment, viscous boundary layers, turbulence structure, unsteady force fluctuations, three-dimensional torque, plate deformation, or fluid-structure interaction.",
    icon=":material/warning:",
)

if not course_mode:
    st.divider()
    st.info(ADVANCED_MODE_NOTICE, icon=":material/info:")
    advanced_view = st.segmented_control(
        "Supplementary theory",
        options=["Split flow", "Non-ideal outlet speed", "Reynolds diagnostic"],
        default="Split flow",
        required=True,
        width="stretch",
    )
    if advanced_view == "Split flow":
        st.markdown("### Split flow along a flat plate")
        st.write(
            "Two exactly opposed tangent outlets carry mass fractions s and 1 - s. Their mass-flow rates sum to the inlet mass flow."
        )
        st.latex(r"\dot m_1=s\dot m,\quad \dot m_2=(1-s)\dot m")
        st.latex(r"\mathbf{V}_1=kV(\cos\theta,\sin\theta),\quad \mathbf{V}_2=-\mathbf{V}_1")
        st.latex(r"F_x=\dot mV[1-(2s-1)k\cos\theta]")
        st.latex(r"F_y=-\dot mV(2s-1)k\sin\theta")
    elif advanced_view == "Non-ideal outlet speed":
        st.markdown("### User-selected velocity retention")
        st.latex(r"\mathbf{V}_{out}=kV(\cos\beta,\sin\beta),\quad 0\leq k\leq1")
        st.write(
            "k prescribes the retained outlet speed. It is a modeling assumption for aggregate losses, not a CFD result, experimental calibration, or Reynolds-number correction."
        )
    else:
        st.markdown("### Reynolds number as context only")
        st.latex(r"Re=\frac{\rho Vd}{\mu}")
        st.write(
            "Reynolds number characterizes the inlet jet's inertia-to-viscosity ratio. It is reported only as supporting context and never alters the momentum-force equation automatically."
        )

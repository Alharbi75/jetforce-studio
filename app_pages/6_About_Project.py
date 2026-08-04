"""Project purpose, responsible use, privacy, and limitations."""

from __future__ import annotations

import streamlit as st

from src.course import COURSE_MODE_EXPLANATION, PRIVACY_STATEMENT
from src.visualizations import render_brand_bar, render_disclaimer, render_page_intro

render_brand_bar()
render_page_intro(
    "MEC350 course project",
    "About the Project",
    "JetForce Studio is an educational numerical tool for explaining and presenting the control-volume momentum analysis of a water jet striking a stationary plate.",
)
render_disclaimer()

st.markdown("## Project purpose")
st.write(
    "The application connects a defined jet geometry, a compact control volume, mass conservation, prescribed outlet velocity vectors, and the two-dimensional steady linear-momentum equation. Its primary engineering results are Fx, Fy, and FR for the force exerted by the water on the plate."
)

st.markdown("## Course and Advanced modes")
st.info(COURSE_MODE_EXPLANATION, icon=":material/school:")
with st.container(horizontal=True, gap="large"):
    with st.container(border=True):
        st.markdown("### Course Mode")
        st.write(
            "Starts every fresh browser session with water at 1000 kg/m³, d = 20 mm, V = 10 m/s, SI units, and a normal flat plate. Only the main MEC350 inputs, equations, charts, and results are shown."
        )
    with st.container(border=True):
        st.markdown("### Advanced Mode")
        st.write(
            "Adds supplementary fluids, viscosity and Reynolds context, velocity retention, split flow, curved-vane comparisons, alternate display units, and additional studies without changing the governing momentum balance."
        )

st.markdown("## Privacy and local computation")
st.success(PRIVACY_STATEMENT, icon=":material/privacy_tip:")
st.markdown(
    "- No visitor login or account is implemented.\n"
    "- No file upload, payment, subscription, API key, database, advertising, or behavioral tracking is used.\n"
    "- Core calculations use local project code and do not call an external runtime API.\n"
    "- Engineering inputs remain in the visitor's Streamlit session and exports are generated in memory on request."
)
st.caption(
    "The hosting platform may handle its own necessary technical data; this statement describes the application's behavior only."
)

st.markdown("## Academic scope and honesty")
st.write(
    "Analytical verification checks the implementation against equations and limiting cases. It is not experimental validation. A future laboratory comparison would require traceable measurements and uncertainty analysis; a future high-fidelity comparison would require a separately justified dataset."
)
st.warning(
    "Do not present the schematic, animation, or parameter charts as CFD or experimental evidence. They visualize a steady section-average momentum model.",
    icon=":material/warning:",
)

st.markdown("## What the model does not resolve")
limitations = (
    "Spatial pressure, velocity, turbulence, or free-surface fields",
    "Jet breakup, droplets, sheet thickness, or air entrainment",
    "Unsteady pressure and force fluctuations",
    "Viscous boundary layers or distributed plate loading",
    "Three-dimensional flow, torque, or off-axis loading",
    "Plate deformation, vibration, or fluid-structure interaction",
    "Empirical loss calibration without supplied measurements",
)
for limitation in limitations:
    st.markdown(f"- {limitation}")

st.markdown("## Reproducible software structure")
st.code(
    """
app.py                 shared configuration and six-page navigation
app_pages/             Streamlit presentation pages
src/calculations.py    authoritative SI momentum physics
src/models.py          typed inputs, vectors, streams, and results
src/validation.py      input checks and hand-calculation support
src/visualizations.py  result-driven diagrams, controls, and charts
src/reporting.py       in-memory CSV, JSON, HTML, and PDF exports
tests/                 physics, release, export, and UI regression checks
    """.strip(),
    language="text",
)

with st.expander("دليل عربي مختصر", expanded=False):
    st.html(
        '<div dir="rtl">يبدأ التطبيق في <strong>الوضع الدراسي</strong> بقيم مثال جاهزة. '
        "غيّر كثافة الماء وقطر النفث وسرعته ونموذج الاصطدام، ثم اقرأ Fx وFy وFR بوصفها القوة "
        "التي يؤثر بها الماء على اللوح. المحور x الموجب مع اتجاه النفث الداخل، والمحور y الموجب إلى أعلى. "
        "المخطط توضيحي وليس محاكاة CFD كاملة.</div>",
    )

st.markdown("## Responsible academic use")
st.write(
    "Verify the selected inputs and units, explain why each assumption is reasonable for the chosen case, cite only sources you have checked, and follow your institution's academic-integrity policy. Student and instructor details are intentionally left blank in generated-report fields until the user enters them."
)

st.divider()
with st.container(horizontal=True, horizontal_alignment="distribute"):
    st.page_link(
        "app_pages/1_Simulator.py",
        label="Return to Simulator",
        icon=":material/water_drop:",
        width="stretch",
    )
    st.page_link(
        "app_pages/4_Theory_and_Assumptions.py",
        label="Read Theory and Assumptions",
        icon=":material/menu_book:",
        width="stretch",
    )

"""JetForce Studio public Streamlit entry point.

Run locally with ``streamlit run app.py``.
"""

from __future__ import annotations

import streamlit as st

from src.visualizations import (
    configure_page,
    render_application_mode_selector,
    render_presentation_styles,
)


def run_navigation() -> None:
    """Configure the shared frame, declare six public pages, and run one page."""

    # This is deliberately the first Streamlit command in the entry point.
    # The browser-tab title is deliberately page-neutral because Streamlit's
    # multipage router configures the document once before the selected page runs.
    configure_page("MEC350")
    render_application_mode_selector()
    render_presentation_styles()

    selected = st.navigation(
        [
            st.Page(
                "app_pages/1_Simulator.py",
                title="Simulator",
                icon=":material/water_drop:",
                default=True,
            ),
            st.Page(
                "app_pages/2_Hand_Calculation.py",
                title="Hand Calculation",
                icon=":material/calculate:",
            ),
            st.Page(
                "app_pages/3_Results_and_Charts.py",
                title="Results and Charts",
                icon=":material/show_chart:",
            ),
            st.Page(
                "app_pages/4_Theory_and_Assumptions.py",
                title="Theory and Assumptions",
                icon=":material/menu_book:",
            ),
            st.Page(
                "app_pages/5_Report_and_Export.py",
                title="Report and Export",
                icon=":material/download:",
            ),
            st.Page(
                "app_pages/6_About_Project.py",
                title="About the Project",
                icon=":material/info:",
            ),
        ],
        position="top",
    )
    selected.run()


if __name__ == "__main__":
    run_navigation()

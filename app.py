"""JetForce Studio public Streamlit entry point.

Run locally with ``streamlit run app.py``.
"""

from __future__ import annotations

import streamlit as st

from src.course import (
    COURSE_PRIMARY_DESTINATIONS,
    COURSE_SECONDARY_DESTINATION,
    AppMode,
)
from src.visualizations import (
    configure_page,
    render_application_mode_selector,
    render_presentation_styles,
)


def run_navigation() -> None:
    """Configure the shared frame, register stable routes, and run one page."""

    # This is deliberately the first Streamlit command in the entry point.
    # The browser-tab title is deliberately page-neutral because Streamlit's
    # multipage router configures the document once before the selected page runs.
    configure_page("MEC350")
    mode = render_application_mode_selector()
    render_presentation_styles()
    course_mode = mode is AppMode.COURSE

    selected = st.navigation(
        [
            st.Page(
                "app_pages/1_Simulator.py",
                title=COURSE_PRIMARY_DESTINATIONS[0],
                icon=":material/water_drop:",
                default=True,
            ),
            st.Page(
                "app_pages/2_Hand_Calculation.py",
                title=(COURSE_PRIMARY_DESTINATIONS[1] if course_mode else "Hand Calculation"),
                icon=":material/calculate:",
            ),
            st.Page(
                "app_pages/3_Results_and_Charts.py",
                title="Results and Charts",
                icon=":material/show_chart:",
                visibility="hidden" if course_mode else "visible",
            ),
            st.Page(
                "app_pages/4_Theory_and_Assumptions.py",
                title=COURSE_PRIMARY_DESTINATIONS[2],
                icon=":material/menu_book:",
            ),
            st.Page(
                "app_pages/5_Report_and_Export.py",
                title=COURSE_PRIMARY_DESTINATIONS[3],
                icon=":material/download:",
            ),
            st.Page(
                "app_pages/6_About_Project.py",
                title=COURSE_SECONDARY_DESTINATION,
                icon=":material/info:",
                visibility="hidden" if course_mode else "visible",
            ),
        ],
        position="top",
    )
    if course_mode:
        st.sidebar.divider()
        st.sidebar.caption("Project information")
        st.sidebar.page_link(
            "app_pages/6_About_Project.py",
            label=COURSE_SECONDARY_DESTINATION,
            icon=":material/info:",
            width="stretch",
        )
    selected.run()


if __name__ == "__main__":
    run_navigation()

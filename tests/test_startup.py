"""Streamlit entry-point, page, and local headless-startup checks."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PAGES = (
    "app_pages/1_Simulator.py",
    "app_pages/2_Hand_Calculation.py",
    "app_pages/3_Results_and_Charts.py",
    "app_pages/4_Theory_and_Assumptions.py",
    "app_pages/5_Report_and_Export.py",
    "app_pages/6_About_Project.py",
)


def _app() -> AppTest:
    return AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=30).run()


def _element_by_label(elements: object, label: str) -> object:
    return next(element for element in elements if element.label == label)  # type: ignore[attr-defined]


def _html_body(app: AppTest) -> str:
    return "\n".join(element.proto.body for element in app.get("html"))


def _environment_without_secret_values() -> dict[str, str]:
    secret_markers = ("API_KEY", "PASSWORD", "SECRET", "TOKEN")
    return {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in secret_markers)
    }


def test_default_app_starts_in_course_mode_with_complete_textbook_case() -> None:
    app = _app()

    assert not app.exception
    mode = _element_by_label(app.segmented_control, "Application mode")
    model = _element_by_label(app.selectbox, "Impact model")
    assert mode.value == "Course Mode"
    assert model.value == "normal_flat_plate"
    assert _element_by_label(app.number_input, "Fluid density, ρ (kg/m³)").value == 1000.0
    assert _element_by_label(app.slider, "Jet diameter, d (mm)").value == 20.0
    assert _element_by_label(app.slider, "Inlet jet velocity, V (m/s)").value == 10.0
    assert "Jet diameter, d (m) - precise entry" not in {item.label for item in app.number_input}
    assert "Inlet jet velocity, V (m/s) - precise entry" not in {
        item.label for item in app.number_input
    }
    assert [(metric.label, metric.value) for metric in app.metric] == [
        ("Jet area, A", "3.142 × 10⁻⁴ m²"),
        ("Flow rate, Q", "3.142 × 10⁻³ m³/s"),
        ("Mass flow, ṁ", "3.142 kg/s"),
    ]

    html = _html_body(app)
    assert "Fx - Horizontal force on the plate: 31.42 N" in html
    assert "Fy - Vertical force on the plate: 0.00 N" in html
    assert "FR - Resultant force on the plate: 31.42 N" in html
    assert "not a full CFD simulation" in html


def test_course_controls_are_single_purpose_and_angle_is_conditional() -> None:
    app = _app()

    assert sum(item.label == "Fluid density, ρ (kg/m³)" for item in app.number_input) == 1
    assert sum(item.label == "Jet diameter, d (mm)" for item in app.slider) == 1
    assert sum(item.label == "Inlet jet velocity, V (m/s)" for item in app.slider) == 1
    assert sum(item.label == "Impact model" for item in app.selectbox) == 1
    assert "Outlet direction angle, β (degrees)" not in {item.label for item in app.slider}

    _element_by_label(app.selectbox, "Impact model").select_index(1).run()

    assert not app.exception
    assert "Outlet direction angle, β (degrees)" in {item.label for item in app.slider}


def test_demonstration_selector_loads_one_case_and_reset_is_separate() -> None:
    app = _app()

    button_labels = [item.label for item in app.button]
    assert button_labels.count("Load Selected Case") == 1
    assert button_labels.count("Reset to Default") == 1
    assert "Load Demonstration Case" not in button_labels
    assert "Normal Plate" not in button_labels
    assert "Double Velocity" not in button_labels
    assert "90-Degree Deflection" not in button_labels

    _element_by_label(app.selectbox, "Demonstration case").select("Double Velocity").run()
    _element_by_label(app.button, "Load Selected Case").click().run()

    assert not app.exception
    assert _element_by_label(app.slider, "Inlet jet velocity, V (m/s)").value == 20.0
    assert "Fx - Horizontal force on the plate: 125.66 N" in _html_body(app)


def test_course_mode_hides_supplementary_controls_and_advanced_mode_reveals_them() -> None:
    app = _app()

    assert "Dynamic viscosity, μ (Pa·s)" not in {item.label for item in app.number_input}
    assert "Fluid preset" not in {item.label for item in app.selectbox}
    assert "Result display units" not in {item.label for item in app.segmented_control}

    mode = _element_by_label(app.segmented_control, "Application mode")
    mode.select("Advanced Mode").run()

    assert not app.exception
    assert "Dynamic viscosity, μ (Pa·s)" in {item.label for item in app.number_input}
    assert "Fluid preset" in {item.label for item in app.selectbox}
    assert "Result display units" in {item.label for item in app.segmented_control}
    assert any("These options are supplementary" in message.value for message in app.info)


def test_mode_switch_preserves_synchronized_diameter_velocity_and_model_controls() -> None:
    app = _app()

    _element_by_label(app.segmented_control, "Application mode").select("Advanced Mode").run()

    assert not app.exception
    assert _element_by_label(app.slider, "Jet diameter, d (mm)").value == 20.0
    assert _element_by_label(app.number_input, "Jet diameter, d (m) - precise entry").value == 0.02
    assert _element_by_label(app.slider, "Inlet jet velocity, V (m/s)").value == 10.0
    assert (
        _element_by_label(app.number_input, "Inlet jet velocity, V (m/s) - precise entry").value
        == 10.0
    )
    assert _element_by_label(app.selectbox, "Impact model").value == "normal_flat_plate"


def test_reset_and_presentation_view_are_operable() -> None:
    app = _app()

    density = _element_by_label(app.number_input, "Fluid density, ρ (kg/m³)")
    density.set_value(1100.0).run()
    assert _element_by_label(app.number_input, "Fluid density, ρ (kg/m³)").value == 1100.0

    _element_by_label(app.button, "Reset to Default").click().run()
    assert _element_by_label(app.number_input, "Fluid density, ρ (kg/m³)").value == 1000.0

    presentation = _element_by_label(app.toggle, "Presentation View")
    presentation.set_value(True).run()
    assert not app.exception
    assert app.session_state.filtered_state["jf_presentation_view"] is True
    assert "font-size: clamp(2rem, 4vw, 3.35rem)" in _html_body(app)


def test_course_navigation_keeps_secondary_routes_hidden_but_registered() -> None:
    source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

    assert source.count('visibility="hidden" if course_mode else "visible"') == 2
    assert '"app_pages/3_Results_and_Charts.py"' in source
    assert '"app_pages/6_About_Project.py"' in source
    assert "COURSE_PRIMARY_DESTINATIONS[1] if course_mode" in source
    assert "st.sidebar.page_link" in source


def test_styles_define_phone_tablet_desktop_focus_and_motion_contracts() -> None:
    css = (PROJECT_ROOT / "assets/styles.css").read_text(encoding="utf-8")

    for query in (
        "@media (max-width: 340px)",
        "@media (max-width: 390px)",
        "@media (max-width: 768px)",
        "@media (min-width: 1366px) and (max-width: 1599px)",
        "@media (min-width: 1600px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert query in css
    assert "button:focus-visible" in css
    assert '[role="combobox"]:focus-visible' in css
    assert "transition-duration: .01ms" in css
    assert "@media (hover: hover) and (pointer: fine)" in css
    assert '[data-baseweb="tab-list"]' not in css


@pytest.mark.parametrize("page", PUBLIC_PAGES)
def test_every_public_page_runs_without_streamlit_exception(page: str) -> None:
    app = _app()
    app.switch_page(page).run()
    assert not app.exception


def test_report_package_exposes_one_page_presentation_summary() -> None:
    app = _app()
    app.switch_page("app_pages/5_Report_and_Export.py").run()
    _element_by_label(app.button, "Generate Export Package").click().run(timeout=60)

    assert not app.exception
    assert "Download One-Page Presentation Summary" in {
        item.label for item in app.get("download_button")
    }


def test_project_imports_with_no_secret_environment_variables() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import app; import src; import src.reporting"],
        cwd=PROJECT_ROOT,
        env=_environment_without_secret_values(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_headless_streamlit_process_reaches_local_health_endpoint() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app.py"),
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=_environment_without_secret_values(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = ""
    health_body: str | None = None
    try:
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/_stcore/health", timeout=0.5
                ) as response:
                    health_body = response.read().decode("utf-8")
                    break
            except OSError:
                time.sleep(0.1)
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=5)

    assert health_body == "ok", f"Streamlit did not become healthy. Output:\n{output}"

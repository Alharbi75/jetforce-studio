"""Shared Streamlit presentation helpers and engineering visualizations.

The functions in this module do not implement an alternative force model. They
consume :mod:`src.calculations` results so that dashboard values, diagrams, and
charts remain traceable to the project's single physics implementation.
"""

from __future__ import annotations

import base64
import json
import logging
import math
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import fields, replace
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .constants import (
    COURSE_TEXTBOOK_DENSITY_KG_M3,
    DEFAULT_DENSITY_KG_M3,
    DEFAULT_DIAMETER_M,
    DEFAULT_DYNAMIC_VISCOSITY_PA_S,
    DEFAULT_OUTLET_ANGLE_DEG,
    DEFAULT_PLATE_ANGLE_DEG,
    DEFAULT_RETENTION_COEFFICIENT,
    DEFAULT_SPLIT_FRACTION,
    DEFAULT_VELOCITY_M_S,
    FLUID_PROPERTY_PRESETS,
    MAX_ANGLE_DEG,
    MAX_DENSITY_KG_M3,
    MAX_DIAMETER_M,
    MAX_DYNAMIC_VISCOSITY_PA_S,
    MAX_RETENTION_COEFFICIENT,
    MAX_SPLIT_FRACTION,
    MAX_VELOCITY_M_S,
    MIN_ANGLE_DEG,
    MIN_DENSITY_KG_M3,
    MIN_DIAMETER_M,
    MIN_DYNAMIC_VISCOSITY_PA_S,
    MIN_RETENTION_COEFFICIENT,
    MIN_SPLIT_FRACTION,
    MIN_VELOCITY_M_S,
    ZERO_TOLERANCE,
)
from .course import (
    ADVANCED_MODE_NOTICE,
    COURSE_MODE_EXPLANATION,
    COURSE_MODEL_LABELS,
    AppMode,
    DemonstrationPreset,
    demonstration_inputs,
    textbook_course_inputs,
)
from .models import FluidPreset, ImpactModel, JetInputs, UnitSystem
from .utils import convert_from_si, display_unit, format_number

LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"

MODEL_LABELS: dict[str, str] = {
    "normal_flat_plate": "Normal jet on a flat plate",
    "deflected_jet": "Single deflected outlet jet",
    "split_flow": "Split flow along a flat plate",
    "curved_vane": "Curved vane",
}

MODEL_SHORT_LABELS: dict[str, str] = {
    "normal_flat_plate": "Normal plate",
    "deflected_jet": "Deflected outlet",
    "split_flow": "Split flow",
    "curved_vane": "Curved vane",
}

MODEL_DESCRIPTIONS: dict[str, str] = {
    "normal_flat_plate": (
        "The jet loses its net inlet-direction momentum and leaves sideways " "symmetrically."
    ),
    "deflected_jet": (
        "One prescribed outlet carries all mass at angle beta and retained speed kV."
    ),
    "split_flow": ("Two opposite plate-tangent outlets carry fractions s and 1-s of the flow."),
    "curved_vane": (
        "A curved guide turns one outlet stream; the same vector momentum balance applies."
    ),
}

ASSUMPTIONS: tuple[tuple[str, str], ...] = (
    (
        "Steady flow",
        "Stored mass and momentum in the impact control volume do not change with time.",
    ),
    (
        "Incompressible fluid",
        "Density is treated as constant across the inlet and outlet sections.",
    ),
    ("Uniform velocity", "Each jet section is represented by one section-average velocity vector."),
    ("Atmospheric free jets", "Exposed jet sections have zero gauge-pressure contribution."),
    (
        "Stationary rigid plate",
        "Plate motion, deformation, and fluid-structure interaction are outside scope.",
    ),
    (
        "Compact control volume",
        "Gravity across the small impact region and air drag are neglected.",
    ),
    (
        "Constant inlet diameter",
        "The specified circular diameter defines the undisturbed inlet area.",
    ),
    (
        "Mass conservation",
        "Outlet mass flow equals inlet mass flow, including both split branches.",
    ),
    (
        "Prescribed loss model",
        "The coefficient k represents retained outlet speed; it is not inferred from CFD or Reynolds number.",
    ),
    (
        "Two-dimensional balance",
        "Only x and y momentum components and reaction forces are calculated.",
    ),
)

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "density": ("density", "rho", "density_kg_m3"),
    "viscosity": ("dynamic_viscosity", "viscosity", "mu", "viscosity_pa_s"),
    "diameter": ("diameter", "jet_diameter", "d", "diameter_m"),
    "velocity": ("velocity", "inlet_velocity", "jet_velocity", "v", "velocity_m_s"),
    "model": ("impact_model", "model"),
    "theta": ("plate_angle_deg", "theta_deg", "plate_orientation_deg", "theta"),
    "beta": ("outlet_angle_deg", "beta_deg", "deflection_angle_deg", "beta"),
    "retention": ("retention_coefficient", "velocity_retention", "k"),
    "split": ("split_fraction", "s"),
    "fluid_preset": ("fluid_preset", "preset"),
    "unit_system": ("unit_system", "units"),
}

_RESULT_ALIASES: dict[str, tuple[str, ...]] = {
    "fx": ("fx_n", "fx", "force_x", "horizontal_force"),
    "fy": ("fy_n", "fy", "force_y", "vertical_force"),
    "fr": ("resultant_force_n", "fr", "resultant_force", "force_resultant"),
    "force_angle": ("force_angle_deg", "force_direction_deg", "direction_deg"),
    "area": ("area_m2", "area", "jet_area"),
    "flow_rate": ("flow_rate_m3_s", "flow_rate", "q", "volumetric_flow_rate"),
    "mass_flow_rate": ("mass_flow_rate_kg_s", "mass_flow_rate", "mdot", "mass_flow"),
    "reynolds_number": ("reynolds_number", "reynolds", "re"),
    "outlet_speed": ("outlet_speed_m_s", "outlet_speed", "vout_magnitude", "exit_speed"),
    "vin": ("inlet_velocity", "vin", "inlet_velocity_vector", "velocity_in"),
    "vout": (
        "vout_equivalent",
        "outlet_velocity",
        "vout",
        "outlet_velocity_vector",
        "velocity_out",
        "effective_outlet_velocity",
    ),
    "outlet_vectors": ("outlet_streams", "outlet_vectors", "outlet_velocity_vectors", "vouts"),
    "outlet_mass_fractions": ("outlet_mass_fractions", "mass_fractions"),
}


def _render_html(body: str | Path) -> None:
    """Render trusted local HTML/CSS with the current public Streamlit API.

    The Markdown fallback keeps the deterministic presentation helpers easy to
    unit-test with older lightweight test doubles.
    """

    if hasattr(st, "html"):
        st.html(body)
    else:  # pragma: no cover - compatibility with test doubles and Streamlit < 1.33.
        text = Path(body).read_text(encoding="utf-8") if isinstance(body, Path) else body
        st.markdown(text, unsafe_allow_html=True)


def configure_page(page_title: str, *, page_icon: str = ":material/water_drop:") -> None:
    """Apply consistent page configuration, logo, and project styling."""

    st.set_page_config(
        page_title=f"{page_title} · JetForce Studio",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="auto",
        menu_items={
            "Get Help": None,
            "Report a bug": None,
            "About": (
                "JetForce Studio — MEC350 Fluid Mechanics. A numerical "
                "control-volume momentum model; not a CFD solver."
            ),
        },
    )
    css_path = ASSETS_DIR / "styles.css"
    if css_path.exists():
        _render_html(css_path)
    logo_path = ASSETS_DIR / "logo.svg"
    if logo_path.exists():
        with suppress(TypeError, AttributeError):
            st.logo(str(logo_path), size="large")


def render_brand_bar() -> None:
    """Render the common course and analysis identity."""

    logo_uri = _svg_data_uri(ASSETS_DIR / "logo.svg")
    _render_html(
        f"""
        <div class="jf-brandbar">
          <img src="{logo_uri}" alt="JetForce Studio" />
          <div class="jf-brand-meta">Water Jet Impact Engineering Simulator<br/>
          MEC350 Fluid Mechanics · Numerical control-volume analysis</div>
        </div>
        """,
    )


def render_page_intro(eyebrow: str, title: str, description: str) -> None:
    """Render a compact, accessible page heading."""

    _render_html(
        f"""
        <section class="jf-page-intro">
          <div class="jf-eyebrow">{escape(eyebrow)}</div>
          <h1>{escape(title)}</h1>
          <p>{escape(description)}</p>
        </section>
        """,
    )


def render_disclaimer() -> None:
    """Show the scope statement required on engineering views."""

    _render_html(
        """
        <div class="jf-disclaimer" role="note">
          <span aria-hidden="true">ⓘ</span>
          <div><strong>Model scope.</strong> This application uses a numerical control-volume momentum model.
          The flow visualization is illustrative and is not a full CFD simulation.</div>
        </div>
        """,
    )


def _svg_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    from urllib.parse import quote

    return f"data:image/svg+xml,{quote(path.read_text(encoding='utf-8'))}"


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def canonical_model(value: Any) -> str:
    """Normalize model enums or labels to the model's stable string key."""

    raw = str(_enum_value(value)).strip().lower().replace(" ", "_")
    if raw in MODEL_LABELS:
        return raw
    aliases = {
        "normal": "normal_flat_plate",
        "normal_plate": "normal_flat_plate",
        "flat_plate": "normal_flat_plate",
        "single_deflected_outlet": "deflected_jet",
        "deflected": "deflected_jet",
        "split": "split_flow",
        "curved": "curved_vane",
    }
    return aliases.get(raw, raw)


def _dataclass_field_names(instance_or_type: Any) -> set[str]:
    try:
        return {field.name for field in fields(instance_or_type)}
    except (TypeError, ValueError):
        return set()


def _field_name(instance_or_type: Any, canonical: str) -> str | None:
    available = _dataclass_field_names(instance_or_type)
    for candidate in _FIELD_ALIASES[canonical]:
        if candidate in available:
            return candidate
    return None


def _read_value(source: Any, names: Iterable[str], default: Any = None) -> Any:
    if isinstance(source, Mapping):
        for name in names:
            if name in source:
                return source[name]
        return default
    for name in names:
        if hasattr(source, name):
            return getattr(source, name)
    return default


def input_snapshot(inputs: Any) -> dict[str, Any]:
    """Return a canonical, presentation-oriented view of a physics input object."""

    snapshot: dict[str, Any] = {}
    defaults = {
        "density": DEFAULT_DENSITY_KG_M3,
        "viscosity": DEFAULT_DYNAMIC_VISCOSITY_PA_S,
        "diameter": DEFAULT_DIAMETER_M,
        "velocity": DEFAULT_VELOCITY_M_S,
        "model": "normal_flat_plate",
        "theta": DEFAULT_PLATE_ANGLE_DEG,
        "beta": DEFAULT_OUTLET_ANGLE_DEG,
        "retention": DEFAULT_RETENTION_COEFFICIENT,
        "split": DEFAULT_SPLIT_FRACTION,
    }
    for canonical, aliases in _FIELD_ALIASES.items():
        snapshot[canonical] = _read_value(inputs, aliases, defaults.get(canonical))
    snapshot["model"] = canonical_model(snapshot["model"])
    return snapshot


def _vector2(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if value is None:
        return default
    if hasattr(value, "x") and hasattr(value, "y"):
        return float(value.x), float(value.y)
    if isinstance(value, Mapping):
        return float(value.get("x", default[0])), float(value.get("y", default[1]))
    try:
        return float(value[0]), float(value[1])
    except (IndexError, KeyError, TypeError, ValueError):
        return default


def result_snapshot(result: Any, inputs: Any | None = None) -> dict[str, Any]:
    """Return result values under stable names for all UI surfaces."""

    inp = input_snapshot(inputs) if inputs is not None else {}
    result_values: dict[str, Any] = {}
    for canonical, aliases in _RESULT_ALIASES.items():
        result_values[canonical] = _read_value(result, aliases)

    fx = float(result_values["fx"] or 0.0)
    fy = float(result_values["fy"] or 0.0)
    fr_raw = result_values["fr"]
    fr = float(math.hypot(fx, fy) if fr_raw is None else fr_raw)
    angle_raw = result_values["force_angle"]
    angle = (
        math.degrees(math.atan2(fy, fx))
        if angle_raw is None and fr > 0.0
        else float(angle_raw or 0.0)
    )
    velocity = float(inp.get("velocity", 0.0) or 0.0)
    vin = _vector2(result_values["vin"], (velocity, 0.0))
    vout = _vector2(result_values["vout"], (0.0, 0.0))
    outlet_vectors = result_values["outlet_vectors"]
    outlet_mass_fractions = result_values["outlet_mass_fractions"]
    if outlet_vectors is None:
        outlet_vectors_list: list[tuple[float, float]] = [vout]
    else:
        outlet_vectors_list = [
            _vector2(getattr(vector, "velocity_m_s", vector), (0.0, 0.0))
            for vector in outlet_vectors
        ]
        if outlet_mass_fractions is None:
            outlet_mass_fractions = [
                float(getattr(vector, "mass_fraction", 0.0)) for vector in outlet_vectors
            ]

    return {
        "fx": fx,
        "fy": fy,
        "fr": fr,
        "force_angle": angle,
        "area": float(result_values["area"] or 0.0),
        "flow_rate": float(result_values["flow_rate"] or 0.0),
        "mass_flow_rate": float(result_values["mass_flow_rate"] or 0.0),
        "reynolds_number": float(result_values["reynolds_number"] or 0.0),
        "outlet_speed": float(result_values["outlet_speed"] or math.hypot(*vout)),
        "vin": vin,
        "vout": vout,
        "outlet_vectors": outlet_vectors_list,
        "outlet_mass_fractions": outlet_mass_fractions,
    }


def _coerce_enum(enum_type: Any, raw_value: str) -> Any:
    for member in enum_type:
        if canonical_model(member) == canonical_model(raw_value):
            return member
        if str(getattr(member, "name", "")).lower() == raw_value.lower():
            return member
    try:
        return enum_type(raw_value)
    except (TypeError, ValueError) as exc:
        choices = ", ".join(str(member.value) for member in enum_type)
        raise ValueError(
            f"Unsupported {enum_type.__name__} value {raw_value!r}. Choose one of: {choices}."
        ) from exc


def build_inputs_from_values(values: Mapping[str, Any]) -> Any:
    """Construct ``JetInputs`` without coupling the UI to display-only state."""

    from src.models import ImpactModel, JetInputs

    payload: dict[str, Any] = {}
    for canonical in (
        "density",
        "viscosity",
        "diameter",
        "velocity",
        "theta",
        "beta",
        "retention",
        "split",
    ):
        name = _field_name(JetInputs, canonical)
        if name is not None and canonical in values:
            payload[name] = values[canonical]

    model_name = _field_name(JetInputs, "model")
    if model_name is not None:
        payload[model_name] = _coerce_enum(
            ImpactModel, str(values.get("model", "normal_flat_plate"))
        )

    # Some versions keep preset/unit preference with the input dataclass, while
    # others correctly treat them as display state. Populate them only if present.
    for canonical, enum_name in (("fluid_preset", "FluidPreset"), ("unit_system", "UnitSystem")):
        field_name = _field_name(JetInputs, canonical)
        if field_name and canonical in values:
            from src import models

            enum_type = getattr(models, enum_name, None)
            payload[field_name] = (
                _coerce_enum(enum_type, str(values[canonical]))
                if enum_type is not None
                else values[canonical]
            )

    return JetInputs(**payload)


def replace_input(inputs: Any, canonical: str, value: Any) -> Any:
    """Create a new input object with one canonical engineering parameter changed."""

    field_name = _field_name(inputs, canonical)
    if field_name is None:
        raise ValueError(f"The physics input model has no field for {canonical!r}.")
    return replace(inputs, **{field_name: value})


_CASE_STATE_KEYS = (
    "jf_model",
    "jf_fluid_preset",
    "jf_density",
    "jf_viscosity",
    "jf_diameter",
    "jf_velocity",
    "jf_theta",
    "jf_beta",
    "jf_retention",
    "jf_split",
)


def _apply_inputs_to_session(inputs: JetInputs) -> None:
    """Copy one immutable case into widget state and synchronize paired controls."""

    st.session_state.jf_model = inputs.model.value
    st.session_state.jf_model_widget = inputs.model.value
    st.session_state.jf_fluid_preset = inputs.fluid_preset.value
    st.session_state.jf_density = float(inputs.density)
    st.session_state.jf_viscosity = float(inputs.dynamic_viscosity)
    st.session_state.jf_diameter = float(inputs.diameter)
    st.session_state.jf_diameter_mm = 1000.0 * float(inputs.diameter)
    st.session_state.jf_velocity = float(inputs.velocity)
    st.session_state.jf_velocity_slider = float(inputs.velocity)
    st.session_state.jf_theta = float(inputs.plate_angle_deg)
    st.session_state.jf_beta = float(inputs.outlet_angle_deg)
    st.session_state.jf_retention = float(inputs.retention_coefficient)
    st.session_state.jf_split = float(inputs.split_fraction)
    st.session_state.jf_unit_system = "SI"


def _case_state_snapshot() -> dict[str, Any]:
    return {key: st.session_state[key] for key in _CASE_STATE_KEYS}


def initialize_session_state() -> None:
    """Initialize a fresh browser session to the exact Course Mode textbook case."""

    defaults: dict[str, Any] = {
        "jf_mode": AppMode.COURSE.value,
        "jf_previous_mode": AppMode.COURSE.value,
        "jf_presentation_view": False,
        "jf_show_calculation": False,
        "jf_unit_system": "SI",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if "jf_model" not in st.session_state:
        _apply_inputs_to_session(textbook_course_inputs())
    elif st.session_state.get("jf_model") not in MODEL_LABELS:
        saved_course = st.session_state.get("jf_course_case", {})
        st.session_state.jf_model = saved_course.get(
            "jf_model", ImpactModel.NORMAL_FLAT_PLATE.value
        )
    st.session_state.setdefault("jf_model_widget", st.session_state.jf_model)
    st.session_state.setdefault("jf_diameter_mm", 1000.0 * float(st.session_state.jf_diameter))
    st.session_state.setdefault("jf_velocity_slider", float(st.session_state.jf_velocity))
    st.session_state.setdefault("jf_course_case", _case_state_snapshot())


def _restore_case_state(snapshot: Mapping[str, Any]) -> None:
    for key in _CASE_STATE_KEYS:
        if key in snapshot:
            st.session_state[key] = snapshot[key]
    st.session_state.jf_diameter_mm = 1000.0 * float(st.session_state.jf_diameter)
    st.session_state.jf_velocity_slider = float(st.session_state.jf_velocity)
    st.session_state.jf_model_widget = st.session_state.jf_model


def _on_mode_change() -> None:
    new_mode = AppMode(st.session_state.jf_mode)
    previous_mode = AppMode(st.session_state.get("jf_previous_mode", AppMode.COURSE.value))
    if previous_mode is AppMode.COURSE:
        st.session_state.jf_course_case = _case_state_snapshot()
    if new_mode is AppMode.COURSE:
        _restore_case_state(st.session_state.get("jf_course_case", {}))
        st.session_state.jf_unit_system = "SI"
        if st.session_state.jf_model not in {model.value for model in COURSE_MODEL_LABELS}:
            st.session_state.jf_model = ImpactModel.NORMAL_FLAT_PLATE.value
        st.session_state.jf_model_widget = st.session_state.jf_model
        st.session_state.jf_retention = 1.0
        st.session_state.jf_split = 0.5
    st.session_state.jf_previous_mode = new_mode.value


def render_application_mode_selector() -> AppMode:
    """Render the global mode and presentation selectors in the shared sidebar frame."""

    initialize_session_state()
    mode_value = st.sidebar.segmented_control(
        "Application mode",
        options=[mode.value for mode in AppMode],
        key="jf_mode",
        required=True,
        width="stretch",
        persist_state="session",
        on_change=_on_mode_change,
        help="Course Mode is the focused MEC350 interface; Advanced Mode reveals supplementary models and diagnostics.",
    )
    mode = AppMode(mode_value or AppMode.COURSE.value)
    st.sidebar.caption(COURSE_MODE_EXPLANATION)
    st.sidebar.toggle(
        "Presentation View",
        key="jf_presentation_view",
        persist_state="session",
        help="Enlarges the schematic and primary results while hiding secondary controls.",
    )
    if mode is AppMode.ADVANCED:
        st.sidebar.info(ADVANCED_MODE_NOTICE, icon=":material/info:")
    with st.sidebar.expander("مساعدة عربية مختصرة", expanded=False):
        st.markdown(
            "**الوضع الدراسي** يعرض المدخلات الأساسية فقط. الاتجاه الموجب للمحور x هو "
            "اتجاه النفث الداخل، والمحور y الموجب إلى أعلى. النتائج Fx وFy وFR هي القوة "
            "التي يؤثر بها الماء على اللوح. جميع الحسابات في هذا الوضع بوحدات SI."
        )
    return mode


def render_presentation_styles() -> None:
    """Apply a small responsive presentation treatment when the user requests it."""

    if not st.session_state.get("jf_presentation_view", False):
        return
    _render_html("""
        <style>
        .jf-result-value { font-size: clamp(2rem, 4vw, 3.35rem) !important; }
        .jf-schematic-figure img { max-height: min(58vh, 610px) !important; }
        .jf-page-intro p { max-width: 62rem; }
        [data-testid="stSidebar"] [data-testid="stExpander"] { display: none; }
        </style>
        """)


def reset_to_default() -> None:
    """Reset the active engineering case without changing the selected interface mode."""

    _apply_inputs_to_session(textbook_course_inputs())
    st.session_state.jf_show_calculation = False
    st.session_state.jf_course_case = _case_state_snapshot()
    st.session_state.pop("jf_report_package", None)


def load_demonstration_case(preset: DemonstrationPreset | str) -> None:
    """Load one documented classroom preset into the active session."""

    _apply_inputs_to_session(demonstration_inputs(preset))
    st.session_state.pop("jf_report_package", None)
    if st.session_state.get("jf_mode") == AppMode.COURSE.value:
        st.session_state.jf_course_case = _case_state_snapshot()


def _diameter_slider_changed() -> None:
    st.session_state.jf_diameter = float(st.session_state.jf_diameter_mm) / 1000.0


def _diameter_number_changed() -> None:
    st.session_state.jf_diameter_mm = 1000.0 * float(st.session_state.jf_diameter)


def _velocity_slider_changed() -> None:
    st.session_state.jf_velocity = float(st.session_state.jf_velocity_slider)


def _velocity_number_changed() -> None:
    st.session_state.jf_velocity_slider = float(st.session_state.jf_velocity)


def _apply_fluid_preset() -> None:
    selected = st.session_state.get("jf_fluid_preset", "custom")
    if selected in FLUID_PROPERTY_PRESETS and selected != "custom":
        properties = FLUID_PROPERTY_PRESETS[selected]
        st.session_state.jf_density = float(properties["density"])
        st.session_state.jf_viscosity = float(properties["dynamic_viscosity"])


def _model_changed() -> None:
    """Copy the model widget value into durable, page-independent case state."""

    st.session_state.jf_model = str(st.session_state.jf_model_widget)


def render_sidebar_controls(
    *, include_model: bool = True, panel: Any | None = None
) -> tuple[Any, str]:
    """Render mode-aware controls in a supplied panel or in the sidebar."""

    initialize_session_state()
    mode = AppMode(st.session_state.get("jf_mode", AppMode.COURSE.value))
    course_mode = mode is AppMode.COURSE
    presentation = bool(st.session_state.get("jf_presentation_view", False))
    controls = st.sidebar if panel is None else panel

    controls.markdown("### Active engineering case")
    if course_mode:
        controls.caption(
            "Fluid: Water. The default density of 1000 kg/m³ is a convenient textbook value; density remains editable."
        )
    elif not presentation:
        controls.selectbox(
            "Fluid preset",
            options=["textbook_water", "water", "air", "custom"],
            format_func=lambda key: str(FLUID_PROPERTY_PRESETS[key]["name"]),
            key="jf_fluid_preset",
            persist_state="session",
            on_change=_apply_fluid_preset,
            help="Presets are approximate starting values. Custom values remain available.",
        )

    density_max = 1500.0 if course_mode else MAX_DENSITY_KG_M3
    controls.number_input(
        "Fluid density, ρ (kg/m³)",
        min_value=max(1.0, MIN_DENSITY_KG_M3),
        max_value=density_max,
        step=1.0,
        format="%.4g",
        key="jf_density",
        persist_state="session",
        help="Mass per unit volume. The Course Mode demonstration uses 1000 kg/m³ for water.",
    )
    if not course_mode and not presentation:
        controls.number_input(
            "Dynamic viscosity, μ (Pa·s)",
            min_value=MIN_DYNAMIC_VISCOSITY_PA_S,
            max_value=MAX_DYNAMIC_VISCOSITY_PA_S,
            step=1.0e-5,
            format="%.6g",
            key="jf_viscosity",
            persist_state="session",
            help="Used only for the Reynolds-number diagnostic; it does not modify the momentum force.",
        )

    diameter_max_mm = 100.0 if course_mode else 1000.0 * MAX_DIAMETER_M
    controls.slider(
        "Jet diameter, d (mm)",
        min_value=1000.0 * MIN_DIAMETER_M,
        max_value=diameter_max_mm,
        step=0.1,
        key="jf_diameter_mm",
        persist_state="session",
        on_change=_diameter_slider_changed,
        help="Circular inlet diameter. The value is converted to metres before A = πd²/4 is evaluated.",
    )
    controls.caption(f"Internal SI value: {float(st.session_state.jf_diameter):.6g} m")
    if not presentation:
        controls.number_input(
            "Jet diameter, d (m) - precise entry",
            min_value=MIN_DIAMETER_M,
            max_value=MAX_DIAMETER_M if not course_mode else 0.1,
            step=0.0001,
            format="%.4f",
            key="jf_diameter",
            persist_state="session",
            on_change=_diameter_number_changed,
            help="Precise SI entry synchronized with the millimetre slider above.",
        )

    velocity_max = 50.0 if course_mode else MAX_VELOCITY_M_S
    controls.slider(
        "Inlet jet velocity, V (m/s)",
        min_value=MIN_VELOCITY_M_S,
        max_value=velocity_max,
        step=0.5,
        key="jf_velocity_slider",
        persist_state="session",
        on_change=_velocity_slider_changed,
        help="Uniform section-average inlet velocity directed along positive x.",
    )
    if not presentation:
        controls.number_input(
            "Inlet jet velocity, V (m/s) - precise entry",
            min_value=MIN_VELOCITY_M_S,
            max_value=velocity_max,
            step=0.1,
            format="%.2f",
            key="jf_velocity",
            persist_state="session",
            on_change=_velocity_number_changed,
            help="Precise velocity entry synchronized with the slider above.",
        )

    if include_model:
        model_options = (
            [model.value for model in COURSE_MODEL_LABELS] if course_mode else list(MODEL_LABELS)
        )
        course_labels = {model.value: label for model, label in COURSE_MODEL_LABELS.items()}
        current_model = str(st.session_state.get("jf_model", model_options[0]))
        if current_model not in model_options:
            current_model = model_options[0]
            st.session_state.jf_model = current_model
        if st.session_state.get("jf_model_widget") not in model_options:
            st.session_state.jf_model_widget = current_model
        selected_model = controls.segmented_control(
            "Impact model",
            options=model_options,
            format_func=lambda key: course_labels.get(key, MODEL_LABELS[key]),
            key="jf_model_widget",
            persist_state="session",
            required=True,
            width="stretch",
            on_change=_model_changed,
            help="Selects the documented outlet-velocity construction used by the momentum balance.",
        )
        model_key = str(selected_model or current_model)

    else:
        model_key = str(st.session_state.jf_model)
    if model_key == ImpactModel.SPLIT_FLOW.value:
        controls.slider(
            "Plate tangent angle, θ (degrees)",
            min_value=MIN_ANGLE_DEG,
            max_value=MAX_ANGLE_DEG,
            step=1.0,
            key="jf_theta",
            persist_state="session",
            help="First outlet direction measured counterclockwise from positive x; the second is opposite.",
        )
    elif model_key != ImpactModel.NORMAL_FLAT_PLATE.value:
        controls.slider(
            "Outlet direction angle, β (degrees)",
            min_value=MIN_ANGLE_DEG,
            max_value=MAX_ANGLE_DEG,
            step=1.0,
            key="jf_beta",
            persist_state="session",
            help="Outlet velocity direction measured counterclockwise from positive x.",
        )
    else:
        controls.caption(
            "Normal impact fixes equal sideways outlet streams; their net outlet momentum is zero."
        )

    if not course_mode and model_key != ImpactModel.NORMAL_FLAT_PLATE.value:
        controls.slider(
            "Velocity retention coefficient, k",
            min_value=MIN_RETENTION_COEFFICIENT,
            max_value=MAX_RETENTION_COEFFICIENT,
            step=0.01,
            key="jf_retention",
            persist_state="session",
            help="User-selected outlet-speed assumption. It is not calculated by CFD or Reynolds number.",
        )
    if not course_mode and model_key == ImpactModel.SPLIT_FLOW.value:
        controls.slider(
            "Forward outlet mass fraction, s",
            min_value=MIN_SPLIT_FRACTION,
            max_value=MAX_SPLIT_FRACTION,
            step=0.01,
            key="jf_split",
            persist_state="session",
            help="The opposite branch carries 1 - s, so outlet and inlet mass flow remain equal.",
        )

    if course_mode:
        st.session_state.jf_unit_system = "SI"
        unit_system = "SI"
    elif presentation:
        unit_system = str(st.session_state.get("jf_unit_system", "SI"))
    else:
        selected_units = controls.segmented_control(
            "Result display units",
            options=["SI", "US"],
            key="jf_unit_system",
            persist_state="session",
            required=True,
            help="The solver remains in SI; Advanced Mode may convert displayed values.",
        )
        unit_system = str(selected_units or "SI")

    with controls.container(horizontal=True, gap="small"):
        st.button(
            "Reset to Default",
            icon=":material/restart_alt:",
            on_click=reset_to_default,
            width="stretch",
            help="Restore the exact 1000 kg/m³, 20 mm, 10 m/s normal-plate case.",
        )
        st.button(
            "Load Demonstration Case",
            icon=":material/science:",
            on_click=load_demonstration_case,
            args=(DemonstrationPreset.NINETY_DEGREE_DEFLECTION,),
            width="stretch",
            help="Load the documented ideal 90-degree deflection example.",
        )

    density = float(st.session_state.jf_density)
    fluid_preset = str(st.session_state.jf_fluid_preset)
    if course_mode:
        fluid_preset = (
            FluidPreset.TEXTBOOK_WATER.value
            if density == COURSE_TEXTBOOK_DENSITY_KG_M3
            else FluidPreset.CUSTOM.value
        )
    values = {
        "density": density,
        "viscosity": st.session_state.jf_viscosity,
        "diameter": st.session_state.jf_diameter,
        "velocity": st.session_state.jf_velocity,
        "model": model_key,
        "theta": (
            90.0 if model_key == ImpactModel.NORMAL_FLAT_PLATE.value else st.session_state.jf_theta
        ),
        "beta": st.session_state.jf_beta,
        "retention": (
            1.0
            if course_mode or model_key == ImpactModel.NORMAL_FLAT_PLATE.value
            else st.session_state.jf_retention
        ),
        "split": 0.5 if course_mode else st.session_state.jf_split,
        "fluid_preset": fluid_preset,
        "unit_system": "us_customary" if unit_system == "US" else "si",
    }
    return build_inputs_from_values(values), unit_system


def simulate_safely(inputs: Any) -> Any | None:
    """Run the public physics API while shielding users from implementation traces."""

    try:
        from src.calculations import simulate

        return simulate(inputs)
    except (TypeError, ValueError) as exc:
        st.error(f"The current inputs are not valid: {exc}", icon=":material/error:")
    except Exception:  # pragma: no cover - depends on external/runtime failures.
        LOGGER.exception("Simulation failed")
        st.error(
            "The simulation could not be completed. Check the input ranges and application dependencies, then try again.",
            icon=":material/error:",
        )
    return None


def display_value(value_si: float, quantity: str, unit_system: str) -> tuple[float, str]:
    """Convert a scalar from internal SI to the selected display system."""

    system = UnitSystem.US_CUSTOMARY if unit_system.upper().startswith("US") else UnitSystem.SI
    return float(convert_from_si(value_si, quantity, system)), display_unit(quantity, system)


def format_engineering(value: float, *, sig: int = 4) -> str:
    """Use the project's centralized significant-figure formatter."""

    return format_number(value, significant_figures=sig)


def _direction_for_component(value: float, axis: str) -> tuple[str, str]:
    if abs(value) < 1.0e-10:
        return "—", "No resolved component"
    if axis == "x":
        return ("→", "Acts in +x, with the incoming jet") if value > 0 else ("←", "Acts in −x")
    return ("↑", "Acts upward in +y") if value > 0 else ("↓", "Acts downward in −y")


def render_force_cards(
    result: Any,
    inputs: Any,
    unit_system: str = "SI",
    *,
    course_mode: bool = False,
) -> None:
    """Render the three primary force outputs as interpretation-rich cards."""

    values = result_snapshot(result, inputs)
    force_unit = display_value(1.0, "force", unit_system)[1]
    factor = display_value(1.0, "force", unit_system)[0]
    fx_arrow, fx_note = _direction_for_component(values["fx"], "x")
    fy_arrow, fy_note = _direction_for_component(values["fy"], "y")
    if values["fr"] < 1.0e-10:
        fr_arrow, fr_note = "—", "No net reaction force"
    else:
        directions = ("→", "↗", "↑", "↖", "←", "↙", "↓", "↘")
        normalized_angle = values["force_angle"] % 360.0
        fr_arrow = directions[int((normalized_angle + 22.5) // 45.0) % 8]
        fr_note = f"Resultant at {values['force_angle']:.1f}° from +x"

    cards = (
        (
            "F<sub>x</sub>",
            "Fx - Horizontal force on the plate",
            values["fx"] * factor,
            fx_arrow,
            fx_note,
            "#22d3ee",
        ),
        (
            "F<sub>y</sub>",
            "Fy - Vertical force on the plate",
            values["fy"] * factor,
            fy_arrow,
            fy_note,
            "#fbbf24",
        ),
        (
            "F<sub>R</sub>",
            "FR - Resultant force on the plate",
            values["fr"] * factor,
            fr_arrow,
            fr_note,
            "#fb7185",
        ),
    )
    columns = st.columns(3)
    for column, (symbol, name, value, arrow, note, color) in zip(columns, cards, strict=True):
        with column:
            value_text = f"{value:.2f}" if course_mode else format_engineering(value)
            _render_html(
                f"""
                <div class="jf-result" style="--metric-color:{color}" aria-label="{escape(name)}: {value_text} {escape(force_unit)}. {escape(note)}">
                  <div class="jf-direction" aria-hidden="true">{arrow}</div>
                  <div class="jf-result-symbol">{symbol}</div>
                  <div class="jf-result-name">{escape(name)}</div>
                  <div class="jf-result-value">{value_text} <span>{escape(force_unit)}</span></div>
                  <div class="jf-result-note">{escape(note)}</div>
                </div>
                """,
            )


def _superscript_exponent(exponent: int) -> str:
    return str(exponent).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))


def _course_metric_value(value: float, quantity: str) -> str:
    if quantity in {"area", "flow_rate"} and value != 0.0:
        exponent = math.floor(math.log10(abs(value)))
        coefficient = value / (10.0**exponent)
        return f"{coefficient:.4g} × 10{_superscript_exponent(exponent)}"
    return f"{value:.4g}"


def render_supporting_metrics(
    result: Any,
    inputs: Any,
    unit_system: str = "SI",
    *,
    course_mode: bool = False,
) -> None:
    """Render area, flow, mass flow, Reynolds number, exit speed, and angle."""

    values = result_snapshot(result, inputs)
    course_entries = (
        ("Jet area, A", "area", values["area"]),
        ("Flow rate, Q", "flow_rate", values["flow_rate"]),
        ("Mass flow, ṁ", "mass_flow_rate", values["mass_flow_rate"]),
    )
    advanced_entries = (
        *course_entries,
        ("Reynolds number, Re", None, values["reynolds_number"]),
        ("Outlet speed", "velocity", values["outlet_speed"]),
        ("Force direction", "angle", values["force_angle"]),
    )
    entries = course_entries if course_mode else advanced_entries
    columns = st.columns(3)
    for index, (label, quantity, raw_value) in enumerate(entries):
        if quantity == "angle" and values["fr"] <= ZERO_TOLERANCE:
            columns[index % 3].metric(label, "Not applicable — zero resultant")
            if index == 2:
                columns = st.columns(3)
            continue
        if quantity is None:
            display, unit = raw_value, "dimensionless"
        elif quantity == "angle":
            display, unit = raw_value, "° from +x"
        else:
            display, unit = display_value(raw_value, quantity, unit_system)
        formatted = (
            _course_metric_value(display, quantity)
            if course_mode and quantity is not None
            else format_engineering(display)
        )
        columns[index % 3].metric(label, f"{formatted} {unit}", border=True)
        if index == 2:
            columns = st.columns(3)


def render_case_summary(inputs: Any) -> None:
    """Render the active model and compact input tags."""

    values = input_snapshot(inputs)
    model = values["model"]
    details = [
        f"ρ = {format_engineering(float(values['density']))} kg/m³",
        f"d = {format_engineering(float(values['diameter']))} m",
        f"V = {format_engineering(float(values['velocity']))} m/s",
    ]
    if model != "normal_flat_plate":
        details.append(f"k = {float(values['retention']):.2f}")
    if model in {"deflected_jet", "curved_vane"}:
        details.append(f"β = {float(values['beta']):.1f}°")
    if model == "split_flow":
        details.extend((f"θ = {float(values['theta']):.1f}°", f"s = {float(values['split']):.2f}"))

    tags = "".join(f'<span class="jf-tag">{escape(detail)}</span>' for detail in details)
    _render_html(
        f"""
        <div class="jf-card">
          <div class="jf-card-kicker">Active physical model</div>
          <h3>{escape(MODEL_LABELS.get(model, model.replace('_', ' ').title()))}</h3>
          <p>{escape(MODEL_DESCRIPTIONS.get(model, 'Control-volume momentum analysis.'))}</p>
          <div style="margin-top:.75rem">{tags}</div>
        </div>
        """,
    )


def render_assumptions(*, expanded: bool = False) -> None:
    """Explain each modeling assumption in a readable expander."""

    with st.expander("Model assumptions and their engineering meaning", expanded=expanded):
        for title, explanation in ASSUMPTIONS:
            st.markdown(f"**{title}.** {explanation}")
        st.info(
            "Reynolds number characterizes the inlet jet. It does not automatically modify the momentum-force result.",
            icon=":material/info:",
        )


def schematic_controls(prefix: str = "schematic") -> dict[str, bool]:
    """Render animation and overlay controls with reset behavior."""

    defaults = {"play": True, "cv": True, "labels": True, "vectors": True}

    def reset() -> None:
        for suffix, value in defaults.items():
            st.session_state[f"{prefix}_{suffix}"] = value

    for suffix, value in defaults.items():
        st.session_state.setdefault(f"{prefix}_{suffix}", value)

    if hasattr(st, "container"):
        controls = st.container(horizontal=True, gap="small")
        controls.button(
            "Reset view",
            icon=":material/restart_alt:",
            key=f"{prefix}_reset",
            on_click=reset,
            width="content",
        )
        controls.toggle(
            "Play animation",
            key=f"{prefix}_play",
            help="Play or pause the lightweight illustrative particle motion.",
        )
        controls.toggle("Control volume", key=f"{prefix}_cv")
        controls.toggle("Labels", key=f"{prefix}_labels")
        controls.toggle("Vectors", key=f"{prefix}_vectors")
    else:  # pragma: no cover - lightweight unit-test compatibility.
        cols = st.columns(5)
        cols[0].button("Reset view", key=f"{prefix}_reset", on_click=reset, width="content")
        cols[1].toggle("Play animation", key=f"{prefix}_play")
        cols[2].toggle("Control volume", key=f"{prefix}_cv")
        cols[3].toggle("Labels", key=f"{prefix}_labels")
        cols[4].toggle("Vectors", key=f"{prefix}_vectors")
    return {
        "play": bool(st.session_state[f"{prefix}_play"]),
        "cv": bool(st.session_state[f"{prefix}_cv"]),
        "labels": bool(st.session_state[f"{prefix}_labels"]),
        "forces": bool(st.session_state[f"{prefix}_vectors"]),
        "velocities": bool(st.session_state[f"{prefix}_vectors"]),
    }


def _point_at(cx: float, cy: float, length: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return cx + length * math.cos(angle), cy - length * math.sin(angle)


def _rectangle_exit_point(
    cx: float,
    cy: float,
    angle_deg: float,
    bounds: tuple[float, float, float, float],
    *,
    margin: float = 18.0,
) -> tuple[float, float]:
    """Return a point just beyond the first rectangle boundary crossed by a ray."""

    angle = math.radians(angle_deg)
    dx, dy = math.cos(angle), -math.sin(angle)
    left, top, right, bottom = bounds
    distances: list[float] = []
    if dx > 0.0:
        distances.append((right - cx) / dx)
    elif dx < 0.0:
        distances.append((left - cx) / dx)
    if dy > 0.0:
        distances.append((bottom - cy) / dy)
    elif dy < 0.0:
        distances.append((top - cy) / dy)
    distance = min(item for item in distances if item >= 0.0) + margin
    return cx + distance * dx, cy + distance * dy


def _svg_line(x1: float, y1: float, x2: float, y2: float, css_class: str, marker: str = "") -> str:
    marker_attribute = f' marker-end="url(#{marker})"' if marker else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'class="{css_class}"{marker_attribute}/>'
    )


def _angle_arc(cx: float, cy: float, angle_deg: float, symbol: str) -> str:
    if abs(angle_deg) < 1.0:
        return ""
    radius = 43.0
    end_x, end_y = _point_at(cx, cy, radius, angle_deg)
    sweep = 0 if angle_deg > 0 else 1
    large = 1 if abs(angle_deg) > 180 else 0
    label_x, label_y = _point_at(cx, cy, radius + 18.0, angle_deg / 2.0)
    return (
        f'<path d="M {cx + radius:.1f} {cy:.1f} A {radius} {radius} 0 {large} {sweep} '
        f'{end_x:.1f} {end_y:.1f}" class="angle-arc"/>'
        f'<text x="{label_x:.1f}" y="{label_y:.1f}" class="angle-label">{escape(symbol)} = {angle_deg:.0f}°</text>'
    )


def _particle_markup(
    path: str, count: int, duration: float, *, radius: float = 4.0, opacity: float = 1.0
) -> str:
    particles: list[str] = []
    for index in range(count):
        begin = -(duration * index / max(count, 1))
        particles.append(
            f'<circle r="{radius:.1f}" class="particle" opacity="{opacity:.2f}">'
            f'<animateMotion dur="{duration:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" path="{path}"/>'
            "</circle>"
        )
    return "".join(particles)


def build_schematic_html(
    inputs: Any, result: Any, options: Mapping[str, bool] | None = None
) -> str:
    """Build a directionally accurate, lightweight animated engineering SVG."""

    inp = input_snapshot(inputs)
    res = result_snapshot(result, inputs)
    model = inp["model"]
    opts = {"play": True, "cv": True, "labels": True, "forces": True, "velocities": True}
    if options:
        opts.update(options)

    width, height = 920.0, 440.0
    cx, cy = 465.0, 220.0
    velocity = max(float(inp["velocity"]), 0.0)
    k = max(0.0, min(float(inp["retention"]), 1.0))
    beta = float(inp["beta"])
    theta = float(inp["theta"])
    split = max(0.0, min(float(inp["split"]), 1.0))
    duration = max(0.7, 3.2 - min(velocity, 100.0) * 0.022)
    incoming_path = f"M 127 {cy:.1f} L {cx:.1f} {cy:.1f}"
    control_volume_bounds = (185.0, 76.0, 740.0, 364.0)

    outlet_paths: list[tuple[str, float, float]] = []
    geometry = ""
    angle_markup = ""
    if model == "normal_flat_plate":
        plate_a = _point_at(cx, cy, 128, 90)
        plate_b = _point_at(cx, cy, 128, -90)
        geometry += _svg_line(*plate_a, *plate_b, "plate")
        for direction in (90.0, -90.0):
            end = _rectangle_exit_point(cx, cy, direction, control_volume_bounds)
            path = f"M {cx:.1f} {cy:.1f} Q {cx + 23:.1f} {cy:.1f} {end[0]:.1f} {end[1]:.1f}"
            outlet_paths.append((path, 0.5, max(0.15, k)))
    elif model == "split_flow":
        plate_a = _point_at(cx, cy, 150, theta)
        plate_b = _point_at(cx, cy, 150, theta + 180.0)
        geometry += _svg_line(*plate_a, *plate_b, "plate")
        for direction, fraction in ((theta, split), (theta + 180.0, 1.0 - split)):
            end = _rectangle_exit_point(cx, cy, direction, control_volume_bounds)
            path = f"M {cx:.1f} {cy:.1f} L {end[0]:.1f} {end[1]:.1f}"
            outlet_paths.append((path, fraction, max(0.15, k)))
        angle_markup = _angle_arc(cx, cy, theta, "θ")
    else:
        end = _rectangle_exit_point(cx, cy, beta, control_volume_bounds)
        if model == "curved_vane":
            control_x, control_y = cx + 72.0, cy
            path = (
                f"M {cx:.1f} {cy:.1f} Q {control_x:.1f} {control_y:.1f} {end[0]:.1f} {end[1]:.1f}"
            )
            offset_a = _point_at(cx + 15.0, cy, 102, beta)
            geometry += (
                f'<path d="M {cx - 8:.1f} {cy + 22:.1f} Q {control_x:.1f} {control_y + 28:.1f} '
                f'{offset_a[0]:.1f} {offset_a[1] + 18:.1f}" class="vane"/>'
            )
        else:
            path = f"M {cx:.1f} {cy:.1f} L {end[0]:.1f} {end[1]:.1f}"
            plate_a = _point_at(cx, cy, 132, beta)
            plate_b = _point_at(cx, cy, 60, beta + 180.0)
            normal_shift = _point_at(0.0, 0.0, 24.0, beta - 90.0)
            geometry += _svg_line(
                plate_a[0] + normal_shift[0],
                plate_a[1] + normal_shift[1],
                plate_b[0] + normal_shift[0],
                plate_b[1] + normal_shift[1],
                "plate",
            )
        outlet_paths.append((path, 1.0, max(0.15, k)))
        angle_markup = _angle_arc(cx, cy, beta, "β")

    active_outlets = [
        (path, fraction, speed_ratio)
        for path, fraction, speed_ratio in outlet_paths
        if fraction > ZERO_TOLERANCE and velocity > ZERO_TOLERANCE and k > ZERO_TOLERANCE
    ]
    stream_markup = (
        f'<path d="{incoming_path}" class="jet inlet"/>' if velocity > ZERO_TOLERANCE else ""
    )
    stream_markup += "".join(
        f'<path d="{path}" class="jet outlet" style="stroke-width:{max(3.0, 11.0 * fraction):.1f}px;opacity:{0.35 + 0.65 * speed_ratio:.2f}"/>'
        for path, fraction, speed_ratio in active_outlets
    )
    if opts["play"] and velocity > 0.0:
        stream_markup += _particle_markup(incoming_path, 9, duration)
        for path, fraction, speed_ratio in outlet_paths:
            if fraction > 0.005 and k > 0.0:
                count = max(2, round(8 * fraction))
                stream_markup += _particle_markup(
                    path,
                    count,
                    duration / max(speed_ratio, 0.2),
                    radius=max(2.5, 4.5 * math.sqrt(fraction)),
                    opacity=0.9,
                )

    cv_markup = ""
    if opts["cv"]:
        cv_markup = (
            '<rect x="185" y="76" width="555" height="288" rx="24" class="control-volume"/>'
            '<text x="201" y="101" class="cv-label">CONTROL VOLUME</text>'
        )

    axis_markup = (
        '<g class="axes">'
        + _svg_line(72, 375, 147, 375, "axis x-axis", "axis-arrow")
        + _svg_line(72, 375, 72, 305, "axis y-axis", "axis-arrow")
        + '<text x="154" y="380" class="axis-text">+x</text><text x="61" y="297" class="axis-text">+y</text>'
        + "</g>"
    )

    velocity_markup = ""
    if opts["velocities"]:
        max_speed = max(velocity, k * velocity, 1.0e-12)
        vin_length = 125.0 * velocity / max_speed if velocity > 0.0 else 0.0
        if vin_length > 0.0:
            velocity_markup += _svg_line(
                220, cy - 37, 220 + vin_length, cy - 37, "vector velocity", "velocity-arrow"
            )
        if opts["labels"] and vin_length > 0.0:
            velocity_markup += f'<text x="220" y="{cy - 49:.1f}" class="vector-label velocity-label">V<tspan baseline-shift="sub">in</tspan> = {velocity:.3g} m/s</text>'
        for index, (_path, fraction, _ratio) in enumerate(outlet_paths):
            if fraction <= ZERO_TOLERANCE:
                continue
            if model == "normal_flat_plate":
                direction = 90.0 if index == 0 else -90.0
                branch_speed = (
                    math.hypot(*res["outlet_vectors"][index])
                    if index < len(res["outlet_vectors"])
                    else k * velocity
                )
            elif model == "split_flow":
                direction = theta if index == 0 else theta + 180.0
                branch_speed = k * velocity
            else:
                direction = beta
                branch_speed = k * velocity
            length = 125.0 * branch_speed / max_speed if branch_speed > 0.0 else 0.0
            if length <= 0:
                continue
            start = _point_at(cx, cy, 24.0, direction)
            end = _point_at(*start, length, direction)
            velocity_markup += _svg_line(
                *start, *end, "vector velocity outlet-vector", "velocity-arrow"
            )
            if opts["labels"]:
                suffix = str(index + 1) if len(outlet_paths) > 1 else "out"
                label_point = _point_at(*start, length * 0.58, direction)
                velocity_markup += f'<text x="{label_point[0] + 7:.1f}" y="{label_point[1] - 8:.1f}" class="vector-label velocity-label">V<tspan baseline-shift="sub">{suffix}</tspan></text>'
        if opts["labels"]:
            velocity_markup += angle_markup

    force_markup = ""
    if opts["forces"] and res["fr"] > 1.0e-12:
        fx, fy, fr = res["fx"], res["fy"], res["fr"]
        scale = 112.0 / fr
        origin_x, origin_y = cx + 10.0, cy + 12.0
        if abs(fx) > 1.0e-12:
            force_markup += _svg_line(
                origin_x,
                origin_y,
                origin_x + fx * scale,
                origin_y,
                "vector force fx",
                "force-x-arrow",
            )
            if opts["labels"]:
                force_markup += f'<text x="{origin_x + fx * scale * .52:.1f}" y="{origin_y + 22:.1f}" class="vector-label fx-label">F<tspan baseline-shift="sub">x</tspan></text>'
        if abs(fy) > 1.0e-12:
            force_markup += _svg_line(
                origin_x,
                origin_y,
                origin_x,
                origin_y - fy * scale,
                "vector force fy",
                "force-y-arrow",
            )
            if opts["labels"]:
                force_markup += f'<text x="{origin_x + 9:.1f}" y="{origin_y - fy * scale * .55:.1f}" class="vector-label fy-label">F<tspan baseline-shift="sub">y</tspan></text>'
        force_markup += _svg_line(
            origin_x,
            origin_y,
            origin_x + fx * scale,
            origin_y - fy * scale,
            "vector force resultant",
            "force-r-arrow",
        )
        if opts["labels"]:
            force_markup += f'<text x="{origin_x + fx * scale * .62 + 8:.1f}" y="{origin_y - fy * scale * .62 - 8:.1f}" class="vector-label fr-label">F<tspan baseline-shift="sub">R</tspan></text>'

    outlet_labels = ""
    if opts["labels"] and model == "split_flow":
        for index, (direction, fraction) in enumerate(
            ((theta, split), (theta + 180.0, 1.0 - split))
        ):
            point = _point_at(cx, cy, 184.0, direction)
            outlet_labels += f'<text x="{point[0] + 7:.1f}" y="{point[1] - 7:.1f}" class="stream-label">Outlet {index + 1}: {fraction:.0%} ṁ</text>'

    if velocity <= ZERO_TOLERANCE:
        status = "No particle motion — zero inlet flow"
    elif not opts["play"]:
        status = "Particle motion paused"
    else:
        status = "Illustrative particle motion playing"
    schematic = f"""
    <!doctype html>
    <html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
    <style>
      * {{ box-sizing:border-box; }}
      body {{ margin:0; background:transparent; color:#dbeafe; font-family:Arial,Helvetica,sans-serif; }}
      .frame {{ position:relative; border:1px solid rgba(113,177,214,.22); border-radius:18px; overflow:hidden;
        background:radial-gradient(circle at 58% 42%,rgba(34,211,238,.08),transparent 33%),linear-gradient(145deg,#0b2135,#071726); }}
      svg {{ width:100%; height:auto; display:block; }}
      .grid {{ stroke:rgba(130,177,209,.07); stroke-width:1; }}
      .control-volume {{ fill:rgba(34,211,238,.025); stroke:#38bdf8; stroke-width:2; stroke-dasharray:10 8; }}
      .cv-label {{ fill:#7dd3fc; font-size:11px; letter-spacing:2px; font-weight:700; }}
      .nozzle {{ fill:#52687b; stroke:#b5c8d7; stroke-width:2; }}
      .nozzle-inner {{ fill:#081927; }}
      .plate,.vane {{ stroke:#e2e8f0; stroke-width:12; stroke-linecap:round; fill:none; filter:url(#plate-shadow); }}
      .jet {{ fill:none; stroke:#22d3ee; stroke-linecap:round; filter:url(#water-glow); }}
      .inlet {{ stroke-width:13; }} .outlet {{ stroke:#38bdf8; }}
      .particle {{ fill:#e0faff; filter:url(#water-glow); }}
      .axis {{ stroke:#7f9caf; stroke-width:2; }} .axis-text {{ fill:#9fb6c9; font-size:13px; font-weight:650; }}
      .vector {{ stroke-width:3; stroke-linecap:round; }} .velocity {{ stroke:#67e8f9; }}
      .force.fx {{ stroke:#22d3ee; }} .force.fy {{ stroke:#fbbf24; }} .force.resultant {{ stroke:#fb7185; stroke-width:4; }}
      .vector-label,.stream-label,.angle-label {{ paint-order:stroke; stroke:#071726; stroke-width:5px; stroke-linejoin:round; font-weight:750; font-size:13px; }}
      .velocity-label {{ fill:#a5f3fc; }} .fx-label {{ fill:#67e8f9; }} .fy-label {{ fill:#fde68a; }} .fr-label {{ fill:#fda4af; }}
      .stream-label {{ fill:#c6e6f4; font-size:12px; }}
      .angle-arc {{ fill:none; stroke:#c4b5fd; stroke-width:2; stroke-dasharray:4 4; }} .angle-label {{ fill:#ddd6fe; font-size:12px; }}
      .impact {{ fill:#fb7185; stroke:#ffe4e6; stroke-width:2; }}
      .footer {{ position:absolute; left:14px; bottom:11px; padding:5px 9px; border-radius:99px; background:rgba(3,14,25,.72); color:#91a9bb; font-size:11px; letter-spacing:.02em; }}
      @media (prefers-reduced-motion:reduce) {{ .particle {{ display:none; }} }}
    </style></head><body>
    <div class="frame" role="img" aria-label="Control-volume schematic for {escape(MODEL_LABELS.get(model, model))}. Positive x follows the inlet jet and positive y is upward.">
      <svg viewBox="0 0 {width:.0f} {height:.0f}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid" width="38" height="38" patternUnits="userSpaceOnUse"><path d="M38 0H0V38" fill="none" class="grid"/></pattern>
          <filter id="water-glow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          <filter id="plate-shadow" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="5" dy="7" stdDeviation="6" flood-color="#000" flood-opacity=".42"/></filter>
          <marker id="axis-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L0 6L7 3Z" fill="#7f9caf"/></marker>
          <marker id="velocity-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto"><path d="M0 0L0 7L8 3.5Z" fill="#67e8f9"/></marker>
          <marker id="force-x-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto"><path d="M0 0L0 7L8 3.5Z" fill="#22d3ee"/></marker>
          <marker id="force-y-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto"><path d="M0 0L0 7L8 3.5Z" fill="#fbbf24"/></marker>
          <marker id="force-r-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto"><path d="M0 0L0 7L8 3.5Z" fill="#fb7185"/></marker>
        </defs>
        <rect width="920" height="440" fill="url(#grid)"/>
        {cv_markup}
        {axis_markup}
        <path d="M42 {cy - 37:.1f} L127 {cy - 22:.1f} L127 {cy + 22:.1f} L42 {cy + 37:.1f} Z" class="nozzle"/>
        <rect x="43" y="{cy - 22:.1f}" width="73" height="44" rx="4" class="nozzle-inner"/>
        {stream_markup}
        {geometry}
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" class="impact"/>
        {velocity_markup}
        {force_markup}
        {outlet_labels}
      </svg>
      <div class="footer">{escape(status)} · engineering visualization, not CFD</div>
    </div></body></html>
    """
    return schematic


def build_schematic_svg(
    inputs: Any,
    result: Any,
    options: Mapping[str, bool] | None = None,
) -> str:
    """Return the schematic as a self-contained animated SVG image asset."""

    document = build_schematic_html(inputs, result, options)
    style_start = document.find("<style>")
    style_end = document.find("</style>", style_start)
    svg_start = document.find("<svg ")
    svg_end = document.find("</svg>", svg_start)
    if min(style_start, style_end, svg_start, svg_end) < 0:
        raise ValueError("The schematic document could not be converted to SVG.")
    css = document[style_start + len("<style>") : style_end]
    svg = document[svg_start : svg_end + len("</svg>")]
    opening_end = svg.find(">")
    background = (
        '<rect width="920" height="440" rx="18" fill="#071726"/>'
        '<rect x="1" y="1" width="918" height="438" rx="17" fill="none" '
        'stroke="rgba(113,177,214,.35)" stroke-width="2"/>'
    )
    return (
        svg[: opening_end + 1]
        + f"<style><![CDATA[{css}]]></style>"
        + background
        + svg[opening_end + 1 :]
    )


def render_engineering_schematic(
    inputs: Any,
    result: Any,
    *,
    prefix: str = "schematic",
    show_controls: bool = True,
    height: int = 470,
) -> None:
    """Render the control-volume schematic with a responsive height cap."""

    options = schematic_controls(prefix) if show_controls else None
    svg = build_schematic_svg(inputs, result, options)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    height_cap = max(260, min(int(height), 720))
    model_label = MODEL_LABELS.get(input_snapshot(inputs)["model"], "selected impact model")
    velocity = float(input_snapshot(inputs)["velocity"])
    if velocity <= ZERO_TOLERANCE:
        status = "No particle motion — zero inlet flow"
    elif options is None or options.get("play", True):
        status = "Illustrative particle motion playing"
    else:
        status = "Illustrative particle motion paused"
    _render_html(
        f"""
        <figure class="jf-schematic-figure">
          <img src="data:image/svg+xml;base64,{encoded}"
               alt="Control-volume schematic for {escape(model_label)}"
               style="max-height:{height_cap}px" />
          <figcaption>{status}. Arrow lengths are scaled for visibility; numerical values are shown in the result cards. Static SVG content remains visible if animation is unavailable.</figcaption>
        </figure>
        """,
    )


def render_vector_interpretation(result: Any, inputs: Any) -> None:
    """Provide a screen-reader-friendly interpretation of the displayed vectors."""

    values = result_snapshot(result, inputs)
    inlet = values["vin"]
    outlet = values["vout"]
    fx_direction = (
        "positive x" if values["fx"] > 0 else "negative x" if values["fx"] < 0 else "no x component"
    )
    fy_direction = (
        "positive y" if values["fy"] > 0 else "negative y" if values["fy"] < 0 else "no y component"
    )
    st.caption(
        "Vector interpretation: "
        f"Vin = ({inlet[0]:.4g}, {inlet[1]:.4g}) m/s; mass-weighted Vout = "
        f"({outlet[0]:.4g}, {outlet[1]:.4g}) m/s. The water-on-plate reaction has "
        f"{fx_direction} and {fy_direction}. Positive x follows the incoming jet; positive y is upward."
    )


def plotly_layout(
    fig: go.Figure, *, height: int = 470, legend_title: str | None = None
) -> go.Figure:
    """Apply the shared scientific chart theme."""

    fig.update_layout(
        height=height,
        margin=dict(l=45, r=25, t=55, b=45),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,24,39,.72)",
        font=dict(color="#dcecf7", family="Arial, Helvetica, sans-serif", size=13),
        title=dict(font=dict(size=19, color="#f1f9ff"), x=0.02, xanchor="left"),
        legend=dict(
            title_text=legend_title,
            bgcolor="rgba(5,19,32,.72)",
            bordercolor="rgba(148,197,231,.18)",
            borderwidth=1,
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hoverlabel=dict(bgcolor="#0b2135", bordercolor="#38bdf8", font_color="#eaf7ff"),
        hovermode="x unified",
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="rgba(148,197,231,.10)", zerolinecolor="rgba(148,197,231,.23)"
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148,197,231,.10)",
        zeroline=True,
        zerolinecolor="rgba(226,232,240,.30)",
    )
    return fig


@st.cache_data(show_spinner=False, max_entries=32)
def compute_parameter_sweep(
    inputs: Any,
    variable: str,
    start: float,
    stop: float,
    points: int,
) -> pd.DataFrame:
    """Evaluate a deterministic sweep through the single public physics model."""

    from src.calculations import parameter_sweep

    if points < 2 or points > 501:
        raise ValueError("Sweep points must be between 2 and 501.")
    canonical = {
        "velocity": "velocity",
        "diameter": "diameter",
        "beta": "outlet_angle_deg",
        "theta": "plate_angle_deg",
        "retention": "retention_coefficient",
        "split": "split_fraction",
    }.get(variable, variable)
    frame = parameter_sweep(
        inputs,
        canonical,
        start=float(start),
        stop=float(stop),
        points=int(points),
    )
    return frame.rename(columns={canonical: "input"})


def study_axis(variable: str, unit_system: str) -> tuple[str, str, float]:
    """Return label, unit, and conversion multiplier for a sweep axis."""

    if variable == "velocity":
        factor, unit = display_value(1.0, "velocity", unit_system)
        return "Inlet jet speed, V", unit, factor
    if variable == "diameter":
        factor, unit = display_value(1.0, "diameter", unit_system)
        return "Jet diameter, d", unit, factor
    if variable == "beta":
        return "Outlet angle, β", "°", 1.0
    if variable == "theta":
        return "Plate tangent angle, θ", "°", 1.0
    if variable == "retention":
        return "Velocity retention, k", "–", 1.0
    if variable == "split":
        return "Forward outlet mass fraction, s", "–", 1.0
    return variable.replace("_", " ").title(), "", 1.0


def create_parameter_chart(
    frame: pd.DataFrame,
    variable: str,
    unit_system: str = "SI",
    *,
    title: str | None = None,
) -> go.Figure:
    """Plot Fx, Fy, and FR with complete engineering hover data."""

    x_label, x_unit, x_factor = study_axis(variable, unit_system)
    force_factor, force_unit = display_value(1.0, "force", unit_system)
    flow_factor, flow_unit = display_value(1.0, "flow_rate", unit_system)
    mass_factor, mass_unit = display_value(1.0, "mass_flow_rate", unit_system)
    x = frame["input"].to_numpy(dtype=float) * x_factor
    custom = np.column_stack(
        (
            frame["Fx_N"] * force_factor,
            frame["Fy_N"] * force_factor,
            frame["FR_N"] * force_factor,
            frame["Q_m3_s"] * flow_factor,
            frame["mdot_kg_s"] * mass_factor,
        )
    )
    fig = go.Figure()
    series = (
        ("Fx — horizontal", "Fx_N", "#22d3ee", "solid"),
        ("Fy — vertical", "Fy_N", "#fbbf24", "dash"),
        ("FR — resultant", "FR_N", "#fb7185", "solid"),
    )
    hover = (
        f"{escape(x_label)}: %{{x:.4g}} {x_unit}<br>"
        f"Fx: %{{customdata[0]:.5g}} {force_unit}<br>"
        f"Fy: %{{customdata[1]:.5g}} {force_unit}<br>"
        f"FR: %{{customdata[2]:.5g}} {force_unit}<br>"
        f"Q: %{{customdata[3]:.5g}} {flow_unit}<br>"
        f"ṁ: %{{customdata[4]:.5g}} {mass_unit}<extra>%{{fullData.name}}</extra>"
    )
    for name, column, color, dash in series:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=frame[column] * force_factor,
                mode="lines",
                name=name,
                customdata=custom,
                hovertemplate=hover,
                line=dict(color=color, width=3, dash=dash),
            )
        )
    fig.update_layout(
        title=title or f"Force response to {x_label.lower()}",
        xaxis_title=f"{x_label} ({x_unit})" if x_unit else x_label,
        yaxis_title=f"Force on plate ({force_unit})",
    )
    return plotly_layout(fig, height=500, legend_title="Force output")


def create_force_component_chart(result: Any, inputs: Any, unit_system: str = "SI") -> go.Figure:
    """Create a signed component and resultant comparison."""

    res = result_snapshot(result, inputs)
    factor, unit = display_value(1.0, "force", unit_system)
    values = [res["fx"] * factor, res["fy"] * factor, res["fr"] * factor]
    colors = ["#22d3ee", "#fbbf24", "#fb7185"]
    fig = go.Figure(
        go.Bar(
            x=["Fx — horizontal", "Fy — vertical", "FR — resultant"],
            y=values,
            marker_color=colors,
            text=[format_engineering(value) for value in values],
            textposition="outside",
            hovertemplate=f"%{{x}}<br>%{{y:.5g}} {unit}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Force component comparison", yaxis_title=f"Force on plate ({unit})", showlegend=False
    )
    return plotly_layout(fig, height=410)


def create_ideal_nonideal_chart(
    inputs: Any, unit_system: str = "SI"
) -> tuple[go.Figure, pd.DataFrame]:
    """Compare the selected retained-speed case against k = 1."""

    from src.calculations import simulate

    selected = simulate(inputs)
    ideal_inputs = replace_input(inputs, "retention", 1.0)
    ideal = simulate(ideal_inputs)
    selected_values = result_snapshot(selected, inputs)
    ideal_values = result_snapshot(ideal, ideal_inputs)
    factor, unit = display_value(1.0, "force", unit_system)
    frame = pd.DataFrame(
        {
            "component": ["Fx", "Fy", "FR"],
            "Ideal, k = 1": [ideal_values["fx"], ideal_values["fy"], ideal_values["fr"]],
            "Selected k": [selected_values["fx"], selected_values["fy"], selected_values["fr"]],
        }
    )
    fig = go.Figure()
    for label, color in (("Ideal, k = 1", "#38bdf8"), ("Selected k", "#fb7185")):
        fig.add_trace(
            go.Bar(
                name=label,
                x=frame["component"],
                y=frame[label] * factor,
                marker_color=color,
                hovertemplate=f"%{{x}}<br>%{{y:.5g}} {unit}<extra>{label}</extra>",
            )
        )
    fig.update_layout(
        title="Ideal versus prescribed non-ideal outlet speed",
        barmode="group",
        xaxis_title="Force component",
        yaxis_title=f"Force on plate ({unit})",
    )
    return plotly_layout(fig, height=440), frame


def _add_vector(fig: go.Figure, x: float, y: float, name: str, color: str, unit: str) -> None:
    fig.add_trace(
        go.Scatter(
            x=[0.0, x],
            y=[0.0, y],
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=4),
            marker=dict(size=[1, 8], color=color),
            hovertemplate=f"{name}<br>x: %{{x:.5g}} {unit}<br>y: %{{y:.5g}} {unit}<extra></extra>",
        )
    )
    fig.add_annotation(
        x=x,
        y=y,
        ax=0.0,
        ay=0.0,
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.2,
        arrowwidth=2.6,
        arrowcolor=color,
        text="",
    )


def create_momentum_vector_chart(result: Any, inputs: Any, unit_system: str = "SI") -> go.Figure:
    """Show inlet flux, effective outlet flux, and their plate-reaction difference."""

    res = result_snapshot(result, inputs)
    mdot = res["mass_flow_rate"]
    factor, unit = display_value(1.0, "force", unit_system)
    inlet = (mdot * res["vin"][0] * factor, mdot * res["vin"][1] * factor)
    outlet = (mdot * res["vout"][0] * factor, mdot * res["vout"][1] * factor)
    reaction = (res["fx"] * factor, res["fy"] * factor)
    fig = go.Figure()
    _add_vector(fig, *inlet, "Inlet momentum flux, ṁVin", "#38bdf8", unit)
    _add_vector(fig, *outlet, "Net outlet momentum flux, ΣṁVout", "#a78bfa", unit)
    _add_vector(fig, *reaction, "Plate reaction, Fplate", "#fb7185", unit)
    span = max(*(abs(value) for vector in (inlet, outlet, reaction) for value in vector), 1.0)
    fig.update_layout(
        title="Momentum vector balance",
        xaxis_title=f"x component ({unit})",
        yaxis_title=f"y component ({unit})",
        hovermode="closest",
    )
    fig.update_xaxes(range=[-1.25 * span, 1.25 * span], scaleanchor="y", scaleratio=1)
    fig.update_yaxes(range=[-1.25 * span, 1.25 * span])
    plotly_layout(fig, height=520, legend_title="Vector")
    fig.update_layout(
        hovermode="closest",
        margin=dict(l=45, r=25, t=65, b=105),
        legend=dict(yanchor="top", y=-0.16, xanchor="center", x=0.5),
    )
    return fig


def dataframe_to_csv_bytes(
    frame: pd.DataFrame, *, metadata: Mapping[str, Any] | None = None
) -> bytes:
    """Create a rectangular, round-trip-safe CSV with optional repeated metadata columns."""

    export_frame = frame.copy()
    if metadata:
        for key, value in metadata.items():
            normalized = "".join(
                character if character.isalnum() else "_" for character in str(key)
            )
            export_frame[f"metadata_{normalized.strip('_').lower()}"] = str(value)
    csv_text = export_frame.to_csv(index=False, float_format="%.17g")
    if not isinstance(csv_text, str):
        raise TypeError("Pandas did not return CSV text for the in-memory export.")
    return csv_text.encode("utf-8")


def inputs_as_json(inputs: Any) -> str:
    """Serialize canonical input values for debugging or report metadata."""

    return json.dumps(input_snapshot(inputs), default=str, indent=2)


__all__ = [
    "ASSUMPTIONS",
    "MODEL_DESCRIPTIONS",
    "MODEL_LABELS",
    "MODEL_SHORT_LABELS",
    "build_inputs_from_values",
    "build_schematic_html",
    "build_schematic_svg",
    "canonical_model",
    "compute_parameter_sweep",
    "configure_page",
    "create_force_component_chart",
    "create_ideal_nonideal_chart",
    "create_momentum_vector_chart",
    "create_parameter_chart",
    "dataframe_to_csv_bytes",
    "display_value",
    "format_engineering",
    "initialize_session_state",
    "input_snapshot",
    "inputs_as_json",
    "load_demonstration_case",
    "render_application_mode_selector",
    "render_assumptions",
    "render_brand_bar",
    "render_case_summary",
    "render_disclaimer",
    "render_engineering_schematic",
    "render_force_cards",
    "render_page_intro",
    "render_presentation_styles",
    "render_sidebar_controls",
    "render_supporting_metrics",
    "render_vector_interpretation",
    "replace_input",
    "reset_to_default",
    "result_snapshot",
    "schematic_controls",
    "simulate_safely",
    "study_axis",
]

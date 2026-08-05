# AGENTS.md - JetForce Studio Contributor Guide

## Purpose and scope

JetForce Studio is an MEC350 educational simulator for the steady force exerted by a free jet on a stationary flat plate or curved vane. Preserve physical transparency, reproducibility, and student-readable terminology before adding features.

Use this exact public disclaimer wherever the model scope is summarized:

> This application uses a numerical control-volume momentum model.  
> The flow visualization is illustrative and is not a full CFD simulation.

These instructions apply to the entire repository.

## Architecture

- `src/models.py`: public enums and typed input/result records.
- `src/calculations.py`: authoritative physics and parameter sweeps.
- `src/validation.py`: user-input constraints and hand-calculation/comparison support.
- `src/visualizations.py`: Plotly/SVG schematics and plots; visuals must agree with calculated vectors.
- `src/reporting.py`: flat and structured serialization plus printable report formats.
- `src/course.py`: Course/Advanced interface modes, Course defaults, presentation presets, and release copy; it does not implement physics.
- `src/constants.py`: property presets, limits, units, and shared defaults.
- `src/utils.py`: numerical formatting and unit conversions.
- `app.py`: shared Streamlit configuration, four-destination Course navigation, and six stable page routes.
- `app_pages/`: Streamlit presentation pages only; do not duplicate governing equations there.
- `tests/`: unit, analytical regression, input-validation, and export tests.
- `docs/`: derivations, assumptions, verification cases, and course-deliverable guidance.

Keep dependencies directed from UI/export code toward the public `src` model/calculation interfaces. Keep Streamlit imports out of physics modules so calculations remain testable without launching the app.

The router registers these stable page routes, in this order:

1. `app_pages/1_Simulator.py` - **Simulator** (default)
2. `app_pages/2_Hand_Calculation.py` - **Calculation and Results** in Course Mode; **Hand Calculation** in Advanced Mode
3. `app_pages/3_Results_and_Charts.py` - **Results and Charts** (hidden from the Course top menu but retained for deep links; visible in Advanced Mode)
4. `app_pages/4_Theory_and_Assumptions.py` - **Theory and Assumptions**
5. `app_pages/5_Report_and_Export.py` - **Report and Export**
6. `app_pages/6_About_Project.py` - **About the Project** (compact Course sidebar link; visible in Advanced navigation)

Course Mode exposes exactly four primary top destinations: **Simulator**,
**Calculation and Results**, **Theory and Assumptions**, and **Report and
Export**. Keep the hidden legacy routes registered with `st.Page(...,
visibility="hidden")` so existing bookmarks remain safe.

`st.set_page_config` must be called through the shared entry point before any widget or navigation command. Individual page scripts must not call it again. Keep page links and documentation synchronized with the `app_pages/` paths above.
Do not place source pages in the legacy `pages/` directory; JetForce Studio declares navigation explicitly with `st.navigation` so the public order and labels remain deterministic.
Keep `app_pages/` files as direct scripts. Initialize shared per-visitor session state from the entry-point flow before the selected page runs, use stable prefixed widget keys, and use session-scoped widget persistence only for values intended to survive page changes.

## Interface modes and release behavior

- **Course Mode** is the fresh-session default. Its textbook case is water at `rho = 1000 kg/m3`, `d = 0.02 m`, `V = 10 m/s`, normal flat-plate impact, and SI display units. It exposes one visible control per active physical quantity, the main MEC350 calculations, and velocity/diameter studies.
- Classroom demonstrations use one selector and one **Load Selected Case** action. Keep **Reset to Default** separate; do not restore duplicate preset buttons.
- **Advanced Mode** reveals supplementary fluids, viscosity and Reynolds-number context, velocity retention, split flow, curved-vane comparisons, alternate display units, and extended studies. These additions must not change the governing momentum balance.
- Preserve the legacy calculation-layer defaults and public schemas when adding Course-specific defaults. Course presentation policy belongs in `src/course.py` and UI state, not in hard-coded physics results.
- Switching modes must not silently overwrite the saved Course case. Reset and demonstration controls must load deterministic inputs and invalidate stale export packages.
- Presentation View may enlarge primary results and hide secondary controls, but it must not change inputs, calculations, units, or exported values.
- Do not create separate Advanced-only source pages; mode-specific content belongs conditionally inside the same six stable routes.

## Governing physics and sign convention

- Positive x is the direction of the incoming horizontal jet; positive y is upward.
- `Vin = (V, 0)`.
- `A = pi d^2/4`, `Q = AV`, and `mdot = rho Q`.
- For the fluid control volume, `sum(F_on_fluid) = sum(mdot Vout) - sum(mdot Vin)`.
- The primary application result is the opposite reaction, force exerted by the water on the plate:
  `Fplate = mdot Vin - sum(mdot_j Vout,j)`.
- `Fx` and `Fy` are the Cartesian components of `Fplate`; `FR = hypot(Fx, Fy)`.
- A single outlet uses `Vout = kV(cos(beta), sin(beta))`, with the angle measured counterclockwise from positive x and `0 <= k <= 1`.
- Split flow uses masses `s mdot` and `(1-s) mdot` along opposite plate tangents. Their sum must equal inlet mass flow.
- Reynolds number `rho V d / mu` is diagnostic only. Never introduce a Reynolds-number force correction without a documented, validated model requirement.

Read `docs/equations.md` before changing physics. Critical executable equations belong in `src/calculations.py`; critical constraints belong in `src/validation.py` and `src/models.py`.

## Non-negotiable integrity rules

- Never describe the animation, schematic, or momentum model as CFD.
- Never invent experimental data, CFD contours, pressure values, empirical corrections, calibration, references, or agreement claims.
- Do not call analytical equation checks experimental validation.
- Do not mix force on fluid with force on plate. Label the reported reaction explicitly.
- Keep SI units internally. Centralize conversions and show units at the UI/export boundary.
- Do not add arbitrary multipliers or hard-code validation outputs.
- Report division-by-zero cases such as percentage difference from a zero reference as not applicable.

## Compatibility and change discipline

- Preserve existing public names, enum values, dataclass fields, file formats, and function signatures whenever practical. Add a compatibility wrapper before breaking a page, saved case, or downstream notebook.
- When the governing physics changes, update the derivation, assumptions, analytical values, export labels, tests, and UI explanation in the same change.
- Add or update meaningful regression tests for every physics change. Do not delete or weaken a test merely to obtain a passing run.
- Keep report schemas deterministic and backward-compatible. Add metadata fields rather than renaming established input/result keys without a migration.
- Use deterministic calculations. No random engineering results or hidden cached user state.
- Keep error messages actionable and user-facing; log technical context without exposing a raw traceback in the normal interface.

## Local commands

Set up and run:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows, activate with `.venv\Scripts\activate` (Command Prompt) or `.venv\Scripts\Activate.ps1` (PowerShell).

Before completing any change, run from the repository root:

```bash
pytest
ruff check .
black --check .
python -c "import src; import src.reporting; print('Imports OK')"
```

For calculation or validation changes, also run:

```bash
pytest --cov=src --cov-report=term-missing
mypy src
```

For UI changes, start a headless smoke test:

```bash
python -m streamlit run app.py --server.headless true
```

Open the health URL or review the terminal, exercise the changed page with default and boundary inputs, then stop the server. Review all warnings; fix or explain them rather than suppressing them blindly.

## Test minimums

Maintain tests for area, flow, mass flow, Reynolds number, outlet vectors, all impact models, resultant and direction, degree conversion, zero velocity, valid extremes, invalid inputs, mass conservation, analytical regression cases, parameter sweeps, CSV/JSON/HTML export, and PDF generation when ReportLab is available. Compare unrounded floating-point values with defensible tolerances.

Every completed task must leave the full suite green, lint and format checks clean, imports working, and documentation consistent with implementation. If a check cannot run, state the exact command, reason, and unverified risk in the handoff.

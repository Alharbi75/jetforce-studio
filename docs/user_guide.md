# JetForce Studio User Guide

## What the application does

JetForce Studio estimates the steady force exerted by a water or gas jet on a stationary plate or vane using a two-dimensional control-volume momentum balance. It reports the horizontal component `Fx`, vertical component `Fy`, and resultant `FR`, plus relevant flow quantities.

> This application uses a numerical control-volume momentum model.  
> The flow visualization is illustrative and is not a full CFD simulation.

The model does not predict a spatial pressure or velocity field, turbulence, splashing, jet breakup, or transient loading.

## Start the application

From the project folder, create an environment, install dependencies, and run:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

Streamlit normally opens `http://localhost:8501` in the default browser. Course Mode keeps four primary destinations in the top navigation:

1. **Simulator**
2. **Calculation and Results**
3. **Theory and Assumptions**
4. **Report and Export**

**About the Project** is available as a compact secondary sidebar link.
Advanced Mode also exposes the dedicated **Results and Charts** route and the
About route in the top navigation. All six source routes remain registered so
existing bookmarks continue to work.

The sidebar contains the global **Application mode** and **Presentation View** selectors. The active engineering-case controls appear in the Simulator workspace and, where needed, in the sidebar on the other pages.

## Application modes

### Course Mode

Every fresh browser session starts in **Course Mode** with the MEC350 textbook case:

- Water with `rho = 1000 kg/m3`
- `d = 0.02 m` (20 mm)
- `V = 10 m/s`
- Normal Flat Plate
- SI display units

Course Mode includes only the main control-volume momentum concepts required for the MEC350 project. Its impact choices are **Normal Flat Plate** and **Deflected Jet / Curved Plate Comparison**. For the comparison model, set the outlet direction `beta`; Course Mode fixes the ideal retained-speed value at `k = 1`.

### Advanced Mode

Advanced Mode adds supplementary fluids, viscosity and Reynolds-number context, prescribed outlet-speed retention `k`, split flow, a separate curved-vane choice, alternate display units, and additional studies. These options use the same governing momentum equation; they do not turn the application into CFD or add an empirical force correction.

Switching back to Course Mode restores the saved Course case and SI display policy. **Reset to Default** restores the textbook normal-plate inputs. It does not alter the selected application mode.

### Presentation View

Presentation View enlarges the schematic and primary force results and hides selected secondary controls. It changes presentation only: inputs, physics, units, and exported values remain unchanged.

For a short demonstration, choose one case from **Demonstration case** and
select **Load Selected Case**:

- **Normal Plate** loads the textbook case.
- **Double Velocity** changes the normal case from 10 to 20 m/s. Because `F = rho A V^2`, the force becomes four times larger when density and diameter remain fixed.
- **90-Degree Deflection** loads an ideal outlet at `beta = 90 degrees`.

## 1. Simulator

### Choose the active case

In Course Mode:

1. Enter water density `rho` in kg/m3.
2. Set jet diameter `d`; the millimetre control is synchronized with the internal metre value.
3. Set inlet speed `V` in m/s.
4. Choose the impact model.
5. For the deflected-jet/curved-plate comparison, set `beta` counterclockwise from positive x.

Exactly zero inlet speed is valid. If a positive speed is too small for its momentum scale to be represented reliably in binary64 arithmetic, the app requests zero or a larger value rather than displaying a false zero force. Invalid inputs are not silently clipped.

Advanced Mode additionally exposes:

- `mu`, dynamic viscosity in Pa s, for the Reynolds diagnostic only;
- `k`, retained outlet speed divided by inlet speed, with `0 <= k <= 1`;
- `theta`, the split-flow plate tangent angle;
- `s`, the first split-outlet mass fraction, with `0 <= s <= 1`;
- SI or US customary display units.

All calculations remain in SI internally.

### Impact-model meaning

**Normal Flat Plate** represents a normal jet whose opposing sideways outlet momenta cancel. The ideal axial reaction is `rho A V^2`, and `Fy = 0`.

**Deflected Jet / Curved Plate Comparison** uses one ideal section-average outlet vector at angle `beta`. A deflected free jet and a curved guide are compared through this same vector construction; the application does not solve their detailed spatial flow fields.

In Advanced Mode, **Split Flow** assigns fractions `s` and `1-s` to opposite plate tangents. The fractions always sum to the inlet mass flow. The Advanced **Curved Vane** option uses the same single-outlet vector foundation as a deflected jet and adds no empirical multiplier.

### Read the results

- `Fx - Horizontal reaction force`: positive means the water pushes the plate in positive x.
- `Fy - Vertical reaction force`: positive means upward; negative means downward.
- `FR - Resultant force`: the nonnegative magnitude `sqrt(Fx^2 + Fy^2)`.
- Force direction: the angle of `(Fx, Fy)` measured counterclockwise from positive x; it is not applicable when the resultant is zero.

The displayed result is always the **force exerted by the water on the plate**. The force exerted by the plate on the control-volume fluid is equal and opposite.

Course supporting quantities are jet area `A`, volumetric flow rate `Q`, and mass flow rate `mdot`. Advanced Mode may also show outlet and Reynolds-number diagnostics. Reynolds number characterizes the inlet flow regime only; it does not modify force automatically.

### Use the schematic

The schematic uses the same coordinates and outlet-angle convention as the calculation. Use its controls to show or hide labels, the control volume, velocity vectors, and force vectors, and to play or pause the illustrative particles. Arrow lengths may be scaled for readability; use the vector labels and result cards for numerical magnitudes.

Select **Show Calculation** to display the main equations and current numerical substitution on the Simulator page.

## 2. Calculation and Results

Open **Calculation and Results** to follow the active case through given values, assumptions, area, flow rate, mass flow, inlet/outlet vectors, momentum balance, `Fx`, `Fy`, `FR`, and the final comparison. Advanced Mode labels this route **Hand Calculation**.

Choose **Standard rounded calculation** for presentation values or **More numerical precision** to inspect additional digits. The underlying calculation does not change.

A near-zero difference is expected because the displayed hand calculation and simulator implement the same documented control-volume equation. The **Independent Closed-Form Check** separately evaluates textbook formulas for normal impact, ideal 90-degree deflection, and ideal 180-degree reversal and reports expected value, simulator value, absolute difference, and PASS or CHECK. This is **analytical verification**, not experimental validation.

### Supporting charts from Calculation and Results

In Course Mode, select **Open charts and parameter studies** from **Calculation
and Results**. This opens the bookmark-safe supporting Results and Charts route,
which is intentionally omitted from the four-item primary navigation. Course
Mode provides one-parameter studies for inlet velocity and jet diameter in SI
units:

1. Select **Force versus inlet velocity** or **Force versus jet diameter**.
2. Choose the start, stop, and number of study points.
3. Review signed `Fx`, signed `Fy`, and resultant `FR`.
4. Download the exact visible table as CSV.

Only the selected variable changes. For ideal normal impact, force is proportional to both `V^2` and `d^2`.

Advanced Mode adds applicable angle, split-fraction, and retention studies, plus ideal/non-ideal and momentum-vector views. A selected `k` remains an input assumption; it is not calculated from experiment, CFD, or Reynolds number.

## 3. Theory and Assumptions

Use **Theory and Assumptions** to review the control-volume boundary, coordinate convention, mass and momentum equations, model-specific outlet construction, assumptions, and limitations. Course Mode emphasizes the normal and ideal deflected cases. Advanced Mode reveals split flow, velocity retention, and Reynolds-number context.

## 4. Report and Export

The **Report and Export** page prepares artifacts in memory:

- CSV for a flat, machine-readable case record;
- JSON for a structured record with inputs, results, metadata, assumptions, and units;
- printable HTML for browser review or printing to PDF;
- PDF when ReportLab is available and generation succeeds.
- a printable one-page presentation summary containing the active inputs,
  control-volume schematic, momentum equation, primary results, flow
  quantities, force-versus-velocity chart, assumptions, interpretation, and
  explicit not-CFD limitation.

Course reports can include both velocity and diameter studies, their exact data, and print-ready figures. Review the preview and identity fields, add a case-specific discussion and conclusion, and select **Generate Export Package**. If a format fails, correct the stated problem and select **Retry Report Generation**.

Changing the case or report fields makes an existing package stale and hides its downloads until it is regenerated. Course and Advanced filenames identify their interface mode and generation date.

Select **Download One-Page Presentation Summary** for the compact printable
artifact. Every export is generated in memory and is a draft. Verify inputs
and units, complete student details, insert only references you have personally
checked, and edit the discussion and conclusion before submission. If PDF
generation is unavailable, use printable HTML and the browser's **Print > Save
as PDF** feature.

## Secondary destination: About the Project

**About the Project** explains Course and Advanced modes, academic scope,
limitations, software structure, privacy, responsible use, application version,
analytical-model revision, build commit when available, and page-generation
timestamp. A concise Arabic help section is available there and in the
sidebar; equations, symbols, and units retain their standard notation.

The application privacy statement is:

> This application does not request personal information and does not store visitor-entered engineering values in a database.

The application implements no visitor login, file upload, payment, API key, database, advertising, or behavioral tracking. Engineering inputs remain in the visitor's temporary Streamlit session, and requested exports are generated in memory. Session state is per browser session and is lost when the session ends or the server restarts. A hosting platform may still process technical data required to deliver the service; consult that platform's policy for details.

## Reproduce the baseline analytical check

With the default Course case:

- `rho = 1000 kg/m3`
- `d = 0.02 m`
- `V = 10 m/s`
- Normal Flat Plate

the unrounded expected values are `Fx = 31.4159265 N`, `Fy = 0 N`, and `FR = 31.4159265 N`. The primary cards display `31.42 N` subject to their configured presentation precision.

## Troubleshooting

### `streamlit: command not found`

Activate the correct virtual environment and run `python -m pip install -r requirements.txt`. You can also start with `python -m streamlit run app.py`.

### The browser does not open

Copy the local URL printed in the terminal, normally `http://localhost:8501`. Check that port 8501 is not blocked or already in use.

### An input is rejected

Read the input-validation message for the exact allowed range. Ensure decimal separators and units match the field; do not enter millimetres into a field labeled metres.

### The force sign seems unexpected

Trace the outlet direction on the schematic. For example, an upward outlet requires the plate to push the fluid upward, so the water exerts a downward `Fy` reaction on the plate.

### PDF is unavailable

Install ReportLab with `python -m pip install reportlab` or download printable HTML and print it from a browser. Other export formats do not depend on ReportLab.

### The app fails after dependencies change

From an activated environment, rerun `python -m pip install -r requirements.txt`, then `pytest` and `ruff check .`. See the README for clean-environment and platform-specific launch options.

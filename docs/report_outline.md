# MEC350 Engineering Report Outline

Target length: 8-12 pages excluding references and appendices. Replace bracketed fields, verify every generated value, and follow the course citation style. The simulator can supply tables and figures, but the student remains responsible for interpretation, source verification, and final editing.

Use the application's scope statement verbatim where the method or visualization is introduced:

> This application uses a numerical control-volume momentum model.  
> The flow visualization is illustrative and is not a full CFD simulation.

## Cover Page (not counted)

Include the title **Interactive Numerical Modeling and Analysis of a Water Jet Striking a Flat or Curved Plate**, course `MEC350 Fluid Mechanics`, institution, instructor, submission date, and `[Student name - ID]` entries. Add the JetForce Studio subtitle only if permitted by the course template.

## Abstract (about 150-200 words)

State the physical problem, control-volume method, implemented impact models, primary outputs (`Fx`, `Fy`, `FR`), and analytical verification approach. Summarize only results actually generated for the submitted case. End with one restrained conclusion about the studied parameter effects; do not claim CFD or experimental agreement.

## 1. Introduction (about 0.5 page)

Introduce momentum exchange when a jet is stopped or redirected and explain why the resulting plate force matters in hydraulic machinery, propulsion, cleaning, or laboratory demonstrations. Cite suitable fluid-mechanics sources after the student verifies them. Distinguish an engineering control-volume model from a field solution.

## 2. Project Objectives (about 0.25 page)

List measurable objectives: formulate a two-dimensional momentum model, calculate horizontal and vertical reaction components and their resultant, compare the numerical result with a hand calculation, perform parametric studies, and communicate assumptions and limitations transparently.

## 3. Theory (about 0.75 page)

Explain steady linear momentum conservation in vector form. Define momentum flux and why changing velocity direction creates force even when speed is unchanged. Explain action-reaction: the balance first gives external force on the fluid, while the reported result is force by water on the plate. Reference `docs/equations.md` and cite a verified textbook source.

### 3.1 Control Volume

Show a labeled schematic crossing the undisturbed inlet jet and prescribed outlet stream(s). Mark positive x along the inlet and positive y upward, inlet/outlet normals, atmospheric boundaries, plate, and reaction components. State that the control volume encloses the impact region and that accumulation is zero under the steady assumption.

### 3.2 Governing Equations

Present `A = pi d^2 / 4`, `Q = AV`, `mdot = rho Q`, the vector momentum balance, `F_plate = mdot Vin - sum(mdot_j Vout,j)`, and `FR = sqrt(Fx^2 + Fy^2)`. Define every symbol and SI unit immediately below the equations.

## 4. Assumptions (about 0.5 page)

Summarize the assumptions most influential to the submitted case: steady incompressible flow, uniform section-average velocities, atmospheric free-jet boundaries, stationary rigid plate, negligible local weight and air drag, constant inlet diameter, two-dimensional flow, and prescribed velocity retention. Explain the likely consequence of each important simplification rather than giving only a list.

## 5. Geometry and Model Description (about 0.75 page)

Describe the selected normal-plate or ideal deflected-jet/curved-plate Course construction. If an Advanced Mode case is used, identify the single-deflected-jet, split-flow, or curved-vane construction and define the outlet angle convention, plate tangent angle, retention coefficient `k`, and split fraction `s` only where applicable. Include a geometry figure exported from the Simulator page and repeat the exact scope statement above.

## 6. Numerical Model Setup (about 0.75 page)

Explain the software architecture at a high level: `app.py` defines shared configuration and six-page navigation, `app_pages/` contains presentation code, and `src/` contains typed inputs, validation, physics, visualization helpers, and reporting. Note that the physics uses validated SI inputs, model-specific outlet vectors, a shared momentum calculation, double-precision arithmetic, and explicit degree-to-radian conversion. Describe error handling and the safe range of the parameter sweep. Do not reproduce source code unless a short excerpt materially clarifies the method.

### 6.1 Input Parameters

Provide a table containing only inputs active for the submitted case. A Course Mode table normally contains water, density, diameter, inlet velocity, selected model, and `beta` when required. Add viscosity, `k`, `theta`, `s`, alternate display units, or extended sweep settings only for an Advanced Mode case that actually uses them. Show units, distinguish editable properties from approximate presets, and add a one-sentence rationale for each study range.

## 7. Hand Calculation and Analytical Verification (about 0.75 page)

Use the phrase **analytical verification** for comparisons against closed-form momentum results. Include at least normal impact, unchanged velocity, 180-degree reversal, 90-degree deflection, zero velocity, and symmetric split cases as appropriate. Report expected values, simulator values, absolute differences, tolerance, and pass/fail status. Do not claim experimental validation without traceable measured data and uncertainties.

## 8. Results (about 1 page)

Present `Fx`, `Fy`, and `FR` prominently for the main case, followed by area, flow rate, and mass flow rate. Add outlet speed, Reynolds number, and other diagnostics only when they are relevant to an Advanced Mode analysis. Mark direction as not applicable when the resultant is zero. Use a consistent number of significant figures. Caption every figure and table with enough information to understand the case without searching the text.

### 8.1 Hand-Calculation Comparison

Show numerical substitution for area, flow rate, mass flow, outlet velocity components, `Fx`, `Fy`, and `FR`. Compare unrounded simulator and hand-calculation results using absolute difference and, where the reference is nonzero, percentage difference. Explain that near-zero differences are expected because both implement the same documented physical equation.

### 8.2 Results and Charts

Use the **Results and Charts** page to include plots that answer specific questions. The Course minimum is force versus velocity and force versus diameter. A model-dependent angle, split, or retention study may be added from Advanced Mode when it supports a stated objective. State which variables were held constant. For an ideal normal jet, connect `F proportional to V^2` and `F proportional to d^2` to the equation rather than describing the curve only.

## 9. Discussion (about 1 page)

Interpret component signs and relate them to the outlet direction. Explain how velocity, diameter, angle, split fraction, and retention affect outlet momentum and force. Discuss whether trends match limiting cases. Avoid treating the user-selected `k` as a measured prediction.

### 9.1 Sources of Difference

Separate numerical/display differences from real-model discrepancy. Potential physical sources include nonuniform velocity, splashing, jet breakup, three-dimensional spreading, viscous dissipation, uncertain fluid properties, nozzle contraction, plate alignment, transient loads, and measurement uncertainty. Include only sources relevant to the stated setup.

### 9.2 Limitations

State that the simulator does not solve pressure and velocity fields, turbulence, free-surface shape, air entrainment, structural response, torque, or unsteady force. Note that Reynolds number is diagnostic only and that a chosen velocity-retention coefficient is not calibration unless supported by data.

## 10. Conclusion (about 0.5 page)

Return directly to the objectives. State verified model behavior and the key quantitative results of the submitted cases. Give no more precision than inputs justify. Do not introduce new evidence.

### 10.1 Recommendations

Suggest defensible extensions such as a controlled laboratory comparison with uncertainty analysis, measured outlet-speed retention, three-dimensional momentum balances, torque for moving vanes, or verified CFD comparison. Label them as future work rather than completed work.

## References

Add only sources the student personally checked. Use one consistent citation style and include edition, publisher or DOI/URL, and access date where required. The export deliberately provides a placeholder rather than unverified references.

## Appendix (not counted)

Include full analytical-verification tables, additional parameter-study plots, sample export data, selected code listings if required, and instructions for reproducing the run. Keep the main argument in the report body.

## Final review checklist

- All names, IDs, dates, figures, and numerical values are verified.
- Force is consistently described as force exerted by water on the plate.
- Angles, component signs, units, and significant figures are consistent.
- Every table and figure is numbered, captioned, and referenced in the text.
- The exact no-CFD scope statement is included, and no visualization or result is called CFD or experimental data.
- References are complete, authoritative, and actually consulted.
- The exported draft has been edited into the student's own coherent report.

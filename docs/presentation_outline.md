# 15-Minute Presentation Outline

Plan for about 15 minutes across 12 slides, followed by 5 minutes of questions. Rehearse to the stated timings and replace bracketed content with verified outputs from the final submitted case.

Use the exact application scope statement on the first slide that shows the interface or visualization:

> This application uses a numerical control-volume momentum model.  
> The flow visualization is illustrative and is not a full CFD simulation.

## Slide 1 - Title (0:30)

- Content: project title, JetForce Studio subtitle, MEC350, `[student names and IDs]`.
- Suggested figure: clean jet/plate schematic or application title view.
- Speaking point: one sentence defining the problem and the three primary reaction outputs.

## Slide 2 - Problem and motivation (1:00)

- Content: a jet carries momentum; stopping or redirecting it transfers momentum to a surface.
- Suggested figure: inlet and outlet velocity vectors beside a real engineering application image with a verified source.
- Important result: direction change can create force even if speed is retained.

## Slide 3 - Objectives (0:45)

- Content: formulate the model, calculate `Fx`, `Fy`, `FR`, verify analytically, and explore parameters.
- Suggested figure: compact workflow from inputs to momentum balance to outputs.
- Speaking point: accuracy and traceability take priority over visual complexity.

## Slide 4 - Geometry and control volume (1:30)

- Content: positive x along the inlet, positive y upward, control-volume boundary, inlet and outlet sections.
- Suggested figure: simulator schematic with control volume and labeled vectors.
- Important equation: `Vin = (V, 0)`.
- Emphasis: the reported force is water on plate, opposite to plate on fluid.

## Slide 5 - Assumptions (1:00)

- Content: steady, incompressible, uniform section-average velocity, atmospheric free jets, stationary plate, negligible local weight/air drag, two-dimensional flow.
- Suggested figure: icons paired with short labels, plus a small limitations flag.
- Speaking point: Course Mode uses the ideal retained-speed case; Advanced `k` is a prescribed outlet-speed loss, not a CFD prediction.

## Slide 6 - Governing momentum equation (1:45)

- Content: mass flow definitions and vector force balance.
- Suggested figure: color-coded vector equation matching the schematic.
- Important equations: `A = pi d^2/4`, `mdot = rho AV`, and `Fplate = mdot Vin - sum(mdot_j Vout,j)`.
- Speaking point: calculate components first, then `FR = sqrt(Fx^2 + Fy^2)`.

## Slide 7 - Application design and modes (1:15)

- Content: six-page `app_pages/` interface, Course Mode default, optional Advanced Mode, validated SI inputs, shared physics layer, and in-memory exports.
- Suggested figure: Presentation View on the Simulator page or a compact map of Simulator, Hand Calculation, Results and Charts, Theory and Assumptions, Report and Export, and About the Project.
- Important definitions: Course Mode offers Normal Flat Plate and the ideal Deflected Jet / Curved Plate Comparison. Advanced Mode adds prescribed `k`, split fractions `s` and `1-s`, and supplementary diagnostics.
- Clarification: changing interface mode changes available controls and explanations, not the governing momentum equation.

## Slide 8 - Main numerical results (1:15)

- Content: `Fx`, `Fy`, `FR` plus flow rate and mass flow for `[selected case]`.
- Suggested figure: result cards and a force-vector diagram.
- Important result: `[insert verified value and direction]`.
- Speaking point: interpret signs physically, not only numerically.

## Slide 9 - Hand calculation and analytical verification (1:30)

- Content: one concise numerical substitution; comparison table for known limiting cases.
- Suggested figure: hand-calculation steps beside expected/simulator/difference columns.
- Important result: normal impact with `rho=1000 kg/m3`, `d=0.02 m`, `V=10 m/s` gives `Fx=31.4159 N`.
- Speaking point: this verifies implementation against the same documented conservation law; it is not experimental validation.

## Slide 10 - Results and Charts (1:30)

- Content: Course Mode force-versus-velocity and force-versus-diameter charts; add a model-specific parameter only if an Advanced Mode objective requires it.
- Suggested figure: clearly labeled Plotly export or report-ready static chart with fixed inputs in the caption.
- Important relationship: ideal normal-impact force is proportional to `V^2` and `d^2`.
- Speaking point: doubling velocity gives four times the force when other inputs and the model are unchanged.

## Slide 11 - Discussion and limitations (1:15)

- Content: vector-direction effects, selected `k`, sources of physical discrepancy, and omitted physics.
- Suggested figure: two-column strengths/limitations graphic.
- Important point: the model does not predict detailed pressure, turbulence, splashing, or transient loads.

## Slide 12 - Conclusion (0:45)

- Content: objectives achieved, verified limiting behavior, main case result, and one future improvement.
- Suggested figure: final result and three concise takeaways.
- Closing sentence: control-volume momentum provides a transparent first engineering estimate when its assumptions are appropriate.

## Five-minute question and answer preparation

### Why was the momentum equation used?

The required plate reaction follows directly from the change in fluid momentum across a control volume. The method needs section-average inlet and outlet velocities without resolving the full spatial flow field.

### Why is pressure neglected at the free-jet boundaries?

The exposed jets are taken to be at atmospheric pressure. Using gauge pressure makes those boundary pressure terms zero. Pressure inside the impact region is not assumed to be zero; its integrated action is part of the plate-fluid interaction represented by the momentum balance.

### What is the difference between ideal and non-ideal results?

The ideal outlet retains speed with `k=1`. A non-ideal case uses a user-selected `k<1`, reducing the prescribed outlet momentum to represent aggregate losses. It is a sensitivity input, not an experimentally derived correction unless data are supplied.

### Is this CFD?

No. Use the application statement exactly: **This application uses a numerical control-volume momentum model. The flow visualization is illustrative and is not a full CFD simulation.** A full CFD model would solve governing field equations over a discretized spatial domain.

### What effect does velocity have on force?

For normal impact, `F = rho A V^2`, so force grows quadratically with velocity when density and area are fixed. In the other implemented models the common momentum scale is also `rho A V^2`, multiplied by direction and retention terms.

### Why does force vary with the square of velocity?

Mass flow is `rho AV`, which is proportional to `V`, and the velocity change contributes another factor of `V`. Their product therefore scales with `V^2` for geometrically similar velocity vectors.

### How was the simulator verified?

It was analytically verified against closed-form cases: normal impact, unchanged velocity, 180-degree reversal, 90-degree deflection, zero velocity, symmetric split flow, and prescribed outlet-speed retention. Automated regression tests compare computed and expected values within floating-point tolerances. No experimental validation is claimed.

### Why is the 90-degree `Fy` negative when the outlet goes upward?

The plate must push the fluid upward, so the fluid exerts an equal downward reaction on the plate. With positive y upward, that plate-force component is negative.

### What does Reynolds number change in the calculation?

Nothing automatically. It is shown as a supporting regime diagnostic. Applying a force correction from Reynolds number would require a defensible correlation or measured calibration, which this model does not assume.

### What are the main limitations?

Uniform section-average velocities, prescribed outlets, two-dimensional steady flow, no free-surface or turbulence solution, no transient loads, and no structural response. Real splashing and outlet-speed loss require measurements or a higher-fidelity model.

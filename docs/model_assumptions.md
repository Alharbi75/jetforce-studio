# Model Assumptions and Scope

## Scope

JetForce Studio is a two-dimensional, steady control-volume momentum model for a free jet striking a stationary flat plate or curved vane. It calculates the reaction force exerted by the fluid on the plate.

> This application uses a numerical control-volume momentum model.  
> The flow visualization is illustrative and is not a full CFD simulation.

The schematic and particle motion illustrate velocity vectors prescribed by the model; they do not solve a spatial pressure, velocity, turbulence, or free-surface field. Course Mode presents the normal flat plate and ideal deflected-jet/curved-plate comparison. Advanced Mode exposes supplementary outlet constructions and diagnostics without changing the governing momentum balance.

The control volume surrounds the compact impact and turning region. Its inlet crosses the undisturbed incoming jet; its outlet surfaces cross the prescribed outgoing stream or streams. Positive x is the incoming jet direction and positive y is upward.

## Assumptions

1. **Steady flow.** Stored mass and momentum inside the control volume do not change with time. The model therefore reports a steady mean force, not pressure or force fluctuations.
2. **Incompressible fluid.** Density is constant between inlet and outlet. This is appropriate for ordinary liquid-water cases and for low-speed gases when compressibility is negligible.
3. **Uniform section-average velocity.** Each jet section is represented by one velocity vector. Boundary layers and nonuniform velocity profiles are not resolved.
4. **Atmospheric free-jet boundaries.** The exposed inlet and outlet jet surfaces are at the same atmospheric pressure, so their gauge-pressure contributions are zero. This does not imply that pressure is uniform inside the impact region.
5. **Stationary, rigid plate.** Plate translation, rotation, elastic deformation, and fluid-structure interaction are outside the model.
6. **Negligible gravity over the impact control volume.** The impact region is assumed small enough that the jet weight within it is small relative to the momentum-flux terms. Ballistic jet curvature before impact is not modeled.
7. **Negligible air resistance.** Aerodynamic drag on the free jet before and immediately after impact is omitted.
8. **Constant inlet diameter.** The specified circular diameter defines the inlet area. Jet contraction, breakup, and nozzle details are not resolved.
9. **Mass conservation.** The single-outlet model sends all inlet mass through one outlet. The split model sends fractions `s` and `1 - s` through two outlets, so their mass flow rates sum to the inlet mass flow.
10. **Losses represented by velocity retention only.** In non-ideal cases, the prescribed coefficient `k` sets outlet speed to `kV`, where `0 <= k <= 1`. For `0<k<1`, mass conservation implicitly requires an effective outlet area different from the inlet area; outlet area is not solved. Exact `k=0` is a limiting zero-outlet-momentum construction, not a literal finite-area section carrying positive mass flow at zero speed. The coefficient is an input assumption representing aggregate loss effects; it is not inferred from Reynolds number, CFD, or experiment.
11. **Two-dimensional momentum balance.** Only x and y force components are calculated. Out-of-plane splashing, torque, and distributed pressure are not predicted.
12. **Fluid force on the plate.** The primary result is the reaction opposite to the external force on the control-volume fluid. Force on the fluid has the opposite sign.

## Interpretation cautions

- Reynolds number is a flow-regime diagnostic only. The program does not apply an invented Reynolds-number correction to force.
- A realistic jet may spread into a sheet, splash, entrain air, or form several streams. The implemented outlets are section-average idealizations.
- The symmetric split-flow cancellation is a vector-momentum result, not evidence that all local plate loads cancel.
- Report exports contain calculated model outputs. They do not constitute experimental or CFD validation.
- Exactly zero inlet speed is a supported boundary. A positive speed whose force scale falls below reliable binary64 resolution is rejected with an input error rather than reported as a false zero.
- Approximate preset fluid properties should be replaced with measured or authoritative values when higher accuracy is required.

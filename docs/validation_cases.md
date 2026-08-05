# Analytical Verification Cases

## Terminology

These cases are analytical **verification** of the implemented equations. They do not compare the model with measured data, so they must not be described as experimental validation. If laboratory measurements are later added, record their provenance, uncertainty, and test conditions separately.

> This application uses a numerical control-volume momentum model.  
> The flow visualization is illustrative and is not a full CFD simulation.

Unless stated otherwise, use \(\rho=1000\ \mathrm{kg/m^3}\), \(d=0.02\ \mathrm{m}\), and \(V=10\ \mathrm{m/s}\). Then

\[
A=\frac{\pi(0.02)^2}{4}=3.14159265\times10^{-4}\ \mathrm{m^2},
\]

\[
Q=AV=3.14159265\times10^{-3}\ \mathrm{m^3/s},
\quad
\dot m=\rho Q=3.14159265\ \mathrm{kg/s},
\]

and \(\dot mV=31.4159265\ \mathrm{N}\).

## Case 1 - normal impact

- Model: normal flat plate.
- Expected: \(F_x=\rho AV^2=31.4159265\ \mathrm{N}\), \(F_y=0\), \(F_R=31.4159265\ \mathrm{N}\).
- Checks: area, mass flow, axial momentum removal, resultant.

## Case 2 - unchanged velocity vector

- Model: one outlet, \(k=1\), \(\beta=0^\circ\).
- Expected outlet: \((10,0)\ \mathrm{m/s}\).
- Expected force: \((F_x,F_y,F_R)=(0,0,0)\ \mathrm{N}\).
- Checks: inlet and outlet momentum cancel without numerical instability.

## Case 3 - ideal 180-degree reversal

- Model: one outlet, \(k=1\), \(\beta=180^\circ\).
- Expected outlet: \((-10,0)\ \mathrm{m/s}\).
- Expected: \(F_x=2\rho AV^2=62.8318531\ \mathrm{N}\), \(F_y\approx0\), \(F_R=62.8318531\ \mathrm{N}\).
- Checks: factor-of-two momentum change and near-zero sine roundoff handling.

## Case 4 - ideal 90-degree deflection

- Model: one outlet, \(k=1\), \(\beta=90^\circ\).
- Expected outlet: \((0,10)\ \mathrm{m/s}\).
- Expected: \(F_x=31.4159265\ \mathrm{N}\), \(F_y=-31.4159265\ \mathrm{N}\), \(F_R=44.4288294\ \mathrm{N}\).
- Checks: the water pushes the plate downward because the plate turns the fluid upward.

## Case 5 - zero inlet speed

- Set \(V=0\) for any model and any valid angle.
- Expected: \(Q=0\), \(\dot m=0\), \(F_x=F_y=F_R=0\).
- Reynolds number is zero when viscosity is positive.
- Checks: no division by velocity and no crash.

## Case 6 - prescribed outlet-speed loss

Use the 90-degree single-outlet case:

| `k` | `Fx` (N) | `Fy` (N) | `FR` (N) |
|---:|---:|---:|---:|
| 1.0 | 31.4159265 | -31.4159265 | 44.4288294 |
| 0.8 | 31.4159265 | -25.1327412 | 40.2320161 |

The inlet x-momentum removal is unchanged at exactly 90 degrees, while the y-reaction magnitude falls with the retained outlet speed. This is a model-input comparison, not an experimentally calibrated loss prediction.

## Case 7 - symmetric split flow

- Model: split flow at any valid \(\theta\), `s = 0.5`.
- Each outlet receives \(0.5\dot m\) and its direction is opposite the other.
- Expected summed outlet momentum: \((0,0)\).
- Expected force: \((31.4159265,0)\ \mathrm{N}\).
- Checks: outlet mass flows sum to inlet mass flow and tangential momentum cancels.

## Acceptance tolerances

Use `pytest.approx` or `numpy.testing` with a typical relative tolerance of `1e-9` for scalar analytical cases and a small absolute tolerance (for example `1e-10`) for components expected to be zero. Do not round calculation values before comparison; round only for presentation.

## Hand-calculation comparison protocol

1. Open **Calculation and Results** in Course Mode (or **Hand Calculation** in Advanced Mode) and record all SI inputs and the selected model.
2. Display substitutions for area, flow rate, mass flow, the simulator's explicit outlet streams, force components, and resultant.
3. Compare the displayed hand-calculation values with the simulator's unrounded result.
4. Report absolute difference. Report percentage difference only when the comparison reference is nonzero.
5. Expect only floating-point or display-rounding differences because this selected-case trace re-sums the simulator's explicit stream state. Use Cases 1–7 above as the independent closed-form checks.
6. Do not claim external validation unless traceable measured data are supplied.

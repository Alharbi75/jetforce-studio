# Governing Equations and Model Derivations

The interface uses these equations through one shared calculation layer. Course Mode presents four primary destinations while six stable source routes preserve deep links. It exposes the normal flat plate and the ideal deflected-jet/curved-plate comparison. Advanced Mode exposes supplementary outlet constructions, velocity retention, and diagnostics. Changing interface mode does not change the governing momentum balance or create a second force formula.

## 1. Coordinates, control volume, and sign convention

Use a Cartesian plane with positive x in the horizontal incoming-jet direction and positive y upward:

\[
\mathbf{V}_{in} = (V, 0)
\]

A steady control volume encloses the impact region. For atmospheric free jets, pressure forces at the inlet and outlets vanish in gauge form. With gravity and other body forces neglected, the steady linear-momentum equation for the fluid is

\[
\sum \mathbf{F}_{on\ fluid}
= \sum_{out}\dot m_j\mathbf{V}_{out,j}
- \sum_{in}\dot m_i\mathbf{V}_{in,i}.
\]

The plate force reported by the simulator is the opposite reaction, the force exerted by the water on the plate:

\[
\boxed{\mathbf{F}_{plate}
= \dot m\mathbf{V}_{in}
- \sum_j \dot m_j\mathbf{V}_{out,j}}
\]

Thus

\[
F_x = \dot m V_{in,x} - \sum_j \dot m_j V_{out,x,j},
\qquad
F_y = \dot m V_{in,y} - \sum_j \dot m_j V_{out,y,j}
\]

and

\[
F_R = \sqrt{F_x^2+F_y^2},
\qquad
\phi_F=\operatorname{atan2}(F_y,F_x).
\]

The direction angle is defined only when $F_R>0$. For a zero resultant, the UI and reports show **not applicable**; the low-level vector property retains `0°` only as a backward-compatible numeric sentinel and exports a separate applicability flag.

The force exerted by the plate on the fluid is `(-Fx, -Fy)`.

## 2. Common inlet quantities

For a circular jet of diameter \(d\), fluid density \(\rho\), speed \(V\), and dynamic viscosity \(\mu\):

\[
A=\frac{\pi d^2}{4},\qquad
Q=AV,\qquad
\dot m=\rho Q=\rho AV,
\]

\[
Re=\frac{\rho Vd}{\mu}.
\]

The Reynolds number characterizes the inlet flow regime. It does not alter the momentum-force equation automatically.

## 3. Model A - normal jet on a flat plate

For a normal jet whose post-impact flow has zero net outlet x-momentum, symmetry also gives zero net outlet y-momentum:

\[
\sum \dot m_j\mathbf V_{out,j}=(0,0).
\]

Therefore

\[
\boxed{F_x=\rho AV^2},\qquad F_y=0,\qquad F_R=|F_x|.
\]

This is the primary analytical verification case.

## 4. Model B - one deflected outlet

Let the outlet angle \(\beta\) be measured counterclockwise from positive x and let `k` be the retained outlet-speed fraction:

\[
\mathbf V_{out}=kV(\cos\beta,\sin\beta),\qquad 0\le k\le1.
\]

All mass exits through this outlet, so

\[
\boxed{F_x=\dot mV(1-k\cos\beta)},
\qquad
\boxed{F_y=-\dot mVk\sin\beta}.
\]

For \(\beta=0^\circ\), \(k=1\), the velocity vector is unchanged and the force is zero. For \(\beta=180^\circ\), \(k=1\), the axial force is \(2\rho AV^2\). For \(\beta=90^\circ\), \(k=1\), \((F_x,F_y)=(\dot mV,-\dot mV)\).

## 5. Model C - split flow along a flat plate

The first outlet follows plate tangent angle \(\theta\); the second is opposite at \(\theta+180^\circ\). The forward mass fraction is `s`:

\[
\dot m_1=s\dot m,\qquad
\dot m_2=(1-s)\dot m,
\]

\[
\mathbf V_1=kV(\cos\theta,\sin\theta),
\qquad
\mathbf V_2=-kV(\cos\theta,\sin\theta).
\]

The summed outlet momentum flux is

\[
\dot m_1\mathbf V_1+\dot m_2\mathbf V_2
=\dot m(2s-1)kV(\cos\theta,\sin\theta).
\]

Consequently

\[
\boxed{F_x=\dot mV[1-(2s-1)k\cos\theta]},
\]

\[
\boxed{F_y=-\dot mV(2s-1)k\sin\theta}.
\]

At `s = 0.5`, the two outlet momentum fluxes cancel exactly and the result is \((\rho AV^2,0)\), independent of tangent angle and `k` within this idealized symmetric construction. For `s != 0.5`, a net tangential outlet momentum changes both components according to \(\theta\).

## 6. Model D - curved vane

The curved-vane option uses the same single-outlet vector model as Model B. The specified exit or deflection angle determines \(\beta\); no separate empirical force multiplier is introduced. The model therefore remains traceable to the boxed control-volume equation.

## 7. Ideal and non-ideal comparison

The ideal comparison uses `k = 1`. A selected non-ideal case uses the user's `k < 1`; its change arises only from the changed outlet momentum vector. A percentage difference for a component or resultant can be reported as

\[
\%\Delta=100\frac{|F_{nonideal}-F_{ideal}|}{|F_{ideal}|},
\]

when the ideal reference is nonzero. If the reference is zero, the percentage is undefined and should be reported as not applicable rather than divided by zero.

## 8. Numerical implementation

All calculations use SI units and double-precision floating point. User-entered angles are converted by

\[
\beta_{rad}=\beta_{deg}\frac{\pi}{180}.
\]

The implementation evaluates momentum vectors first and obtains the resultant with a Euclidean norm. Exact cardinal and opposed outlet vectors prevent trigonometric residue at the documented limiting cases. Values sufficiently close to zero may be displayed as zero, but stored physical force values are not tolerance-clipped or replaced by hard-coded validation results.

Exactly zero inlet speed is evaluated directly. A positive input whose momentum scale would fall below reliable binary64 resolution is rejected during validation, so the calculation layer does not silently replace an unrepresentable physical force with zero.

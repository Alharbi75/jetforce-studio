# JetForce Studio presentation fallback

These files are a static snapshot of the documented Course Mode default case:

- textbook water density: 1000 kg/m³
- jet diameter: 0.02 m
- inlet velocity: 10 m/s
- model: Normal Flat Plate
- calculated force: Fx = FR = 31.4159 N and Fy = 0 N

Use `default_simulator.png` if the live app cannot be shown. The HTML/PDF,
result table, and charts provide offline evidence of the same calculation.
They are presentation fallbacks, not an interactive simulator and not CFD.

The live public application is:

<https://jetforce-studio-mec350.streamlit.app/>

`public_app_qr.png` encodes that exact URL for presentation slides and printed
material. Recheck the live link shortly before presenting because Community
Cloud may need a brief cold start after inactivity.

To rebuild every generated fallback except the browser screenshot, run:

```bash
python scripts/build_presentation_backup.py
```

The student-name, student-ID, institution, and reference fields remain honest
placeholders and must be completed or reviewed before academic submission.

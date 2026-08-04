# Streamlit Community Cloud deployment

JetForce Studio requires no secret, API key, database, authentication provider, or paid service. The deployment entry point is `app.py`; runtime dependencies are in `requirements.txt`.

## Deployment procedure

1. Create or select a GitHub repository.
2. Upload the clean source files.
3. Confirm `app.py` is in the documented repository root.
4. Confirm `requirements.txt` is committed.
5. Connect GitHub to Streamlit Community Cloud.
6. Create a new app.
7. Select the repository and branch.
8. Set the app entry point to `app.py`.
9. Select the tested Python version where the platform allows it; use Python 3.11 as the baseline.
10. Deploy.
11. Set access to **Public**.
12. Choose a clear URL if available.
13. Test in a signed-out incognito/private window.
14. Test on a phone, including a mobile-data connection when possible.
15. Record the final URL in the deployment record below.
16. Generate a QR code for the presentation only after the final URL is known.

## Current public deployment

JetForce Studio was deployed on 5 August 2026 using the public
[`Alharbi75/jetforce-studio`](https://github.com/Alharbi75/jetforce-studio)
repository, branch `main`, entry point `app.py`, and Python 3.11.

**Public application:** <https://jetforce-studio-mec350.streamlit.app/>

The presentation QR code is stored at
`presentation_backup/public_app_qr.png` and encodes this exact URL.

## Required post-deployment checks

- A fresh signed-out visitor sees Course Mode and the complete default result.
- No login, repository prompt, API-key prompt, or file upload is required.
- The local logo, CSS, schematic, and chart assets render.
- Density, diameter, velocity, model, angle, reset, presets, and Presentation View work.
- The Hand Calculation page agrees with the simulator.
- Velocity and diameter studies resize and their CSV downloads work.
- Case CSV, JSON, printable HTML, and PDF downloads work.
- Mobile layout has no horizontal page scrolling and remains usable at 200% zoom.
- Two simultaneous private sessions do not share engineering values.
- No raw traceback is visible.

These checks must be recorded in `RELEASE_CHECKLIST.md` only after an actual public deployment.

## Local pre-deployment smoke check

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

For Windows, activate with `.venv\Scripts\activate`.

## Optional container fallback

```bash
docker build -t jetforce-studio .
docker run --rm -p 8501:8501 jetforce-studio
```

The image runs as an unprivileged user and uses the same runtime-only requirements. A container engine is optional and is not required by Streamlit Community Cloud.

## Rollback and recovery

If deployment fails, review the build log for Python-version or wheel-install errors, confirm filename case exactly matches the repository, and reproduce the failure in a clean Python 3.11 environment. Keep the `presentation_backup/` directory available during the classroom presentation.

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
- The Calculation and Results page agrees with the simulator and its independent closed-form checks pass.
- Velocity and diameter studies resize and their CSV downloads work.
- Case CSV, JSON, printable HTML, and PDF downloads work.
- Mobile layout has no horizontal page scrolling and remains usable at 200% zoom.
- Two simultaneous private sessions do not share engineering values.
- No raw traceback is visible.

These checks must be recorded in `RELEASE_CHECKLIST.md` only after an actual public deployment.

## Two-part public verification policy

A public-deployment claim requires both checks below. Passing only one is not
sufficient.

### 1. Automated anonymous link and health check

Run the repository's standard-library checker against the real deployed URL:

```bash
python scripts/check_public_deployment.py https://jetforce-studio-mec350.streamlit.app/
```

The checker begins with an empty in-memory cookie jar and sends no preexisting
credential, API key, or authenticated browser session. It never loads cookies
from disk and never persists cookies issued during the check. For a
`*.streamlit.app` URL it preserves the original URL in the report but adds
`embed=true` only to the page probe. This provides a strict anonymous HTTP path
without relying on an interactive browser bootstrap. Any authentication-route
redirect from that probe is a failure.

The checker records every followed redirect and reports the UTC check time,
public-page HTTP status, probe URL, and final URL. It checks Community Cloud's
`/healthz` JSON endpoint; local or non-Community Streamlit targets use
`/_stcore/health`. Credential-like query values are redacted from log output.

The check fails when sign-in is encountered, when either request completes on
an origin other than the requested app, when the page or health endpoint is
unavailable or unsuccessful, or when the health body is not explicitly
healthy. It exits nonzero so it can be used in an external deployment monitor
or release command.

Exit code `0` means the anonymous HTTP and health checks passed. Any nonzero
exit means the public-link assurance failed or the command input was invalid.
The normal automated test suite does not contact the internet; it tests this
checker against local HTTP servers.

### 2. Manual signed-out browser and device verification

The checker cannot render Streamlit's JavaScript interface, exercise widgets,
prove that two browser sessions are isolated, validate responsive layout, or
confirm browser downloads. A reviewer must still open the real URL signed out
and complete the required browser checks above, plus the independent browser
and physical-phone/mobile-data items in `RELEASE_CHECKLIST.md`.

Record an actual public deployment as fully verified only when the automated
checker passes and every claimed manual item has genuinely been completed.

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

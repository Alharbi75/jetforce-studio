# JetForce Studio release checklist

Checked items below include repository-local facts and the cloud checks completed on 5 August 2026. Physical-phone, mobile-data, and independent second-browser checks remain presentation-day owner checks.

## Application and physics

- [x] `app.py` is the documented entry point.
- [x] Course Mode is the fresh-session default.
- [x] The default result is visible without data entry.
- [x] The default textbook case uses `rho = 1000 kg/m3`, `d = 0.02 m`, and `V = 10 m/s`.
- [x] Normal flat-plate `Fx`, `Fy`, and `FR` match the analytical result.
- [x] Force sign convention is defined and tested.
- [x] Zero velocity is handled without division by zero.
- [x] The hand calculation matches the documented analytical model.
- [x] Independent closed-form checks pass for normal impact, ideal 90-degree deflection, and ideal 180-degree reversal.
- [x] Advanced Mode is optional and explicitly supplementary.
- [x] The application does not claim to be CFD or experimental validation.

## Visitor experience and privacy

- [x] No application login or account is implemented.
- [x] No paid API, API key, external database, or user upload is required.
- [x] No application analytics, advertising, tracking pixel, or marketing widget is included.
- [x] Core features require no outbound runtime API.
- [x] Visitor-entered engineering values are not written to a database.
- [x] Reports are generated in memory.
- [x] The one-page presentation summary is generated in memory and contains the required MEC350 inputs, equations, results, chart, assumptions, and model limitation.
- [x] Critical assets are local and repository-relative.
- [x] Course Mode exposes SI controls only.
- [x] Advanced controls are hidden in Course Mode.
- [x] Presentation View and one compact selector for three classroom cases are available.
- [x] Course Mode shows one visible control per active physical quantity.
- [x] Course Mode has four primary destinations; secondary routes remain bookmark-safe.
- [x] Concise Arabic help is available without partial interface translation.

## Quality and release artifacts

- [x] `.streamlit/config.toml` exists and usage-stat collection is disabled.
- [x] `requirements.txt` contains runtime dependencies only.
- [x] `requirements-dev.txt` contains development tools.
- [x] README, deployment guide, and this checklist exist.
- [x] About and generated reports expose application version, model revision, build commit fallback, and UTC generation time.
- [x] Windows, macOS, and Linux launch helpers exist.
- [x] Presentation backup artifacts exist.
- [x] Clean release ZIP exists and excludes environments, caches, secrets, and build artifacts.
- [x] Linux-case-sensitive page and asset names are checked.
- [x] Automated tests pass.
- [x] Ruff, Black, mypy, and import checks pass.
- [x] Headless Streamlit startup and health check pass.
- [x] Runtime-only clean-environment installation and tests pass.
- [x] The anonymous public-deployment checker is covered by offline unit tests and documented separately from the normal test suite.
- [x] GitHub Actions CI runs the complete Python 3.11 quality gate without secrets or paid services.

## Actual public deployment - complete only after deployment

- [x] Repository pushed to the selected GitHub account.
- [x] Streamlit Community Cloud app created from `app.py`.
- [x] Deployment access set to Public.
- [x] Final public URL recorded in `DEPLOYMENT.md`.
- [x] Signed-out incognito/private-window test passed.
- [ ] Second-browser test passed.
- [ ] Phone test passed.
- [ ] Mobile-data test passed.
- [x] No login or repository prompt appeared during signed-out browser and no-credential public HTTP checks.
- [x] Public study CSV and case CSV/JSON/HTML/PDF downloads passed.
- [x] Public mobile layout and effective 200% zoom review passed.
- [x] Final QR code generated from the real public URL.

The application is actually deployed. Do not claim the remaining physical-device and independent-browser checks until they are completed.

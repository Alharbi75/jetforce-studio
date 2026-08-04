#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  JF_PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  JF_PYTHON="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  JF_PYTHON="$(command -v python3)"
else
  echo "Python 3.11 or newer was not found. Install Python, then follow README.md." >&2
  exit 1
fi

if ! "$JF_PYTHON" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)'; then
  echo "JetForce Studio requires Python 3.11, 3.12, or 3.13." >&2
  exit 1
fi

if ! "$JF_PYTHON" -c 'import streamlit' >/dev/null 2>&1; then
  echo "Dependencies are missing. Run: $JF_PYTHON -m pip install -r requirements.txt" >&2
  exit 1
fi

exec "$JF_PYTHON" -m streamlit run app.py

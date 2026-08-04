@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "JF_PYTHON=.venv\Scripts\python.exe"
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
      echo Python 3.11 or newer was not found. Install Python, then follow README.md.
      exit /b 1
    )
    set "JF_PYTHON=python"
  ) else (
    set "JF_PYTHON=py -3.11"
  )
)

%JF_PYTHON% -c "import sys; raise SystemExit(0 if (3,11) ^<= sys.version_info ^< (3,14) else 1)"
if errorlevel 1 (
  echo JetForce Studio requires Python 3.11, 3.12, or 3.13.
  exit /b 1
)

%JF_PYTHON% -c "import streamlit" >nul 2>nul
if errorlevel 1 (
  echo Dependencies are missing. Run: %JF_PYTHON% -m pip install -r requirements.txt
  exit /b 1
)

%JF_PYTHON% -m streamlit run app.py
endlocal

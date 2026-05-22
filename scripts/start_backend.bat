@echo off
setlocal
cd /d "%~dp0.."

if exist "venv\Scripts\activate.bat" (
  call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
) else (
  echo [WARN] No venv found. Using system Python.
)

if not exist ".env" (
  echo [WARN] Missing .env — copy .env.example to .env and add secrets.
)

echo Starting Gmail Genie API on http://127.0.0.1:8000
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
endlocal

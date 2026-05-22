@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

title Gmail Genie Launcher
echo.
echo  ========================================
echo   Gmail Genie - Local inbox organizer
echo   Labels only - inbox always preserved
echo  ========================================
echo.

set "ROOT=%CD%"
set "VENV_PY=%ROOT%\venv\Scripts\python.exe"
if not exist "%VENV_PY%" set "VENV_PY=python"

echo [1/6] Checking Python...
"%VENV_PY%" --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found. Run: python -m venv venv
  pause
  exit /b 1
)
if not exist "%ROOT%\venv\" (
  echo WARN: No venv folder - using system Python. Recommend: python -m venv venv
)

echo [2/6] Checking frontend dependencies...
if not exist "%ROOT%\frontend\node_modules\" (
  echo WARN: Run once: cd frontend ^&^& npm install
) else (
  echo OK: frontend node_modules
)

echo [3/6] Checking Ollama...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo WARN: Ollama not responding on http://127.0.0.1:11434
  echo       Start Ollama app, then: ollama pull mistral
) else (
  echo OK: Ollama reachable
)

echo [4/6] Checking Gmail OAuth files...
if not exist "%ROOT%\backend\credentials.json" (
  echo WARN: Missing backend\credentials.json - see README OAuth section
) else (
  echo OK: credentials.json found
)
if not exist "%ROOT%\backend\token.json" (
  echo WARN: Missing backend\token.json - run one-time OAuth after credentials
) else (
  echo OK: token.json found
)

echo [5/6] Starting backend and frontend...
start "Gmail Genie API" cmd /k "%ROOT%\scripts\start_backend.bat"
timeout /t 4 /nobreak >nul
start "Gmail Genie UI" cmd /k "%ROOT%\scripts\start_frontend.bat"
timeout /t 6 /nobreak >nul

echo [6/6] Opening dashboard...
start "" "http://localhost:5173"

echo.
echo  Backend:  http://127.0.0.1:8000
echo  Frontend: http://localhost:5173
echo.
echo  First run uses PREVIEW mode - apply labels when ready.
echo  Press any key to close this launcher (services keep running).
pause >nul
endlocal

@echo off
setlocal
cd /d "%~dp0.."

echo Launching backend in new window...
start "Gmail Genie API" cmd /k "%~dp0start_backend.bat"

timeout /t 3 /nobreak >nul

echo Launching frontend in new window...
start "Gmail Genie UI" cmd /k "%~dp0start_frontend.bat"

echo Both services starting. Backend: http://127.0.0.1:8000  Frontend: http://localhost:5173
endlocal

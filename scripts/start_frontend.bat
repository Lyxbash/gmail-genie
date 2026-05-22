@echo off
setlocal
cd /d "%~dp0..\frontend"

if not exist "node_modules" (
  echo Installing frontend dependencies...
  call npm install
)

echo Starting Gmail Genie UI (Vite)...
call npm run dev
endlocal

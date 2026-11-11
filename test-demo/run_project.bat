@echo off
title Sangeeta Infotech - Lead & Outreach Hub
cd /d "%~dp0"
echo ==============================================================
echo   STARTING FULL SYSTEM (PYTHON BACKEND + NEXT.JS FRONTEND)
echo ==============================================================

REM Auto-detect Python binary (virtualenv or Windows py launcher)
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
) else (
    set "PY_CMD=py"
)

echo [*] 1. Starting Python Backend API on http://127.0.0.1:5000 ...
start "Lead Hub - Backend API (Port 5000)" cmd /k "cd /d "%~dp0" && "%PY_CMD%" app.py"

echo [*] Waiting 3 seconds for Python Backend to initialize...
timeout /t 3 /nobreak >nul

echo [*] 2. Starting Next.js Frontend Dashboard on http://localhost:3000 ...
cd /d "%~dp0frontend"
start http://localhost:3000
npm run dev

pause


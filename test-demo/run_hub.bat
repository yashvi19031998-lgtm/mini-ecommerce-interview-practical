@echo off
title Sangeeta Infotech - Lead and Outreach Hub
cd /d "%~dp0"
echo ==============================================================
echo   STARTING SANGEETA INFOTECH LEAD & OUTREACH HUB
echo   Opening: http://127.0.0.1:5000 (Ultra Fast Local Mode)
echo ==============================================================
REM Legacy Flask UI has no login screen, so auth is turned off here.
REM This only works because app.py is bound to 127.0.0.1 (local machine only).
set API_AUTH_DISABLED=true
start http://127.0.0.1:5000
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" app.py
) else (
    py app.py
)
pause

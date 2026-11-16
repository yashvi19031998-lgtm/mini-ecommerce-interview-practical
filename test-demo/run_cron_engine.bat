@echo off
title SANGEETA INFOTECH — 4-IN-1 AUTONOMOUS MASTER CRON ENGINE
cd /d "%~dp0"
cls
echo ======================================================================
echo   SANGEETA INFOTECH — AUTONOMOUS 4-IN-1 MASTER CRON ENGINE
echo ======================================================================
echo   [1] Multi-Source Business Scraper  -> Runs Hourly
echo   [2] AI Concept-Wise Email Outreach -> Runs Hourly & Updates DB
echo   [3] Freelance & Project Scraper    -> Runs Every 30 Mins
echo   [4] Daily Summary Report           -> Runs Nightly at 8:00 PM
echo ======================================================================
echo.

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe master_cron_runner.py %*
) else (
    python master_cron_runner.py %*
)

pause

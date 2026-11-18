@echo off
chcp 65001 >nul
title test-demo - 4-IN-1 AUTONOMOUS MASTER CRON ENGINE
cd /d "%~dp0"
cls
rem In echo lines "&" and ">" must be written as "^&" and "^>", otherwise cmd runs / redirects them.
echo ======================================================================
echo   TEST-DEMO - AUTONOMOUS 4-IN-1 MASTER CRON ENGINE
echo ======================================================================
echo   [1] Multi-Source Business Scraper  -^> every hour
echo   [2] Freelance ^& Project Scraper    -^> every 2 hours
echo   [3] AI Email Outreach              -^> every hour, Mon-Sat 10:00-19:00 only
echo   [4] Daily Summary Report           -^> every day at 20:00
echo   Logs: logs\cron\   Status: logs\cron_status.json
echo ======================================================================
echo.

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe master_cron_runner.py %*
) else (
    python master_cron_runner.py %*
)

pause

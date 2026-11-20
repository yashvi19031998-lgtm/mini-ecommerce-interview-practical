@echo off
REM SME post-pack outreach (2 free sample posts, then 10 posts for Rs 500) to local businesses.
REM   run_sme_outreach_automation.bat            -> DRY RUN: shows who would get a mail, sends nothing
REM   run_sme_outreach_automation.bat live       -> sends (max 15 a day in total)
REM   run_sme_outreach_automation.bat live auto  -> same, for Windows Task Scheduler (no pause at the end)
REM Extra options for the script can follow, e.g.:  ... live auto --region india
title SME post-pack outreach
cd /d "%~dp0"

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "logs" mkdir "logs"

set "MODE=--dry-run"
if /i "%~1"=="live" set "MODE="
set "AUTO="
if /i "%~2"=="auto" set "AUTO=1"
set "EXTRA="
if /i "%~1"=="live" shift
if defined AUTO shift
:collect
if "%~1"=="" goto run
set "EXTRA=%EXTRA% %1"
shift
goto collect

:run
if defined AUTO (
    "%PY%" cron_job_sme_outreach.py %MODE% %EXTRA% >> "logs\sme_outreach.log" 2>&1
) else (
    "%PY%" cron_job_sme_outreach.py %MODE% %EXTRA%
    pause
)

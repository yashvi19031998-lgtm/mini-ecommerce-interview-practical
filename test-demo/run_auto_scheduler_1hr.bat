@echo off
title Autonomous 1-Hour Lead Engine Scheduler
cd /d "%~dp0"
echo ==============================================================
echo   AUTONOMOUS LEAD GENERATION & OUTREACH ENGINE
echo   - Runs all scrapers every 1 hour
echo   - AI qualifies and deduplicates fresh leads
echo   - Dispatches automated cold outreach emails via Gmail SMTP
echo   - Automatically syncs all leads to Supabase cloud database
echo   - Relaxed AI score threshold (4+) and prospect signal enabled
echo ==============================================================
echo.

set AUTO_SCHEDULER_INTERVAL_HOURS=1
set MIN_AI_SCORE_FOR_AUTO_EMAIL=4
set AUTO_EMAIL_PROSPECT_SIGNALS=true
set MAX_PENDING_EMAILS_PER_RUN=25
set MAX_EMAILS_PER_DAY=100

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scheduler.py
) else (
    python scheduler.py
)

pause

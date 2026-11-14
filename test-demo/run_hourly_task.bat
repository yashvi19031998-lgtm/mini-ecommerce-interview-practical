@echo off
title Sangeeta Infotech - Autonomous Lead Engine Scraper
cd /d "%~dp0"

echo ==============================================================
echo   SANGEETA INFOTECH - LEAD ENGINE & OUTREACH SYSTEM
echo   - Scraping active target locations & keywords
echo   - AI qualifying leads & verifying mailboxes
echo   - Syncing to Supabase Cloud Database
echo ==============================================================
echo.

:: Set automation environment variables
set AUTO_SEND_EMAIL=true
set MIN_AI_SCORE_FOR_AUTO_EMAIL=4
set AUTO_EMAIL_PROSPECT_SIGNALS=true
set MAX_PENDING_EMAILS_PER_RUN=25
set MAX_EMAILS_PER_DAY=100

echo [%date% %time%] Starting Scraper Engine...
echo.

"C:\Users\Admin\AppData\Local\Python\pythoncore-3.14-64\python.exe" run_all_scrapers.py

echo.
echo ==============================================================
echo [%date% %time%] Scraper Engine Cycle Finished!
echo ==============================================================
echo.
pause
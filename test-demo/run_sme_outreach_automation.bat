@echo off
title Autonomous SME Post Pack Outreach Engine (Non-IT Businesses)
cd /d "%~dp0"
echo ==============================================================
echo   AUTONOMOUS SME POST PACK OUTREACH ENGINE
echo   - Targets local Gujarat SMEs (Clinics, Salons, Gyms, Sweets, Jewellers)
echo   - STRICT IT COMPANY SHIELD: 100%% IT / Software companies blocked
echo   - Dispatches 70-word '2 Free Samples' hook via Gmail SMTP
echo   - Enforces duplicate shield (never contacts the same lead twice)
echo ==============================================================
echo.

if exist "C:\Users\Lenovo\AppData\Local\Python\bin\python.exe" (
    "C:\Users\Lenovo\AppData\Local\Python\bin\python.exe" cron_job_sme_outreach.py --limit 15
) else if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe cron_job_sme_outreach.py --limit 15
) else (
    python cron_job_sme_outreach.py --limit 15
)

pause

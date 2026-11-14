@echo off
cd /d "e:\MyWork\mini-ecommerce-interview-practical\test-demo"

:: Environment setup for Full Autopilot Outreach & Follow-ups
set AUTO_SEND_EMAIL=true
set MIN_AI_SCORE_FOR_AUTO_EMAIL=4
set AUTO_EMAIL_PROSPECT_SIGNALS=true
set MAX_PENDING_EMAILS_PER_RUN=25
set MAX_EMAILS_PER_DAY=100
set FOLLOWUP_AUTO_SEND=true
set FOLLOWUP_SEQUENCE_DAYS=3,7,14

echo [%date% %time%] Background Task Started >> "logs\windows_task_runner.log"

"C:\Users\Admin\AppData\Local\Python\pythoncore-3.14-64\python.exe" run_all_scrapers.py >> "logs\windows_task_runner.log" 2>&1

echo [%date% %time%] Background Task Finished >> "logs\windows_task_runner.log"
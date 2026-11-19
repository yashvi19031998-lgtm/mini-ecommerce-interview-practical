@echo off
REM ==============================================================================
REM Sangeeta Infotech - Automated WhatsApp Web Outreach Dispatcher
REM ==============================================================================
title Sangeeta Infotech - WhatsApp Outreach Dispatcher

echo ==============================================================================
echo   SANGEETA INFOTECH - AUTOMATED WHATSAPP OUTREACH
echo ==============================================================================
echo.
echo Mode: WhatsApp Web Automation (100%% Free, uses your +91 9106060400 session)
echo.

if "%1"=="--login" (
    echo [ACTION] Opening WhatsApp Web for initial QR code scan...
    python cron_job_whatsapp_outreach.py --login-only
    goto end
)

if "%1"=="--dry-run" (
    echo [ACTION] Running Dry-Run preview (no messages will be sent)...
    python cron_job_whatsapp_outreach.py --dry-run
    goto end
)

echo [ACTION] Starting automated WhatsApp outreach batch (default: 5 leads)...
python cron_job_whatsapp_outreach.py %*

:end
echo.
echo ==============================================================================
echo   Execution finished.
echo ==============================================================================
pause

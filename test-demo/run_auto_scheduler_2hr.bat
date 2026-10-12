@echo off
title Sangeeta Infotech - 2 Hour Automated Lead Engine
cd /d "E:\MyWork\mini-ecommerce-interview-practical\test-demo"
echo ==============================================================
echo   SANGEETA INFOTECH - AUTONOMOUS 2-HOUR SCRAPER ENGINE
echo   - Scrapes fresh leads every 2 hours
echo   - Sends direct customized cold outreach emails via Gmail SMTP
echo   - Automatically syncs all leads to Supabase cloud database
echo ==============================================================
echo.
python scheduler.py
pause

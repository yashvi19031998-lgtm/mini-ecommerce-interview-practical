@echo off
title Sangeeta Infotech - Lead and Outreach Hub
cd /d "%~dp0"
echo ==============================================================
echo   STARTING SANGEETA INFOTECH LEAD & OUTREACH HUB
echo   Opening: http://localhost:5000
echo ==============================================================
start http://localhost:5000
python app.py
pause

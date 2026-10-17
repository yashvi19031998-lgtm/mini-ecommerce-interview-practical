@echo off
title Sangeeta Infotech - Lead and Outreach Hub
cd /d "%~dp0"
echo ==============================================================
echo   STARTING SANGEETA INFOTECH LEAD & OUTREACH HUB
echo   Opening: http://127.0.0.1:5000 (Ultra Fast Local Mode)
echo ==============================================================
start http://127.0.0.1:5000
python app.py
pause

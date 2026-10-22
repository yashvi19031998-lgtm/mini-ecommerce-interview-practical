@echo off
title Sangeeta Infotech - Next.js Lead & Outreach UI
cd /d "%~dp0frontend"
echo ==============================================================
echo   STARTING NEXT.JS LEAD & OUTREACH HUB
echo   Opening: http://localhost:3001
echo ==============================================================
start http://localhost:3001
npm.cmd run dev -- -p 3001
pause

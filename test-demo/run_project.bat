@echo off
title Sangeeta Infotech - Lead & Outreach Hub
cd /d "%~dp0"
echo ==============================================================
echo   STARTING FULL SYSTEM (PYTHON BACKEND + NEXT.JS FRONTEND)
echo ==============================================================

echo [*] 1. Starting Python Backend API on http://127.0.0.1:5000 ...
start "Lead Hub - Backend API" cmd /k "python app.py"

echo [*] 2. Starting Next.js Frontend Dashboard on http://localhost:3000 ...
cd frontend
start http://localhost:3000
npm run dev

pause

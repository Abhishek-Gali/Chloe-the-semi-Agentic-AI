@echo off
title Project Chloe 2.0 // Abhishek's Personal Assistant
cd /d "%~dp0"
echo ============================================================
echo PROJECT CHLOE 2.0 // AGENTIC AI ONLINE
echo ============================================================
start "" "http://localhost:8000"
python -u run.py
if %ERRORLEVEL% NEQ 0 (
    echo [!] Chloe encountered an issue. Press any key to exit.
    pause
)

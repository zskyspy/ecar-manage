@echo off
title ECAR Space - Offline Development Mode
cd /d "%~dp0"
echo ==========================================
echo Starting ECAR Space (Development Mode)
echo Code changes will auto-reload automatically!
echo Local URL: http://127.0.0.1:8000
echo Press Ctrl+C to stop.
echo ==========================================
call .\venv\Scripts\activate.bat
python manage.py runserver 127.0.0.1:8000
pause

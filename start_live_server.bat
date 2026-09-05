@echo off
title ECAR Space - Fast Production Server (Waitress)
cd /d "%~dp0"
echo ==========================================
echo Preparing & Launching Live Fast Server...
echo ==========================================
call .\venv\Scripts\activate.bat
echo [1/2] Updating and compressing static files...
python manage.py collectstatic --noinput
echo [2/2] Starting Waitress server (8 threads)...
echo Server running on http://0.0.0.0:8000
echo KEEP THIS WINDOW OPEN!
echo ==========================================
.\venv\Scripts\waitress-serve.exe --host=0.0.0.0 --port=8000 --threads=8 garageapp.wsgi:application
pause

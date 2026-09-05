@echo off
title ECAR Space - Cloudflare Public Tunnel
cd /d "%~dp0"
echo =======================================================
echo Starting Cloudflare Tunnel...
echo Look for your public URL below (https://....trycloudflare.com)
echo KEEP THIS WINDOW OPEN while you want people to access it!
echo =======================================================
.\cloudflared.exe tunnel --url http://localhost:8000 --no-autoupdate
pause

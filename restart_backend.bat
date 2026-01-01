@echo off
echo Killing all Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo Starting fresh backend on port 8000...
cd /d "c:\Users\rcarb\Downloads\FOPS\fopsbackend"
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

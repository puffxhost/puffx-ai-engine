@echo off
cd /d "%~dp0..\.."
if not exist .venv\Scripts\python.exe (echo Run installers\windows\install.bat first.& exit /b 1)
echo Starting on 127.0.0.1:8000; press Ctrl+C to stop.
.venv\Scripts\python -m uvicorn api.app:app --host 127.0.0.1 --port 8000

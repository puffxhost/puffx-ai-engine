@echo off
setlocal
cd /d "%~dp0..\.."
where py >nul 2>nul || (echo Python launcher not found. Install Python 3.11+ from python.org and enable the launcher.& exit /b 1)
py -3.11 -m venv .venv || (echo Could not create virtual environment.& exit /b 1)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt || exit /b 1
if not exist .env copy .env.example .env
echo Install complete. Edit .env and run start.bat.

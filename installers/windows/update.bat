@echo off
cd /d "%~dp0..\.."
.venv\Scripts\python -m pip install --upgrade -r requirements.txt

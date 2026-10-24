@echo off
where ollama >nul 2>nul || (echo Ollama is not installed. Install it from ollama.com first.& exit /b 1)
set MODEL_NAME=qwen2.5:3b
if not "%~1"=="" set MODEL_NAME=%~1
echo Downloading model %MODEL_NAME%. Review its publisher license before use.
ollama pull %MODEL_NAME%

@echo off
cd /d "%~dp0"

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo uv not found. Please install uv: https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Port 80 requires elevated permissions. Restarting as Administrator...
    powershell -Command "Start-Process -Verb RunAs cmd '/c cd /d \"%~dp0\" && uv run --with flask --with requests python app.py --port 80 %*'"
    exit /b
)

uv run --with flask --with requests python app.py --port 80 %*

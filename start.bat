@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure "Add python.exe to PATH" is checked during installation.
    pause
    exit /b 1
)

if not exist ".venv" (
    py -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install -r requirements.txt

cls

if "%~1"=="" (
    python main.py
) else (
    python main.py "%~1"
)

pause

@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Please install Python 3.11, 3.12, or 3.13 from https://www.python.org/downloads/
    echo Make sure "Add python.exe to PATH" is checked during installation.
    pause
    exit /b 1
)

py -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)" >nul 2>nul
if errorlevel 1 (
    echo This project requires Python 3.11, 3.12, or 3.13.
    echo Python 3.14 is not supported by the pinned Pillow dependency.
    pause
    exit /b 1
)

if not exist ".venv" (
    py -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install -r requirements.txt

cls

python main.py %*

pause

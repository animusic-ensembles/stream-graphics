@echo off
setlocal

cd /d "%~dp0"

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

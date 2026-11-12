@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Please install Python 3.11, 3.12, 3.13, or 3.14 from https://www.python.org/downloads/
    echo Make sure "Add python.exe to PATH" is checked during installation.
    pause
    exit /b 1
)

py -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 15) else 1)" >nul 2>nul
if errorlevel 1 (
    echo This project requires Python 3.11, 3.12, 3.13, or 3.14.
    pause
    exit /b 1
)

where soffice >nul 2>nul
if errorlevel 1 (
    if not exist "C:\Program Files\LibreOffice\program\soffice.exe" (
        if not exist "C:\Program Files (x86)\LibreOffice\program\soffice.exe" (
            echo LibreOffice was not found.
            where winget >nul 2>nul
            if errorlevel 1 (
                echo Please install LibreOffice from https://www.libreoffice.org/download/download-libreoffice/
                pause
                exit /b 1
            )

            echo Installing LibreOffice with winget...
            winget install --id TheDocumentFoundation.LibreOffice --exact --accept-package-agreements --accept-source-agreements
            if errorlevel 1 (
                echo LibreOffice installation failed.
                pause
                exit /b 1
            )
        )
    )
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo FFmpeg was not found.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Please install FFmpeg and make sure it is available on PATH.
        pause
        exit /b 1
    )

    echo Installing FFmpeg with winget...
    winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo FFmpeg installation failed.
        pause
        exit /b 1
    )
)

if not exist ".venv" (
    py -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install -r requirements.txt

cls

python main.py %*

exit /b %errorlevel%

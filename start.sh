#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 was not found."
    echo "Please install Python 3.11, 3.12, or 3.13, then run this script again."
    exit 1
fi

if ! python3 -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)"; then
    echo "This project requires Python 3.11, 3.12, or 3.13."
    echo "Python 3.14 is not supported by the pinned Pillow dependency."
    exit 1
fi

if ! command -v soffice >/dev/null 2>&1 && ! command -v libreoffice >/dev/null 2>&1; then
    echo "LibreOffice was not found."

    if command -v apt-get >/dev/null 2>&1; then
        echo "Installing LibreOffice with apt-get..."
        sudo apt-get update
        sudo apt-get install -y libreoffice
    elif command -v dnf >/dev/null 2>&1; then
        echo "Installing LibreOffice with dnf..."
        sudo dnf install -y libreoffice
    elif command -v pacman >/dev/null 2>&1; then
        echo "Installing LibreOffice with pacman..."
        sudo pacman -Sy --needed libreoffice-fresh
    else
        echo "Please install LibreOffice, then run this script again."
        exit 1
    fi
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "FFmpeg was not found."

    if command -v apt-get >/dev/null 2>&1; then
        echo "Installing FFmpeg with apt-get..."
        sudo apt-get update
        sudo apt-get install -y ffmpeg
    elif command -v dnf >/dev/null 2>&1; then
        echo "Installing FFmpeg with dnf..."
        sudo dnf install -y ffmpeg
    elif command -v pacman >/dev/null 2>&1; then
        echo "Installing FFmpeg with pacman..."
        sudo pacman -Sy --needed ffmpeg
    else
        echo "Please install FFmpeg, then run this script again."
        exit 1
    fi
fi

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

. ".venv/bin/activate"

python -m pip install -r requirements.txt

clear

exec python main.py "$@"

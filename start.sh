#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

OS_NAME="$(uname -s)"
PYTHON_BIN="python3"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python 3 was not found."

    if [ "$OS_NAME" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
        echo "Installing Python with Homebrew..."
        brew install python@3.14
        if command -v python3.14 >/dev/null 2>&1; then
            PYTHON_BIN="python3.14"
        fi
    else
        echo "Please install Python 3.11, 3.12, 3.13, or 3.14, then run this script again."
        exit 1
    fi
fi

if ! "$PYTHON_BIN" -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 15) else 1)"; then
    echo "This project requires Python 3.11, 3.12, 3.13, or 3.14."
    exit 1
fi

if ! command -v soffice >/dev/null 2>&1 \
    && ! command -v libreoffice >/dev/null 2>&1 \
    && [ ! -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
    echo "LibreOffice was not found."

    if [ "$OS_NAME" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
        echo "Installing LibreOffice with Homebrew..."
        brew install --cask libreoffice
    elif command -v apt-get >/dev/null 2>&1; then
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

    if [ "$OS_NAME" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
        echo "Installing FFmpeg with Homebrew..."
        brew install ffmpeg
    elif command -v apt-get >/dev/null 2>&1; then
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
    "$PYTHON_BIN" -m venv .venv
fi

. ".venv/bin/activate"

python -m pip install -r requirements.txt

clear

exec python main.py "$@"

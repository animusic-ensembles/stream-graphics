#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 was not found."
    echo "Please install Python 3, then run this script again."
    exit 1
fi

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

. ".venv/bin/activate"

python -m pip install -r requirements.txt

clear

if [ "$#" -eq 0 ]; then
    python main.py
else
    python main.py "$1"
fi

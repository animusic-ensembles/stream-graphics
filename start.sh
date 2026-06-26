#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

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

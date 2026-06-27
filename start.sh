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

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

. ".venv/bin/activate"

python -m pip install -r requirements.txt

clear

exec python main.py "$@"

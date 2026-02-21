#!/usr/bin/env bash
set -e

if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Port 80 requires elevated permissions. Re-running with sudo..."
    exec sudo "$(which uv)" run --with flask --with requests python app.py --port 80 "$@"
fi

uv run --with flask --with requests python app.py --port 80 "$@"

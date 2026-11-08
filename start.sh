#!/usr/bin/env bash
# Local Music Drop Server Launcher for macOS / Linux

cd "$(dirname "$0")" || exit 1

echo "================================================="
echo " Starting Local Music Server & Audio Studio..."
echo "================================================="

# Check for Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3 is not installed or not in PATH."
    exit 1
fi

# Run server
exec "$PYTHON_CMD" server.py


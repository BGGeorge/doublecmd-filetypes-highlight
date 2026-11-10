#!/usr/bin/env sh
# Double Commander file-type highlighter - GUI (Linux/macOS).
# Usage: ./dcmd_hl_gui.sh [-c CONFIG_DIR] [--rules FILE]
set -eu
HERE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "Python 3.8+ is required. Install python3 first." >&2
    exit 1
fi
exec "$PY" "$HERE/dcmd_hl_gui.py" "$@"

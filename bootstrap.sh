#!/bin/sh
# First launch: build the player environment (a venv) from requirements-player.txt
# instead of shipping a bundled Python. Finds python3, then `python3 -m venv
# venv` and installs the pinned deps from wheels (no Rust toolchain needed).
# Prints the venv python path on success.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is not on your PATH: install Python 3.x and try again." >&2
    exit 1
fi
if [ ! -f "$here/venv/bin/python" ]; then
    echo "Building the player environment from requirements-player.txt (first launch)..."
    python3 -m venv "$here/venv"
    "$here/venv/bin/pip" install -q -r "$here/requirements-player.txt"
fi
printf '%s\n' "$here/venv/bin/python"

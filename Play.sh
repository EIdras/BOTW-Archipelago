#!/bin/sh
# Play a prepared seed: the Linux equivalent of Play.cmd. bootstrap.sh builds the
# player venv on first launch.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
venv=$("$here/bootstrap.sh") || exit 1
"$venv" "$here/tools/play_session.py" "$@"
echo "Press Enter to exit." >&2
read -r _ || true

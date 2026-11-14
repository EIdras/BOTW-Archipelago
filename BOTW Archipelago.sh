#!/bin/sh
# Breath of the Wild Archipelago. Drop a slot file (.apbotw.json) or a seed's zip
# on it, or start it. On first launch bootstrap.sh builds the player venv.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
venv=$("$here/bootstrap.sh") || exit 1
# -I: no PYTHON* variable or user package of this computer reaches the tools.
"$venv" -I "$here/tools/launcher.py" "$@"
echo "Press Enter to exit." >&2
read -r _ || true

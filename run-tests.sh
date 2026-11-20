#!/bin/sh
# Product tests. "run-tests.sh full" also builds whole packs (minutes): before a
# commit that changes what a pack holds (tests/full_build.py). Linux equivalent of
# run-tests.cmd. bootstrap.sh builds the player venv on first launch.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
full=""
if [ "${1:-}" = "full" ]; then
    full=1
    shift
fi
export BOTW_FULL_TESTS="$full"
venv=$("$here/bootstrap.sh") || exit 1
"$venv" -m unittest discover -s tests
echo "Press Enter to exit." >&2
read -r _ || true

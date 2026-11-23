"""python -m botw_launcher.tk: the tk window, from a source checkout."""
from __future__ import annotations

import sys

if __name__ == "__main__":
    # The guard matters: a job's child process imports this module again.
    from botw_launcher.tk.app import run
    sys.exit(run(sys.argv[1:]))

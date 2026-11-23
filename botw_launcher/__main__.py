"""The launcher's entry point (see botw_launcher/__init__.py), from a source
checkout: BOTW Archipelago.cmd. Inside Archipelago, botw_world/client opens the
window instead."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# The project first; never this folder itself, whose modules would hide the standard library's.
sys.path[:] = [str(ROOT)] + [entry for entry in sys.path
                            if Path(entry).resolve() not in (ROOT, ROOT / "botw_launcher")]


def main(arguments: list[str]) -> int:
    if arguments[:1] == ["--job"]:
        from botw_launcher import jobs
        return jobs.main(arguments[1:])
    from botw_launcher.tk.app import run
    return run(arguments)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

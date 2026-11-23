"""At start, the newest installed version takes over (botw_launcher/versions.py).

This is the one piece of an old release that keeps running after updates: the
player's shortcut still starts the release they unzipped, and that release
starts the newest version through this module. It must therefore stay small,
and what it relies on is a contract every version honours:

  * a version is started as `python -I botw_launcher/__main__.py <arguments>`
    from its own folder, and takes the arguments this one was given;
  * BOTW_AP_PINNED set tells it not to hand over in its turn;
  * it exits with 0 unless it could not start.

A version that fails to start within STARTUP_GRACE seconds is given up for this
launch and the caller's own version runs instead: a broken update never locks
the player out.
"""
from __future__ import annotations

import os
import subprocess

from botw_client.paths import RELEASE_MARKER, ROOT
from botw_client.version import VERSION

from . import versions

STARTUP_GRACE = 6.0     # seconds


def take_over(arguments: list[str]) -> str | None:
    """Hand over to a newer installed version and exit; return when this
    version is the one to run, with a notice for the player if the newer one
    failed to start."""
    # A source checkout is the version its developer works on: it never hands over.
    if os.environ.get(versions.PINNED_VARIABLE) or not (ROOT / RELEASE_MARKER).is_file():
        return None
    newer = versions.newest(than=VERSION)
    if newer is None:
        return None
    try:
        process = versions.start(newer.folder, arguments)
        code = process.wait(STARTUP_GRACE)
    except subprocess.TimeoutExpired:
        raise SystemExit(0) from None       # it runs: this process has nothing more to do
    except OSError as exc:
        return f"Version {newer.version} is installed but could not be started ({exc}): this is {VERSION}."
    if code == 0:
        raise SystemExit(0)
    return (f"Version {newer.version} is installed but failed to start (exit code {code}): "
            f"this is {VERSION}. Its log is in the Logs page's folder.")

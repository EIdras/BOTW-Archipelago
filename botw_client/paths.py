"""Where the project's files are read, and where its own are written.

ROOT holds the code and the project's data, and is only read. DATA holds what
the tools write for the player: the isolated Cemu profile, the seeds and their
packs, session logs, the client's state, the GameData flag table.

    BOTW_AP_DATA set              that folder
    a release (release.json)      %LOCALAPPDATA%\\BOTW Archipelago (Windows) or
                                  the XDG data directory, kept across updates,
                                  whatever folder the release is in
    a source checkout             ROOT/.build on Windows, the XDG data
                                  directory on Linux

BUILD is the developer's workspace of a source checkout (the Archipelago
runtime, generated seeds, historical candidates). On Windows the player's data
shares it; on Linux it lives in the home directory, so the profile and the
seeds do not sit in the project.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
RELEASE_MARKER = "release.json"
DATA_VARIABLE = "BOTW_AP_DATA"
RELEASE_FOLDER = "BOTW Archipelago"


def _os_data_location(environ: dict) -> Path:
    """The player's data in the OS data location: %LOCALAPPDATA% on Windows,
    the XDG data directory on Linux."""
    if os.name == "nt":
        # A Windows release keeps its state under LOCALAPPDATA across updates.
        local = environ.get("LOCALAPPDATA")
        return (Path(local) if local else Path.home() / "AppData" / "Local") / RELEASE_FOLDER
    # On Linux the client's state lives in the XDG data directory. Cemu
    # segfaults (signal 11) on a space in its profile path, so the folder is
    # hyphenated here; the Windows release keeps the spaced "BOTW Archipelago".
    xdg = environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(xdg) / "botw-archipelago"


def data_folder(root: Path = ROOT, environ=os.environ) -> Path:
    if environ.get(DATA_VARIABLE):
        return Path(environ[DATA_VARIABLE])
    # On Windows a source checkout keeps the project's developer workspace; on
    # Linux the player's data follows the OS data location in a release or a
    # checkout, so the profile and the seeds live in the home directory, kept
    # across updates and out of the project.
    if os.name == "nt" and not (root / RELEASE_MARKER).is_file():
        return root / ".build"
    return _os_data_location(environ)


DATA = data_folder()

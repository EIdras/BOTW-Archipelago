"""Where the project's files are read, and where its own are written.

ROOT holds the code and the project's data, and is only read. DATA holds what
the tools write for the player: the isolated Cemu profile, the seeds and their
packs, session logs, the client's state, the GameData flag table.

    BOTW_AP_DATA set              that folder
    a release (release.json)      %LOCALAPPDATA%\\BOTW Archipelago, kept across
                                  updates, whatever folder the release is in
    a source checkout             ROOT/.build

BUILD is the developer's workspace of a source checkout (the Archipelago
runtime, generated seeds, historical candidates); in a checkout, DATA is the
same folder.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
RELEASE_MARKER = "release.json"
DATA_VARIABLE = "BOTW_AP_DATA"
RELEASE_FOLDER = "BOTW Archipelago"


def data_folder(root: Path = ROOT, environ=os.environ) -> Path:
    if environ.get(DATA_VARIABLE):
        return Path(environ[DATA_VARIABLE])
    if (root / RELEASE_MARKER).is_file():
        local = environ.get("LOCALAPPDATA")
        return (Path(local) if local else Path.home() / "AppData" / "Local") / RELEASE_FOLDER
    return root / ".build"


DATA = data_folder()

"""Where the project's files are read, and where its own are written.

ROOT holds the code and the project's data, and is only read. DATA holds what
the tools write for the player: the isolated Cemu profile, the seeds and their
packs, session logs, the client's state, the GameData flag table.

    BOTW_AP_DATA set              that folder
    a release (release.json)      the folder the player chose in the launcher
                                  (location.json in the default one), else the
                                  default: %LOCALAPPDATA%\\BOTW Archipelago, or
                                  $XDG_DATA_HOME/BOTW Archipelago off Windows;
                                  kept across updates, whatever folder the
                                  release is in
    a source checkout             ROOT/.build

BUILD is the developer's workspace of a source checkout (the Archipelago
runtime, generated seeds, historical candidates); in a checkout, DATA is the
same folder.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
RELEASE_MARKER = "release.json"
DATA_VARIABLE = "BOTW_AP_DATA"
RELEASE_FOLDER = "BOTW Archipelago"
LOCATION_FILE = "location.json"


def default_data_folder(environ=os.environ, platform: str = sys.platform) -> Path:
    """Where a release writes until the player chooses another folder."""
    if platform == "win32":
        local = environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
    else:
        shared = environ.get("XDG_DATA_HOME")
        base = Path(shared) if shared else Path.home() / ".local" / "share"
    return base / RELEASE_FOLDER


def chosen_data_folder(default: Path) -> Path | None:
    """The folder location.json names, written by the launcher when the player
    moves the data (botw_launcher/core/storage.py)."""
    try:
        chosen = json.loads((default / LOCATION_FILE).read_text(encoding="utf-8"))["data"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return Path(chosen) if isinstance(chosen, str) and chosen else None


def data_folder(root: Path = ROOT, environ=os.environ, platform: str = sys.platform) -> Path:
    if environ.get(DATA_VARIABLE):
        return Path(environ[DATA_VARIABLE])
    if (root / RELEASE_MARKER).is_file():
        default = default_data_folder(environ, platform)
        return chosen_data_folder(default) or default
    return root / ".build"


DATA = data_folder()

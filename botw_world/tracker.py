"""Universal Tracker's map tab (its worlds/tracker/docs/map-integration.md): the PopTracker pack
the BOTW Archipelago window builds from the player's own game (tools/build_poptracker.py),
for its map, its locations' places and its items' icons; what is in logic is the world's own.
The map is the player's game's, never in the apworld: the pack is found where the window
writes it, or asked for once (settings ut_pack_path, host.yaml).

Link's mark: the client writes his whereabouts in the room's data storage (botw_client/uat.py,
ROOM_KEY, seldom), and the pack's grid (maps/link_grid.json) places them on its map.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any
import zipfile

import settings

from .catalog import MAPS

PACK = "botw_archipelago.zip"
ROOM_KEY = "botw_link_{team}_{player}"
LINK_ICON = "images/link.png"
# His mark facing where he faces: the pack's arrow turned ARROWS times around, from up the map
# (tools/build_poptracker.py link_arrows).
ARROWS, ARROW_ICON = 16, "images/link/{:02d}.png"
# The items beside the map, as the pack's own grid (tools/build_poptracker.py ROWS), and the Spirit Orbs.
ITEMS = ["Paraglider", "Magnesis", "Progressive Remote Bomb", "Progressive Stasis", "Cryonis",
         "Progressive Sheikah Sensor", "Progressive Revali's Gale", "Progressive Daruk's Protection",
         "Progressive Urbosa's Fury", "Progressive Mipha's Grace", "Master Sword", "Hylian Shield",
         "Flamebreaker Set", "Zora Set", "Gerudo Set", "Warm Doublet", "Snowquill Set", "Desert Voe Set",
         "Rubber Set", "Progressive Climbing Gear", "Progressive Stealth Set", "Barbarian Set", "Ancient Set",
         "Radiant Set", "Heart Container", "Stamina Vessel", "Champion's Tunic", "Ancient Bridle",
         "Ancient Saddle", "Korok Mask", "Master Cycle Zero", "Travel Medallion", "Epona",
         "Weapon Pouch Upgrade", "Bow Pouch Upgrade", "Shield Pouch Upgrade", "Spirit Orb"]
MAP_ITEMS = sorted(MAPS.values())


def data_folder(environ=os.environ) -> Path:
    """Where the BOTW Archipelago window writes (botw_client/paths.py): BOTW_AP_DATA, a source
    checkout's .build, else the folder the player chose, else the default."""
    if environ.get("BOTW_AP_DATA"):
        return Path(environ["BOTW_AP_DATA"])
    root = Path(__file__).resolve().parents[1]
    if (root / "botw_client").is_dir() and not (root / "release.json").is_file():
        return root / ".build"
    if sys.platform == "win32":
        base = Path(environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    default = base / "BOTW Archipelago"
    try:
        chosen = json.loads((default / "location.json").read_text(encoding="utf-8"))["data"]
    except (OSError, ValueError, KeyError, TypeError):
        chosen = None
    return Path(chosen) if isinstance(chosen, str) and chosen else default


def built_pack(environ=os.environ) -> str:
    """The pack the window built, "" when there is none (Universal Tracker then asks for it)."""
    path = data_folder(environ) / "poptracker" / PACK
    return str(path) if path.is_file() else ""


class TrackerPackPath(settings.FilePath):
    """The PopTracker pack Universal Tracker draws its map from: botw_archipelago.zip, which the
    BOTW Archipelago window builds from your game (Settings > PopTracker pack)."""
    required = False
    ut_dialog_name = "Select the BOTW PopTracker pack (botw_archipelago.zip)"


class BotwSettings(settings.Group):
    ut_pack_path: TrackerPackPath | str = TrackerPackPath(built_pack())


_grids: dict[str, dict | None] = {}


def link_grid(pack: str) -> dict | None:
    if pack not in _grids:
        try:
            with zipfile.ZipFile(pack) as archive:
                _grids[pack] = json.loads(archive.read("maps/link_grid.json"))
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            _grids[pack] = None
    return _grids[pack]


def link_coords(_index: int, data: Any, pack: str | None = None) -> tuple[int, int, str] | None:
    """Link's mark on the map, from his whereabouts in the room (None: not shown)."""
    if not isinstance(data, dict) or not isinstance(data.get("x"), (int, float)) \
            or not isinstance(data.get("z"), (int, float)):
        return None
    if pack is None:
        from . import BotwWorld
        pack = str(BotwWorld.settings.ut_pack_path or "")
    grid = link_grid(pack) if pack else None
    if grid is None:
        return None
    x = round((data["x"] - grid["origin_x"]) * grid["scale"] - grid["left"])
    y = round((data["z"] - grid["origin_z"]) * grid["scale"] - grid["top"])
    heading = data.get("heading")
    icon = (ARROW_ICON.format(round(heading * ARROWS / 360) % ARROWS)
            if isinstance(heading, (int, float)) and grid.get("arrows") == ARROWS else LINK_ICON)
    return (x, y, icon) if x >= 0 and y >= 0 else None


TRACKER_WORLD = {
    "external_pack_key": "ut_pack_path",
    "map_page_maps": "maps/maps.json",
    "map_page_locations": "locations/locations.json",
    "map_page_index": lambda _data: 0,
    "location_setting_key": ROOM_KEY,
    "location_icon_coords": link_coords,
    "item_page_items": "items/items.json",
    "map_page_item_layouts_left": [
        {"name": "Items", "items": ITEMS, "orientation": "lr", "cols": 6},
        {"name": "Maps", "items": MAP_ITEMS, "orientation": "lr", "cols": 5},
    ],
}

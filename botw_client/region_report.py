"""Link's region, for the trackers: written to the server's data storage when it changes.

The PopTracker pack (tools/build_poptracker.py) has a map of each region and
switches to the one Link enters: it watches the key of this slot,
botw_region_<team>_<slot>, as AP packs watch a key for their maps. The region is
the tower area at Link's position, the regions of the world (tools/map_regions.py,
botw_client/region_border.Areas), in the MainField only: in a shrine, a Divine
Beast or a loading, the last region stays.

Its cost: once a second (SECONDS), the stage's type and Link's position (5 small
reads, as the region border's) and a lookup in the area rows; one message to the
server when the region changes, none otherwise.
"""
from __future__ import annotations

import math
import struct
from typing import Callable

from tools.cemu.guest import in_guest

from .cucco_swarm import PLAYER_INFO
from .region_border import MAIN_FIELD, MAP_TYPE

SECONDS = 1.0
KEY = "botw_region_{team}_{slot}"


def key(team: int, slot: int) -> str:
    return KEY.format(team=team, slot=slot)


def link_region(read: Callable, areas) -> str | None:
    """The region at Link's position in the MainField, or None (elsewhere, unreadable).
    read(guest, size) -> bytes or None."""
    raw = read(MAP_TYPE, 32)
    if not raw or raw.split(b"\0", 1)[0] != MAIN_FIELD.encode():
        return None

    def u32(guest):
        value = read(guest, 4)
        return int.from_bytes(value, "big") if value and len(value) == 4 else None

    info = u32(PLAYER_INFO)
    player = u32(info + 0x30) if in_guest(info) else None
    if not in_guest(player):
        return None
    coords = [read(player + offset, 4) for offset in (0x204, 0x224)]
    if not all(c and len(c) == 4 for c in coords):
        return None
    x, z = (struct.unpack(">f", c)[0] for c in coords)
    if not (math.isfinite(x) and math.isfinite(z) and abs(x) < 10000 and abs(z) < 10000):
        return None
    return areas.region_at(x, z)


def set_command(team: int, slot: int, region: str) -> dict:
    """The data storage write of a new region."""
    return {"cmd": "Set", "key": key(team, slot), "default": "", "want_reply": False,
            "operations": [{"operation": "replace", "value": region}]}

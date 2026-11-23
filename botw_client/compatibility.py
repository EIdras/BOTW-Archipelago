"""Which seeds this version plays.

One statement, read by the check before a session (tools/play_seed.py) and by
the client, and written into a release's release.json (tools/build_release.py),
where the launcher of any other version reads it (botw_launcher/core/worlds.py).
"""
from __future__ import annotations

from .locations import WORLD_SCHEMA

# The client schemas of the seeds this version plays: 4 added the Gerudo Set, 5 the
# goal and the sanctum's requirements, 6 the new filler, 7 the weapons, 8 the travel items,
# 9 Epona and the Master Cycle Zero selected only when no rune is, 10 the tower maps,
# 11 the Downpour, Yiga Ambush and Paranoia traps, 12 the travel points a map opens,
# 13 the chests as locations, their AP items taken out of the pouch, 14 the Koroks as locations,
# 15 the quests as locations, 16 the Goddess Statues' offerings as locations, 17 the field
# bosses as locations, 18 the Progressive Horse, 19 the bonus items, 20 the extra filler,
# 21 the elemental traps, 22 the Master Mode chests as locations.
CLIENT_SCHEMAS = (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22)
# The key of release.json that holds the statement.
KEY = "plays"


def statement() -> dict:
    """What this version plays, as release.json states it."""
    return {"world_schemas": [WORLD_SCHEMA], "client_schemas": list(CLIENT_SCHEMAS)}


def plays(statement: dict, world_schema: int | None, client_schema: int | None = None) -> bool:
    """Whether the version a statement describes plays a seed of these schemas.
    A client schema not known (a seed prepared before it was recorded, a
    statement without it) is not checked: the world schema decides."""
    if world_schema not in statement.get("world_schemas", ()):
        return False
    clients = statement.get("client_schemas")
    return client_schema is None or clients is None or client_schema in clients

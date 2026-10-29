"""A shrine's travel point opened as its terminal opens it (map_travel_points:
a region's map opens the travel point of one shrine of the region).

Activating a terminal sets three flags (measured 29/10, lab shrine travel
probe): Location_DungeonNNN, the s32 the shrine's map marker reads (its
LocationMarker's SaveFlag: without it, no icon), Open_DungeonNNN and the
terminal's own flag (MainField_<its actor>_<its HashId>): the icon blue, the
warp open, the shrine's check (Clear_) untouched. As the horse's
(botw_client/horse_stable.py), the writes go through the game's GameData
manager: a raw write of the live flags showed no icon and was lost at the save.
Writing Location_ shows the shrine's name with its sound, as when Link
discovers it, whatever the value, in a menu on its close: the player sees which
shrine opened. Read in the Wii U EUR v208 executable, called from the cave's
per-frame invoker:
  * HANDLES: a bool or s32 flag's handle by its name (a SafeString);
  * SETTERS: Manager::setBool(value, handle, debug), and Manager::setS32 its
    twin (its TriggerParam setter reads the s32 block), both copies of the flag.
Measured with the probe: the icon blue and the warp open after a save and a
reload, no check sent.
"""
from __future__ import annotations

import struct
from typing import Callable

from .cucco_swarm import HEAP_HOLDER, NEW_IN_HEAP, SAFESTRING_VTABLE
from .horse_stable import MANAGER

HANDLES = {"bool": 0x02E1E100, "s32": 0x02E1E16C}
SETTERS = {"bool": 0x02E142DC, "s32": 0x02E14848}
# A far travel point waits for the Paraglider, as the logic does.
PARAGLIDER = "IsGet_PlayerStole2"
# The block of one opening in the actor heap: a SafeString (the flag's name), its text.
NAME_SS, NAME_TEXT, MEMORY = 0x00, 0x10, 0x100


def due(get: Callable, shrines) -> tuple[str, str] | None:
    """The first of `shrines` (map's flag, shrine, terminal's flag) whose map
    is held and travel point still closed, once the Paraglider is held, as
    (shrine, terminal's flag). get(flag, kind): the live value, None unreadable."""
    if not get(PARAGLIDER, "bool"):
        return None
    for map_flag, shrine, terminal in shrines:
        opened = get(f"Open_{shrine}", "bool")
        if get(map_flag, "bool") and opened is not None and not opened:
            return shrine, terminal
    return None


def open_point(read: Callable, write: Callable, call: Callable, get: Callable,
               shrine: str, terminal: str) -> str:
    """'opened', 'already' (Open_ set: a terminal activated), or the step that
    failed (to ask again). Open_ is written last: an opening cut short is done
    again. Location_ only while 0: it counts the visits and is never lowered.
    read(guest, size), write(guest, data), call(address, *args) -> r3 or None
    as the horse's; get as due's."""
    def u32(guest):
        raw = read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    opened, visits = get(f"Open_{shrine}", "bool"), get(f"Location_{shrine}", "s32")
    if opened is None or visits is None:
        return "read"
    if opened:
        return "already"
    manager, holder = u32(MANAGER), u32(HEAP_HOLDER)
    heap = u32(holder + 0x10) if holder else None
    if not (manager and heap):
        return "manager"
    block = call(NEW_IN_HEAP, MEMORY, heap, 4)
    if not block:
        return "memory"
    writes = [(terminal, "bool")] + ([(f"Location_{shrine}", "s32")] if not visits else [])
    for flag, kind in writes + [(f"Open_{shrine}", "bool")]:
        raw = flag.encode("ascii") + b"\0"
        if len(raw) > MEMORY - NAME_TEXT:
            raise ValueError(f"flag name too long: {flag}")
        write(block + NAME_TEXT, raw)
        write(block + NAME_SS, struct.pack(">II", block + NAME_TEXT, SAFESTRING_VTABLE))
        handle = call(HANDLES[kind], manager, block + NAME_SS)
        if handle in (None, 0xFFFFFFFF) or call(SETTERS[kind], 1, handle, 0) != 1:
            return f"write {flag}"
    return "opened" if get(f"Open_{shrine}", "bool") else "check"

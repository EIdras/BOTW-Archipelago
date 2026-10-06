"""An AP item that does not fit in the pouch falls at Link's feet.

When the pouch is full, the delivery entry shows the game's own "pouch full"
message and gives nothing (botw_patch/delivery_flow.py). For the items that
can lie on the ground (delivery_plan.droppable), the client then creates the
item next to Link, and only after that commits the delivery through the
step's drop entry, which only advances the cursor: the queue goes on. A crash
between the two gives the item twice, never zero times. An item left on the
ground is lost with the area (a reload, a fast travel): the player's choice,
as an enemy's loot.

The creation is the game's own (ActorCreator::requestCreateActor, as the
Cucco Swarm creates its attackers, botw_client/cucco_swarm.py), with only a
place (@P). Measured in the lab (drop probe, 06/10): a two-handed sword, a
bow, a shield and an arrow bundle fall, stay, and are picked up as usual,
with their normal durability; with the pouch full, Link cannot pick them up
and the game says so.
"""
from __future__ import annotations

import math
import struct
from typing import Callable

from .cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                          REQUEST_CREATE, SAFESTRING_VTABLE)

POSITION, FORWARD = 0x204, 0x200    # Link's matrix: place and forward (x; y, z every 0x10)
AHEAD, UP = 0.5, 1.0                # metres in front of Link and above his feet: it falls by him
# The InstParamPack's room: the game builds the pack there, over whatever lies
# in it. The name, the key and the place come after, as the swarm lays them out
# (written inside it, they were overwritten: the next call hung and the game
# crashed, seen in play).
PACK_ROOM = 0x100
MEMORY = 0x200


def drop(read: Callable, write: Callable, call: Callable, actor: str) -> str:
    """Create `actor` by Link: 'ok', or the step that failed. read(guest, size),
    write(guest, data) and call(address, *args) -> r3 or None, as the swarm's."""
    def u32(guest):
        raw = read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    def vector(address):
        raw = [read(address + 0x10 * axis, 4) for axis in range(3)]
        if not all(raw) or any(len(r) != 4 for r in raw):
            return None
        return tuple(struct.unpack(">f", r)[0] for r in raw)

    name = actor.encode("ascii") + b"\0"
    if len(name) > 0x40:
        raise ValueError(f"actor name too long: {actor}")
    info = u32(PLAYER_INFO)
    player = u32(info + 0x30) if info else None
    position = vector(player + POSITION) if player else None
    forward = vector(player + FORWARD) if player else None
    creator, holder = u32(CREATOR), u32(HEAP_HOLDER)
    heap = u32(holder + 0x10) if holder else None
    if not (position and forward and creator and heap):
        return "player"
    base = call(NEW_IN_HEAP, MEMORY, heap, 4)
    if not base:
        return "memory"
    pack = base
    text, key_text, key, value = (base + PACK_ROOM + offset for offset in (0x00, 0x50, 0x60, 0x70))
    norm = math.hypot(forward[0], forward[2]) or 1.0
    at = (position[0] + AHEAD * forward[0] / norm, position[1] + UP,
          position[2] + AHEAD * forward[2] / norm)
    write(base, bytes(MEMORY))
    write(text, name)
    write(key_text, b"@P\0")
    write(key, struct.pack(">II", key_text, SAFESTRING_VTABLE))
    write(value, struct.pack(">fff", *at))
    if call(PACK_CTOR, pack + 4) is None:
        return "busy (pack)"
    if call(PACK_ADD, pack + 4, value, key, 0xC, 4) is None:
        return "busy (place)"
    return "ok" if call(REQUEST_CREATE, creator, text, heap, 0, pack, 0, 1) == 1 else "request"

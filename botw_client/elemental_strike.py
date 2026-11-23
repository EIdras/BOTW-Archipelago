"""The Freeze, Fire and Lightning Strike traps: an element let loose on Link.

The game's own actor creation (ActorCreator::requestCreateActor), as the Yiga
Ambush creates its squad (botw_client/yiga_ambush.py), with only a place (@P), no
handle: one actor where Link stands. Measured in the game, outside, at
normal speed:

  * Freeze: ExpandIceField, the chemical field the game leaves where ice bursts
    (no model), 0.5 m above Link's feet: Link frozen, half a heart;
  * Fire: ExpandFireField, the same of fire: Link on fire at once, a heart and a
    half, then half a heart a second till he moves or goes into water, the grass
    burnt a little around him;
  * Lightning Strike: LastBossThunder, the lightning of the final fight, at Link's
    feet: its sign on the ground, then the strike 37 frames later, three hearts and
    the shock if Link is still within a metre or so; three metres away, nothing.
    He can run from it. The game takes its damage for a blast (death cause 9) with
    LastBossThunder as the attacker (botw_client/death_cause.py).

The fields vanish by themselves. The memory of each creation is the actor heap's,
never reused: without a handle, nothing says when the creator is done with its
name and its place.
"""
from __future__ import annotations

import struct
from typing import Callable

from .cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                          REQUEST_CREATE, SAFESTRING_VTABLE)
from .item_drop import MEMORY, PACK_ROOM, POSITION

# By effect (data/item_map.json): the actor, how far above Link's feet, the trap's name.
ACTORS = {"freeze": ("ExpandIceField", 0.5), "fire": ("ExpandFireField", 0.5),
          "lightning": ("LastBossThunder", 0.0)}
NAMES = {"freeze": "Freeze", "fire": "Fire", "lightning": "Lightning Strike"}


def strike(read: Callable, write: Callable, call: Callable, effect: str) -> dict[str, int]:
    """Create the effect's actor on Link: {outcome: 1}, 'ok' if the game took it.
    read(guest, size), write(guest, data), call(address, *args) -> r3 or None, as
    the ambush's."""
    actor, up = ACTORS[effect]

    def u32(guest):
        raw = read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    info = u32(PLAYER_INFO)
    player = u32(info + 0x30) if info else None
    raw = [read(player + POSITION + 0x10 * axis, 4) for axis in range(3)] if player else []
    creator, holder = u32(CREATOR), u32(HEAP_HOLDER)
    heap = u32(holder + 0x10) if holder else None
    if not (player and creator and heap and all(raw) and all(len(r) == 4 for r in raw)):
        return {"player": 1}
    x, y, z = (struct.unpack(">f", r)[0] for r in raw)
    return {_create(write, call, creator, heap, actor, (x, y + up, z)): 1}


def _create(write, call, creator: int, heap: int, actor: str, at) -> str:
    base = call(NEW_IN_HEAP, MEMORY, heap, 4)
    if not base:
        return "memory"
    pack = base
    text, key_text, key, value = (base + PACK_ROOM + offset for offset in (0x00, 0x50, 0x60, 0x70))
    write(base, bytes(MEMORY))
    write(text, actor.encode("ascii") + b"\0")
    write(key_text, b"@P\0")
    write(key, struct.pack(">II", key_text, SAFESTRING_VTABLE))
    write(value, struct.pack(">fff", *at))
    if call(PACK_CTOR, pack + 4) is None:
        return "busy (pack)"
    if call(PACK_ADD, pack + 4, value, key, 0xC, 4) is None:
        return "busy (place)"
    return "ok" if call(REQUEST_CREATE, creator, text, heap, 0, pack, 0, 1) == 1 else "request"

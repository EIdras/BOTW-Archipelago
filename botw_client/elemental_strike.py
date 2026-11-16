"""The Freeze, Lightning Strike and Fire traps: an element let loose on Link.

The game's own actor creation (ActorCreator::requestCreateActor), as the Yiga
Ambush creates its squad (botw_client/yiga_ambush.py), with only a place (@P), no
handle: one actor at Link's feet, the chemical field the game leaves where an
element bursts (Actor/Pack/Expand*Field.sbactorpack: no model, a chemical
shape that spreads, Actor/Chemical/Expand*Field.bchemical):
  * Freeze: ExpandIceField, of the ice magic (IceMagic), which freezes what it
    touches, as an Ice Wizzrobe's spell freezes Link;
  * Fire: ExpandFireField, of the fire magic, which sets Link and the grass
    around him on fire;
  * Lightning Strike: ExpandElectricField, the burst of an Electric Chuchu
    (ElectricChuchu_Exp), which shocks Link: he drops his weapon and shield.

Read in the game's files only: none of the three has been seen in play yet. The
Thunderstorm Rod's bolt (ThunderRodLv2Thunder) would look more like a strike,
but it is created by its rod, which an actor created alone has not: left out.

The memory of each creation is the actor heap's, never reused: without a handle,
nothing says when the creator is done with its name and its place.
"""
from __future__ import annotations

import struct
from typing import Callable

from .cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                          REQUEST_CREATE, SAFESTRING_VTABLE)
from .item_drop import MEMORY, PACK_ROOM, POSITION

# What each trap creates at Link's feet, by its effect (data/item_map.json).
FIELDS = {"freeze": ("ExpandIceField",), "fire": ("ExpandFireField",),
          "lightning": ("ExpandElectricField",)}
NAMES = {"freeze": "Freeze", "fire": "Fire", "lightning": "Lightning Strike"}
UP = 0.5                    # above his feet, metres


def strike(read: Callable, write: Callable, call: Callable, effect: str) -> dict[str, int]:
    """Create the effect's actors on Link: {outcome: count}, 'ok' for each one the
    game took. read(guest, size), write(guest, data), call(address, *args) -> r3 or
    None, as the ambush's."""
    actors = FIELDS[effect]

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
    results: dict[str, int] = {}
    for actor in actors:
        outcome = _create(write, call, creator, heap, actor, (x, y + UP, z))
        results[outcome] = results.get(outcome, 0) + 1
    return results


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

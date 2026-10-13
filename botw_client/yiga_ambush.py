"""The Yiga Ambush trap: a squad of the Yiga Clan falls on Link.

The game's own actor creation (ActorCreator::requestCreateActor, as the Cucco
Swarm creates its attackers, botw_client/cucco_swarm.py, and as an item falls at
Link's feet, botw_client/item_drop.py), with only a place (@P), no handle: the
Yiga are the game's, with their own AI. Measured in the lab (probe 19, 09/10):
two Yiga Footsoldiers and a Yiga archer created around Link come with the
Yiga's appearing effect, fight with their weapons, flips and warps, drop their
loot (bananas, rupees) when defeated, and vanish if Link runs far away.

Each comes with its weapon (EquipItem1, a string of type 5, as the game's own
creations add it, 0x020c00fc), as the map gives the Yiga theirs: created
without one, a Yiga carries what the level sensor finds for its series at the
player's progress, nothing on a new game (seen in play: footsoldiers bare
handed, some idle, an archer without a bow warping again and again). Given its
series' first weapon, the level sensor raises it as the game goes on
(Ecosystem/LevelSensor: the Vicious Sickle becomes a Demon Carver).

One time in BLADEMASTER_CHANCE, a Yiga Blademaster comes alone instead.

Each Yiga has a block of memory of its own: without a handle, nothing says when
the creator is done with its name and its place, so no block is ever reused.
"""
from __future__ import annotations

import math
import random
import struct
from typing import Callable

from .cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR, PLAYER_INFO,
                          REQUEST_CREATE, SAFESTRING_VTABLE)
from .item_drop import MEMORY, PACK_ROOM, POSITION

FOOTSOLDIER = ("Enemy_Assassin_Junior", "Weapon_Sword_053")             # the Vicious Sickle
ARCHER = ("Enemy_Assassin_Shooter_Junior", "Weapon_Bow_040")            # the Duplex Bow
BLADEMASTER = ("Enemy_Assassin_Middle", "Weapon_Lsword_074")            # the Windcleaver
SQUAD = (FOOTSOLDIER, FOOTSOLDIER, ARCHER)
BLADEMASTER_SQUAD = (BLADEMASTER,)
BLADEMASTER_CHANCE = 0.1
DISTANCE = (6.0, 8.0)       # metres from Link, on the ground's plane
UP = 1.0                    # above his feet: they land by him


def places(centre, count: int, rng: random.Random) -> list[tuple[float, float, float]]:
    """`count` places around `centre`, evenly spread from a random bearing."""
    start = rng.uniform(0.0, 2.0 * math.pi)
    out = []
    for index in range(count):
        angle = start + 2.0 * math.pi * index / count
        distance = rng.uniform(*DISTANCE)
        out.append((centre[0] + distance * math.cos(angle), centre[1] + UP,
                    centre[2] + distance * math.sin(angle)))
    return out


def draw(rng: random.Random) -> tuple:
    """The squad of one ambush: the Blademaster one time in BLADEMASTER_CHANCE."""
    return BLADEMASTER_SQUAD if rng.random() < BLADEMASTER_CHANCE else SQUAD


def ambush(read: Callable, write: Callable, call: Callable, *,
           squad=None, rng: random.Random | None = None) -> dict[str, int]:
    """Create the squad around Link: {outcome: count}, 'ok' for each Yiga the game
    took. read(guest, size), write(guest, data), call(address, *args) -> r3 or
    None, as the swarm's."""
    rng = rng or random.Random()
    squad = squad if squad is not None else draw(rng)
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
    centre = tuple(struct.unpack(">f", r)[0] for r in raw)
    results: dict[str, int] = {}
    for (actor, weapon), at in zip(squad, places(centre, len(squad), rng)):
        outcome = _create(write, call, creator, heap, actor, weapon, at)
        results[outcome] = results.get(outcome, 0) + 1
    return results


def _create(write, call, creator: int, heap: int, actor: str, weapon: str, at) -> str:
    base = call(NEW_IN_HEAP, MEMORY, heap, 4)
    if not base:
        return "memory"
    pack = base
    text, key_text, key, value, weapon_key_text, weapon_key, weapon_name = (
        base + PACK_ROOM + offset for offset in (0x00, 0x50, 0x60, 0x70, 0x80, 0x90, 0xA0))
    write(base, bytes(MEMORY))
    write(text, actor.encode("ascii") + b"\0")
    write(key_text, b"@P\0")
    write(key, struct.pack(">II", key_text, SAFESTRING_VTABLE))
    write(value, struct.pack(">fff", *at))
    write(weapon_key_text, b"EquipItem1\0")
    write(weapon_key, struct.pack(">II", weapon_key_text, SAFESTRING_VTABLE))
    write(weapon_name, weapon.encode("ascii") + b"\0")
    if call(PACK_CTOR, pack + 4) is None:
        return "busy (pack)"
    if call(PACK_ADD, pack + 4, value, key, 0xC, 4) is None:
        return "busy (place)"
    if call(PACK_ADD, pack + 4, weapon_name, weapon_key, len(weapon) + 1, 5) is None:
        return "busy (weapon)"
    return "ok" if call(REQUEST_CREATE, creator, text, heap, 0, pack, 0, 1) == 1 else "request"

"""What Beedle's buy list and the stalls show, read from the game's own shop GameData.

Measured in the game (docs/reference/shops.md): while the buy list is
open, Shop_ScreenType is 1 and the string64 Shop_SelectItemName holds the actor
of the selected entry (the first one when the list opens). The shops built by
botw_patch/shops.py list their AP items first, so opening the list selects
AP_Shop_<id>, which names the shop location and so the merchant. At a 3D
stall, Link looking at an object on sale, before any purchase, sets
Shop_ScreenType to 7 and Shop_SelectItemName to that object's actor: the AP
medallion names its own location.

String flags are not in the scalar index (LiveGdt): their object is found once
by its hash in the TriggerParam arrays; the text lies 0x40 bytes before the
hash (value buffer of the Flag<string64>). A string read while the game writes
it can be torn (a read gave "bj_ArrowNormal_A_01"): a name counts only when
two consecutive reads agree.
"""
from __future__ import annotations

import struct
import zlib

from .shop_catalog import BY_ACTOR, same_merchant
from .stall_catalog import LOCATIONS as STALLS

SELECTED = "Shop_SelectItemName"
SCREEN = "Shop_ScreenType"
LIST_OPEN = 1
STALL_LOOKED_AT = 7
STALL_BY_ACTOR = {location.actor: location for location in STALLS}
TEXT_BEFORE_HASH = 0x40
TEXT_BYTES = 64
# The hash of a string64 flag sits at +0x138: read the whole object.
OBJECT_BYTES = 0x200
# TriggerParam PtrArrays (count at 0x04 + 12 * k): strings after the three
# scalar arrays, so search those first; the 44k bools last.
ARRAY_SLOTS = (*range(3, 12), 1, 2, 0)


def crc(name: str) -> int:
    return zlib.crc32(name.encode()) & 0xFFFFFFFF


def locate_string_flags(read, tp: int, hashes: dict[int, str]) -> dict:
    """Find, in every TriggerParam array, the flag objects carrying these hashes.

    ``read(guest_address, size)`` returns bytes or None. Layout-free: the hash
    is searched as an aligned big-endian word inside each object.
    """
    found = {}
    for k in ARRAY_SLOTS:
        head = read(tp + 0x04 + 12 * k, 12)
        if not head or len(head) != 12:
            continue
        count, _capacity, array = struct.unpack(">III", head)
        if not (0 < count < 60000) or not (0x10000000 <= array < 0x60000000):
            continue
        ptrs = read(array, count * 4)
        if not ptrs or len(ptrs) != count * 4:
            continue
        for obj in struct.unpack(f">{count}I", ptrs):
            if not (0x10000000 <= obj < 0x60000000):
                continue
            raw = read(obj, OBJECT_BYTES)
            if not raw:
                continue
            for offset in range(0, len(raw) - 3, 4):
                value = struct.unpack_from(">I", raw, offset)[0]
                if value in hashes and hashes[value] not in found:
                    found[hashes[value]] = {"array_slot": k, "array_count": count,
                                            "object": obj, "hash_offset": offset}
        if len(found) == len(hashes):
            break
    return found


class ShopWatch:
    """Which AP shop the open buy list belongs to, if any."""

    def __init__(self, live):
        self.live = live
        located = locate_string_flags(self._read, live.tp, {crc(SELECTED): SELECTED})
        if SELECTED not in located:
            raise RuntimeError(f"{SELECTED} not found in the GameData")
        info = located[SELECTED]
        self.text_address = info["object"] + info["hash_offset"] - TEXT_BEFORE_HASH

    def _read(self, guest: int, size: int):
        return self.live.p.read(self.live.base + guest, size)

    def selected(self) -> str | None:
        """The selected actor, or None if two reads disagree."""
        first, second = (self._read(self.text_address, TEXT_BYTES) for _ in range(2))
        if not first or first != second:
            return None
        return first.split(b"\0", 1)[0].decode("ascii", "replace")

    def seen(self) -> list[int]:
        """Shop location IDs seen: every AP item of the merchant whose list is
        open, or the stall's AP medallion Link looks at; else []."""
        screen = self.live.get(crc(SCREEN), "s32")
        if screen == LIST_OPEN:
            location = BY_ACTOR.get(self.selected() or "")
            return same_merchant(location.id) if location else []
        if screen == STALL_LOOKED_AT:
            location = STALL_BY_ACTOR.get(self.selected() or "")
            return [location.id] if location else []
        return []

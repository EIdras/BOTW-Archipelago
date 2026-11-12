"""The AP shop items left in the pouch: the safety net of a purchase the game
did not record.

A Beedle item or a stall's jewel bought is recorded by the merchant's own flow
(botw_patch/shop_items.add_purchase_record): its location flag APShop_<id> set
to 1, the item taken out of the pouch, in the event of the purchase. Players
have reported jewels of Kakariko's arrow stall left in the pouch, unrecorded,
their location never sent; the cause is unknown. An AP shop item has no other
way into the pouch, and no reason to stay in it once the purchase's event is
over: one still there, unrecorded, Link back in the world for HOLD_SECONDS,
is a purchase the flow missed, and its location is sent.

The pouch, measured in the game (lab/tools/cemu/pouch_probe.py): PorchItem,
the string64 array flag of the pouch's 420 names, is a PtrArray inside one of
TriggerParam's arrays; each element is a flag object holding its hash at
+0x138 and its text 0x40 bytes before. The names are packed from the first,
in the pouch's order, and change as soon as an item enters or leaves the
pouch, without a save.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from tools.cemu.guest import in_heap

from .shop_catalog import LOCATIONS as BEEDLE
from .shop_state import OBJECT_BYTES, TEXT_BEFORE_HASH, TEXT_BYTES, crc
from .stall_catalog import LOCATIONS as STALLS

POUCH = "PorchItem"
POUCH_HASH = crc(POUCH)
POUCH_SIZE = 420
# TriggerParam's arrays past the three scalar ones, the measured one first.
ARRAY_SLOTS = (13, *range(3, 13), *range(14, 24))
# Every AP shop item, by its actor: Beedle's and the stalls'.
SHOP_ITEMS = {location.actor: location for location in (*BEEDLE, *STALLS)}
# How long an unrecorded AP item must stay in the pouch, Link in the world,
# before its location is sent. A purchase takes it out within its own event.
HOLD_SECONDS = 20.0


class PouchMoved(RuntimeError):
    """The pouch's flag objects are no longer where they were found."""


def _pointers(read, at: int) -> list[int] | None:
    """The elements of the PtrArray whose header (count, capacity, data) is at `at`."""
    head = read(at, 12)
    if not head or len(head) != 12:
        return None
    count, _capacity, data = struct.unpack(">III", head)
    if not (0 < count < 60000) or not in_heap(data):
        return None
    raw = read(data, count * 4)
    return list(struct.unpack(f">{count}I", raw)) if raw and len(raw) == count * 4 else None


def _hash_offset(read, obj: int) -> int | None:
    raw = read(obj, OBJECT_BYTES) if in_heap(obj) else None
    if not raw:
        return None
    for offset in range(TEXT_BEFORE_HASH, len(raw) - 3, 4):
        if struct.unpack_from(">I", raw, offset)[0] == POUCH_HASH:
            return offset
    return None


class PouchWatch:
    """The names of the pouch, read from the live GameData.

    ``read(guest_address, size)`` returns bytes or None."""

    def __init__(self, read, tp: int):
        self.read = read
        for k in ARRAY_SLOTS:
            outer = _pointers(read, tp + 0x04 + 12 * k)
            for obj in (outer or [])[:4096]:
                inner = _pointers(read, obj) if in_heap(obj) else None
                if not inner or len(inner) != POUCH_SIZE:
                    continue
                offset = _hash_offset(read, inner[0])
                if offset is not None:
                    self.elements, self.offset = inner, offset
                    return
        raise RuntimeError(f"{POUCH} not found in the GameData")

    def _texts(self) -> list[str]:
        names = []
        for obj in self.elements:
            raw = self.read(obj + self.offset - TEXT_BEFORE_HASH, TEXT_BYTES)
            if not raw:
                raise PouchMoved("pouch name unreadable")
            name = raw.split(b"\0", 1)[0].decode("ascii", "replace")
            if not name:
                break               # packed: the first empty name ends the pouch
            names.append(name)
        return names

    def names(self) -> list[str] | None:
        """The pouch's names, or None when two reads disagree (the game writing
        it). PouchMoved when its first object no longer carries its hash."""
        head = self.read(self.elements[0] + self.offset, 4)
        if head != POUCH_HASH.to_bytes(4, "big"):
            raise PouchMoved(f"{POUCH} moved")
        first, second = self._texts(), self._texts()
        return first if first == second else None


@dataclass
class StrayShopItems:
    """Which AP shop items have stayed in the pouch unrecorded long enough.

    observe() takes the AP shop items in the pouch whose location is in the
    seed and still unchecked, each with its APShop_<id> value (None: unread),
    the time and whether Link was in the world before the pouch was read; it
    returns the location IDs due. An item counts only while it stays in the
    pouch with its flag read 0 and Link in the world, from one observation to
    the next: missing once, flag unread or set, or Link in an event, a menu or
    a dialogue, and it starts again. A purchase's own event keeps the item in
    the pouch until it records it (Beedle's for as long as his list is open):
    Link is never in the world meanwhile. It is due once it has stayed
    HOLD_SECONDS; then it is forgotten (the caller sends its location)."""
    hold: float = HOLD_SECONDS
    since: dict[int, float] = field(default_factory=dict)

    def observe(self, items: dict[int, int | None], now: float, playing: bool) -> list[int]:
        if not playing:
            self.since = {}
            return []
        held = {location for location, flag in items.items() if flag == 0}
        self.since = {location: self.since.get(location, now) for location in held}
        due = sorted(location for location, start in self.since.items() if now - start >= self.hold)
        for location in due:
            del self.since[location]
        return due

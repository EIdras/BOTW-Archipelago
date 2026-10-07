"""A horse registered at the stables, as a stable registers one.

The stables keep their horses in GameData arrays of six slots: 0 to 4 the
registered horses, 5 the last wild horse Link rode (measured on saves, 07/10).
Registering Epona wrote her slot's Horse_ActorName, Horse_UserName (her name in
the game's language, ActorType/Horse.msbt GameRomHorseEpona_Name), Horse_ManeName,
Horse_SaddleName and Horse_ReinsName, then Horse_Is_Registration, which only an
event may set (it is not program-writable: the delivery entry sets it).

The writes go through the game's GameData manager, never by a raw write to the
live flags: the save keeps only what the manager writes (measured at the
pedestal), and the manager writes both copies of a flag. Read in the Wii U EUR
v208 executable, called from the cave's per-frame invoker:
  * HANDLE: a string64 array flag's handle by its name (a SafeString);
  * SET: Manager::setStr64(SafeString value, handle, sub_idx, debug), both copies
    (*(manager + 0x6FC), then *(manager + 0x700) when manager + 0x705 says so);
  * GET: Manager::getStr64(const char** out, handle, sub_idx, debug).
Measured in the lab (horse register probe, 07/10): a stable then offers Epona,
gives her out with her saddle, and still has her after a save and a reload.
"""
from __future__ import annotations

import struct
from typing import Callable

from .cucco_swarm import HEAP_HOLDER, NEW_IN_HEAP, SAFESTRING_VTABLE

MANAGER = 0x1046D5B0
HANDLE = 0x02E1E5A4
SET = 0x02E15524
GET = 0x02E15438
SLOTS = 5                       # 0..4; 5 is the last wild horse ridden
# The block of one registration in the actor heap: the getter's out pointer,
# two SafeStrings (the flag's name, the value), their texts.
OUT, NAME_SS, VALUE_SS, NAME_TEXT, VALUE_TEXT, MEMORY = 0x00, 0x10, 0x18, 0x40, 0x80, 0x100
# Horse_ActorName last: a slot is taken only once all is written, and a
# registration cut short is written again in the same, still free, slot.
FIELDS = ("Horse_UserName", "Horse_ManeName", "Horse_SaddleName", "Horse_ReinsName", "Horse_ActorName")


def register(read: Callable, write: Callable, call: Callable, actor: str, name: str,
             mane: str, saddle: str, reins: str) -> str:
    """'registered' (in the first free slot), 'already' (a slot holds `actor`),
    'full', or the step that failed (to ask again). read(guest, size),
    write(guest, data) and call(address, *args) -> r3 or None, as the drop's."""
    def u32(guest):
        raw = read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    manager, holder = u32(MANAGER), u32(HEAP_HOLDER)
    heap = u32(holder + 0x10) if holder else None
    if not (manager and heap):
        return "manager"
    block = call(NEW_IN_HEAP, MEMORY, heap, 4)
    if not block:
        return "memory"

    def safestring(slot, text_at, text):
        raw = text.encode("utf-8") + b"\0"
        if len(raw) > 0x40:
            raise ValueError(f"longer than a string64: {text!r}")
        write(block + text_at, raw)
        write(block + slot, struct.pack(">II", block + text_at, SAFESTRING_VTABLE))
        return block + slot

    def handle(flag):
        value = call(HANDLE, manager, safestring(NAME_SS, NAME_TEXT, flag))
        return None if value in (None, 0xFFFFFFFF) else value

    def get(flag, index):
        flag_handle = handle(flag)
        if flag_handle is None:
            return None
        write(block + OUT, bytes(4))
        if call(GET, block + OUT, flag_handle, index, 0) != 1:
            return None
        pointer = u32(block + OUT)
        if not pointer:
            return None
        return (read(pointer, 0x40) or b"").split(b"\0", 1)[0].decode("utf-8", "replace")

    slots = [get("Horse_ActorName", index) for index in range(SLOTS)]
    if None in slots:
        return "read"
    if actor in slots:
        return "already"
    if "" not in slots:
        return "full"
    free = slots.index("")
    for flag, value in zip(FIELDS, (name, mane, saddle, reins, actor)):
        flag_handle = handle(flag)
        if flag_handle is None or call(SET, safestring(VALUE_SS, VALUE_TEXT, value),
                                       flag_handle, free, 0) != 1:
            return f"write {flag}"
    return "registered" if get("Horse_ActorName", free) == actor else "check"

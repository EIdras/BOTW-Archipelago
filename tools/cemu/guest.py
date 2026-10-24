"""The game's memory as Cemu maps it (Cemu's MMU.cpp, mmuRange_*).

MEM2, the main memory that holds the game's heaps and objects, is
0x10000000-0x50000000, unless a graphic pack's [RAM] section moves its end
(GraphicPack2, memory_mapForCurrentTitle): Extended Memory, which mods that
need more memory ask for, moves it to 0xA0000000, where the overlay area
starts; a mapping that would overlap it is refused. The code and data of
the executable and the code caves lie below MEM2, from 0x01000000.

Python reads the game from outside: an address Cemu did not map only fails
the read, so its pointers are checked against the furthest MEM2 can go
(plausible()). The code a seed pack injects runs inside the game, where
following such a pointer stops Cemu: it is built for the end MEM2 really has
(tools/player_packs.py heap_end(); below()).
"""
from __future__ import annotations

CODE_START = 0x01000000         # the executable's code and data, the code caves
MEM2_START = 0x10000000
MEM2_END = 0x50000000           # mmuRange_MEM2, without any [RAM] mapping
MEM2_MAX_END = 0xA0000000       # mmuRange_OVERLAY_AREA's base: no mapping may go further


def in_heap(address: int | None) -> bool:
    """A plausible pointer to the game's heaps, whatever end MEM2 has."""
    return address is not None and MEM2_START <= address < MEM2_MAX_END


def in_guest(address: int | None) -> bool:
    """A plausible pointer to the game's code, data or heaps."""
    return address is not None and CODE_START <= address < MEM2_MAX_END


def below(end: int, pointer: str, scratch: str, otherwise: str, margin: int = 0) -> list[str]:
    """PowerPC lines that branch to `otherwise` unless `pointer` < end - margin
    (unsigned), using the register `scratch`: the injected code reads
    `margin` bytes from the pointer, all within MEM2 ending at `end`."""
    limit = end - margin
    if not MEM2_START < end <= MEM2_MAX_END or end & 0xFFF or not 0 <= margin < 0x1000:
        raise ValueError(f"not an end of MEM2: {end:#x} (margin {margin:#x})")
    lines = [f"lis {scratch}, 0x{limit >> 16:04x}"]
    if limit & 0xFFFF:
        lines.append(f"ori {scratch}, {scratch}, 0x{limit & 0xFFFF:04x}")
    return lines + [f"cmplw {pointer}, {scratch}", f"bge {otherwise}"]

"""master_mode: a seed whose Master Mode chests are locations is played in a Master
Mode save, the only one that has them.

A save's mode is the saved bool AoC_HardMode_Enabled (kept in each save's
caption.sav): 1 from a Master Mode game's New Game on, and, when one of its saves
loads, written one frame after the rest of the save (measured). The client reads
it before binding a save, with Link in the world: the same value twice,
SETTLE_SECONDS apart, is the save's. A Normal mode save stops the client before it
binds the save or gives anything; a seed without master_mode plays in either mode,
the Master Mode chests then keeping their contents: said once, the mode read for
PLAYED_SECONDS after the save is bound.
"""
from __future__ import annotations

import zlib

FLAG = "AoC_HardMode_Enabled"
FLAG_HASH = zlib.crc32(FLAG.encode()) & 0xFFFFFFFF
SETTLE_SECONDS = 1.0
PLAYED_SECONDS = 5.0
REFUSAL = ("WRONG GAME MODE: this seed's Master Mode chests are locations, and a Normal mode save "
           "has none of them. Load a Master Mode save (Master Mode, on the title screen), "
           "then start the client again.")
PLAYED = "Master Mode save: its chests keep their contents (this seed is not set for master_mode)."


def read(game) -> int | None:
    """The save's mode as the live GameData holds it now; None when unreadable."""
    live = getattr(game, "live", None)
    if live is None:
        return None
    try:
        return live.get(FLAG_HASH, "bool")
    except Exception:  # noqa: BLE001 - a read during a load
        return None


class SaveMode:
    """The save's mode, once read the same SETTLE_SECONDS apart."""

    def __init__(self):
        self._seen: tuple[bool, float] | None = None

    def reset(self) -> None:
        self._seen = None

    def settled(self, value: int | None, now: float) -> bool | None:
        """True (Master Mode) or False once `value` stayed the same SETTLE_SECONDS;
        None until then, and for an unreadable value."""
        if value is None:
            self._seen = None
            return None
        mode = bool(value)
        if self._seen is None or self._seen[0] != mode:
            self._seen = (mode, now)
            return None
        return mode if now - self._seen[1] >= SETTLE_SECONDS else None

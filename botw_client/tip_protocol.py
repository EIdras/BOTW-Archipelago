"""The AP tip channel's shared contract: native data layout and borrowed tip.

Pure data, imported by the native generator (tools/build_tip_channel.py) and
the client adapter (botw_client/tip_channel.py), so both read one layout.

The channel shows AP text in the game's own tip frame (top right,
LayoutMsg/MessageTipsRunTime_00; docs/reference/ap_messages.md). It borrows
one of the game's 23 tips: the request goes
through the game's public request 0x02fd4730, and our text replaces the
tip's only for our request; the tip's "seen" flag is given back as it was.
"""
from __future__ import annotations

import zlib

MAGIC = 0x41505450              # "APTP"
VERSION = 1
# Borrowed tip: table index 21 = label 0023, "control of a Divine Beast",
# shown once, at one moment inside the beasts; ordinary (not button) path.
TIP_INDEX = 21
TIP_KEY = "GuideS_RelicControl"
TIP_KEY_HASH = zlib.crc32(TIP_KEY.encode()) & 0xFFFFFFFF

# Game (EUR v208).
REQUEST = 0x02fd4730            # (widget, index, force): public tip request
FLAG_GETTER = 0x02e1cc84        # (SafeString* key, 0) -> bool, as the request reads it
TABLE_POINTER = 0x10542e24      # -> 23 entries of 16 bytes; key SafeString at +8
QUEUED = 0x1ba8                 # widget: requested index (-1: none)
SHOWN = 0x1bb0                  # widget: index on screen (-1: none)
TEXT_SITE = 0x02fd48c8          # in 0x02fd4848, before bl 0x03082d88 (r30 widget, r31 index, r5 text)
FRAME_SITE = 0x02fd4a30         # in 0x02fd4a1c, per frame (r31 widget)
BOOL_VALUE = 0x07               # live Flag<bool>: value bit in byte +7, hash at +8
BOOL_HASH = 0x08

# Game layout: 3 lines of at most 34 characters (vanilla tips, fr/en/de).
LINE_WIDTH = 34
LINES = 3
TEXT_UNITS = 255                # buffer: 255 UTF-16 units + terminator

# apTipData, words.
OFFSETS = {
    "magic": 0, "version": 4, "phase": 8, "generation": 12, "completed": 16,
    "outcome": 20, "widget": 24, "index": 28, "saved": 32, "flag_object": 40,
    "flag_hash": 44, "units": 48, "fault": 52, "wait": 56, "cr": 60,
    "submit": 64, "text": 68,
}
DATA_WORDS = 18
# phase: 0 idle, 1 requested (queued by the game), 2 shown (our text set).
IDLE, REQUESTED, SHOWN_PHASE = 0, 1, 2
# outcome of the last completed generation.
CLOSED, DROPPED, REFUSED = 1, 2, 3
# submit return values (r3).
ACCEPTED, REFUSED_BY_GAME, BUSY, INVALID = 1, 0, 2, 0xFFFFFFFF
# A request not seen queued nor shown for this many frames is dropped.
DROP_FRAMES = 60

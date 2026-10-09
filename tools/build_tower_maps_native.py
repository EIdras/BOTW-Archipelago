"""The native side of the tower maps (the world's tower_maps option): a stage of the native build.

Only ``patch_apInject.asm`` changes; each anchor must match once.

* The map's opening for a map item. The action StartMapOpenDemo (its trigger
  0x023F8898) takes its actor's position and asks 0x0307E020 for the map's tower
  nearest to it; with one, it calls 0x03077AA0(tower index, IsPlayerClose), which
  prepares the map screen on that tower and opens the menu. A tower's event plays
  it with the tower as its actor (Demo004_0, Starter). A map item's delivery entry
  plays it with EventSystemActor, near no tower: the action did nothing
  (measured). Patched, the action takes, when no tower is near, the tower index
  the client wrote in ``apMapTower`` just before the delivery, and spends it
  (back to -1). A tower's own event never reaches the fallback. In every pack.
* The tower icons, only in a pack whose maps are items. A tower icon of the map
  (0x02E94C4C) reads the flag "MapTower_" + its number to show the tower
  activated, which offers its travel point (measured: Lanayru's icon, made to read
  APTower_12, turned blue and was warped to). Patched, it reads "APTower_" + its
  number, the flag a tower of such a pack saves when activated
  (botw_patch/tower_maps.py); the Great Plateau's (index 6) stays as the game made
  it, its map being no item.

The client writes ``apMapTower`` through the cave's fixed offsets
(tools/cemu/mailbox.py, ``map_magic`` and ``map_tower``).
"""
from __future__ import annotations

MAGIC = 0x4D4F5031  # "MOP1"
# The data block's end, after the rune selection's fields.
DATA_ANCHOR = """apSelResult:
.int 0
.align 4
"""
CODE_ANCHOR = "\napProbe:\n"
OPEN_CHECK = 0x023F88EC          # cmpwi r3, 0x0 after 0x0307E020, in the action's trigger
ICON_PREFIX = 0x02E94C8C         # lwz r5, 0x0(r31): the icon's flag prefix, "MapTower_"
PLATEAU_INDEX = 6

DATA_FIELDS = DATA_ANCHOR + f"""; --- tower maps (tools/build_tower_maps_native.py) ------------------------
; Appended at the END of the block: no existing field moves. apMapMagic is
; 0x{MAGIC:08X}; on a stale patch these words fall on code, and Python then
; leaves apMapTower alone.
apMapMagic:
.int 0x{MAGIC:08X}
; The tower index (0..14) the next map opening without a tower near its actor
; takes; -1: none. Written by the client, spent by apMapOpenCheck.
apMapTower:
.int 0xFFFFFFFF
apTowerName:
.string "APTower_"
.align 4
"""
OPEN_ROUTINE = f"""
apMapOpenCheck:                  ; 0x{OPEN_CHECK:08x}, after 0x0307e020: a tower near the actor?
    cmpwi r3, 0                  ; original
    beq   apMapOpenFallback
    blr                          ; a tower near the actor: as the game
apMapOpenFallback:
    ; No tower near the actor (a map item's delivery): the tower index the
    ; client wrote, spent at once. The out word of 0x0307e020 is 0x8(r1): the
    ; game reads the index there and calls 0x03077aa0 with it.
    lis   r12, apMapTower@ha
    lwz   r3, apMapTower@l(r12)
    cmpwi r3, 0
    blt   apMapOpenNone
    cmpwi r3, 15
    bge   apMapOpenNone
    stw   r3, 0x8(r1)
    li    r3, -1
    stw   r3, apMapTower@l(r12)
    li    r3, 1
    cmpwi r3, 0                  ; not equal: on to the opening
    blr
apMapOpenNone:
    li    r3, 0
    cmpwi r3, 0                  ; equal: nothing, as the game
    blr

0x{OPEN_CHECK:08x} = bla apMapOpenCheck
"""
ICON_ROUTINE = f"""
apTowerPrefix:                   ; 0x{ICON_PREFIX:08x}, a tower icon's flag: prefix + its number
    lwz   r5, 0x0(r31)           ; original: "MapTower_"
    cmpwi r12, {PLATEAU_INDEX}                ; r12: the icon's tower index; the Great Plateau's map is no item
    beq   apTowerPrefixEnd
    lis   r5, apTowerName@ha
    addi  r5, r5, apTowerName@l
apTowerPrefixEnd:
    blr

0x{ICON_PREFIX:08x} = bla apTowerPrefix
"""


def patch_injection(text: str, *, icons: bool) -> str:
    """The map opening's fallback, and with ``icons`` the tower icons' flag."""
    for anchor, label in ((DATA_ANCHOR, "data block end"), (CODE_ANCHOR, "per-frame hook")):
        if text.count(anchor) != 1:
            raise ValueError(f"anchor not unique in parent injection: {label}")
    if "apMapMagic" in text:
        raise ValueError("parent injection already has the tower maps")
    text = text.replace(DATA_ANCHOR, DATA_FIELDS)
    routines = OPEN_ROUTINE + (ICON_ROUTINE if icons else "")
    return text.replace(CODE_ANCHOR, routines + CODE_ANCHOR)

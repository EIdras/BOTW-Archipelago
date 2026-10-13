"""The native side of the Downpour trap: the weather held, frame after frame. A stage
of the native build, in every pack.

Only ``patch_apInject.asm`` changes; each anchor must match once.

The game's weather setter, read in the executable (the flows' Demo_EventSetWeather,
class EventSetWeather, calls it once: 0x021c2d50), as zeldaret/botw has it
(worldManager.cpp, setWeatherType): SET_WEATHER(*WORLD_MGR, type, 1, 0, 0) sets the
type (+0x649) and a timer of 4 (+0x60c). Every frame of the world, the manager counts
the timer down and, at 0, gives the type back to 0xff: the climate's weather
(0x03677f84). One request is thus 4 frames of weather; the game's weather zones
(ChangeWeatherTag) call the setter as long as Link is in them. So does this stage,
for as long as ``apWeatherFrames`` says, from the per-frame hook: at the head of
apCheckCall, which every frame goes through (the per-frame invoker's block).

The frames are the world's: one is counted when the manager's timer went below 4
since the last call, that is when the world was updated, so that a menu, which
stops the world, does not shorten the weather. Another caller of the setter in the
same frame (a weather zone, a Wizzrobe) would keep the timer at 4 and the count
still: ``apWeatherPasses``, the hook's passes, ends the hold in any case (the
client gives three times the frames). Measured with the setter called 30 times a
second (lab probe 19): rain within 5 to 10 s, the walls slippery, a storm with its
lightning, held across a fast travel, nothing in a shrine; the climate's weather
back within a few seconds.

The client writes the type, the passes, then the frames, through the cave's fixed
offsets (tools/cemu/mailbox.py, ``weather_type``, ``weather_passes`` and
``weather_frames``).
"""
from __future__ import annotations

MAGIC = 0x57544831  # "WTH1"
WORLD_MGR = 0x1047BE88
SET_WEATHER = 0x03679688
WEATHER_TIMER = 0x60C
# The data block's end, after the tower maps' fields (tools/build_tower_maps_native.py).
DATA_ANCHOR = """apTowerName:
.string "APTower_"
.align 4
"""
CODE_ANCHOR = "\napCheckCall:\n"

DATA_FIELDS = DATA_ANCHOR + f"""; --- the forced weather (tools/build_weather_native.py) -----------------
; Appended at the END of the block: no existing field moves. apWeatherMagic
; is 0x{MAGIC:08X}; on a stale patch these words fall on code, and Python then
; leaves them alone.
apWeatherMagic:
.int 0x{MAGIC:08X}
; The weather type (0 Bluesky .. 8 BlueskyRain, zeldaret/botw worldDefines.h).
apWeatherType:
.int 0
; The world's frames it still lasts; 0: the game's own weather.
apWeatherFrames:
.int 0
; The hook's passes it may still last, whatever the world: the ceiling.
apWeatherPasses:
.int 0
"""
HOLD_BLOCK = f"""
apCheckCall:
    ; --- the forced weather (tools/build_weather_native.py) --------------
    ; As long as apWeatherFrames lasts, the game's setter, as its weather
    ; zones call it: its timer of 4 frames never runs out.
    lis   r12, apWeatherFrames@ha
    lwz   r12, apWeatherFrames@l(r12)
    cmpwi r12, 0
    ble   apWeatherEnd

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; The ceiling: so many passes of the hook at most, whatever the timer says.
    lis   r12, apWeatherPasses@ha
    lwz   r4, apWeatherPasses@l(r12)
    addi  r4, r4, -1
    stw   r4, apWeatherPasses@l(r12)
    cmpwi r4, 0
    bgt   apWeatherWorld
    li    r4, 0
    lis   r12, apWeatherFrames@ha
    stw   r4, apWeatherFrames@l(r12)
    b     apWeatherRestore
apWeatherWorld:
    lis   r3, 0x{(WORLD_MGR + 0x8000) >> 16:04x}
    lwz   r3, -0x{0x10000 - (WORLD_MGR & 0xFFFF):x}(r3)       ; the world manager, *0x{WORLD_MGR:08x}
    cmpwi r3, 0
    beq   apWeatherRestore
    ; A frame of the world since the last call: the manager counted its
    ; timer down. A menu stops the world, and the weather's time with it.
    lwz   r12, 0x{WEATHER_TIMER:x}(r3)
    cmpwi r12, 4
    bge   apWeatherSet
    lis   r12, apWeatherFrames@ha
    lwz   r4, apWeatherFrames@l(r12)
    addi  r4, r4, -1
    stw   r4, apWeatherFrames@l(r12)
    cmpwi r4, 0
    ble   apWeatherRestore      ; spent: the climate's weather, 4 frames later
apWeatherSet:
    lis   r12, apWeatherType@ha
    lwz   r4, apWeatherType@l(r12)
    li    r5, 1
    li    r6, 0
    li    r7, 0
    lis   r12, 0x{SET_WEATHER >> 16:04x}
    ori   r12, r12, 0x{SET_WEATHER & 0xFFFF:04x}   ; setWeatherType, beyond bla's reach
    mtctr r12
    bctrl

apWeatherRestore:
    lis   r11, apTick@ha        ; the call destroyed r11
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)
apWeatherEnd:
"""


def patch_injection(text: str) -> str:
    """The weather hold, at the head of the per-frame invoker's block."""
    for anchor, label in ((DATA_ANCHOR, "tower maps' data end"), (CODE_ANCHOR, "per-frame invoker")):
        if text.count(anchor) != 1:
            raise ValueError(f"anchor not unique in parent injection: {label}")
    if "apWeatherMagic" in text:
        raise ValueError("parent injection already has the weather hold")
    return text.replace(DATA_ANCHOR, DATA_FIELDS).replace(CODE_ANCHOR, HOLD_BLOCK)

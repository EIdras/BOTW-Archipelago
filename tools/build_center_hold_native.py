"""The center message held, frame after frame: the border of a locked region. A stage of
the native build, after the weather's.

Only ``patch_apInject.asm`` changes; each anchor must match once.

The game shows its own border message (LayoutMsg/MainScreen_00 0007, « You can't go any
farther. ») for as long as Link stays out of bounds by asking for it at every frame: the
center message of index 46 in the table the game builds at 0x02ed2b00. Asked once, it
vanishes at once; asked at every frame, it stays without a flicker or a sound (index 41,
the same text, is a notification instead: asked again, it plays its sound again).

Why, in the executable: the screen's public API (0x02ed1e1c), while a message is shown
(its state, +0x8c, neither 0, 2, 4 nor 6), compares the message shown (+0xbc) with the
one asked for. Another one replaces it. The same one is consumed, and shown again from
the start, except 46 (0x02ed1e0c), which simply stays.

As long as ``apCenterPasses`` lasts, this stage arms the request of message
``apCenterIndex`` again at every pass of the per-frame hook, at the head of apCheckPlay:
the two blocks that follow (the push, then the public API that pops and shows) make the
calls, as for a request of the client. Nothing more: the fields the client's trigger
writes, and no call of its own. A pass is counted, and nothing armed, while a request is
already pending (another writer, or a channel not yet resolved), and while the screen
shows another message: the game's own (a weapon about to break...) goes to its end, then
the held one follows. apCheckMsg writes the index asked for into +0xbc before the call:
armed over another message, it would make the screen take that one for ours and keep it.

The client writes the index, then the passes, through the cave's fixed offsets
(tools/cemu/mailbox.py, ``hold_index`` and ``hold_passes``), again and again while Link
is near the border, a few passes ahead: the message ends by itself within those passes
if the client stops. 0 passes lets it go at once.

Closed by the game while held (the screen free again although ours was on it at the last
pass: a window opens, the HUD is hidden), the message is not armed again: the game closes
it again at the next frame, and each new start plays its sound, six in five frames
(measured, lab/journal/etude_verrou_regions.md). The hold stops instead (its passes to 0)
and counts it in ``apCenterClosed``, which the client reads to ask again later.
"""
from __future__ import annotations

MAGIC = 0x484C4432  # "HLD2": with apCenterSeen and apCenterClosed ("HLD1" before)
BORDER_MESSAGE = 46
# The data block's end, after the weather's fields (tools/build_weather_native.py).
DATA_ANCHOR = """apWeatherPasses:
.int 0
"""
CODE_ANCHOR = "\napCheckPlay:\n"

DATA_FIELDS = DATA_ANCHOR + f"""; --- the held center message (tools/build_center_hold_native.py) ------
; Appended at the END of the block: no existing field moves. apCenterMagic is
; 0x{MAGIC:08X}; on a patch without the stage these words are something else,
; and Python then leaves them alone.
apCenterMagic:
.int 0x{MAGIC:08X}
; The center message asked for (46: the border).
apCenterIndex:
.int 0
; The hook's passes it is still asked for; 0: none.
apCenterPasses:
.int 0
; 1: the held message was on the screen at the last pass.
apCenterSeen:
.int 0
; The times the game closed it while held (the hold then stopped).
apCenterClosed:
.int 0
"""
HOLD_BLOCK = """
apCheckPlay:
    ; --- the held center message (tools/build_center_hold_native.py) -----
    ; As long as apCenterPasses lasts, the request of message apCenterIndex is
    ; armed again, as the game asks for its border message at every frame;
    ; the push and the pop below make the calls. r11 is apTick@ha here.
    stw   r3, apS3@l(r11)
    lis   r12, apCenterPasses@ha
    lwz   r12, apCenterPasses@l(r12)
    cmpwi r12, 0
    bgt   apCenterHeld
    ; Not asked for: the next request starts afresh.
    li    r3, 0
    lis   r12, apCenterSeen@ha
    stw   r3, apCenterSeen@l(r12)
    b     apCenterRestore

apCenterHeld:
    addi  r3, r12, -1
    lis   r12, apCenterPasses@ha
    stw   r3, apCenterPasses@l(r12)
    ; A request already pending keeps its index.
    lwz   r12, apPlayReq@l(r11)
    cmpwi r12, 0
    bne   apCenterRestore
    lwz   r12, apMSReq@l(r11)
    cmpwi r12, 0
    bne   apCenterRestore
    ; The screen shows another message: it goes to its end first.
    lwz   r12, apMS1This@l(r11)     ; resolved every frame, 0 before the UI
    cmpwi r12, 0
    beq   apCenterRestore
    lwz   r3, 0x8c(r12)             ; its state: 0, 2, 4, 6 free, as 0x02ed1e70 tests it
    cmpwi r3, 0
    beq   apCenterFree
    cmpwi r3, 2
    beq   apCenterFree
    cmpwi r3, 4
    beq   apCenterFree
    cmpwi r3, 6
    beq   apCenterFree
apCenterShown:
    lwz   r12, 0xbc(r12)            ; the message shown
    lis   r3, apCenterIndex@ha
    lwz   r3, apCenterIndex@l(r3)
    cmpw  r12, r3
    bne   apCenterOther
    li    r3, 1                     ; ours on the screen
    lis   r12, apCenterSeen@ha
    stw   r3, apCenterSeen@l(r12)
    b     apCenterArm
apCenterOther:
    li    r3, 0                     ; another one: its end is not ours closed
    lis   r12, apCenterSeen@ha
    stw   r3, apCenterSeen@l(r12)
    b     apCenterRestore
apCenterFree:
    ; Ours on the screen at the last pass: the game closed it. Not armed again (it
    ; would start again, with its sound, at every frame): the hold stops, counted.
    lis   r12, apCenterSeen@ha
    lwz   r3, apCenterSeen@l(r12)
    cmpwi r3, 0
    beq   apCenterArm
    li    r3, 0
    stw   r3, apCenterSeen@l(r12)
    lis   r12, apCenterPasses@ha
    stw   r3, apCenterPasses@l(r12)
    lis   r12, apCenterClosed@ha
    lwz   r3, apCenterClosed@l(r12)
    addi  r3, r3, 1
    stw   r3, apCenterClosed@l(r12)
    b     apCenterRestore

apCenterArm:
    lis   r12, apCenterIndex@ha
    lwz   r3, apCenterIndex@l(r12)
    stw   r3, apPlayA@l(r11)
    stw   r3, apMSIndex@l(r11)
    li    r3, 0
    stw   r3, apPlayRaw@l(r11)      ; our SafeString, not the game's pointer
    li    r3, 1
    stw   r3, apMSFlag@l(r11)
    stw   r3, apMSReq@l(r11)
    stw   r3, apPlayReq@l(r11)
apCenterRestore:
    lwz   r3, apS3@l(r11)
apCenterEnd:
"""


def patch_injection(text: str) -> str:
    """The message hold, at the head of the push block of the per-frame hook."""
    for anchor, label in ((DATA_ANCHOR, "weather's data end"), (CODE_ANCHOR, "push block")):
        if text.count(anchor) != 1:
            raise ValueError(f"anchor not unique in parent injection: {label}")
    if "apCenterMagic" in text:
        raise ValueError("parent injection already has the message hold")
    return text.replace(DATA_ANCHOR, DATA_FIELDS).replace(CODE_ANCHOR, HOLD_BLOCK)

"""The AP tip channel: AP text in the game's tip frame (the AP journal).

Part of every pack: the native build (tools/build_native_from_source.py)
composes it into the injection source.

Measured (docs/reference/ap_messages.md): 0x02fd4848 alone only sets
the text of a frame nobody opened; the game's public request 0x02fd4730
(widget, index, force) queues a tip (refused if the index is queued or shown,
or if the tip's GuideS_ flag is already true), and the per-frame update
0x02fd4a1c shows it 15 frames later through 0x02fd4848, which hands a
{pointer, length} text object to the pane just before `bl 0x03082d88`.
0x02fd4bc0 sets the shown index back to -1 when the frame closes.

The channel, all on the game thread:
  * apTipSubmit, run by the per-frame invoker when the client asks: refuses
    while a tip of ours is active or any tip is queued or shown (forced over
    the game's heat warning, which the game asks for again at once, ours
    evicted it and was evicted in turn: the warning came back in a loop,
    measured);
    reads the tip's flag with the game's getter, clears its live value bit
    (object checked by its hash), publishes the request, calls the game's
    request with force, and checks it was queued; otherwise the flag is given
    back at once;
  * at the text site (composed into the existing probe hook there): only for
    our request (same widget, same index, phase requested), our text object
    replaces the game's, then phase shown; the game sets the pane itself;
  * per frame (composed into the existing probe hook of 0x02fd4a1c): the
    widget is kept; when our index is neither queued nor shown any more, the
    flag gets back its saved value and the generation is completed.
Nothing else of the game changes: the borrowed tip keeps its own text and
shows once, as in vanilla (see botw_client/tip_protocol.py).
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from botw_client import tip_protocol as tp  # noqa: E402

SYNC = ".int 0x7c0004ac"
MFCR_R12 = ".int 0x7d800026"
MTCRF_R12 = ".int 0x7d8ff120"

# The existing hooks, exactly as native/cemu/legacy/patch_apInject.asm has them.
FRAME_HOOK = """apTipsProbe1:                    ; 0x02fd4a1c, per-frame update
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    stw   r31, apTipsThis@l(r11)       ; a dedicated field: THIS is the `this`
                                       ; replayed, the persistent object's
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0002
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips1@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips1@l(r11)
    blr
"""
TEXT_HOOK = """    stw   r0, 0x8(r1)           ; original
    lis   r11, apTick@ha
    lwz   r12, 0x0(r5)
    stw   r12, apTipsSpyPtr@l(r11)
    lwz   r12, 0x4(r5)
    stw   r12, apTipsSpyLen@l(r11)
    blr
"""


def pointer(label: str, reg: int) -> list[str]:
    return [f"lis r{reg}, {label}@ha", f"addi r{reg}, r{reg}, {label}@l"]


def o(name: str) -> int:
    return tp.OFFSETS[name]


def data_source() -> list[str]:
    words = {o("magic"): f"{tp.MAGIC:#x}", o("version"): str(tp.VERSION),
             o("index"): str(tp.TIP_INDEX), o("flag_hash"): f"{tp.TIP_KEY_HASH:#x}",
             o("submit"): "apTipSubmit", o("text"): "apTipText"}
    lines = ["apTipData:"]
    lines += [f".int {words.get(4 * i, '0')}" for i in range(tp.DATA_WORDS)]
    lines += ["apTipText:"] + [".int 0"] * ((tp.TEXT_UNITS + 1) // 2 + 1)
    return lines


def submit_source() -> list[str]:
    """apTipSubmit: r3 = 1 accepted, 0 refused by the game, 2 busy, -1 invalid."""
    d = 31
    lines = ["apTipSubmit:", "stwu r1, -32(r1)", "mflr r0", "stw r0, 36(r1)",
             "stw r31, 28(r1)", "stw r30, 24(r1)"] + pointer("apTipData", d)
    lines += [f"lwz r0, {o('fault')}(r31)", "cmpwi r0, 0", "bne apTipSubmitInvalid",
              f"lwz r0, {o('phase')}(r31)", "cmpwi r0, 0", "bne apTipSubmitBusy",
              f"lwz r30, {o('widget')}(r31)", "cmpwi r30, 0", "beq apTipSubmitBusy",
              f"lwz r0, {o('units')}(r31)", "cmpwi r0, 0", "beq apTipSubmitInvalid",
              f"cmplwi r0, {tp.TEXT_UNITS}", "bgt apTipSubmitInvalid",
              # the live flag object: a guest pointer whose hash is the tip's key
              f"lwz r12, {o('flag_object')}(r31)", "lis r0, 0x1000", "cmplw r12, r0",
              "blt apTipSubmitInvalid", "lis r0, 0x6000", "cmplw r12, r0",
              "bge apTipSubmitInvalid", f"lwz r0, {tp.BOOL_HASH}(r12)",
              f"lwz r11, {o('flag_hash')}(r31)", "cmpw r0, r11", "bne apTipSubmitInvalid",
              # no tip queued nor on screen, the game's included: forced over
              # one, ours evicts it, and a tip the game keeps asking for (the
              # heat warning) evicts ours in turn, again at every retry
              f"lwz r11, {o('index')}(r31)", f"lwz r0, {tp.QUEUED}(r30)", "cmpwi r0, -1",
              "bne apTipSubmitBusy", f"lwz r0, {tp.SHOWN}(r30)", "cmpwi r0, -1",
              "bne apTipSubmitBusy",
              # the flag as the game reads it, through its own getter and key
              f"lis r12, {tp.TABLE_POINTER >> 16:#x}",
              f"lwz r12, {tp.TABLE_POINTER & 0xFFFF:#x}(r12)", "slwi r0, r11, 4",
              "add r3, r12, r0", "addi r3, r3, 8", "li r4, 0", f"bl {tp.FLAG_GETTER:#010x}",
              "rlwinm r3, r3, 0, 31, 31", f"stw r3, {o('saved')}(r31)",
              # cleared, so that the game's request accepts the tip
              f"lwz r12, {o('flag_object')}(r31)", f"lbz r0, {tp.BOOL_VALUE}(r12)",
              "rlwinm r0, r0, 0, 24, 30", f"stb r0, {tp.BOOL_VALUE}(r12)",
              # published before the request: the text site may run on the
              # next update, and must see our generation
              f"lwz r12, {o('generation')}(r31)", "addi r12, r12, 1",
              f"stw r12, {o('generation')}(r31)", "li r0, 0", f"stw r0, {o('wait')}(r31)",
              f"stw r0, {o('outcome')}(r31)", "li r0, 1", SYNC, f"stw r0, {o('phase')}(r31)",
              "mr r3, r30", f"lwz r4, {o('index')}(r31)", "li r5, 1", f"bl {tp.REQUEST:#010x}",
              f"lwz r11, {o('index')}(r31)", f"lwz r0, {tp.QUEUED}(r30)", "cmpw r0, r11",
              "beq apTipSubmitAccepted",
              # refused by the game: flag given back, generation completed
              f"lwz r12, {o('flag_object')}(r31)", f"lbz r0, {tp.BOOL_VALUE}(r12)",
              "rlwinm r0, r0, 0, 24, 30", f"lwz r11, {o('saved')}(r31)", "or r0, r0, r11",
              f"stb r0, {tp.BOOL_VALUE}(r12)", f"li r0, {tp.REFUSED}",
              f"stw r0, {o('outcome')}(r31)", f"lwz r0, {o('generation')}(r31)",
              f"stw r0, {o('completed')}(r31)", "li r0, 0", SYNC, f"stw r0, {o('phase')}(r31)",
              "li r3, 0", "b apTipSubmitReturn",
              "apTipSubmitAccepted:", "li r3, 1", "b apTipSubmitReturn",
              "apTipSubmitBusy:", "li r3, 2", "b apTipSubmitReturn",
              "apTipSubmitInvalid:", "li r3, -1",
              "apTipSubmitReturn:", "lwz r30, 24(r1)", "lwz r31, 28(r1)", "lwz r0, 36(r1)",
              "mtlr r0", "addi r1, r1, 32", "blr"]
    return lines


def text_observer() -> list[str]:
    """At 0x02fd48c8 (r30 widget, r31 index, r5 the game's text object; r6-r12,
    CR volatile before the call): our text object, for our request only."""
    return pointer("apTipData", 11) + [
        f"lwz r12, {o('phase')}(r11)", f"cmpwi r12, {tp.REQUESTED}", "bne apTipTextEnd",
        f"lwz r12, {o('widget')}(r11)", "cmpw r12, r30", "bne apTipTextEnd",
        f"lwz r12, {o('index')}(r11)", "cmpw r12, r31", "bne apTipTextEnd",
        f"lwz r12, {o('text')}(r11)", "stw r12, 0x0(r5)",
        f"lwz r12, {o('units')}(r11)", "stw r12, 0x4(r5)",
        f"li r12, {tp.SHOWN_PHASE}", SYNC, f"stw r12, {o('phase')}(r11)",
        "apTipTextEnd:"]


def frame_observer() -> list[str]:
    """At 0x02fd4a30 (r31 widget; r0 already saved, r10-r12 rewritten next):
    keep the widget; complete our tip once neither queued nor shown."""
    return pointer("apTipData", 11) + [
        MFCR_R12, f"stw r12, {o('cr')}(r11)",
        f"stw r31, {o('widget')}(r11)",
        f"lwz r12, {o('phase')}(r11)", "cmpwi r12, 0", "beq apTipFrameEnd",
        f"lwz r10, {o('index')}(r11)", f"lwz r12, {tp.QUEUED}(r31)", "cmpw r12, r10",
        "beq apTipFrameActive", f"lwz r12, {tp.SHOWN}(r31)", "cmpw r12, r10",
        "beq apTipFrameActive",
        f"lwz r12, {o('phase')}(r11)", f"cmpwi r12, {tp.SHOWN_PHASE}", "beq apTipFrameDone",
        # requested but neither queued nor shown: allow a few frames, then drop
        f"lwz r12, {o('wait')}(r11)", "addi r12, r12, 1", f"stw r12, {o('wait')}(r11)",
        f"cmpwi r12, {tp.DROP_FRAMES}", "blt apTipFrameEnd",
        "apTipFrameDone:",
        f"lwz r12, {o('flag_object')}(r11)", f"lbz r10, {tp.BOOL_VALUE}(r12)",
        "rlwinm r10, r10, 0, 24, 30", f"lwz r0, {o('saved')}(r11)", "or r10, r10, r0",
        f"stb r10, {tp.BOOL_VALUE}(r12)",
        f"lwz r12, {o('phase')}(r11)", f"cmpwi r12, {tp.SHOWN_PHASE}",
        f"li r12, {tp.CLOSED}", "beq apTipFrameOutcome", f"li r12, {tp.DROPPED}",
        "apTipFrameOutcome:", f"stw r12, {o('outcome')}(r11)",
        f"lwz r12, {o('generation')}(r11)", f"stw r12, {o('completed')}(r11)",
        "li r12, 0", SYNC, f"stw r12, {o('phase')}(r11)", "b apTipFrameEnd",
        "apTipFrameActive:", "li r12, 0", f"stw r12, {o('wait')}(r11)",
        "apTipFrameEnd:", f"lwz r12, {o('cr')}(r11)", MTCRF_R12]


def compose(native: str) -> str:
    """The channel over a generated injection source (LF line ends)."""
    if "apTipData:" in native:
        raise ValueError("tip channel already composed")
    for hook in (FRAME_HOOK, TEXT_HOOK):
        if native.count(hook) != 1:
            raise ValueError("existing tip hook not found, or ambiguous")
    frame = FRAME_HOOK.replace("    blr\n", "\n".join(frame_observer()) + "\n    blr\n")
    text = TEXT_HOOK.replace("    blr\n", "\n".join(text_observer()) + "\n    blr\n")
    out = native.replace(FRAME_HOOK, frame).replace(TEXT_HOOK, text)
    for site, label in ((tp.FRAME_SITE, "apTipsProbe1"), (tp.TEXT_SITE, "apTipsSpy")):
        if out.count(f"{site:#010x} = bla {label}") != 1:
            raise ValueError(f"hook {label} not set at {site:#010x}")
    return out + "\n".join(data_source() + submit_source()) + "\n"

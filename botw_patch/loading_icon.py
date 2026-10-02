"""The Archipelago icon of the loading screen (docs/reference/hud_indicator.md).

The loading screen is Bootup.pack > Layout/Common.sblarc >
blyt/FadeStatus_00.bflyt. Under N_ParamInOut_00, the node that brings the
player's status in and out, it shows one icon per freed Divine Beast
(Pa_Ancient_00..03, x 564 to 324, the first freed on the right) and the
Master Cycle Zero (Pa_DLC_00, x 200). Read in the game's code (the screen's
setup at 0x02f99510, its update at 0x02f999d4): each freed beast makes the
next slot visible, from Pa_Ancient_00, with that beast's picture; the other
slots are hidden and the cycle shows once owned. Nothing is ever moved: with
two beasts, the vanilla row already has a gap before the cycle.

One more part, Pa_AP_00, sits left of the cycle, the same way: a fixed place,
under N_ParamInOut_00 (it fades in and out with the others, its alpha
inherited as Pa_DLC_00's), always visible since only Archipelago packs have
it. It points to PaFadeIconAP_00, a single picture built from the vanilla
PaIconChallenge_00, whose texture is the Archipelago logo as a silhouette in
the style of the screen's icons: black, its lighter symbols cut out.
"""
from __future__ import annotations

import struct

import numpy as np

from botw_patch.hud_layout import (TEMPLATE, _pane, _string, logo_rgba, pane_name,
                                   picture_layout, read_layout, write_flim, write_layout)

SCREEN = "blyt/FadeStatus_00.bflyt"
MODEL_PART = "Pa_DLC_00"           # the cycle: a part with no property, alpha inherited
AFTER = "Pa_Ancient_00"            # last of the icons under N_ParamInOut_00
PART_PANE = "Pa_AP_00"
PART_LAYOUT = "PaFadeIconAP_00"
PICTURE = "P_IconAP_00"
TEXTURE = "Nt_APFade_00^l.bflim"
POSITION = (144.0, 113.0)          # left of the cycle, above the screen's line like the others
SIZE = 54.0
TEXTURE_SIZE = 128
# The silhouette: a pixel lighter than its surroundings by more than CUT_DELTA
# (grey levels) is cut out; the surroundings are three box blurs of radius
# BLUR_RADIUS, at 512 px. Integer arithmetic only, so that every machine
# builds the same texture.
CUT_DELTA = 30
BLUR_RADIUS = 12


def _box(image: np.ndarray, radius: int) -> np.ndarray:
    """Mean over a (2r+1)^2 window, edges clamped, integer."""
    size = 2 * radius + 1
    for axis in (0, 1):
        padded = np.pad(image, [(radius, radius) if a == axis else (0, 0) for a in (0, 1)],
                        mode="edge")
        total = np.cumsum(padded, axis=axis, dtype=np.int64)
        total = np.concatenate([np.zeros_like(total.take([0], axis=axis)), total], axis=axis)
        n = image.shape[axis]
        image = (total.take(range(size, n + size), axis=axis)
                 - total.take(range(0, n), axis=axis)) // size
    return image


def _window(mask: np.ndarray, radius: int) -> np.ndarray:
    """How many pixels of each (2r+1)^2 window are set."""
    size = 2 * radius + 1
    padded = np.pad(mask.astype(np.int64), radius)
    total = np.zeros(mask.shape, dtype=np.int64)
    for dy in range(size):
        for dx in range(size):
            total += padded[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return total


def silhouette(width: int, height: int, rgba: bytes) -> bytes:
    """The logo in black, its lighter details (the symbols) cut out."""
    pixels = np.frombuffer(rgba, dtype=np.uint8).reshape(height, width, 4).astype(np.int64)
    grey = (299 * pixels[..., 0] + 587 * pixels[..., 1] + 114 * pixels[..., 2]) // 1000
    around = grey
    for _ in range(3):
        around = _box(around, BLUR_RADIUS)
    cut = (grey - around) > CUT_DELTA
    cut = _window(cut, 2) >= 13                 # median of 5x5: no marble speckles
    cut = _window(cut, 1) > 0                   # 3x3 dilation: readable strokes
    alpha = np.where(cut, 0, pixels[..., 3])
    out = np.zeros((height, width, 4), dtype=np.uint8)
    out[..., 3] = alpha
    return out.tobytes()


def texture(icon_raw: bytes) -> bytes:
    from botw_patch.hud_layout import shrink
    width, height, rgba = logo_rgba(icon_raw)
    return write_flim(TEXTURE_SIZE, TEXTURE_SIZE,
                      shrink(width, height, silhouette(width, height, rgba), TEXTURE_SIZE))


def add_part(screen: bytes) -> tuple[bytes, dict]:
    """FadeStatus_00 with Pa_AP_00 after Pa_Ancient_00, modelled on Pa_DLC_00."""
    header, sections = read_layout(screen)
    names = [pane_name(data) if magic in (b"pan1", b"prt1", b"pic1") else None
             for magic, data in sections]
    if PART_PANE in names:
        raise ValueError(f"{PART_PANE} already present")
    model = sections[names.index(MODEL_PART)][1]
    # A part with no property: pane block, count 0, magnification, layout name.
    if sections[names.index(MODEL_PART)][0] != b"prt1" or struct.unpack_from(">I", model, 0x4c)[0]:
        raise ValueError("unexpected model part")
    after = names.index(AFTER)
    part = (_pane(model[:0x4c], PART_PANE, visible=True, position=POSITION, size=(SIZE, SIZE))
            + model[0x4c:0x58] + _string(PART_LAYOUT))
    sections = sections[:after + 1] + [(b"prt1", part)] + sections[after + 1:]
    return write_layout(header, sections), {"part": PART_PANE, "layout": PART_LAYOUT,
                                           "after": AFTER, "position": POSITION, "size": SIZE}


def patch_archive(raw_sarc: bytes, icon_raw: bytes) -> tuple[bytes, dict]:
    """Common.sblarc (decompressed SARC) with the loading screen icon added."""
    import oead
    archive = oead.Sarc(raw_sarc)
    writer = oead.SarcWriter.from_sarc(archive)
    added = [f"blyt/{PART_LAYOUT}.bflyt", f"timg/{TEXTURE}"]
    if any(archive.get_file(name) is not None for name in added):
        raise ValueError("loading screen icon already in the archive")
    screen, detail = add_part(bytes(archive.get_file(SCREEN).data))
    writer.files[SCREEN] = screen
    writer.files[f"blyt/{PART_LAYOUT}.bflyt"] = picture_layout(
        bytes(archive.get_file(TEMPLATE).data), PART_LAYOUT, SIZE, [(PICTURE, TEXTURE, True)])
    writer.files[f"timg/{TEXTURE}"] = texture(icon_raw)
    return bytes(writer.write()[1]), {**detail, "added": added}

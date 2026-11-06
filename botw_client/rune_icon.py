"""The HUD's rune icon after a rune's "+", client side.

A rune's "+" (IsGet_Obj_RemoteBombLv2, IsGet_Obj_StopTimerLv2) is a flag on the
same rune: the HUD went on showing the base icon until the rune was changed in
a menu or the save reloaded.

The cause, in the game: the shortcut screen (MainShortCut_00, the HUD's rune
icon Pa_MainU_00 and the quick menu) sets its rune icon by 0x02fc85a4(screen,
rune), which returns at once when screen+0x1bd4 already holds that rune; else
it builds the icon's name (0x0307a924, which reads the "+") and asks for it.
A "+" never changes the rune, so the icon was never asked again.

The remedy, measured in the game (06/11, Bomb+ written with the bomb in hand):
writing -1 to screen+0x1bd4 makes the game call its setter again by itself,
about 1.5 s later, and the icon becomes the "+" one. The client writes it only
when screen+0x1bd4 holds the rune just upgraded: another rune in hand gets its
icon fresh when the player switches back to it.
"""
from __future__ import annotations

from .ui_panes import UiPanes

SHORTCUT_PANE = "Pa_MainU_00"
SHOWN_RUNE = 0x1BD4
INVALID = 0xFFFFFFFF


def refresh_rune_icon(process, cave, rune: int) -> str:
    """Have the HUD ask its rune icon again if it shows `rune`; a short report."""
    panes = UiPanes(process, cave)
    found = panes.screen_with(SHORTCUT_PANE)
    if found is None:
        return "rune icon not refreshed: the shortcut screen is not there"
    field = found[0] + SHOWN_RUNE
    shown = panes.word(field)
    if shown != rune:
        return f"rune icon not refreshed: the HUD shows rune {shown:#x}, not {rune}"
    if not process.write(cave.base + field, INVALID.to_bytes(4, "big")):
        return "rune icon not refreshed: write refused"
    return "rune icon asked again"

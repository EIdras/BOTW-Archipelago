"""Cutscenes skipped with + alone, from a first game on (the world's cutscene_skip option).

Native, a patch group after the injection's. The game lets a cutscene be skipped
(X opens the prompt, + confirms) once its skip controller (0x02DCD430, states
0 idle, 1 skippable, 2 prompt shown, 3 skip asked) sees it skippable. Measured
in the laboratory (lab/journal/etude_saut_cinematiques.md):

* first game: 0x02DCD6E0 sends the opening (Demo102_0) back to idle while no save
  exists, and an Archipelago game always starts on a fresh Cemu account. The
  branch to that reset is gone: the opening is skippable as on a later game;
* + alone: state 1 waited for X. Without X, it now runs state 2's own confirm
  test (0x02DCD580): + asks the skip as it does after X, and X still opens the
  prompt. State 4 (prompt already shown, X skips) takes + as well;
* fade: a cutscene became skippable only once the Fade screen (UI 0x4E) is idle,
  some 5 s into the opening. The skip drives that same screen: it is allowed
  during the fade;
* intro: a new game's code (0x02C2AE4C) requests the 48 s black-screen intro,
  Demo169_0<Timeline>, which no skip reaches (the controller never sees a
  timeline event). The request is never made; the wake-up follows at once.
  Demo169_0 sets no flag.

Kept as the game has them: cutscenes whose .bdemo forbids the skip (SkipPolicy
Forbid: Demo700_0, Demo701_0, the Shrine of Resurrection's pedestal and exit, which
activate its terminal) and those whose request forbids it (Demo103_0). Events
played by an event flow (dialogues, pedestals, terminals) are not cutscenes the
controller sees.
"""
from __future__ import annotations

MODULE = 0x6267BFD0     # moduleMatches of the v208 executable, in every version
GROUP = "BOTW_AP_CutsceneSkip_V208"
# address -> (the game's word, the patch, why); checked against the executable by the tests.
PATCHES = {
    0x02DCD7D4: (0x40820030, "nop",
                 "first game: bne 0x02DCD804, the opening's reset while no save exists"),
    0x02DCD568: (0x4182009C, ".int 0x41820018 ; beq 0x02DCD580",
                 "+ alone: state 1 without X runs state 2's confirm test"),
    0x02DCD5E0: (0x55890739, ".int 0x71890808 ; andi. r9, r12, 0x808",
                 "+ alone: state 4 skips on X or +"),
    0x02DD53C0: (0x41820008, "nop",
                 "fade: beq 0x02DD53C8, not skippable while the Fade screen runs"),
    0x02C2AE48: (0x40820058, ".int 0x48000058 ; b 0x02C2AEA0",
                 "intro: bne 0x02C2AEA0, Demo169_0<Timeline> requested only when not yet"),
}
NATIVE = (f"[{GROUP}]\nmoduleMatches = 0x{MODULE:08X}\n"
          + "".join(f"; {why}\n0x{address:08X} = {patch}\n"
                    for address, (_, patch, why) in PATCHES.items()))
SOURCE_FILES = ("botw_patch/cutscene_skip.py",)


def enabled(status: dict | None) -> bool:
    """The slot asks for the cutscenes skipped (the world's cutscene_skip)."""
    return bool(status and status.get("slot_data", {}).get("cutscene_skip"))


def patch_injection(text: str) -> str:
    """The injection with the cutscene patch group after its own."""
    if GROUP in text:
        raise ValueError("parent injection already has the cutscene skip")
    return text.rstrip("\n") + "\n\n" + NATIVE

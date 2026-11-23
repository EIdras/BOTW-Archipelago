"""Revali's Gale opens no paraglider the game would refuse. A stage of the native
build, in every pack, after the center message hold's: a patch group of its own, first.

The Gale is a progressive item and may come before the Paraglider. The game asks
0x02D72C20 whether Link may glide (IsGet_PlayerStole2, unless an exception of the
engine's): a refusal keeps the paraglider shut. The player's state function
(0x02D164E8, r30 its state holder) does not ask when the Gale's super jump
(スーパージャンプ, 0x02D1FA20) or the Zora armor's waterfall climb (滝登り, 0x02D1FC0C)
ends: 0x02D1FC58 changes state to パラショール滑空 (the glide) at once.

These five words ask, and change state to 落下 (the fall) on a refusal, the name the
Gale's own state function passes on the same holder (0x02D164BC). They end in the
function's common block 0x02D1FC10 (change state to r26, then the epilogue, whose lmw
restores r26). The gate returns 0 or 1: 0x101E07F0 (落下) + 1 * 0x5D4 = 0x101E0DC4.

Measured: the Gale still lifts Link;
without the Paraglider, the glide shuts as the player takes control back and does
not open again. With it, the Gale glides as before.
"""
from __future__ import annotations

MODULE = 0x6267BFD0     # moduleMatches of the v208 executable, in every version
GROUP = "BOTW_AP_GaleNoGlide_V208"
GATE, COMMON, START = 0x02D72C20, 0x02D1FC10, 0x02D1FC58
FALL, GLIDE = 0x101E07F0, 0x101E0DC4
# address -> (the game's word, the patch, why); checked against the executable by the tests.
PATCHES = {
    START: (0x3C80101E, ".int 0x48052FC9", "bl 0x02D72C20, may Link glide? (was lis r4, 0x101e)"),
    START + 4: (0x7FC3F378, ".int 0x1F4305D4", "mulli r26, r3, 0x5d4 (was mr r3, r30)"),
    START + 8: (0x38A00000, ".int 0x3F5A101E", "addis r26, r26, 0x101e (was li r5, 0)"),
    START + 12: (0x38840DC4, ".int 0x3B5A07F0", "addi r26, r26, 0x7f0: the fall, or the glide (was addi r4, r4, 0xdc4)"),
    START + 16: (0x4BFEA8DD, ".int 0x4BFFFFA8", "b 0x02D1FC10, change state to r26 (was bl 0x02D0A544)"),
}
NATIVE = (f"[{GROUP}]\nmoduleMatches = 0x{MODULE:08X}\n"
          + "".join(f"; {why}\n0x{address:08X} = {patch}\n" for address, (_, patch, why) in PATCHES.items()))


def patch_injection(text: str) -> str:
    """The injection with the Gale's patch group before its own: the injection's group
    stays the last one, where the message stage (tools/message_submission.py) appends."""
    if GROUP in text:
        raise ValueError("parent injection already has the Gale's paraglider check")
    return NATIVE + "\n" + text

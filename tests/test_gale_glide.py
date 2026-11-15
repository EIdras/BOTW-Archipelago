"""Revali's Gale opens no paraglider the game would refuse (tools/build_gale_glide_native.py)."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

from tools import build_gale_glide_native as gale
from tools.build_native_from_source import generate
from tools.patch_lint import lint

ROOT = Path(__file__).resolve().parents[1]
HAS_RPX = (ROOT / "U-King.rpx").is_file()


def word(text: str) -> int:
    return int(text.split()[1], 16)


def target(address: int, value: int) -> int:
    offset = value & 0x03FFFFFC
    return address + offset - (0x04000000 if offset & 0x02000000 else 0)


class GaleGlideTests(unittest.TestCase):
    def test_every_pack_carries_the_group_once(self):
        for options in ({}, {"bike_anywhere": True, "cutscene_skip": True}):
            with self.subTest(options=options):
                injection = generate(**options)["runtime/patch_apInject.asm"].decode()
                self.assertEqual(injection.count(gale.GROUP), 1)
                self.assertTrue(injection.startswith(gale.NATIVE + "\n[BOTW_AP_InjectionTest_V208]\n"))
                self.assertEqual(lint(injection), [])

    def test_the_words_ask_the_gate_and_pick_the_fall_or_the_glide(self):
        words = [word(patch) for _, patch, _ in gale.PATCHES.values()]
        self.assertEqual(list(gale.PATCHES), [gale.START + 4 * i for i in range(5)])
        self.assertEqual(words[0] >> 26, 18)                       # bl
        self.assertEqual(words[0] & 3, 1)
        self.assertEqual(target(gale.START, words[0]), gale.GATE)
        self.assertEqual(words[1], (7 << 26) | (26 << 21) | (3 << 16) | (gale.GLIDE - gale.FALL))
        self.assertEqual(words[2], (15 << 26) | (26 << 21) | (26 << 16) | (gale.FALL >> 16))
        self.assertEqual(words[3], (14 << 26) | (26 << 21) | (26 << 16) | (gale.FALL & 0xFFFF))
        self.assertEqual(words[4] & 3, 0)                          # b, no link
        self.assertEqual(target(gale.START + 16, words[4]), gale.COMMON)

    @unittest.skipUnless(HAS_RPX, "the game's executable is read")
    def test_the_patched_words_and_the_state_names_are_the_games(self):
        sys.path.insert(0, str(ROOT / "tools/cemu"))
        from rpx import Rpx
        rpx = Rpx(ROOT / "U-King.rpx")
        for address, (game, _, _) in gale.PATCHES.items():
            self.assertEqual(struct.unpack(">I", rpx.read(address, 4))[0], game, hex(address))
        # The game's own call changed the state to the glide, by name.
        self.assertEqual(target(gale.START + 16, gale.PATCHES[gale.START + 16][0]), 0x02D0A544)
        for address, name in ((gale.FALL, "落下"), (gale.GLIDE, "パラショール滑空")):
            self.assertEqual(rpx.read(address, 32).split(b"\0")[0].decode("utf-8"), name)
        # The common block changes state to r26 (li r5, 0; mr r4, r26; mr r3, r30; bl).
        self.assertEqual(struct.unpack(">4I", rpx.read(gale.COMMON, 16))[:3],
                         (0x38A00000, 0x7F44D378, 0x7FC3F378))
        self.assertEqual(target(gale.COMMON + 12, struct.unpack(">I", rpx.read(gale.COMMON + 12, 4))[0]),
                         0x02D0A544)


if __name__ == "__main__":
    unittest.main()

"""Cutscenes skipped with + alone (botw_patch/cutscene_skip.py): its patch group comes
only with the option, and each patched word is still the game's."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

from botw_patch import cutscene_skip as skip
from tools.build_native_from_source import generate
from tools.patch_lint import lint
from tools.player_packs import addresses, our_addresses

ROOT = Path(__file__).resolve().parents[1]
HAS_RPX = (ROOT / "U-King.rpx").is_file()


class NativeTests(unittest.TestCase):
    def test_the_group_comes_only_with_the_option(self):
        self.assertNotIn(skip.GROUP, generate()["runtime/patch_apInject.asm"].decode())
        injection = generate(cutscene_skip=True)["runtime/patch_apInject.asm"].decode()
        self.assertEqual(injection.count(skip.GROUP), 1)
        self.assertTrue(injection.endswith(skip.NATIVE))
        self.assertEqual(lint(injection), [])

    def test_every_patch_is_written_and_reserved(self):
        written = addresses(skip.NATIVE)
        self.assertEqual(written, set(skip.PATCHES))
        self.assertTrue(written <= our_addresses())    # a player's pack there is left out

    def test_the_stage_runs_only_for_a_slot_that_asks(self):
        self.assertFalse(skip.enabled(None))
        self.assertFalse(skip.enabled({"slot_data": {"cutscene_skip": 0}}))
        self.assertTrue(skip.enabled({"slot_data": {"cutscene_skip": 1}}))

    @unittest.skipUnless(HAS_RPX, "the game's executable is read")
    def test_each_patched_word_is_the_games(self):
        sys.path.insert(0, str(ROOT / "tools/cemu"))
        from rpx import Rpx
        rpx = Rpx(ROOT / "U-King.rpx")
        for address, (word, _, _) in skip.PATCHES.items():
            with self.subTest(address=hex(address)):
                self.assertEqual(struct.unpack(">I", rpx.read(address, 4))[0], word)


if __name__ == "__main__":
    unittest.main()

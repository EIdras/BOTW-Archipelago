"""The center message held by the pack: the regions' border (tools/build_center_hold_native.py)."""
from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock

from tools.build_center_hold_native import BORDER_MESSAGE, MAGIC


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.build_native_from_source import generate
        cls.text = generate()["runtime/patch_apInject.asm"].decode("utf-8")

    def test_every_pack_arms_the_request_at_the_head_of_the_push_block(self):
        self.assertEqual(self.text.count("\napCheckPlay:\n"), 1)
        block = self.text[self.text.index("\napCheckPlay:\n"):self.text.index("\napCheckMsg:\n")]
        hold = block[:block.index("apCenterEnd:")]
        # Before the push, which the hold leaves to make the call in the same pass.
        self.assertLess(block.index("apCenterEnd:"), block.index("bctrl"))
        self.assertNotIn("bctrl", hold)
        # The fields the client's trigger writes, our SafeString's text.
        for field in ("apPlayA", "apMSIndex", "apPlayRaw", "apMSFlag", "apMSReq", "apPlayReq"):
            self.assertIn(f"stw   r3, {field}@l(r11)", hold[hold.index("apCenterArm:"):])
        # The pass is counted before anything can leave it unarmed.
        self.assertLess(hold.index("stw   r3, apCenterPasses@l(r12)"), hold.index("apPlayReq@l(r11)"))

    def test_another_message_shown_goes_to_its_end_first(self):
        hold = self.text[self.text.index("\napCheckPlay:\n"):self.text.index("apCenterEnd:")]
        check = hold[hold.index("lwz   r12, apMS1This@l(r11)"):hold.index("apCenterArm:")]
        # The screen's state: 0, 2, 4, 6 free (0x02ed1e1c); else the message shown, +0xbc,
        # must be the one held, which apCheckMsg writes there again.
        self.assertIn("lwz   r3, 0x8c(r12)", check)
        for state in (0, 2, 4, 6):
            self.assertIn(f"cmpwi r3, {state}\n    beq   apCenterArm", check)
        self.assertLess(check.index("cmpwi r3, 6"), check.index("apCenterShown:"))
        self.assertIn("lwz   r12, 0xbc(r12)", check)
        self.assertIn("cmpw  r12, r3\n    bne   apCenterRestore", check)
        self.assertIn("cmpwi r12, 0\n    beq   apCenterRestore", check)

    def test_the_fields_follow_the_weathers_where_the_client_writes_them(self):
        tail = self.text[self.text.index("apWeatherMagic:"):]
        words = [line for line in tail.split("\n")[:30] if line.startswith(".int") or line.endswith(":")]
        self.assertEqual(words[6:14], [
            "apWeatherPasses:", ".int 0", "apCenterMagic:", f".int 0x{MAGIC:08X}", "apCenterIndex:",
            ".int 0", "apCenterPasses:", ".int 0"])
        from tools.cemu import mailbox
        source = inspect.getsource(mailbox)
        self.assertIn("self.weather_passes = version_addr + 9324", source)
        for name, offset in (("hold_magic", 9328), ("hold_index", 9332), ("hold_passes", 9336)):
            self.assertIn(f"self.{name} = version_addr + {offset}", source)
        self.assertEqual(mailbox.Cave.HOLD_MAGIC, MAGIC)


class CaveTests(unittest.TestCase):
    def test_the_index_is_written_before_the_passes(self):
        from tools.cemu.mailbox import Cave
        memory = Mock()
        memory.read.return_value = MAGIC.to_bytes(4, "big")
        cave = Cave(memory, 0x1000, 0)
        self.assertTrue(cave.center_hold_ready())
        self.assertTrue(cave.hold_center(BORDER_MESSAGE, 15))
        self.assertEqual([call.args for call in memory.write.call_args_list],
                         [(cave.hold_index, (46).to_bytes(4, "big")),
                          (cave.hold_passes, (15).to_bytes(4, "big"))])

    def test_no_passes_lets_it_go_at_once(self):
        from tools.cemu.mailbox import Cave
        memory = Mock()
        memory.read.return_value = MAGIC.to_bytes(4, "big")
        cave = Cave(memory, 0x1000, 0)
        self.assertTrue(cave.hold_center(BORDER_MESSAGE, 0))
        self.assertEqual([call.args for call in memory.write.call_args_list],
                         [(cave.hold_passes, bytes(4))])

    def test_a_patch_without_the_hold_is_left_alone(self):
        from tools.cemu.mailbox import Cave
        memory = Mock()
        memory.read.return_value = bytes(4)
        cave = Cave(memory, 0x1000, 0)
        self.assertFalse(cave.center_hold_ready())
        self.assertFalse(cave.hold_center(BORDER_MESSAGE, 15))
        memory.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()

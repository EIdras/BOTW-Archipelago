"""The game's memory as Cemu maps it (tools/cemu/guest.py), and the code built for it."""
import unittest

from tools.cemu import guest
from tools.player_packs import addresses


class GuestTest(unittest.TestCase):
    def test_plausible_pointers_reach_the_furthest_end(self):
        self.assertTrue(guest.in_heap(0x674F90E4))          # a GameDataMgr with Extended Memory
        self.assertTrue(guest.in_heap(0x10000000))
        self.assertFalse(guest.in_heap(0xA0000000))
        self.assertFalse(guest.in_heap(0x01800000))         # the code cave: not the heaps
        self.assertTrue(guest.in_guest(0x01800000))
        for nothing in (None, 0, 0x00FFFFFF, 0xF4000000):
            self.assertFalse(guest.in_guest(nothing))

    def test_the_injected_bound(self):
        self.assertEqual(guest.below(guest.MEM2_END, "r12", "r0", "out"),
                         ["lis r0, 0x5000", "cmplw r12, r0", "bge out"])
        self.assertEqual(guest.below(0xA0000000, "r12", "r10", "out", margin=0x40),
                         ["lis r10, 0x9fff", "ori r10, r10, 0xffc0", "cmplw r12, r10", "bge out"])
        for wrong in (0xA0001000, 0x10000000, 0x50000800):
            with self.assertRaises(ValueError):
                guest.below(wrong, "r12", "r0", "out")

    def test_the_native_code_follows_no_pointer_past_the_end(self):
        from tools import build_native_from_source as native
        lines = {}
        for end in (guest.MEM2_END, 0xA0000000):
            text = native.generate(resource_gate=True, event_gate=True, tower_maps=True,
                                   mem2_end=end)["runtime/patch_apInject.asm"]
            text = text.decode() if isinstance(text, bytes) else text
            lines[end] = text.splitlines()
            self.assertNotIn("lis r10, 0x6000", text)
            self.assertNotIn("lis r0, 0x6000", text)
            self.assertEqual(text.count(f"lis r0, 0x{(end - 0x40) >> 16:04x}"), 3)
            self.assertEqual(text.count(f"lis r10, 0x{(end - 0x40) >> 16:04x}"), 1)
        # Only the bounds differ, and the addresses patched stay the same.
        changed = [(a, b) for a, b in zip(lines[guest.MEM2_END], lines[0xA0000000]) if a != b]
        self.assertEqual(len(lines[guest.MEM2_END]), len(lines[0xA0000000]))
        self.assertEqual(len(changed), 4)
        self.assertTrue(all(a.startswith("lis r") and b.startswith("lis r") for a, b in changed))
        self.assertEqual(addresses("\n".join(lines[guest.MEM2_END])), addresses("\n".join(lines[0xA0000000])))


if __name__ == "__main__":
    unittest.main()

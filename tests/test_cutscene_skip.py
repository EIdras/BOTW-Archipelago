"""Cutscenes skipped with + alone (botw_patch/cutscene_skip.py): its patch group comes
only with the option, and each patched word is still the game's."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

import oead

from botw_patch import cutscene_skip as skip
from botw_patch.events import graph_snapshot, read_flow
from botw_patch.resources import unpack
from tools.build_native_from_source import generate
from tools.patch_lint import lint
from tools.player_packs import addresses, our_addresses

ROOT = Path(__file__).resolve().parents[1]
HAS_RPX = (ROOT / "U-King.rpx").is_file()
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAS_UPDATE = all((UPDATE / name).is_file() for name in skip.FLOWS)


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


@unittest.skipUnless(HAS_UPDATE, "the game's files are read")
class FlowTests(unittest.TestCase):
    def test_the_pedestal_and_exit_become_cancellable(self):
        files = {skip.TABLE: (UPDATE / skip.TABLE).read_bytes()}
        out, changes = skip.generate(files, UPDATE)
        self.assertEqual(set(out), {*skip.FLOWS, skip.TABLE})
        self.assertEqual([change["edits"]["replayed"] for change in changes],
                         [expected for *_, expected in skip.FLOWS.values()])
        for archive, (name, *_) in skip.FLOWS.items():
            with self.subTest(flow=name):
                sarc = oead.Sarc(unpack(out[archive]))
                events = graph_snapshot(read_flow(bytes(sarc.get_file(f"EventFlow/{name}.bfevfl").data)))["events"]
                used = [e.get("actor_action") or e.get("actor_query") for e in events.values()]
                for node in ("Demo_EventCancelStart", "Demo_EventCancelEnd", "CheckEventCancel"):
                    self.assertEqual(used.count(node), 1)
        with self.assertRaises(ValueError):     # once only
            skip.generate({**files, **out}, UPDATE)


if __name__ == "__main__":
    unittest.main()

"""master_mode: the Master Mode chests as locations (botw_world/data/master_chests.json,
botw_patch/chests.py), and the client that binds only a Master Mode save for them
(botw_client/master_mode.py)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from botw_client import gamedata_table, master_mode
from botw_client.backend import DeliveryResult, DeliveryStatus
from botw_client.locations import CHEST_NUMBERS, load_targets
from botw_client.runtime import BotwClientRuntime, FatalClientError
from botw_patch import chests

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT / "botw_world/data/master_chests.json").read_text(encoding="utf-8"))
NEEDS_TABLE = unittest.skipUnless(gamedata_table.available(), "the GameData flag table is read from the game")


class DataTests(unittest.TestCase):
    def test_numbered_after_the_divine_beasts(self):
        self.assertEqual([row["number"] for row in ROWS],
                         list(range(chests.MASTER_FIRST, chests.MASTER_FIRST + chests.MASTER_CHEST_COUNT)))
        self.assertEqual(chests.MASTER_FIRST, chests.BEAST_FIRST + chests.BEAST_CHEST_COUNT)
        self.assertEqual({row["kind"] for row in ROWS}, {"Master Mode Iron", "Master Mode Wooden"})

    def test_the_other_chests_keep_their_numbers(self):
        others = json.loads((ROOT / "botw_world/data/chests.json").read_text(encoding="utf-8"))
        self.assertLess(max(row["number"] for row in others), chests.MASTER_FIRST)
        self.assertFalse({row["name"] for row in others} & {row["name"] for row in ROWS})

    @NEEDS_TABLE
    def test_world_schema_11_tracks_them_10_does_not(self):
        names = {row["name"] for row in ROWS}
        self.assertLessEqual(names, {target.name for target in load_targets(world_schema=11)})
        self.assertFalse(names & {target.name for target in load_targets(world_schema=10)})
        self.assertLessEqual(names, set(CHEST_NUMBERS))

    def test_held_only_with_master_mode(self):
        self.assertFalse(chests.holds_item(chests.MASTER_FIRST))
        self.assertTrue(chests.holds_item(chests.MASTER_FIRST, master=True))
        self.assertTrue(chests.master_asked({"slot_data": {"chest_sanity": 2, "master_mode": 1}}))
        self.assertFalse(chests.master_asked({"slot_data": {"chest_sanity": 1, "master_mode": 1}}))
        self.assertFalse(chests.master_asked({"slot_data": {"chest_sanity": 2, "master_mode": 0}}))

    def test_a_master_chest_is_not_a_normal_one(self):
        normal = {"UnitConfigName": "TBox_Field_Iron", "!Parameters": {"IsHardModeActor": False}}
        master = {"UnitConfigName": "TBox_Field_Wood", "!Parameters": {"IsHardModeActor": True}}
        trial = {"UnitConfigName": "TBox_Field_Wood", "!Parameters": {"IsHardModeActor": True, "IsIchigekiActor": True}}
        self.assertEqual([chests.is_chest(o) for o in (normal, master, trial)], [True, False, False])
        self.assertEqual([chests.is_master_chest(o) for o in (normal, master, trial)], [False, True, False])


class SaveModeTests(unittest.TestCase):
    def test_settles_once_the_same_a_second_apart(self):
        mode = master_mode.SaveMode()
        self.assertIsNone(mode.settled(0, 10.0))
        self.assertIsNone(mode.settled(1, 10.02))      # the load writes it a frame later
        self.assertIsNone(mode.settled(1, 10.5))
        self.assertTrue(mode.settled(1, 11.02))
        self.assertIsNone(mode.settled(None, 11.5))
        self.assertIsNone(mode.settled(0, 12.0))
        self.assertFalse(mode.settled(0, 13.0))


class BindingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.lines, self.binds = [], []
        self.flag, self.in_world, self.now = [1], [True], [100.0]
        self.runtime = BotwClientRuntime(
            "localhost:1", "Player", state_path=Path(self.directory.name) / "state.json",
            log=self.lines.append, game_factory=SimpleNamespace, tip_factory=object, native_delivery=True)
        self.runtime.game = SimpleNamespace(
            live=SimpleNamespace(get=lambda key, kind: self.flag[0] if key == master_mode.FLAG_HASH else None),
            delivery_block_reason="")
        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            _link_in_world=lambda: self.in_world[0],
            bind_session=lambda: self.binds.append(1) or DeliveryResult(DeliveryStatus.APPLIED, 0)))
        clock = mock.patch("botw_client.runtime.time.monotonic", lambda: self.now[0])
        clock.start()
        self.addCleanup(clock.stop)

    def seed(self, **slot_data):
        self.runtime.ap = SimpleNamespace(slot_data=slot_data)

    async def bind(self, *times):
        """_ensure_native_session at each time; its last answer."""
        answer = None
        for at in times:
            self.now[0] = at
            answer = await self.runtime._ensure_native_session()
        return answer

    async def test_a_master_seed_binds_a_master_save_once_settled(self):
        self.seed(master_mode=1)
        self.assertFalse(await self.bind(100.0, 100.5))
        self.assertEqual(self.binds, [])
        self.assertTrue(await self.bind(101.1))
        self.assertEqual(self.binds, [1])
        self.assertNotIn(master_mode.PLAYED, self.lines)

    async def test_a_master_seed_stops_on_a_normal_save_before_binding(self):
        self.seed(master_mode=1)
        self.flag[0] = 0
        self.assertFalse(await self.bind(100.0))
        with self.assertRaisesRegex(FatalClientError, "WRONG GAME MODE"):
            await self.bind(101.1)
        self.assertEqual(self.binds, [])

    async def test_a_master_seed_waits_for_link_in_the_world(self):
        self.seed(master_mode=1)
        self.flag[0], self.in_world[0] = 0, False      # the title screen: a stale value
        self.assertFalse(await self.bind(100.0, 101.0, 102.0))
        self.flag[0], self.in_world[0] = 1, True
        self.assertFalse(await self.bind(103.0))
        self.assertTrue(await self.bind(104.1))
        self.assertEqual(self.binds, [1])

    async def test_another_seed_binds_at_once_and_says_master_mode_once(self):
        self.seed(chest_sanity=2)
        self.assertTrue(await self.bind(100.0))
        self.assertEqual(self.binds, [1])
        self.assertEqual(self.lines.count(master_mode.PLAYED), 1)

    async def test_another_seed_says_master_mode_once_written_after_the_binding(self):
        self.seed(chest_sanity=2)
        self.flag[0] = 0                               # a reload: the mode a frame late
        self.assertTrue(await self.bind(100.0))
        self.flag[0] = 1
        self.assertTrue(await self.bind(100.2, 100.4))
        self.assertEqual(self.binds, [1])
        self.assertEqual(self.lines.count(master_mode.PLAYED), 1)

    async def test_another_seed_in_a_normal_save_says_nothing(self):
        self.seed(chest_sanity=2)
        self.flag[0] = 0
        self.assertTrue(await self.bind(100.0, 104.0, 106.0))
        self.flag[0] = 1                               # past PLAYED_SECONDS: not read any more
        self.assertTrue(await self.bind(106.5))
        self.assertNotIn(master_mode.PLAYED, self.lines)


if __name__ == "__main__":
    unittest.main()

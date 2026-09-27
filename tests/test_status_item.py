"""The Archipelago key item: the seed's fixed facts in the inventory."""
from pathlib import Path
import unittest

import oead

from botw_patch.events import graph_snapshot, read_flow
from botw_patch.resources import unpack
from botw_patch.status_item import (ACTOR, ENTRY, add_event_info,
                                    add_status_entry, texts)

CONTENT = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
MANIFEST = {"seed": "56866616677933465054", "slot": 1, "slot_name": "Player",
            "slot_data": {"goal_type": 0, "shrines_required": 40,
                          "divine_beasts_required": 4}}


class TextTests(unittest.TestCase):
    def test_description_names_seed_slot_and_goal(self):
        name, description = texts(MANIFEST)
        self.assertEqual(name, "Archipelago")
        self.assertEqual(description.split("\n"), [
            "Seed 56866616677933465054", "Player: Player (slot 1)",
            "Goal: defeat Ganon"])
        shrines = {**MANIFEST, "slot_data": {**MANIFEST["slot_data"], "goal_type": 2}}
        self.assertEqual(texts(shrines)[1].split("\n")[2],
                         "Goal: complete 40 shrines")

    def test_a_description_too_long_is_refused(self):
        long = {**MANIFEST, "slot_name": "X" * 40}
        with self.assertRaises(ValueError):
            texts(long)


@unittest.skipUnless((CONTENT / "Pack/TitleBG.pack").is_file(), "requires the Wii U update")
class ResourceTests(unittest.TestCase):
    def test_entry_grants_the_item_only_when_it_is_not_held(self):
        title = oead.Sarc(unpack((CONTENT / "Pack/TitleBG.pack").read_bytes()))
        raw = bytes(title.get_file("EventFlow/Demo007_1.bfevfl").data)
        out, _ = add_status_entry(raw)
        before, after = graph_snapshot(read_flow(raw)), graph_snapshot(read_flow(out))
        self.assertEqual(set(after["events"]) - set(before["events"]),
                         {f"{ENTRY}_Held", f"{ENTRY}_Grant"})
        self.assertEqual(dict(after["entry_points"])[ENTRY], f"{ENTRY}_Held")
        held = after["events"][f"{ENTRY}_Held"]
        self.assertEqual((held["actor_query"], held["params"], held["cases"]), (
            "HasPorchItem", {"Count": 1, "PorchItemName": ACTOR}, {0: f"{ENTRY}_Grant"}))
        grant = after["events"][f"{ENTRY}_Grant"]
        self.assertEqual((grant["actor_action"], grant["params"], grant["nxt"]), (
            "Demo_SetItemDataToPouch",
            {"IsWaitFinish": False, "TargetActorName": ACTOR}, None))
        with self.assertRaises(ValueError):
            add_status_entry(out)

    def test_event_info_registers_the_entry_like_the_deliveries(self):
        pack = Path(".build/tip-play-packs/e6e6a6ac6af1bdf7/content/Pack/Bootup.pack")
        if not pack.is_file():
            self.skipTest("requires a built play pack")
        boot = oead.Sarc(unpack(pack.read_bytes()))
        raw = bytes(boot.get_file("Event/EventInfo.product.sbyml").data)
        out, _ = add_event_info(raw)
        info = oead.byml.from_binary(unpack(out))
        self.assertEqual(oead.byml.to_text(info[f"Demo007_1<{ENTRY}>"]),
                         oead.byml.to_text(info["Demo007_1<APD_06986FF9_00>"]))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_asked_once_per_game_connection_after_the_deliveries(self):
        import tempfile
        from unittest.mock import Mock
        from botw_client.runtime import BotwClientRuntime
        with tempfile.TemporaryDirectory() as folder:
            runtime = BotwClientRuntime("localhost:1", "test",
                                        state_path=Path(folder) / "state.json",
                                        game_factory=Mock, log=lambda _: None)
            answers = [False, True]
            backend = Mock()
            backend.request_status_item.side_effect = lambda: answers.pop(0)
            runtime.deliveries = Mock(backend=backend)
            runtime.state = {"apply_queue": [3]}
            await runtime._status_item_tick()
            backend.request_status_item.assert_not_called()   # deliveries first
            runtime.state["apply_queue"] = []
            await runtime._status_item_tick()                  # refused
            runtime._status_item_retry_after = 0.0
            await runtime._status_item_tick()                  # taken
            await runtime._status_item_tick()                  # done for this connection
            self.assertEqual(backend.request_status_item.call_count, 2)
            self.assertTrue(runtime._status_item_done)


if __name__ == "__main__":
    unittest.main()

"""The Archipelago quest: the seed's fixed facts in the Adventure Log."""
from pathlib import Path
import unittest

import oead

from botw_patch.ap_quest import (FINISH, FINISH_FLAG, GIVER, LINES, LOCATION, QUEST, START,
                                 START_FLAG, WIDTH, add_entries, add_event_info, add_quest,
                                 goal, messages, sanctum, texts)
from botw_patch.events import graph_snapshot, read_flow
from botw_patch.resources import unpack

CONTENT = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
MANIFEST = {"seed": "56866616677933465054", "slot": 1, "slot_name": "Simon",
            "slot_data": {"goal": 0, "sanctum_divine_beasts": 2, "sanctum_shrines": 0,
                          "sanctum_master_sword": 1, "sanctum_runes": 1, "world_version": "0.2.0"}}


class TextTests(unittest.TestCase):
    def test_title_place_giver_and_the_seeds_facts(self):
        quest = texts(MANIFEST)
        self.assertEqual((quest["title"], quest["location"], quest["giver"]),
                         ("Archipelago", "Multiworld: Simon", "BOTW Archipelago 0.2.0"))
        desc = quest["desc"].split("\n")
        self.assertEqual(desc[-2:], ["Seed 56866616677933465054", "Player: Simon (slot 1)"])
        self.assertTrue(desc[0].startswith("A voice from beyond Hyrule"))
        self.assertIn("Defeat Calamity Ganon in Hyrule Castle.", " ".join(desc))
        self.assertTrue(quest["finish"].startswith("Your goal is reached."))
        self.assertEqual(quest["finish"].split("\n")[-1], "Player: Simon (slot 1)")
        # A seed of an older world: no version.
        old = {**MANIFEST, "slot_data": {"goal": 1}}
        self.assertEqual(texts(old)["giver"], "BOTW Archipelago")

    def test_the_goal_and_what_opens_the_sanctum(self):
        self.assertEqual(sanctum(MANIFEST["slot_data"]),
                         "His sanctum stays sealed until you have freed 2 Divine Beasts and hold "
                         "the Master Sword and the four runes.")
        self.assertEqual(sanctum({"sanctum_divine_beasts": 1, "sanctum_shrines": 1}),
                         "His sanctum stays sealed until you have freed 1 Divine Beast and "
                         "completed 1 shrine.")
        self.assertEqual(sanctum({"sanctum_runes": 1}),
                         "His sanctum stays sealed until you hold the four runes.")
        self.assertIsNone(sanctum({"sanctum_divine_beasts": 0}))
        self.assertEqual(goal({"goal": 1}), "Free the four Divine Beasts.")
        self.assertEqual(goal({"goal": 2, "goal_shrines": 70}), "Complete 70 shrines.")
        self.assertEqual(goal({"goal": 2, "goal_shrines": 1}), "Complete 1 shrine.")
        self.assertEqual(goal({"goal_type": 2, "shrines_required": 40}), "Complete 40 shrines.")
        self.assertEqual(goal({"goal_type": 0}), "Defeat Calamity Ganon in Hyrule Castle.")
        with self.assertRaises(ValueError):
            goal({"goal": 3})

    def test_the_text_fits_the_log_whatever_the_seed_asks(self):
        widest = {**MANIFEST, "slot_name": "Bartholomew0123", "slot": 16,
                  "slot_data": {**MANIFEST["slot_data"], "sanctum_divine_beasts": 4,
                                "sanctum_shrines": 120}}
        for manifest in (MANIFEST, widest):
            quest = texts(manifest)
            for text in (quest["desc"], quest["finish"]):
                lines = text.split("\n")
                self.assertLessEqual(len(lines), LINES, lines)
                self.assertLessEqual(max(map(len, lines)), WIDTH, lines)
        self.assertIn("completed 120 shrines", texts(widest)["desc"].replace("\n", " "))

    def test_too_long_to_tell_it_all_the_voice_goes_first(self):
        from unittest.mock import patch
        from botw_patch import ap_quest
        with patch.object(ap_quest, "INTRO", "A voice speaks. " * 12):
            desc = texts(MANIFEST)["desc"]
        self.assertTrue(desc.startswith("Defeat Calamity Ganon"))
        self.assertTrue(desc.endswith("Player: Simon (slot 1)"))


@unittest.skipUnless((CONTENT / "Pack/TitleBG.pack").is_file(), "requires the Wii U update")
class ResourceTests(unittest.TestCase):
    def title(self, member):
        title = oead.Sarc(unpack((CONTENT / "Pack/TitleBG.pack").read_bytes()))
        return bytes(title.get_file(member).data)

    def test_a_main_quest_of_two_steps_on_the_test_quests_flags(self):
        raw = self.title("Quest/QuestProduct.sbquestpack")
        out, _ = add_quest(raw)
        quests = oead.byml.from_binary(unpack(out))
        self.assertEqual(len(quests), len(oead.byml.from_binary(unpack(raw))) + 1)
        quest = quests[-1]
        self.assertEqual((str(quest["Name"]), str(quest["Type"]), str(quest["Location"]),
                          str(quest["Orderer"])), (QUEST, "Main", LOCATION, GIVER))
        self.assertEqual([(str(s["Name"]), str(s["MessageName"]), str(s["NextFlag"]))
                          for s in quest["Steps"]],
                         [("Ready", "Desc", START_FLAG), ("Finish", "Finish", FINISH_FLAG)])
        # Active from the start (Ready is up): an AttentionOff step would take the "A" prompt
        # from every actor of the world.
        self.assertEqual([bool(s["AttentionOff"]) for s in quest["Steps"]], [False, False])
        with self.assertRaises(ValueError):
            add_quest(out)
        # Not shrunk by shared nodes: the game's file and our quest, every container apart.
        from tests.test_byml_unshared import container_offsets
        offsets = container_offsets(unpack(out))
        self.assertEqual(len(offsets), len(set(offsets)))
        self.assertGreater(len(unpack(out)), len(unpack(raw)))

    def test_each_entry_raises_its_flag_only_when_it_is_down(self):
        raw = self.title("EventFlow/Demo007_1.bfevfl")
        out, _ = add_entries(raw)
        before, after = graph_snapshot(read_flow(raw)), graph_snapshot(read_flow(out))
        for entry, flag in ((START, START_FLAG), (FINISH, FINISH_FLAG)):
            self.assertEqual(dict(after["entry_points"])[entry], f"{entry}_Up")
            up = after["events"][f"{entry}_Up"]
            self.assertEqual((up["actor_query"], up["params"], up["cases"]),
                             ("CheckFlag", {"FlagName": flag}, {0: f"{entry}_Raise"}))
            raise_ = after["events"][f"{entry}_Raise"]
            self.assertEqual((raise_["actor_action"], raise_["params"], raise_["nxt"]),
                             ("Demo_FlagON", {"FlagName": flag, "IsWaitFinish": True}, None))
        self.assertEqual(len(after["events"]) - len(before["events"]), 4)
        with self.assertRaises(ValueError):
            add_entries(out)

    def test_the_texts_place_and_giver_in_a_language(self):
        from botw_patch.death_link import plain, read_labels
        boot = oead.Sarc(unpack((CONTENT / "Pack/Bootup_EUfr.pack").read_bytes()))
        raw = bytes(boot.get_file("Message/Msg_EUfr.product.ssarc").data)
        quest = texts(MANIFEST)
        archive = oead.Sarc(unpack(messages(raw, quest)[0]))

        def label(member, name):
            return plain(read_labels(bytes(archive.get_file(member).data))[name])
        self.assertEqual(label(f"QuestMsg/QL_{QUEST}.msbt", f"QL_{QUEST}_Name"), "Archipelago")
        self.assertEqual(label(f"QuestMsg/QL_{QUEST}.msbt", f"QL_{QUEST}_Desc"), quest["desc"])
        self.assertEqual(label(f"QuestMsg/QL_{QUEST}.msbt", f"QL_{QUEST}_Finish"), quest["finish"])
        self.assertEqual(label("StaticMsg/LocationMarker.msbt", LOCATION), "Multiworld: Simon")
        self.assertEqual(label("ActorType/DemoNPC.msbt", f"{GIVER}_Name"), "BOTW Archipelago 0.2.0")

    def test_event_info_registers_the_entries_like_the_deliveries(self):
        pack = Path(".build/tip-play-packs/e6e6a6ac6af1bdf7/content/Pack/Bootup.pack")
        if not pack.is_file():
            self.skipTest("requires a built play pack")
        boot = oead.Sarc(unpack(pack.read_bytes()))
        raw = bytes(boot.get_file("Event/EventInfo.product.sbyml").data)
        out, _ = add_event_info(raw)
        info = oead.byml.from_binary(unpack(out))
        for entry in (START, FINISH):
            self.assertEqual(oead.byml.to_text(info[f"Demo007_1<{entry}>"]),
                             oead.byml.to_text(info["Demo007_1<APD_06986FF9_00>"]))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self, folder):
        from unittest.mock import Mock
        from botw_client.runtime import BotwClientRuntime
        lines = []
        runtime = BotwClientRuntime("localhost:1", "test", state_path=Path(folder) / "state.json",
                                    game_factory=Mock, log=lines.append)
        return runtime, lines

    async def test_started_once_per_connection_and_completed_once_the_goal_is_sent(self):
        import tempfile
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            runtime, lines = self.runtime(folder)
            answers = {False: [False, True], True: [True]}
            backend = Mock(spec=["request_quest", "request_status_item"])
            backend.request_quest.side_effect = lambda finish=False: answers[finish].pop(0)
            runtime.deliveries = Mock(backend=backend)
            runtime.state = {"apply_queue": [3], "goal_sent": False}
            await runtime._quest_tick()
            backend.request_quest.assert_not_called()           # deliveries first
            runtime.state["apply_queue"] = []
            await runtime._quest_tick()                          # refused
            runtime._quest_retry_after = 0.0
            await runtime._quest_tick()                          # taken
            await runtime._quest_tick()                          # the goal not sent yet
            self.assertEqual(backend.request_quest.call_count, 2)
            runtime.state["goal_sent"] = True
            await runtime._quest_tick()                          # completed
            await runtime._quest_tick()                          # done for this connection
            self.assertEqual([c.args for c in backend.request_quest.call_args_list], [(), (), (True,)])
            self.assertEqual(lines, ["Archipelago quest (seed, slot, goal) checked in the Adventure Log",
                                     "Archipelago quest completed in the Adventure Log"])
            backend.request_status_item.assert_not_called()

    async def test_a_pack_before_the_quest_gives_its_key_item(self):
        import tempfile
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            runtime, lines = self.runtime(folder)
            backend = Mock(spec=["request_quest", "request_status_item"])
            backend.request_quest.return_value = None
            backend.request_status_item.return_value = True
            runtime.deliveries = Mock(backend=backend)
            runtime.state = {"apply_queue": [], "goal_sent": True}
            for _ in range(3):
                await runtime._quest_tick()
            backend.request_status_item.assert_called_once_with()
            self.assertEqual(lines, ["Archipelago key item (seed, slot, goal) checked in the inventory"])


if __name__ == "__main__":
    unittest.main()

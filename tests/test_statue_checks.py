"""The Goddess Statues' trades as locations (the world's spirit_orbs on statue_checks):
the client counts the trades, the pack's statue gives nothing more."""
from __future__ import annotations

from pathlib import Path
import struct
import unittest
import zlib

import oead

from botw_client.locations import (OFFERING_FLAG, OFFERING_NAMES, OFFERING_SCHEMA, LocationTarget, LocationTracker,
                                   load_targets)
from botw_patch import statue_checks
from botw_patch.events import graph_snapshot, read_flow
from botw_patch.resources import unpack
from tools import play_seed

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAS_UPDATE = (UPDATE / statue_checks.ARCHIVE).is_file()
SCENE_FILES = {statue_checks.BOOTUP, statue_checks.ACTOR_INFO,
               *(f"Actor/Pack/{actor}.sbactorpack" for actor in statue_checks.CONTAINERS)}
MODEL_FILES = {f"Model/AP_Item_00{part}.sbfres" for part in ("", ".Tex1", ".Tex2")}


class Memory:
    def __init__(self, base, size):
        self.base, self.data = base, bytearray(size)

    def read(self, address, size):
        offset = address - self.base
        return bytes(self.data[offset:offset + size])


class ClientTests(unittest.TestCase):
    def test_offering_k_waits_for_the_counter_at_4k(self):
        targets = [t for t in load_targets(world_schema=OFFERING_SCHEMA) if t.flag == OFFERING_FLAG]
        self.assertEqual([(t.name, t.kind, t.minimum) for t in targets],
                         [(f"Goddess Statue - Offering {k}", "s32", 4 * k) for k in range(1, 31)])
        self.assertEqual({t.hash_u32 for t in targets}, {zlib.crc32(b"Npc_Goddess_UtuwaSum")})
        self.assertFalse(any(t.flag == OFFERING_FLAG for t in load_targets(world_schema=OFFERING_SCHEMA - 1)))

    def test_each_trade_makes_one_offering_and_a_later_start_all_those_made(self):
        class Live:
            base = 1000
            index = {"bool": {}, "s32": {zlib.crc32(OFFERING_FLAG.encode()): 0x40}}

        def counter(value):
            struct.pack_into(">i", memory.data, 0x40 + 0x14, value)

        memory = Memory(1000, 0x80)
        targets = [t for t in load_targets() if t.flag == OFFERING_FLAG]
        tracker = LocationTracker(memory, {}, targets, live=Live())
        self.assertEqual(tracker.poll(), [])
        counter(4)
        self.assertEqual(tracker.poll(), ["Goddess Statue - Offering 1"])
        self.assertEqual(tracker.poll(), [])
        counter(8)
        self.assertEqual(tracker.poll(), ["Goddess Statue - Offering 2"])
        counter(12)
        later = LocationTracker(memory, {}, targets, live=Live())
        self.assertEqual(later.poll(), list(OFFERING_NAMES[:3]))

    def test_a_flag_set_once_still_counts_from_one(self):
        self.assertEqual(LocationTarget("Shop", "APShop_1", 1, "s32", optional=True).minimum, 1)


class PlacementTests(unittest.TestCase):
    def test_the_offerings_are_placements_with_statue_checks_only(self):
        base = play_seed.expected_placements({})
        self.assertEqual(play_seed.expected_placements({"spirit_orbs": 2, "statue_offerings": 7}), base + 7)
        self.assertEqual(play_seed.expected_placements({"spirit_orbs": 1, "statue_offerings": 7}), base)


class StageTests(unittest.TestCase):
    def test_the_stage_runs_only_for_a_slot_that_asks(self):
        self.assertTrue(statue_checks.enabled({"slot_data": {"spirit_orbs": 2}}))
        for slot_data in ({}, {"spirit_orbs": 0}, {"spirit_orbs": 1}):
            self.assertFalse(statue_checks.enabled({"slot_data": slot_data}))
        self.assertFalse(statue_checks.enabled(None))

    @unittest.skipUnless(HAS_UPDATE, "the game's files are read")
    def test_the_statue_takes_the_orbs_counts_the_trade_and_gives_nothing(self):
        files = {statue_checks.TABLE: (UPDATE / statue_checks.TABLE).read_bytes()}
        out, changes = statue_checks.generate(files, UPDATE)
        self.assertEqual(set(out), {statue_checks.ARCHIVE, statue_checks.TABLE, *SCENE_FILES, *MODEL_FILES})
        sarc = oead.Sarc(unpack(out[statue_checks.ARCHIVE]))
        events = graph_snapshot(read_flow(bytes(sarc.get_file("EventFlow/Demo034_0.bfevfl").data)))["events"]
        self.assertEqual(events[statue_checks.GIFT]["actor_action"], "Demo_WaitFrame")
        self.assertFalse(any(e.get("entry_point_name") == "GetItemByName" for e in events.values()))
        actions = [e.get("actor_action") for e in events.values()]
        self.assertIn("Demo_IncreaseNumDungeonClrSeal", actions)       # the orbs still taken
        self.assertIn("Demo_IncreaseGameDataInt", actions)              # the trade still counted
        with self.assertRaises(ValueError):     # once only
            statue_checks.generate({**files, **out}, UPDATE)

    @unittest.skipUnless(HAS_UPDATE, "the game's files are read")
    def test_the_scene_shows_the_archipelago_item_and_moves_it(self):
        files = {statue_checks.TABLE: (UPDATE / statue_checks.TABLE).read_bytes()}
        out, _changes = statue_checks.generate(files, UPDATE)
        scene = oead.Sarc(unpack(out[statue_checks.ARCHIVE]))
        events = graph_snapshot(read_flow(bytes(scene.get_file("EventFlow/Demo034_0.bfevfl").data)))["events"]
        played = [e["params"]["ASName"] for e in events.values() if e.get("actor_action") == "Demo_PlayASForDemo"
                  and "Utuwa" in e.get("actor", "") + str(e.get("params", {}).get("ASName", ""))]
        self.assertEqual(played, [statue_checks.SCENE_AS] * 2)
        self.assertEqual(statue_checks.SCENE_AS, "Demo034_0-C05-AP_Item_00-A-0")
        heart = statue_checks.AS_PATH.format(statue_checks.CONTAINERS["Obj_HeartUtuwa_A_01"])
        self.assertEqual(bytes(scene.get_file(statue_checks.AS_PATH.format(statue_checks.SCENE_AS)).data),
                         bytes(scene.get_file(heart).data))
        for actor in statue_checks.CONTAINERS:
            pack = oead.Sarc(unpack(out[f"Actor/Pack/{actor}.sbactorpack"]))
            models = oead.aamp.ParameterIO.from_binary(bytes(pack.get_file(f"Actor/ModelList/{actor}.bmodellist").data))
            data = models.lists["ModelData"].lists["ModelData_0"]
            self.assertEqual(str(data.objects["Base"].params["Folder"].v), "AP_Item_00")
            self.assertEqual(str(data.lists["Unit"].objects["Unit_0"].params["UnitName"].v), "AP_Item_00")
        info = oead.byml.from_binary(unpack(out[statue_checks.ACTOR_INFO]))
        self.assertEqual({str(e["name"]): (str(e["bfres"]), str(e["mainModel"])) for e in info["Actors"]
                          if str(e["name"]) in statue_checks.CONTAINERS},
                         {actor: ("AP_Item_00", "AP_Item_00") for actor in statue_checks.CONTAINERS})
        bootup = oead.Sarc(unpack(out[statue_checks.BOOTUP]))
        entries = oead.byml.from_binary(unpack(bytes(bootup.get_file(statue_checks.EVENT_INFO).data)))
        self.assertIn(statue_checks.SCENE_AS, [str(a["file"]) for a in entries["Demo034_0<GetMatome>"]["as"]])

    @unittest.skipUnless(HAS_UPDATE, "the game's files are read")
    def test_a_model_already_added_is_kept(self):
        files = {statue_checks.TABLE: (UPDATE / statue_checks.TABLE).read_bytes(),
                 **{name: b"model of an earlier stage" for name in MODEL_FILES}}
        out, _changes = statue_checks.generate(files, UPDATE)
        self.assertEqual({name: out[name] for name in MODEL_FILES}, {name: files[name] for name in MODEL_FILES})


if __name__ == "__main__":
    unittest.main()

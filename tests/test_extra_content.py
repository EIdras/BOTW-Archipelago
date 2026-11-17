"""World schema 6 and client schema 13: the shrine chests, field chests and bosses
(tools/build_extra_locations.py), the shrine chests' treasure replaced
(botw_patch/shrine_chests.py), the Progressive Horse, the new items, and the
Freeze, Lightning Strike and Fire traps (botw_client/elemental_strike.py)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

import oead

from botw_client import elemental_strike
from botw_client.cucco_swarm import CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PLAYER_INFO, REQUEST_CREATE
from botw_client.delivery_plan import compile_delivery_plan
from botw_client.items import NATIVE_EFFECTS, load_item_map, stage_count
from botw_client.locations import PLAYABLE_WORLD_SCHEMAS, SCHEMA_LOCATION_COUNTS, WORLD_SCHEMA
from botw_patch import horses, shrine_chests

ROOT = Path(__file__).resolve().parents[1]
LOCATIONS = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
ITEMS = json.loads((ROOT / "botw_world/data/items.json").read_text(encoding="utf-8"))
NEW = LOCATIONS[SCHEMA_LOCATION_COUNTS[5]:]


class Memory:
    """The guest memory a trap reads and writes, and the calls it makes."""

    def __init__(self, link=(100.0, 50.0, 200.0)):
        self.words = {PLAYER_INFO: 0x2000, 0x2030: 0x3000, CREATOR: 0x4000, HEAP_HOLDER: 0x5000,
                      0x5010: 0x6000}
        for axis, value in enumerate(link):
            self.words[0x3000 + 0x204 + 0x10 * axis] = struct.unpack(">I", struct.pack(">f", value))[0]
        self.written, self.calls, self.blocks = {}, [], 0

    def read(self, guest, size):
        return self.words.get(guest, 0).to_bytes(4, "big") if size == 4 else bytes(size)

    def write(self, guest, data):
        self.written[guest] = data

    def call(self, address, *args):
        self.calls.append((address, args))
        if address == NEW_IN_HEAP:
            self.blocks += 1
            return 0x10000000 + 0x1000 * self.blocks
        return 1 if address == REQUEST_CREATE else 0


class LocationTests(unittest.TestCase):
    def test_schema_6_appends_the_chests_and_bosses(self):
        self.assertEqual(WORLD_SCHEMA, 6)
        self.assertEqual(SCHEMA_LOCATION_COUNTS[6], len(LOCATIONS))
        self.assertEqual(PLAYABLE_WORLD_SCHEMAS, (5, 6))
        counts = {category: sum(row["category"] == category for row in NEW)
                  for category in ("Shrine Chest", "Chest", "Boss")}
        self.assertEqual(counts, {"Shrine Chest": 174, "Chest": 1312, "Boss": 86})
        self.assertEqual(len(NEW), sum(counts.values()))
        self.assertEqual([row["id"] for row in LOCATIONS], list(range(1, len(LOCATIONS) + 1)))

    def test_no_new_name_counts_for_a_goal(self):
        # runtime._goal_reached counts the names ending in " Shrine" and starting with "Divine Beast".
        for row in NEW:
            self.assertFalse(row["name"].endswith(" Shrine"), row["name"])
            self.assertFalse(row["name"].startswith("Divine Beast"), row["name"])

    def test_the_flags_are_the_games_own(self):
        prefixes = {"Shrine Chest": "CDungeon_TBox_", "Chest": "MainField_TBox_Field_",
                    "Boss": "MainField_IsDefeat_Enemy_"}
        for row in NEW:
            self.assertTrue(row["gamedata_flag"].startswith(prefixes[row["category"]]), row["name"])
            self.assertNotIn("Gamble", row["gamedata_flag"])
        self.assertFalse(any("KeySmall" in row["notes"] for row in NEW))

    def test_a_shrine_chest_is_in_logic_with_its_shrine(self):
        logic = {row["location"]: row for row in csv.DictReader(
            (ROOT / "botw_world/data/logic.csv").read_text(encoding="utf-8").splitlines())}
        shrines = {row["notes"].split()[0]: row["name"] for row in LOCATIONS[:220]
                   if "Shrine" in row["category"].split("|")}
        for row in NEW:
            if row["category"] != "Shrine Chest":
                continue
            shrine = logic[shrines[shrine_chests.dungeon(row)]]
            self.assertEqual(row["region"], shrine["region"])
            self.assertEqual((logic[row["name"]]["climate"], logic[row["name"]]["runes"],
                              logic[row["name"]]["extra"]), (shrine["climate"], shrine["runes"], shrine["extra"]))

    def test_every_new_location_has_a_position(self):
        positions = json.loads((ROOT / "data/location_positions.json").read_text(encoding="utf-8"))
        self.assertTrue(all(row["name"] in positions for row in NEW))


class ShrineChestTests(unittest.TestCase):
    def unit(self, drop="Weapon_Sword_001", hash_id=1234):
        doc = oead.byml.Hash({"Objs": oead.byml.Array([oead.byml.Hash({
            "HashId": oead.U32(hash_id), "UnitConfigName": "TBox_Dungeon_Stone",
            "!Parameters": oead.byml.Hash({"DropActor": drop, "IsInGround": False})})])})
        return bytes(oead.yaz0.compress(bytes(oead.byml.to_binary(doc, big_endian=True, version=2))))

    def row(self, drop="Weapon_Sword_001", hash_id=1234):
        return {"id": 231, "name": "Oman Au Shrine Chest 1", "notes": f"Dungeon004, {drop}",
                "gamedata_flag": f"CDungeon_TBox_Dungeon_Stone_{hash_id}"}

    def test_the_drawn_chest_gives_a_green_rupee_of_its_own(self):
        out, edits = shrine_chests.patch_unit(self.unit(), [self.row()])
        self.assertEqual(out[:4], b"Yaz0")
        obj = oead.byml.from_binary(oead.yaz0.decompress(out))["Objs"][0]
        self.assertEqual(str(obj["!Parameters"]["DropActor"]), "PutRupee_AP0231")
        self.assertEqual(edits[0]["from"], "Weapon_Sword_001")

    def test_the_rupee_is_named_after_the_chests_item(self):
        placement = {"location_id": 231, "location_name": "Oman Au Shrine Chest 1", "item_name": "Hookshot",
                     "recipient_name": "Alice", "recipient_game": "A Link to the Past", "flags": 1}
        name, description = shrine_chests.texts(placement)
        self.assertEqual(name, "Alice's Hookshot")
        self.assertEqual(description.replace("\n", " "), "You got Alice's Hookshot! Seems important.")
        # The tier by the item's classification; a trap passes for junk.
        for flags, tier in ((2, "Seems useful."), (0, "Seems like junk."), (4, "Seems like junk."),
                            (3, "Seems important.")):
            self.assertTrue(shrine_chests.texts({**placement, "flags": flags})[1].replace("\n", " ").endswith(tier))
        # The icon in colour for what seems important or useful, grey for junk and traps.
        self.assertEqual([shrine_chests.bright({"flags": f}) for f in (1, 2, 3, 0, 4, 5)],
                         [True, True, True, False, False, False])
        long = {**placement, "item_name": "Progressive Something Very Long Indeed " * 3,
                "recipient_name": "AVeryLongPlayerName1234"}
        name, description = shrine_chests.texts(long)
        self.assertLessEqual(len(name), shrine_chests.NAME_LIMIT)
        self.assertLessEqual(len(description.split("\n")), 4)
        chest = next(iter(shrine_chests.chests().values()))
        status = {"slot_data": {"extra_locations": [chest["id"]]},
                  "placements": [{**placement, "location_id": chest["id"]}]}
        (rupee,) = shrine_chests.items(status)
        self.assertEqual((rupee.actor, rupee.model_actor, rupee.price),
                         (f"PutRupee_AP{chest['id']:04d}", "PutRupee", None))
        with self.assertRaises(ValueError):
            shrine_chests.items({**status, "placements": []})

    def test_a_chest_holding_something_else_is_refused(self):
        with self.assertRaises(ValueError):
            shrine_chests.patch_unit(self.unit(drop="Item_Ore_A"), [self.row()])
        with self.assertRaises(ValueError):
            shrine_chests.patch_unit(self.unit(hash_id=99), [self.row()])

    def test_only_the_drawn_shrine_chests_one_stage_a_shrine(self):
        chests = list(shrine_chests.chests().values())
        status = {"slot_data": {"extra_locations": [chests[0]["id"], chests[1]["id"], chests[-1]["id"],
                                                    NEW[-1]["id"]]}}
        self.assertEqual([row["id"] for row in shrine_chests.drawn(status)],
                         [chests[0]["id"], chests[1]["id"], chests[-1]["id"]])
        stages = shrine_chests.stages(status)
        self.assertEqual(len(stages), len({shrine_chests.dungeon(row) for row in shrine_chests.drawn(status)}))
        self.assertFalse(shrine_chests.enabled({"slot_data": {"extra_locations": [NEW[-1]["id"]]}}))
        self.assertFalse(shrine_chests.enabled(None))

    def test_the_base_game_is_found_beside_the_update(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            update = Path(temp, "usr/title/0005000e/101c9500/content")
            base = Path(temp, "usr/title/00050000/101c9500/content")
            update.mkdir(parents=True)
            nowhere = Path(temp, "nowhere/code/U-King.rpx")
            with self.assertRaises(FileNotFoundError):
                shrine_chests.base_content(update, launched=nowhere)
            base.mkdir(parents=True)
            self.assertEqual(shrine_chests.base_content(update, launched=nowhere), base.resolve())

    def test_the_base_game_is_found_where_cemu_lists_it(self):
        # The launcher's profile copies only the update and DLC into its own mlc01:
        # the base game is where the player's Cemu launches it from.
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            update = Path(temp, "profile/mlc01/usr/title/0005000e/101c9400/content")
            update.mkdir(parents=True)
            game = Path(temp, "games/BotW [00050000101c9400]")
            (game / "code").mkdir(parents=True)
            (game / "content").mkdir()
            rpx = game / "code" / "U-King.rpx"
            self.assertEqual(shrine_chests.base_content(update, launched=rpx), (game / "content").resolve())
            with self.assertRaises(FileNotFoundError):        # a .wua is not read
                shrine_chests.base_content(update, launched=Path(temp, "games/BotW.wua"))


class ItemTests(unittest.TestCase):
    def test_the_progressive_horse_ends_with_epona_then_the_master_cycle_zero(self):
        entry = load_item_map()["Progressive Horse"]
        self.assertEqual(stage_count(entry), 5)
        stages = entry["delivery"]["stages"]
        self.assertEqual([stage.get("actor") for stage in stages[:4]],
                         ["GameRomHorse00L", "GameRomHorseZelda", "GameRomHorseNushi", "GameRomHorseEpona"])
        self.assertEqual(stages[4], load_item_map()["Master Cycle Zero"]["delivery"])
        self.assertEqual(stages[3], load_item_map()["Epona"]["delivery"])
        world = {row["name"]: row for row in ITEMS}
        self.assertEqual(world["Progressive Horse"]["count"], 5)
        self.assertEqual((world["Epona"]["count"], world["Master Cycle Zero"]["count"]), (0, 0))
        # Every horse it registers is named by the stables (botw_patch/horses.py).
        self.assertTrue({stage["actor"] for stage in stages[:4]} <= set(horses.HORSES))
        for copy in range(5):
            self.assertTrue(compile_delivery_plan("Progressive Horse", copy).steps)

    def test_the_new_traps_are_native(self):
        mapping = load_item_map()
        for name, effect in (("Freeze", "freeze"), ("Lightning Strike", "lightning"), ("Fire", "fire")):
            self.assertEqual(mapping[name]["delivery"]["effect"], effect)
            self.assertIn(effect, NATIVE_EFFECTS)
            self.assertIn(effect, elemental_strike.FIELDS)

    def test_the_new_filler_is_drawn(self):
        # botw_world needs Archipelago to import: its catalog is read as text.
        catalog = (ROOT / "botw_world/catalog.py").read_text(encoding="utf-8")
        mapping = load_item_map()
        for name in ("Farosh's Scale", "Lynel Guts", "Ancient Shaft", "Luminous Stone", "Silent Princess",
                     "Hearty Simmered Fruit", "Mighty Simmered Fruit", "20 Bomb Arrows"):
            self.assertIn(f'"{name}"', catalog)
            self.assertTrue(mapping[name]["generated_filler"])


class ElementalStrikeTests(unittest.TestCase):
    def test_each_trap_creates_its_field_at_links_feet(self):
        for effect, actor in (("freeze", b"ExpandIceField\0"), ("fire", b"ExpandFireField\0")):
            memory = Memory()
            self.assertEqual(elemental_strike.strike(memory.read, memory.write, memory.call, effect), {"ok": 1})
            (request,) = [args for address, args in memory.calls if address == REQUEST_CREATE]
            self.assertEqual(memory.written[request[1]], actor)
            self.assertEqual(request[3], 0)                 # no handle: the game's own
            places = [struct.unpack(">fff", data) for data in memory.written.values() if len(data) == 12]
            self.assertEqual(places, [(100.0, 50.5, 200.0)])
            adds = [args for address, args in memory.calls if address == PACK_ADD]
            self.assertEqual([(args[3], args[4]) for args in adds], [(0xC, 4)])

    def test_lightning_shocks_link_and_a_bolt_strikes_beside_him(self):
        import math
        import random
        memory = Memory()
        result = elemental_strike.strike(memory.read, memory.write, memory.call, "lightning", rng=random.Random(2))
        self.assertEqual(result, {"ok": 1, "bolt ok": 1})
        requests = [args for address, args in memory.calls if address == REQUEST_CREATE]
        self.assertEqual([memory.written[args[1]] for args in requests],
                         [b"ExpandElectricField\0", b"AP_Thunder\0"])
        places = [struct.unpack(">fff", data) for data in memory.written.values() if len(data) == 12]
        self.assertEqual(places[0], (100.0, 50.5, 200.0))
        x, y, z = places[1]
        self.assertAlmostEqual(math.hypot(x - 100.0, z - 200.0), elemental_strike.BOLT_DISTANCE, places=4)
        self.assertEqual(y, 50.0)
        # In parts: the bolt alone, the field alone.
        for part, actor in (("bolt", b"AP_Thunder\0"), ("field", b"ExpandElectricField\0")):
            memory = Memory()
            elemental_strike.strike(memory.read, memory.write, memory.call, "lightning", part=part)
            requests = [args for address, args in memory.calls if address == REQUEST_CREATE]
            self.assertEqual([memory.written[args[1]] for args in requests], [actor])

    def test_the_backend_strikes_the_bolt_then_the_field_as_it_lands(self):
        from unittest import mock
        from botw_client.native_delivery import CemuNativeDeliveryBackend
        backend = CemuNativeDeliveryBackend.__new__(CemuNativeDeliveryBackend)
        backend._drop_blocked = lambda: None
        backend._frames_since_commit = lambda: None
        memory, waits = Memory(), []
        backend._call = memory.call
        backend._in_one_turn = lambda work: work(memory.read, memory.write)
        with mock.patch("time.sleep", waits.append):
            self.assertEqual(backend.elemental_strike("lightning"), {"bolt ok": 1, "ok": 1})
        self.assertEqual(waits, [elemental_strike.BOLT_LEAD])
        requests = [args for address, args in memory.calls if address == REQUEST_CREATE]
        self.assertEqual([memory.written[args[1]] for args in requests], [b"AP_Thunder\0", b"ExpandElectricField\0"])

    def test_no_player_no_strike(self):
        memory = Memory()
        memory.words[PLAYER_INFO] = 0
        self.assertEqual(elemental_strike.strike(memory.read, memory.write, memory.call, "fire"), {"player": 1})
        self.assertEqual(memory.calls, [])

    def test_not_while_the_traps_event_is_closing(self):
        from botw_client.native_delivery import SETTLE_FRAMES, CemuNativeDeliveryBackend
        backend = CemuNativeDeliveryBackend.__new__(CemuNativeDeliveryBackend)
        frame = [1000]
        backend.game = SimpleNamespace(frame_tick=lambda: frame[0])
        backend._committed_at = 970
        backend._drop_blocked = lambda: None
        turns = []
        backend._in_one_turn = lambda work: turns.append(work) or "ok"
        self.assertTrue(backend.elemental_strike("freeze").startswith("the trap's event closing"))
        self.assertEqual(turns, [])
        frame[0] = 970 + SETTLE_FRAMES
        self.assertEqual(backend.elemental_strike("freeze"), {})
        self.assertEqual(len(turns), 1)


class MasterModeTests(unittest.TestCase):
    def runtime(self, master_mode, save_hard):
        from botw_client.runtime import BotwClientRuntime
        runtime = BotwClientRuntime.__new__(BotwClientRuntime)
        runtime.ap = SimpleNamespace(slot_data={"master_mode": master_mode})
        runtime.game = SimpleNamespace(live=SimpleNamespace(get=lambda hash_u32, kind: save_hard))
        return runtime

    def test_a_save_of_the_other_mode_stops_the_client(self):
        from botw_client.runtime import FatalClientError
        self.runtime(True, 1)._check_save_mode()
        self.runtime(False, 0)._check_save_mode()
        self.runtime(True, None)._check_save_mode()          # unreadable: not judged
        with self.assertRaisesRegex(FatalClientError, "MASTER MODE"):
            self.runtime(True, 0)._check_save_mode()
        with self.assertRaisesRegex(FatalClientError, "NORMAL MODE"):
            self.runtime(False, 1)._check_save_mode()

    def test_the_master_mode_chests_are_marked(self):
        marked = [row for row in NEW if "master mode only" in row["notes"]]
        self.assertEqual(len(marked), 118)
        self.assertTrue(all(row["category"] == "Chest" for row in marked))
        self.assertIn("MainField_TBox_Field_Iron_3090346856", {row["gamedata_flag"] for row in marked})

    def test_the_chests_need_what_the_game_asks(self):
        logic = {row["location"]: row for row in csv.DictReader(
            (ROOT / "botw_world/data/logic.csv").read_text(encoding="utf-8").splitlines())}
        chests = [row for row in NEW if row["category"] == "Chest"]
        # The Great Plateau's pond: two metal chests 3 m under water, Magnesis.
        pond = [row for row in chests if row["region"] == "Great Plateau" and "under water" in row["notes"]]
        self.assertGreaterEqual(len(pond), 2)
        self.assertTrue(all("Magnesis" in logic[row["name"]]["runes"] for row in pond))
        for note, rune in (("buried", "Magnesis"), ("under water", "Magnesis"),
                           ("behind a cracked wall", "Progressive Remote Bomb"),
                           ("under rocks", "Progressive Remote Bomb")):
            marked = [row for row in chests if note in row["notes"]]
            self.assertTrue(marked, note)
            self.assertTrue(all(rune in logic[row["name"]]["runes"].split("|") for row in marked), note)
        self.assertEqual(len([row for row in chests if "never drawn" in row["notes"]]), 3)
        self.assertEqual(len([row for row in chests if logic[row["name"]]["extra"] == "All Shrines"]), 3)

    def test_the_new_locations_are_named_after_places(self):
        names = [row["name"] for row in NEW]
        self.assertEqual(len(set(names)), len(names))
        chest = next(row for row in NEW if row["gamedata_flag"] == "MainField_TBox_Field_Iron_3090346856")
        self.assertIn("(Master Mode", chest["name"])
        self.assertFalse([n for n in names if "#" in n])
        shrine = [row["name"] for row in NEW if row["category"] == "Shrine Chest"]
        self.assertTrue(all(" Shrine Chest" in n for n in shrine))
        bosses = [row["name"] for row in NEW if row["category"] == "Boss"]
        self.assertTrue(all(" - " in n for n in bosses))

    def test_the_quest_says_master_mode(self):
        from botw_patch.ap_quest import texts
        manifest = {"seed": "1", "slot_name": "Unix", "slot": 1, "slot_data": {"master_mode": True}}
        self.assertIn("MASTER MODE", texts(manifest)["desc"])
        self.assertNotIn("MASTER MODE", texts({**manifest, "slot_data": {}})["desc"])


class RegionReportTests(unittest.TestCase):
    def test_links_region_in_the_field_only(self):
        from botw_client import region_report
        from botw_client.region_border import MAP_TYPE

        class Areas:
            @staticmethod
            def region_at(x, z):
                return "Hebra" if (x, z) == (100.0, 200.0) else None

        memory = Memory()
        words = {**memory.words}

        def read(guest, size, stage=b"MainField"):
            if guest == MAP_TYPE:
                return stage + bytes(size - len(stage))
            if size == 4 and guest in words:
                return words[guest].to_bytes(4, "big")
            return None
        # The player's pointers of Memory are low addresses: accepted as the game's here.
        import unittest.mock as mock
        with mock.patch.object(region_report, "in_guest", lambda address: bool(address)):
            self.assertEqual(region_report.link_region(read, Areas), "Hebra")
            self.assertIsNone(region_report.link_region(lambda g, s: read(g, s, b"CDungeon"), Areas))
        self.assertEqual(region_report.set_command(0, 2, "Hebra"), {
            "cmd": "Set", "key": "botw_region_0_2", "default": "", "want_reply": False,
            "operations": [{"operation": "replace", "value": "Hebra"}]})


if __name__ == "__main__":
    unittest.main()

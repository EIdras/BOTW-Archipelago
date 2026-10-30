"""The tower maps as items: the towers' own flag in the pack (botw_patch/tower_maps.py),
the client tracking a tower by it, and the maps' delivery."""
from __future__ import annotations

import json
from pathlib import Path
import unittest
import zlib

import oead

from botw_client import gamedata_table
from botw_client.delivery_plan import MutationKind, compile_delivery_plan
from botw_client.locations import LocationTarget, LocationTracker, load_targets, tower_activation_flag
from botw_patch import tower_maps
from botw_patch.resources import unpack
from tests.full_build import full_build

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
AOC = UPDATE.parents[2] / "0005000c/101c9500/content/0010"
HAS_DLC = (AOC / "Map/MainField").is_dir()
NEEDS_TABLE = unittest.skipUnless(gamedata_table.available(), "the GameData flag table is read from the game")


def save_flags(raw: bytes) -> dict[int, str]:
    doc = oead.byml.from_binary(unpack(raw))
    return {int(o["HashId"]): str(o["!Parameters"]["SaveFlag"]) for o in doc["Objs"]
            if str(o["UnitConfigName"]) == tower_maps.TAG and "!Parameters" in o
            and "SaveFlag" in o["!Parameters"]}


class CatalogueTests(unittest.TestCase):
    def test_every_tower_but_the_plateaus_has_its_own_flag(self):
        rows = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
        towers = {row["gamedata_flag"][-2:]: row["region"] for row in rows if row["category"] == "Tower"}
        self.assertEqual({number: region for number, (region, _cell, _tags) in tower_maps.TOWERS.items()},
                         {number: region for number, region in towers.items() if number != "07"})
        self.assertEqual(tower_maps.FLAGS, tuple(f"APTower_{number}" for number in tower_maps.TOWERS))

    @NEEDS_TABLE
    def test_the_towers_flags_take_no_hash_of_the_game(self):
        from botw_client.gamedata_table import load
        taken = {int(key) & 0xFFFFFFFF for key in load()}
        self.assertFalse({zlib.crc32(flag.encode()) for flag in tower_maps.FLAGS} & taken)

    def test_a_tower_flag_names_its_tower(self):
        self.assertEqual(tower_activation_flag("MapTower_08"), "APTower_08")
        with self.assertRaises(ValueError):
            tower_activation_flag("Clear_Dungeon000")


class TrackerTests(unittest.TestCase):
    @NEEDS_TABLE
    def test_towers_but_the_plateaus_may_be_tracked_by_their_own_flag(self):
        targets = {target.name: target for target in load_targets()}
        self.assertEqual(targets["Hebra Tower"].pack_flag, "APTower_01")
        self.assertIsNone(targets["Great Plateau Tower"].pack_flag)
        self.assertIsNone(targets["Oman Au Shrine"].pack_flag)

    def test_a_pack_that_declares_the_flag_tracks_the_tower_by_it(self):
        own = zlib.crc32(b"APTower_01")

        class Memory:
            def __init__(self):
                self.data = bytearray(64)

            def read(self, address, size):
                return bytes(self.data[address:address + size])

        class Live:
            base = 0
            index = {"bool": {own: 16, 10: 32}}

        memory = Memory()
        target = LocationTarget("Hebra Tower", "MapTower_01", 10, pack_flag="APTower_01")
        tracker = LocationTracker(memory, {}, [target], live=Live())
        self.assertEqual(tracker.poll(), [])
        memory.data[32 + 7] = 1         # the map, MapTower_01: not the tower
        self.assertEqual(tracker.poll(), [])
        memory.data[16 + 7] = 1         # the tower's own flag
        self.assertEqual(tracker.poll(), ["Hebra Tower"])

    def test_without_the_flag_the_tower_is_its_map_flag_as_before(self):
        class Memory:
            data = bytearray(64)

            def read(self, address, size):
                return bytes(self.data[address:address + size])

        class Live:
            base = 0
            index = {"bool": {10: 32}}

        memory = Memory()
        tracker = LocationTracker(memory, {}, [LocationTarget("Hebra Tower", "MapTower_01", 10,
                                                              pack_flag="APTower_01")], live=Live())
        memory.data[32 + 7] = 1
        self.assertEqual(tracker.poll(), ["Hebra Tower"])


class DeliveryTests(unittest.TestCase):
    def test_a_map_opens_the_map_on_its_tower_flag(self):
        plan = compile_delivery_plan("Faron Map")
        (step,) = plan.steps
        (mutation,) = step.mutations
        self.assertEqual((mutation.kind, mutation.target), (MutationKind.MAP_OPEN, "MapTower_14"))


class NativeTests(unittest.TestCase):
    """tools/build_tower_maps_native.py, in the native build."""

    @classmethod
    def setUpClass(cls):
        from tools.build_native_from_source import generate
        cls.plain = generate()["runtime/patch_apInject.asm"].decode("utf-8")
        cls.maps = generate(tower_maps=True)["runtime/patch_apInject.asm"].decode("utf-8")

    def test_every_pack_has_the_map_openings_fallback(self):
        for text in (self.plain, self.maps):
            self.assertEqual(text.count("0x023f88ec = bla apMapOpenCheck"), 1)
            self.assertIn("apMapTower:\n.int 0xFFFFFFFF", text)

    def test_only_a_pack_whose_maps_are_items_patches_the_tower_icons(self):
        self.assertNotIn("apTowerPrefix", self.plain)
        self.assertEqual(self.maps.count("0x02e94c8c = bla apTowerPrefix"), 1)
        self.assertIn('apTowerName:\n.string "APTower_"', self.maps)
        self.assertIn("cmpwi r12, 6", self.maps)            # the Great Plateau's icon as the game made it

    def test_the_fields_follow_the_rune_selections_where_the_client_reads_them(self):
        # tools/cemu/mailbox.py: sel_result +9288, then map_magic +9292 and map_tower +9296.
        tail = self.plain[self.plain.index("apSelResult:"):]
        words = [line for line in tail.split("\n")[:12] if line.startswith((".int", ".string")) or line.endswith(":")]
        self.assertEqual(words[:5], ["apSelResult:", ".int 0", "apMapMagic:", ".int 0x4D4F5031", "apMapTower:"])
        import inspect
        from tools.cemu import mailbox
        source = inspect.getsource(mailbox)
        self.assertIn("self.map_magic = version_addr + 9292", source)
        self.assertIn("self.map_tower = version_addr + 9296", source)
        self.assertIn("self.sel_result = version_addr + 9288", source)


@unittest.skipUnless(HAS_DLC, "requires the DLC")
class MapUnitTests(unittest.TestCase):
    def test_each_towers_tags_save_its_own_flag(self):
        for number, (_region, cell, tags) in tower_maps.TOWERS.items():
            with self.subTest(tower=number):
                raw = (AOC / tower_maps.unit(cell)).read_bytes()
                new, detail = tower_maps.patch_map(raw, [number])
                before, after = save_flags(raw), save_flags(new)
                self.assertEqual(sorted(h for h, flag in before.items() if flag == f"MapTower_{number}"),
                                 sorted(tags))
                self.assertFalse([h for h, flag in after.items() if flag == f"MapTower_{number}"])
                self.assertEqual({h: after[h] for h in tags}, {h: f"APTower_{number}" for h in tags})
                # Everything else is as it was.
                self.assertEqual({h: f for h, f in after.items() if h not in tags},
                                 {h: f for h, f in before.items() if h not in tags})
                old = oead.byml.from_binary(unpack(raw))["Objs"]
                self.assertEqual([int(o["HashId"]) for o in oead.byml.from_binary(unpack(new))["Objs"]],
                                 [int(o["HashId"]) for o in old])

    def test_the_plateaus_tower_is_left_alone(self):
        self.assertNotIn("07", tower_maps.TOWERS)

    @full_build
    def test_a_seed_with_maps_and_stalls_patches_the_shared_units_once_for_both(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from botw_patch.shops import plan_from_manifest
        from tools.build_resources_from_source import generate
        ids = [202, 208]          # Kakariko (G-6) and Tarrey Town (I-3): towers' units too
        manifest = {"slot": 1, "seed": "1", "slot_name": "Player", "slot_data": {"tower_maps": 2},
                    "shops": [{"location_id": i, "price": 100} for i in ids],
                    "placements": [{"location_id": i, "item_name": f"Item {i}",
                                    "recipient_name": "Player", "recipient_game": "Breath of the Wild",
                                    "flags": 1, "recipient": 1} for i in ids]}
        files, _catalog, _changes = generate(UPDATE, 417391497, shops=plan_from_manifest(manifest),
                                             status=manifest, aoc=AOC)
        for number, (_region, cell, tags) in tower_maps.TOWERS.items():
            flags = save_flags(files["aoc/0010/" + tower_maps.unit(cell)])
            self.assertEqual({flags[h] for h in tags}, {f"APTower_{number}"})
        kakariko = save_flags(files["aoc/0010/" + tower_maps.unit("G-6")])
        self.assertIn("IsGet_AP_Shop_202", kakariko.values())
        self.assertEqual(files["aoc/0010/Pack/AocMainField.pack"], b"")


if __name__ == "__main__":
    unittest.main()

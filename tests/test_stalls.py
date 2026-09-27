"""3D stall locations: catalogue, map units, merchant flows, seed option."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import unittest

import oead

from botw_client.stall_catalog import (BY_ID, FIRST_LOCATION_ID, LOCATIONS, MERCHANTS,
                                       SLOTS_PER_MERCHANT, catalogue_row, world_row)
from botw_patch.resources import unpack

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
AOC = UPDATE.parents[2] / "0005000c/101c9500/content/0010"
HAS_GAME = (UPDATE / "Pack/TitleBG.pack").is_file() and AOC.is_dir()


def objects(unit):
    doc = oead.byml.from_binary(unpack((AOC / unit).read_bytes()))
    return {int(o["HashId"]): o for o in doc["Objs"]}


def links(obj):
    return ([(str(l["DefinitionName"]), int(l["DestUnitHashId"])) for l in obj["LinksToObj"]]
            if "LinksToObj" in obj else [])


class CatalogueTests(unittest.TestCase):
    def test_ids_follow_the_beedle_items_without_gaps(self):
        self.assertEqual(FIRST_LOCATION_ID, 186)
        self.assertEqual([l.id for l in LOCATIONS],
                         list(range(186, 186 + len(MERCHANTS) * SLOTS_PER_MERCHANT)))
        self.assertEqual(len(LOCATIONS), 28)
        self.assertEqual(len({l.name for l in LOCATIONS}), 28)
        self.assertEqual(len({l.object_hash for l in LOCATIONS}), 28)
        self.assertEqual(BY_ID[202].name, "Kakariko Village - Arrow Stall Item 1")
        self.assertTrue(all(len(l.actor) == 11 for l in LOCATIONS))

    def test_a_stall_keeps_a_copy_of_everything_it_sold(self):
        for merchant in MERCHANTS:
            self.assertEqual(len(merchant.objects), SLOTS_PER_MERCHANT)

    def test_data_files_carry_exactly_the_catalogue(self):
        with (ROOT / "data/locations_master.csv").open(encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["category"] == "Stall"]
        self.assertEqual(rows, [catalogue_row(l) for l in LOCATIONS])
        world = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
        self.assertEqual([r for r in world if r["category"] == "Stall"],
                         [world_row(l) for l in LOCATIONS])
        self.assertEqual([r["id"] for r in world][-28:], [l.id for l in LOCATIONS])


@unittest.skipUnless(HAS_GAME, "requires the Wii U update and the DLC")
class GameFileTests(unittest.TestCase):
    def test_every_object_is_on_sale_at_its_merchant_in_several_copies(self):
        for merchant in MERCHANTS:
            objs = objects(merchant.map_unit)
            me = objs[merchant.hash_id]
            self.assertEqual(str(me["UnitConfigName"]), merchant.actor)
            rotate = me["Rotate"] if "Rotate" in me else 0.0
            yaw = float(rotate[1]) if isinstance(rotate, oead.byml.Array) else float(rotate)
            self.assertAlmostEqual(yaw, merchant.yaw, places=5)
            sold = [o for o in objs.values() if ("ForSale", merchant.hash_id) in links(o)]
            counts = {}
            for o in sold:
                counts[str(o["UnitConfigName"])] = counts.get(str(o["UnitConfigName"]), 0) + 1
            for hash_id, actor in merchant.objects:
                self.assertEqual(str(objs[hash_id]["UnitConfigName"]), actor)
                self.assertIn(objs[hash_id], sold)
                counts[actor] -= 1
            self.assertTrue(all(n >= 1 for n in counts.values()), merchant.actor)

    def test_the_buy_event_is_the_merchants_display_shop(self):
        from botw_patch.events import graph_snapshot, read_flow
        for merchant in MERCHANTS:
            pack = oead.Sarc(unpack((UPDATE / f"Event/{merchant.actor}.sbeventpack").read_bytes()))
            flow = graph_snapshot(read_flow(bytes(
                pack.get_file(f"EventFlow/{merchant.actor}.bfevfl").data)))
            event = flow["events"][merchant.buy_event]
            self.assertEqual((event["type"], event["res_flowchart_name"],
                              event["entry_point_name"]),
                             ("SubFlowEvent", "DisplayShop", "Multiple"), merchant.actor)

    def test_map_objects_become_ap_actors_created_by_their_flag(self):
        from botw_patch.stalls import patch_map, tag_hash
        located = [l for l in LOCATIONS if l.merchant.cell == "G-6"]
        raw = (AOC / located[0].merchant.map_unit).read_bytes()
        new, _ = patch_map(raw, located)
        before = oead.byml.from_binary(unpack(raw))
        after = oead.byml.from_binary(unpack(new))
        objs = {int(o["HashId"]): o for o in after["Objs"]}
        self.assertEqual(len(after["Objs"]), len(before["Objs"]) + len(located))
        hashes = [int(o["HashId"]) for o in after["Objs"]]
        self.assertEqual(hashes, sorted(hashes))
        for location in located:
            obj = objs[location.object_hash]
            self.assertEqual(str(obj["UnitConfigName"]), location.actor)
            self.assertAlmostEqual(float(obj["Rotate"]), location.merchant.yaw, places=5)
            self.assertIn(("ForSale", location.merchant.hash_id), links(obj))
            tag = objs[tag_hash(location)]
            self.assertEqual(str(tag["UnitConfigName"]), "LinkTagAnd")
            self.assertEqual(str(tag["!Parameters"]["SaveFlag"]), location.shown_flag)
            self.assertFalse(tag["!Parameters"]["NoChangeSignal"])
            self.assertEqual(links(tag), [("Create", location.object_hash)])
            self.assertEqual([float(v) for v in tag["Translate"]],
                             [float(v) for v in obj["Translate"]])
        # Nothing else moved.
        old = {int(o["HashId"]): o for o in before["Objs"]}
        for hash_id, obj in old.items():
            if hash_id not in {l.object_hash for l in located}:
                self.assertEqual(oead.byml.to_text(objs[hash_id]), oead.byml.to_text(obj))

    def test_a_seed_with_stalls_only_leaves_beedle_alone(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from botw_patch.shops import plan_from_manifest
        from tools.build_resources_from_source import generate
        ids = [202, 203, 212]
        manifest = {"slot": 1, "shops": [{"location_id": i, "price": 100} for i in ids],
                    "placements": [{"location_id": i, "item_name": f"Item {i}",
                                    "recipient_name": "Simon",
                                    "recipient_game": "Breath of the Wild",
                                    "flags": 1, "recipient": 1} for i in ids]}
        files, _catalog, _changes = generate(UPDATE, 417391497,
                                             shops=plan_from_manifest(manifest), aoc=AOC)
        self.assertIn("aoc/0010/Map/MainField/G-6/G-6_Static.smubin", files)
        self.assertIn("aoc/0010/Map/MainField/I-7/I-7_Static.smubin", files)
        self.assertIn("Event/Npc_Kakariko010.sbeventpack", files)
        self.assertIn("Event/Npc_HatenoVillage002.sbeventpack", files)
        self.assertFalse(any("TripMaster" in name for name in files))
        for i in ids:
            self.assertIn(f"Actor/Pack/AP_Shop_{i}.sbactorpack", files)


if __name__ == "__main__":
    unittest.main()

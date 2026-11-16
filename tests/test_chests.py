"""Chests that hold the Archipelago item (botw_patch/chests.py): the map units,
the removal entry, the item's texts, and the stage in a seed's pack."""
from __future__ import annotations

import collections
from pathlib import Path
import unittest

import oead

from botw_patch import chests
from botw_patch.events import read_flow
from botw_patch.resources import unpack, vanilla_digest
from tests.full_build import full_build

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
AOC = UPDATE.parents[2] / "0005000c/101c9500/content/0010"
HAS_DLC = (AOC / "Map/MainField").is_dir()


def contents(raw: bytes) -> dict[int, tuple[str, str | None]]:
    """HashId: (actor, DropActor) of every chest-like object of a unit."""
    doc = oead.byml.from_binary(unpack(raw))
    return {int(o["HashId"]): (str(o["UnitConfigName"]),
                               str(o["!Parameters"]["DropActor"]) if "!Parameters" in o
                               and "DropActor" in o["!Parameters"] else None)
            for o in doc["Objs"] if str(o["UnitConfigName"]).startswith("TBox")}


class CatalogueTests(unittest.TestCase):
    def test_off_unless_the_slot_asks(self):
        self.assertFalse(chests.enabled(None))
        self.assertFalse(chests.enabled({"slot_data": {}}))
        self.assertTrue(chests.enabled({"slot_data": {"chest_sanity": 1}}))

    def test_the_stage_is_not_listed_without_the_option(self):
        from tools.build_resources_from_source import stage_names
        self.assertNotIn("the chests", stage_names(None, {"slot_data": {}}))
        self.assertIn("the chests", stage_names(None, {"slot_data": {"chest_sanity": 1}}))

    def test_every_language_has_a_name_and_description(self):
        from botw_client import regions
        for region in (regions.EUR, regions.USA, regions.JPN):
            for language in region.languages:
                with self.subTest(language=language):
                    item = chests.item(language)
                    self.assertTrue(item.name and item.description)
        self.assertEqual(chests.item("USfr").name, chests.item("EUfr").name)
        self.assertEqual(chests.item("EUfr").name, "Objet Archipelago")


@unittest.skipUnless(HAS_DLC, "requires the DLC")
class MapUnitTests(unittest.TestCase):
    @full_build
    def test_the_units_are_the_games(self):
        for name, expected in chests.MAP_HASHES.items():
            with self.subTest(unit=name):
                self.assertEqual(vanilla_digest((AOC / chests.unit(name)).read_bytes()), expected)

    @full_build
    def test_every_chest_holds_the_item_and_nothing_else_changes(self):
        total, kinds = 0, collections.Counter()
        for name in chests.MAP_HASHES:
            with self.subTest(unit=name):
                raw = (AOC / chests.unit(name)).read_bytes()
                new, detail = chests.patch_map(raw)
                before, after = contents(raw), contents(new)
                changed = {h for h in before if before[h] != after[h]}
                self.assertEqual(len(changed), len(detail))
                for h in changed:
                    self.assertEqual(after[h], (before[h][0], chests.ACTOR))
                    kinds[before[h][0]] += 1
                total += len(detail)
                # Master Mode, the One-Hit trial and the gamble chests keep their own.
                self.assertFalse(any(before[h][0] == "TBox_Field_Gamble" for h in changed))
                old = oead.byml.from_binary(unpack(raw))["Objs"]
                self.assertEqual([int(o["HashId"]) for o in oead.byml.from_binary(unpack(new))["Objs"]],
                                 [int(o["HashId"]) for o in old])
        self.assertEqual(total, chests.CHEST_COUNT)
        self.assertEqual(kinds["TBox_Field_Enemy"], 54)

    @full_build
    def test_the_numbers_follow_the_flags(self):
        items = chests.numbering({name: (AOC / chests.unit(name)).read_bytes() for name in chests.MAP_HASHES})
        self.assertEqual(len(items), chests.CHEST_COUNT)
        self.assertEqual(sorted(items.values()), [chests.actor(n) for n in range(1, chests.CHEST_COUNT + 1)])
        self.assertEqual([items[flag] for flag in sorted(items)], sorted(items.values()))

    def test_master_mode_one_hit_and_gamble_chests_are_left(self):
        left = collections.Counter()
        for path in (AOC / "Map/MainField").glob("*/*.smubin"):
            for obj in oead.byml.from_binary(unpack(path.read_bytes()))["Objs"]:
                if not str(obj["UnitConfigName"]).startswith("TBox") or chests.is_chest(obj):
                    continue
                parameters = obj["!Parameters"] if "!Parameters" in obj else {}
                left[next((name for name in chests.LEFT_PARAMETERS if name in parameters
                           and bool(parameters[name])), str(obj["UnitConfigName"]))] += 1
        self.assertEqual(dict(left), {"IsHardModeActor": 118, "IsIchigekiActor": 4, "TBox_Field_Gamble": 3})


@unittest.skipUnless(HAS_DLC, "requires the DLC")
class EntryTests(unittest.TestCase):
    def test_the_removal_entry_is_added_to_the_quiet_host(self):
        from botw_patch.delivery_flow import QUIET_FLOW
        title = oead.Sarc(unpack((UPDATE / chests.TITLE).read_bytes()))
        raw = bytes(title.get_file(f"EventFlow/{QUIET_FLOW}.bfevfl").data)
        items = [chests.actor(1), chests.actor(1190)]
        new, detail = chests.add_entry(raw, items)
        self.assertEqual(detail, [f"{QUIET_FLOW}<APChestRemove_0001>", f"{QUIET_FLOW}<APChestRemove_1190>"])
        chart = read_flow(new).flowchart
        for item in items:
            with self.subTest(item=item):
                self.assertIn(chests.entry(item), [p.name for p in chart.entry_points])
                uses = [event for event in chart.events if getattr(event.data, "params", None) is not None
                        and event.data.params.data.get("PorchItemName") == item]
                self.assertEqual(len(uses), 2)       # the question, then the removal of one
                self.assertEqual({e.data.params.data.get("Count", e.data.params.data.get("DeleteNum"))
                                  for e in uses}, {1})
        with self.assertRaises(ValueError):
            chests.add_entry(new, items[:1])

    def test_a_numbered_item_shows_its_name_and_the_shared_icon(self):
        item = chests.item("EUfr", chests.actor(7), ("Hookshot for Alice", "Found for Alice."))
        self.assertEqual((item.actor, item.name, item.icon_actor), ("AP_Chest_0007", "Hookshot for Alice",
                                                                    chests.ACTOR))
        self.assertEqual(chests.item("EUfr", chests.actor(7)).name, "Objet Archipelago")
        self.assertIsNone(chests.item("EUfr").icon_actor)


@unittest.skipUnless(HAS_DLC, "requires the DLC")
class StageTests(unittest.TestCase):
    @full_build
    def test_a_seed_without_shops_gets_the_model_and_every_unit(self):
        from tools.build_resources_from_source import generate
        status = {"slot": 1, "seed": "1", "slot_name": "Player", "slot_data": {"chest_sanity": 1},
                  "placements": []}
        files, _catalog, changes = generate(UPDATE, 417391497, status=status, aoc=AOC)
        self.assertIn("Model/AP_Item_00.sbfres", files)
        self.assertIn(f"Actor/Pack/{chests.ACTOR}.sbactorpack", files)
        self.assertIn(f"Actor/Pack/{chests.actor(chests.CHEST_COUNT)}.sbactorpack", files)
        self.assertEqual(len([c for c in changes if "chests" in c and c["chests"]
                              and all(x["item"].startswith(chests.ACTOR + "_") for x in c["chests"])]),
                         len(chests.MAP_HASHES))
        self.assertEqual(files["aoc/0010/Pack/AocMainField.pack"], b"")
        units = [name for name in files if name.startswith("aoc/0010/Map/")]
        self.assertEqual(len(units), len(chests.MAP_HASHES))
        self.assertEqual(sum(len(c["chests"]) for c in changes if "chests" in c), chests.CHEST_COUNT)

    @full_build
    def test_with_shops_and_towers_the_shared_units_hold_both(self):
        from botw_patch.shops import plan_from_manifest
        from tools.build_resources_from_source import generate
        from tests.test_tower_maps import save_flags
        ids = [202, 208]          # Kakariko (G-6) and Tarrey Town (I-3): towers' and chests' units too
        manifest = {"slot": 1, "seed": "1", "slot_name": "Player",
                    "slot_data": {"tower_maps": 2, "chest_sanity": 1},
                    "shops": [{"location_id": i, "price": 100} for i in ids],
                    "placements": [{"location_id": i, "item_name": f"Item {i}",
                                    "recipient_name": "Player", "recipient_game": "Breath of the Wild",
                                    "flags": 1, "recipient": 1} for i in ids]}
        files, _catalog, _changes = generate(UPDATE, 417391497, shops=plan_from_manifest(manifest),
                                             status=manifest, aoc=AOC)
        kakariko = files["aoc/0010/" + chests.unit("G-6/G-6_Static")]
        self.assertIn("IsGet_AP_Shop_202", save_flags(kakariko).values())
        self.assertTrue(any(drop and drop.startswith(chests.ACTOR + "_")
                            for _actor, drop in contents(kakariko).values()))


if __name__ == "__main__":
    unittest.main()

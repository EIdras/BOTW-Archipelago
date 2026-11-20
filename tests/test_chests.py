"""Chests that hold the Archipelago item (botw_patch/chests.py): the map units,
the removal entry, the item's texts, and the stage in a seed's pack."""
from __future__ import annotations

import collections
import json
from pathlib import Path
import unittest

import oead

from botw_patch import chests
from botw_patch.events import read_flow
from botw_patch.resources import unpack, vanilla_digest
from tests.full_build import full_build
from tools import chest_locations

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
        # check_only: the chests keep their contents, the pack leaves them alone.
        self.assertFalse(chests.enabled({"slot_data": {"chest_sanity": 1}}))
        self.assertTrue(chests.enabled({"slot_data": {"chest_sanity": chests.AP_ITEMS}}))

    def test_the_stage_is_not_listed_without_the_option(self):
        from tools.build_resources_from_source import stage_names
        self.assertNotIn("the chests", stage_names(None, {"slot_data": {}}))
        self.assertNotIn("the chests", stage_names(None, {"slot_data": {"chest_sanity": 1}}))
        self.assertIn("the chests", stage_names(None, {"slot_data": {"chest_sanity": chests.AP_ITEMS}}))

    def test_every_language_has_a_name_and_description(self):
        from botw_client import regions
        for region in (regions.EUR, regions.USA, regions.JPN):
            for language in region.languages:
                with self.subTest(language=language):
                    item = chests.item(language)
                    self.assertTrue(item.name and item.description)
        self.assertEqual(chests.item("USfr").name, chests.item("EUfr").name)
        self.assertEqual(chests.item("EUfr").name, "Objet Archipelago")


class WorldTests(unittest.TestCase):
    def test_a_chest_location_names_the_item_inside(self):
        status = {"slot": 1, "placements": [
            {"location_id": chests.CHEST_ID_BASE + 7, "location_name": "Biron Snowshelf - Skull Chest 1",
             "item_name": "Hookshot", "recipient": 2, "recipient_name": "Alice", "recipient_game": "Ocarina",
             "flags": 1},
            {"location_id": chests.CHEST_ID_BASE + 8, "item_name": "Arrows", "recipient": 1,
             "recipient_name": "Player", "recipient_game": "Breath of the Wild", "flags": 0},
            {"location_id": 12, "item_name": "Paraglider", "recipient": 1, "recipient_name": "Player",
             "recipient_game": "Breath of the Wild", "flags": 1}]}
        names = chests.placed_names(status)
        self.assertEqual(set(names), {"AP_Chest_0007", "AP_Chest_0008"})
        self.assertEqual(names["AP_Chest_0007"][0], "Hookshot")
        self.assertIn("for Alice (Ocarina)", names["AP_Chest_0007"][1])
        self.assertIn("for you", names["AP_Chest_0008"][1])

    def test_a_chest_is_named_after_the_nearest_place_of_its_region(self):
        marks = [("Lake", 0.0, 0.0), ("Hill", 50.0, 0.0), ("Cape", 500.0, 0.0)]
        region_of = {0.0: "A", 50.0: "B", 500.0: "A"}
        rows = [{"number": 1, "kind": "Iron", "region": "A", "position": [40.0, 0.0, 0.0]},
                {"number": 2, "kind": "Iron", "region": "A", "position": [5.0, 0.0, 0.0]},
                {"number": 3, "kind": "Stone", "region": "A", "position": [45.0, 0.0, 0.0]},
                {"number": 4, "kind": "Iron", "region": "C", "position": [490.0, 0.0, 0.0]}]
        chest_locations.name_chests(rows, marks, lambda x, z: region_of[x])
        # Hill is nearer chests 1 and 3 but in another region; C has no place: the nearest of all.
        self.assertEqual([row["name"] for row in rows],
                         ["Lake - Iron Chest 2", "Lake - Iron Chest 1", "Lake - Stone Chest", "Cape - Iron Chest"])

    def test_the_world_numbers_its_chests_as_the_pack(self):
        rows = json.loads((ROOT / "botw_world/data/chests.json").read_text(encoding="utf-8"))
        source = (ROOT / "botw_world/catalog.py").read_text(encoding="utf-8")
        self.assertIn(f"CHEST_ID_BASE = {chests.CHEST_ID_BASE}\n", source)
        self.assertIn(f'ALL_SHRINES = "{chest_locations.ALL_SHRINES}"\n', source)
        options = (ROOT / "botw_world/options.py").read_text(encoding="utf-8")
        self.assertIn(f"option_ap_items = {chests.AP_ITEMS}\n", options)
        field = [row for row in rows if not row.get("dungeon")]
        shrines = [row for row in rows if row.get("dungeon") and not row.get("sent_with")]
        beasts = [row for row in rows if row.get("sent_with")]
        # Left out too: the Warm Doublet's chest, two of a Lake Saria puzzle's, the Xenoblade collaboration's three.
        self.assertEqual(len(field), chests.CHEST_COUNT - len(chest_locations.INACCESSIBLE) - 6)
        # The base game's 186 shrine chests but their 12 small keys; the DLC's 19 are numbered, not yet locations.
        self.assertEqual(len(shrines), 174)
        self.assertEqual([row["number"] for row in rows], sorted({row["number"] for row in rows}))
        self.assertTrue(all(1 <= row["number"] <= chests.CHEST_COUNT for row in field))
        last = chests.CHEST_COUNT + chests.SHRINE_CHEST_COUNT
        self.assertTrue(all(chests.CHEST_COUNT < row["number"] <= last and row["heat"] is None
                            and row["name"].startswith(row["dungeon"] + " - ") for row in shrines))
        # The Divine Beasts' chests that have a flag, sent with their beast once it is freed.
        self.assertEqual(len(beasts), chests.BEAST_CHEST_COUNT)
        self.assertTrue(all(last < row["number"] <= last + chests.BEAST_CHEST_COUNT
                            and row["sent_with"] == row["dungeon"]
                            and row["name"].startswith(row["dungeon"].removeprefix("Divine Beast ") + " - ")
                            for row in beasts))
        self.assertEqual(len({row["name"] for row in rows}), len(rows))
        self.assertTrue(all(row["name"].isascii() for row in rows))
        self.assertEqual(chest_locations.plain("Boné Pond ’"), "Bone Pond '")

    def test_the_field_and_the_divine_beasts_chests_hold_their_item_not_the_shrines(self):
        last_shrine = chests.CHEST_COUNT + chests.SHRINE_CHEST_COUNT
        self.assertEqual([chests.holds_item(n) for n in (1, chests.CHEST_COUNT, chests.CHEST_COUNT + 1,
                                                          last_shrine, last_shrine + 1, last_shrine + 35,
                                                          last_shrine + 36)],
                         [True, True, False, False, True, True, False])
        self.assertEqual([chests.holds_item(n, shrines=True) for n in (chests.CHEST_COUNT + 1, last_shrine,
                                                                        last_shrine + 36)],
                         [True, True, False])

    def test_the_shrines_hold_their_items_only_when_the_slot_asks_with_ap_items(self):
        def status(sanity, shrines):
            return {"slot_data": {"chest_sanity": sanity, "shrine_chest_items": shrines}}
        self.assertTrue(chests.shrines_asked(status(chests.AP_ITEMS, 1)))
        self.assertFalse(chests.shrines_asked(status(chests.AP_ITEMS, 0)))
        self.assertFalse(chests.shrines_asked(status(1, 1)))
        self.assertFalse(chests.shrines_asked({"slot_data": {"chest_sanity": chests.AP_ITEMS}}))

    def test_the_shrines_chests_are_numbered_after_the_fields_by_flag(self):
        def unit(*objs):
            return bytes(oead.byml.to_binary(oead.byml.Hash({"Objs": oead.byml.Array([
                oead.byml.Hash({"UnitConfigName": actor, "HashId": oead.U32(hash_id)})
                for actor, hash_id in objs])}), big_endian=True))
        items = chests.shrine_numbering({"Dungeon001": unit(("TBox_Dungeon_Stone", 5), ("DgnObj_Switch", 6)),
                                         "Dungeon000": unit(("TBox_Dungeon_Iron", 9))})
        self.assertEqual(items, {"CDungeon_TBox_Dungeon_Iron_9": chests.actor(chests.CHEST_COUNT + 1),
                                 "CDungeon_TBox_Dungeon_Stone_5": chests.actor(chests.CHEST_COUNT + 2)})

    @unittest.skipUnless(HAS_DLC, "requires the DLC")
    @full_build
    def test_the_world_data_is_the_games(self):
        from tools import cemu_profile
        from tools.build_resources_from_source import game_files
        try:
            base = chest_locations.base_content()
        except FileNotFoundError as error:
            self.skipTest(str(error))
        game = game_files(cemu_profile.update() / "content")
        with game.active():
            expected = chest_locations.encode(chest_locations.rows(game, base))
        self.assertEqual((ROOT / "botw_world/data/chests.json").read_bytes().decode("utf-8"), expected)


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
    def test_a_chest_that_is_no_location_keeps_its_contents(self):
        maps = {name: (AOC / chests.unit(name)).read_bytes() for name in chests.MAP_HASHES}
        items = chests.numbering(maps)
        located = {row["number"] for row in json.loads(chests.LOCATIONS.read_text(encoding="utf-8"))
                   if not row.get("dungeon")}
        left = {flag for flag, held in items.items() if int(held.rsplit("_", 1)[1]) not in located}
        self.assertEqual(len(left), chests.CHEST_COUNT - len(located))
        for name, raw in maps.items():
            new, detail = chests.patch_map(raw, {flag: held for flag, held in items.items() if flag not in left})
            before, after = contents(raw), contents(new)
            self.assertEqual(len({h for h in before if before[h] != after[h]}), len(detail))
            self.assertFalse(left & {row["flag"] for row in detail})

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
        status = {"slot": 1, "seed": "1", "slot_name": "Player", "slot_data": {"chest_sanity": chests.AP_ITEMS},
                  "placements": []}
        files, catalog, changes = generate(UPDATE, 417391497, status=status, aoc=AOC)
        self.assertEqual(catalog["chests"]["held"], [[1, chests.CHEST_COUNT], [1396, 1430]])
        self.assertIn("Model/AP_Item_00.sbfres", files)
        self.assertIn(f"Actor/Pack/{chests.ACTOR}.sbactorpack", files)
        self.assertIn(f"Actor/Pack/{chests.actor(chests.CHEST_COUNT)}.sbactorpack", files)
        field = [c for c in changes if "chests" in c and c["resource"].startswith("aoc/0010/Map/")]
        self.assertEqual(len([c for c in field if c["chests"]
                              and all(x["item"].startswith(chests.ACTOR + "_") for x in c["chests"])]),
                         len(chests.MAP_HASHES))
        self.assertEqual(files["aoc/0010/Pack/AocMainField.pack"], b"")
        units = [name for name in files if name.startswith("aoc/0010/Map/")]
        self.assertEqual(len(units), len(chests.MAP_HASHES))
        rows = json.loads(chests.LOCATIONS.read_text(encoding="utf-8"))
        self.assertEqual(sum(len(c["chests"]) for c in field), len([row for row in rows if not row.get("dungeon")]))
        # The Divine Beasts' packs: both static units, each chest its item, nothing else changed.
        beasts = {row["flag"]: chests.actor(row["number"]) for row in rows if row.get("sent_with")}
        for beast in chests.BEASTS:
            with self.subTest(beast=beast):
                ours = oead.Sarc(files[f"aoc/0010/{chests.beast_pack(beast)}"])
                theirs = oead.Sarc((AOC / chests.beast_pack(beast)).read_bytes())
                units = chests.beast_units(beast)
                self.assertEqual({f.name: bytes(f.data) for f in ours.get_files() if f.name not in units},
                                 {f.name: bytes(f.data) for f in theirs.get_files() if f.name not in units})
                for member in units:
                    held = {f"MainFieldDungeon_{actor}_{hash_id}": drop for hash_id, (actor, drop)
                            in contents(bytes(ours.get_file(member).data)).items()}
                    self.assertEqual({flag: held[flag] for flag in held if flag in beasts},
                                     {flag: item for flag, item in beasts.items() if flag in held})
                    self.assertTrue(any(flag in beasts for flag in held))

    @full_build
    def test_with_shrine_chest_items_their_items_are_declared_not_their_shrines(self):
        from unittest import mock
        from tools import build_resources_from_source as build
        status = {"slot": 1, "seed": "1", "slot_name": "Player", "placements": [],
                  "slot_data": {"chest_sanity": chests.AP_ITEMS, "shrine_chest_items": 1}}
        with mock.patch.object(build, "shrine_chests_built", return_value=True):
            files, catalog, _changes = build.generate(UPDATE, 417391497, status=status, aoc=AOC)
        self.assertEqual(catalog["chests"]["held"], [[1, chests.CHEST_COUNT], [1396, 1430], [1191, 1395]])
        self.assertTrue(catalog["chests"]["shrines"])
        rows = json.loads(chests.LOCATIONS.read_text(encoding="utf-8"))
        shrine_rows = [row for row in rows if 1191 <= row["number"] <= 1395]
        self.assertEqual(len(shrine_rows), 174)
        for row in shrine_rows:
            self.assertIn(f"Actor/Pack/{chests.actor(row['number'])}.sbactorpack", files)
        self.assertFalse([name for name in files if "Dungeon" in name and name.endswith(".pack")])

    @full_build
    def test_with_shops_and_towers_the_shared_units_hold_both(self):
        from botw_patch.shops import plan_from_manifest
        from tools.build_resources_from_source import generate
        from tests.test_tower_maps import save_flags
        ids = [202, 208]          # Kakariko (G-6) and Tarrey Town (I-3): towers' and chests' units too
        manifest = {"slot": 1, "seed": "1", "slot_name": "Player",
                    "slot_data": {"tower_maps": 2, "chest_sanity": chests.AP_ITEMS},
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

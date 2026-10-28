"""The PopTracker pack (tools/build_poptracker.py) and the locations' positions."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile

from tools import build_location_positions as positions
from tools import build_poptracker as poptracker
from tools import maptex

ROOT = Path(__file__).resolve().parents[1]
BASE = poptracker.base_content()


class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        target, cls.game_map = poptracker.build(None, Path(cls.temp.name))
        cls.pack = zipfile.ZipFile(target)
        cls.cat = poptracker.catalog()

    @classmethod
    def tearDownClass(cls):
        cls.pack.close()
        cls.temp.cleanup()

    def json(self, name):
        return json.loads(self.pack.read(name))

    def test_every_location_has_one_section_on_the_map(self):
        places = self.json("locations/locations.json")
        names = [section["name"] for place in places for section in place["sections"]]
        self.assertEqual(sorted(names), sorted(row["name"] for row in self.cat.LOCATIONS))
        # The map is cut to the squares, MARGIN pixels around them.
        header = self.pack.read("images/map.png")[16:24]
        width, height = int.from_bytes(header[:4], "big"), int.from_bytes(header[4:], "big")
        self.assertLess((width, height), (2400, 2000))
        xs = [place["map_locations"][0]["x"] for place in places]
        ys = [place["map_locations"][0]["y"] for place in places]
        self.assertEqual((min(xs), min(ys)), (poptracker.MARGIN, poptracker.MARGIN))
        self.assertEqual((width - max(xs), height - max(ys)), (poptracker.MARGIN, poptracker.MARGIN))

    def test_the_autotracker_knows_every_ap_location_and_item(self):
        data = self.pack.read("scripts/data.lua").decode()
        sections = dict(re.findall(r'\[(\d+)\] = "(@[^"]+)"', data.split("REQUIREMENTS")[0]))
        expected = {row["id"] for row in self.cat.LOCATIONS if row["name"] != self.cat.GOAL_LOCATION}
        self.assertEqual({int(key) for key in sections}, expected)
        places = {place["name"]: {s["name"] for s in place["sections"]}
                  for place in self.json("locations/locations.json")}
        for path in sections.values():
            place, section = path[1:].split("/", 1)
            self.assertIn(section, places[place])
        # The goal, no AP location, is cleared by the slot's goal status.
        place, section = re.search(r'GOAL_SECTION = "@([^"]+)"', data).group(1).split("/", 1)
        self.assertEqual(section, self.cat.GOAL_LOCATION)
        self.assertIn(section, places[place])

    def test_every_code_the_logic_names_is_an_item_of_the_pack(self):
        codes = set()
        for entry in self.json("items/items.json"):
            codes.update(stage["codes"] for stage in entry.get("stages", [])) if "stages" in entry \
                else codes.add(entry["codes"])
        data = self.pack.read("scripts/data.lua").decode()
        named = set(re.findall(r'\{\{([^}]*)\}, \d+\}', data))
        for group in named:
            for item in re.findall(r'"([a-z0-9_]+)"', group):
                self.assertIn(item, codes)

    def test_a_region_without_its_map_is_a_sequence_break(self):
        sections = {section["name"]: section for place in self.json("locations/locations.json")
                    for section in place["sections"]}
        rows = {row["name"]: row for row in self.cat.LOCATIONS}
        self.assertEqual(sections["Rin Oyaa Shrine"]["access_rules"],
                         [[f"$botw_access|{rows['Rin Oyaa Shrine']['id']}",
                           f"[$botw_maps|{rows['Rin Oyaa Shrine']['id']}]"]])
        for name in ("Hebra Tower", "Oman Au Shrine"):
            self.assertEqual(sections[name]["access_rules"], [[f"$botw_access|{rows[name]['id']}"]])
        data = self.pack.read("scripts/data.lua").decode()
        keys = dict(re.findall(r'\[(\d+)\] = (\{"[a-z_]+_map"[^}]*\})', data.split("MAP_KEYS")[1]))
        self.assertEqual(keys[str(rows["Tarrey Town - Arrow Stall Item 1"]["id"])],
                         '{"akkala_map", "eldin_map", "wasteland_map", "tabantha_map"}')
        codes = {entry["codes"] for entry in self.json("items/items.json") if "codes" in entry}
        self.assertLessEqual({poptracker.code(name) for name in self.cat.MAPS.values()}, codes)
        logic = self.pack.read("scripts/logic.lua").decode()
        self.assertIn("function botw_maps(id)", logic)
        self.assertIn("SLOT_DATA.tower_maps", logic)

    def test_the_manifest_asks_for_archipelago_auto_tracking(self):
        manifest = self.json("manifest.json")
        self.assertEqual(manifest["game_name"], "Breath of the Wild")
        self.assertEqual(manifest["variants"]["map"]["flags"], ["ap"])
        self.assertIn("scripts/autotracking/archipelago.lua", self.pack.namelist())

    def test_without_the_base_game_the_map_is_a_plain_grid(self):
        self.assertFalse(self.game_map)
        self.assertIn("images/map.png", self.pack.namelist())


class IconTests(unittest.TestCase):
    def test_the_game_icons_are_found_by_name_and_the_rest_keep_a_badge(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "Zora Armor - BotW Icon.png").write_bytes(b"zora")
            (folder / "Armor").mkdir()
            (folder / "Armor/Climber-bandanna.png").write_bytes(b"bandanna")
            (folder / "Key Item").mkdir()
            (folder / "Key Item/Revali-gale+.png").write_bytes(b"gale+")
            (folder / "Key Item/Revali-gale.png").write_bytes(b"gale")
            (folder / "notes.txt").write_bytes(b"not an icon")
            found = poptracker.game_icons(folder)
            self.assertEqual(found, {"zora_set": b"zora", "progressive_climbing_gear_2": b"bandanna",
                                     "revalis_gale": b"gale"})
            _entries, images, _ids = poptracker.items(poptracker.catalog(), found)
            self.assertEqual(images["images/items/zora_set.png"], b"zora")
            self.assertEqual(images["images/items/progressive_climbing_gear_2.png"], b"bandanna")
            self.assertNotIsInstance(images["images/items/paraglider.png"], bytes)


class ReleaseIconTests(unittest.TestCase):
    def test_the_release_zip_is_made_then_fetched_once(self):
        with tempfile.TemporaryDirectory() as temp:
            source, player = Path(temp) / "source", Path(temp) / "player"
            (source / "Key Item").mkdir(parents=True)
            (source / "Key Item/Paraglider.png").write_bytes(b"glider")
            (source / "Magnesis.png").write_bytes(b"magnet")
            archive = Path(temp) / "tracker-icons.zip"
            missing = poptracker.package_icons(source, archive)
            self.assertNotIn("Paraglider", missing)
            self.assertIn("Stasis", missing)
            url = archive.resolve().as_uri()
            self.assertTrue(poptracker.fetch_icons(player, url))
            self.assertFalse(poptracker.fetch_icons(player, url))       # once
            found = poptracker.game_icons(player)
            self.assertEqual((found["paraglider"], found["magnesis"]), (b"glider", b"magnet"))

    def test_an_archive_with_a_path_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bad:
                bad.writestr("../evil.png", b"x")
            with self.assertRaises(ValueError):
                poptracker.fetch_icons(Path(temp) / "player", archive.resolve().as_uri())
            self.assertFalse((Path(temp) / "player/release").exists())


UPDATE = poptracker.update_content()


@unittest.skipUnless(UPDATE is not None and (UPDATE / "Pack/Bootup.pack").is_file(), "update absent")
class InterfaceIconTests(unittest.TestCase):
    def test_every_interface_icon_is_in_the_game_and_decodes(self):
        found = poptracker.ui_icons(UPDATE)
        self.assertEqual(set(found), set(poptracker.UI_ICONS))
        heart = found["heart_container"]
        self.assertEqual(heart.shape, (48, 48, 4))
        # A white heart on nothing: transparent corners, an opaque white middle.
        self.assertEqual(heart[0, 0, 3], 0)
        self.assertTrue((heart[24, 24] == (255, 255, 255, 255)).all())

    def test_the_player_icons_come_first(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "Zora-armor.png").write_bytes(b"zora")
            found = {**poptracker.ui_icons(UPDATE), **poptracker.game_icons(Path(temp))}
            self.assertEqual(found["zora_set"], b"zora")
            self.assertIsInstance(found["flamebreaker_set"], type(found["heart_container"]))


class PositionTests(unittest.TestCase):
    def test_every_location_has_a_position(self):
        data = json.loads((ROOT / "data/location_positions.json").read_text(encoding="utf-8"))
        rows = (ROOT / "data/locations_master.csv").read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual(list(data), [row.split(",")[0] for row in rows])

    @unittest.skipUnless((positions.AOC / "Map/MainField/Static.smubin").is_file(), "DLC content absent")
    def test_the_positions_are_the_map_units(self):
        self.assertEqual(positions.encode(positions.build()),
                         (ROOT / "data/location_positions.json").read_text(encoding="utf-8"))


@unittest.skipUnless(BASE is not None and (BASE / maptex.FOLDER).is_dir(), "base game folder absent")
class MapTests(unittest.TestCase):
    def test_a_section_decodes_to_its_size(self):
        tile = maptex.decode((BASE / maptex.FOLDER / "MapTex2_E-4.sbmaptex").read_bytes())
        self.assertEqual(tile.shape, (200, 200, 3))
        self.assertGreater(tile.std(), 10)          # an image, not a blank



class LauncherStepTests(unittest.TestCase):
    """The pack the launcher keeps in the release's folder, one line a launch."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target = self.root / "PopTracker" / f"{poptracker.PACK_NAME}.zip"
        self.version = "v1"
        for name, value in (("PACK_FOLDER", self.root / "PopTracker"),
                            ("STAMP", self.root / "data/stamp.txt"),
                            ("DECLINED", self.root / "data/declined.txt")):
            patcher = mock.patch.object(poptracker, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, kwargs in (("base_content", {"return_value": None}),
                             ("fetch_icons", {"return_value": False}),
                             ("stamp", {"side_effect": lambda content: self.version}),
                             ("build", {"side_effect": self.build})):
            patcher = mock.patch.object(poptracker, name, **kwargs)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def build(self, content, output):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_bytes(b"pack")
        return self.target, True

    def launch(self, answer=True):
        said, asked = [], []
        poptracker.ensure_pack(said.append, lambda prompt: asked.append(prompt) or answer)
        return said, asked

    def test_the_first_pack_is_built_when_the_player_wants_it(self):
        said, asked = self.launch(answer=True)
        self.assertEqual(len(asked), 1)
        self.assertTrue(self.target.is_file())
        self.assertIn(f"PopTracker pack built: {self.target}", said)
        self.assertTrue(any("drag this file onto PopTracker's window" in line for line in said))
        said, asked = self.launch()                         # the next launch: one line, nothing built
        self.assertEqual((said, asked), ([f"PopTracker pack: up to date, not rebuilt ({self.target})"], []))
        self.assertEqual(self.build.call_count, 1)

    def test_a_no_is_remembered_until_the_pack_would_change(self):
        said, asked = self.launch(answer=False)
        self.assertEqual(len(asked), 1)
        self.assertFalse(self.target.exists())
        self.assertTrue(said[-1].startswith("PopTracker pack: not built. You will be asked again"))
        said, asked = self.launch(answer=False)
        self.assertEqual(asked, [])
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0].startswith("PopTracker pack: not built, as you answered (asked again"))
        self.version = "v2"                                 # a new version asks again
        said, asked = self.launch(answer=True)
        self.assertEqual(len(asked), 1)
        self.assertTrue(self.target.is_file())

    def test_an_out_of_date_pack_is_rebuilt_without_a_question(self):
        self.launch(answer=True)
        self.version = "v2"
        said, asked = self.launch(answer=False)
        self.assertEqual(asked, [])
        self.assertEqual(self.build.call_count, 2)
        self.assertIn(f"PopTracker pack rebuilt, it was out of date: {self.target}", said)
        self.assertTrue(any("again, to replace the one it has" in line for line in said))

    def test_a_failure_is_one_line_and_never_stops_the_game(self):
        self.build.side_effect = OSError("disk full")
        said, _asked = self.launch(answer=True)
        self.assertEqual(said[-1], "PopTracker pack: not built (disk full)")


if __name__ == "__main__":
    unittest.main()

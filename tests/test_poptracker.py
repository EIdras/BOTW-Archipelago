"""The PopTracker pack (tools/build_poptracker.py) and the locations' positions."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile

import numpy as np

from tools import build_location_positions as positions
from tools import build_poptracker as poptracker
from tools import maptex
from tools import poptracker_regions as regions

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
        self.assertEqual(sections["Oman Au Shrine"]["access_rules"], [[f"$botw_access|{rows['Oman Au Shrine']['id']}"]])
        data = self.pack.read("scripts/data.lua").decode()
        keys = dict(re.findall(r'\[(\d+)\] = (\{"[a-z_]+_map"[^}]*\})', data.split("MAP_KEYS")[1]))
        # A tower asks for no map, but for its region with region_lock.
        self.assertNotIn(str(rows["Hebra Tower"]["id"]), keys)
        self.assertEqual(keys[str(rows["Tarrey Town - Arrow Stall Item 1"]["id"])],
                         '{"akkala_map", "eldin_map", "wasteland_map", "tabantha_map"}')
        codes = {entry["codes"] for entry in self.json("items/items.json") if "codes" in entry}
        self.assertLessEqual({poptracker.code(name) for name in self.cat.MAPS.values()}, codes)
        logic = self.pack.read("scripts/logic.lua").decode()
        self.assertIn("function botw_maps(id)", logic)
        self.assertIn("SLOT_DATA.tower_maps", logic)

    def test_with_region_lock_a_region_out_of_reach_is_a_sequence_break(self):
        sections = {section["name"]: section for place in self.json("locations/locations.json")
                    for section in place["sections"]}
        ids = {row["name"]: row["id"] for row in self.cat.LOCATIONS}
        hebra, goal = ids["Hebra Tower"], ids[self.cat.GOAL_LOCATION]
        self.assertEqual(sections["Hebra Tower"]["access_rules"], [[f"$botw_access|{hebra}", f"[$botw_maps|{hebra}]"]])
        self.assertEqual(sections[self.cat.GOAL_LOCATION]["access_rules"], [["$botw_ganon", f"[$botw_maps|{goal}]"]])
        data = self.pack.read("scripts/data.lua").decode()
        table = data.split("REGION_KEYS = {")[1].split("\n}")[0]
        regions = dict(re.findall(r'\[(\d+)\] = (\{[^}]*\})', table))
        # Its own region, a tower's too, and those of a quest's maps; Ganon's, in Central's area.
        self.assertEqual(regions[str(hebra)], '{"Hebra"}')
        self.assertEqual(regions[str(ids["Tarrey Town - Arrow Stall Item 1"])],
                         '{"Akkala", "Eldin", "Wasteland", "Tabantha"}')
        self.assertEqual(regions[str(goal)], '{"Hyrule Castle"}')
        self.assertIn('INNER_REGIONS = {["Hyrule Castle"] = "Central"}', data)
        # The Great Plateau is always reached: its locations have no bracket.
        plateau = {str(row["id"]) for row in self.cat.LOCATIONS if row["region"] == "Great Plateau"}
        self.assertFalse(plateau & set(regions))
        self.assertEqual(len(regions), len(self.cat.LOCATIONS) - len(plateau))
        maps = dict(re.findall(r'\["([A-Za-z ]+)"\] = "([a-z_]+)"', data.split("REGION_MAPS = ")[1].split("\n")[0]))
        self.assertEqual(maps, {region: poptracker.code(item) for region, item in self.cat.MAPS.items()})
        # The seed's own borders, from its slot data.
        logic = self.pack.read("scripts/logic.lua").decode()
        self.assertIn("SLOT_DATA.region_lock", logic)
        self.assertIn("SLOT_DATA.region_borders", logic)
        # With map_travel_points, a region is reached by its map alone.
        self.assertIn("SLOT_DATA.map_travel_points", logic)

    def test_the_regions_panel_combines_each_map_with_its_region_reached(self):
        items = {entry["codes"]: entry for entry in self.json("items/items.json") if "codes" in entry}
        panel = [region for row in poptracker.REGION_PANEL for region in row]
        self.assertEqual(sorted(panel), sorted([*self.cat.MAPS, poptracker.START_REGION]))
        self.assertEqual(set(poptracker.REGION_LABELS), set(panel))
        for region, item in self.cat.MAPS.items():
            map_code = poptracker.code(item)
            self.assertEqual(items[map_code]["type"], "toggle")
            self.assertEqual(items[f"{map_code}_reached"]["type"], "toggle")
            tile = items[f"{map_code}_tile"]
            self.assertEqual((tile["type"], tile["item_left"], tile["item_right"]),
                             ("composite_toggle", map_code, f"{map_code}_reached"))
            # Grey until the map is received, amber while its region is out of reach.
            looks = {(image["left"], image["right"]): image["img"].rsplit("_", 1)[1] for image in tile["images"]}
            self.assertEqual(looks, {(False, False): "off.png", (False, True): "off.png",
                                     (True, False): "cut.png", (True, True): "lit.png"})
            for image in tile["images"]:
                self.assertIn(image["img"], self.pack.namelist())
            # Without the game's map, no mini-map.
            self.assertNotIn(f"{map_code}_piece", items)
        self.assertEqual(items["great_plateau_tile"]["type"], "static")
        layout = self.json("layouts/tracker.json")
        self.assertEqual(layout["region_tiles"]["rows"],
                         [[f"{poptracker.code(region)}_tile" if region == poptracker.START_REGION
                           else f"{poptracker.code(self.cat.MAPS[region])}_tile" for region in row]
                          for row in poptracker.REGION_PANEL])
        self.assertNotIn("_map", json.dumps(layout["item_grid"]))
        logic = self.pack.read("scripts/logic.lua").decode()
        self.assertIn("function botw_update_regions()", logic)
        self.assertIn('code .. "_reached"', logic)
        # Written from a watch, a "reached" toggle would turn its map back off through
        # its composite: the watches and the slot data only mark the panel stale, and a
        # frame handler updates it.
        init = self.pack.read("scripts/init.lua").decode()
        tracking = self.pack.read("scripts/autotracking/archipelago.lua").decode()
        self.assertNotIn("botw_update_regions", init + tracking)
        self.assertEqual(init.count("botw_regions_changed)"), 3)
        self.assertIn('AddOnFrameHandler("botw regions", botw_regions_frame)', init)
        self.assertIn("botw_regions_changed()", tracking)
        self.assertIn("function botw_regions_frame()", logic)

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
                                     "progressive_revalis_gale_1": b"gale", "progressive_revalis_gale_2": b"gale+"})
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


class RegionDrawingTests(unittest.TestCase):
    """tools/poptracker_regions.py on a map of three regions: West and East over
    Start, the bottom quarter."""

    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(1)
        image = rng.integers(40, 200, (200, 240, 3)).astype(np.uint8)

        def lookup(xs, ys):
            out = np.where(np.asarray(xs)[None, :] < 120, "West", "East").repeat(len(ys), 0).astype(object)
            out[np.asarray(ys) >= 150] = "Start"
            return out
        cls.drawn = regions.draw(image, lookup, (0, 0, 240, 200), ["West", "East"], "Start")

    def test_a_tile_has_its_frame_in_its_state_and_is_grey_without_its_map(self):
        tiles = self.drawn.tiles
        self.assertEqual(set(tiles), {(r, s) for r in ("West", "East") for s in regions.STATES} | {("Start", "lit")})
        width, height = regions.TILE
        for image in tiles.values():
            self.assertEqual(image.shape, (height, width, 4))
        red, green, blue = tiles["West", "lit"][height // 2, 0, :3].astype(int)
        self.assertGreater(green, red)
        red, green, blue = tiles["West", "cut"][height // 2, 0, :3].astype(int)
        self.assertGreater(red, green)
        self.assertGreater(green, blue)
        off = tiles["West", "off"]
        self.assertTrue((off[..., 0] == off[..., 1]).all() and (off[..., 1] == off[..., 2]).all())

    def test_the_pieces_lie_where_their_regions_do_on_the_mini_map(self):
        background = self.drawn.background
        self.assertEqual(background.shape, (round(regions.MINI_WIDTH * 200 / 240), regions.MINI_WIDTH, 4))
        west_left, west_top, west = self.drawn.pieces["West", "lit"]
        east_left, east_top, east = self.drawn.pieces["East", "lit"]
        self.assertEqual((west_left, west_top, east_top), (0, 0, 0))
        self.assertEqual(east_left, regions.MINI_WIDTH // 2)
        self.assertEqual(west.shape[1] + east.shape[1], regions.MINI_WIDTH)
        # Start is in the background, not in a piece (whose last row is partly covered).
        self.assertEqual(west.shape[0], -(-background.shape[0] * 150 // 200))
        for state in regions.STATES:
            _left, _top, piece = self.drawn.pieces["West", state]
            self.assertEqual(piece[piece.shape[0] // 2, piece.shape[1] // 2, 3], 255)

    def test_a_label_tile_frames_the_label(self):
        label = poptracker.icon("HEB", poptracker.MAP_COLOUR)
        tile = regions.label_tile(label, "cut")
        self.assertEqual(tile.shape[:2], regions.TILE[::-1])


@unittest.skipUnless(UPDATE is not None and (UPDATE / "Pack/Bootup.pack").is_file(), "update absent")
class TowerAreaTests(unittest.TestCase):
    def test_each_tower_stands_in_its_region(self):
        lookup = regions.tower_areas(UPDATE, poptracker.SCALE, maptex.ORIGIN)
        places = json.loads(poptracker.POSITIONS.read_text(encoding="utf-8"))
        for row in poptracker.catalog().LOCATIONS:
            if "Tower" in row["category"].split("|"):
                x, y = maptex.pixel(*places[row["name"]], poptracker.SCALE)
                self.assertEqual(lookup(np.array([x]), np.array([y]))[0, 0], row["region"], row["name"])



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
        return self.build_file(), True

    def build_file(self):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_bytes(b"pack")
        return self.target

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

    def test_a_map_not_read_is_built_again_at_the_next_session(self):
        # The game's drive disconnected while its map was read: a plain grid,
        # and a stamp that will not match once the game is back.
        self.base_content.return_value = Path("game")
        self.stamp.side_effect = lambda content: f"{self.version} {content}"
        self.build.side_effect = lambda content, output: (self.build_file(), False)
        said, _asked = self.launch(answer=True)
        self.assertTrue(any("the base game could not be read in game" in line for line in said))
        self.build.side_effect = lambda content, output: (self.build_file(), True)   # the game is back
        said, asked = self.launch()
        self.assertEqual(asked, [])
        self.assertEqual(self.build.call_count, 2)
        self.assertIn(f"PopTracker pack rebuilt, it was out of date: {self.target}", said)

    def test_a_failure_is_one_line_and_never_stops_the_game(self):
        self.build.side_effect = OSError("disk full")
        said, _asked = self.launch(answer=True)
        self.assertEqual(said[-1], "PopTracker pack: not built (disk full)")


if __name__ == "__main__":
    unittest.main()

"""The Koroks as locations (korok_sanity): botw_world/data/koroks.json, made
from the game's maps by tools/korok_locations.py, tracked by their flags."""
from __future__ import annotations

import collections
import json
from pathlib import Path
import unittest

from tests.full_build import full_build
from tools import korok_locations

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
AOC = UPDATE.parents[2] / "0005000c/101c9500/content/0010"
HAS_DLC = (AOC / "Map/MainField").is_dir()
ROWS = json.loads((ROOT / "botw_world/data/koroks.json").read_text(encoding="utf-8"))


class KorokDataTests(unittest.TestCase):
    def test_every_korok_numbered_in_the_order_of_its_flag(self):
        self.assertEqual(len(ROWS), korok_locations.COUNT)
        self.assertEqual([row["number"] for row in ROWS], list(range(1, korok_locations.COUNT + 1)))
        self.assertEqual([row["flag"] for row in ROWS], sorted(row["flag"] for row in ROWS))
        self.assertEqual(collections.Counter(row["kind"] for row in ROWS), {"Ground": 567, "Fly": 333})
        for row in ROWS:
            self.assertRegex(row["flag"], rf"^MainField_Npc_HiddenKorok{row['kind']}_\d+$")

    def test_a_korok_is_named_after_its_place_uniquely_in_ascii(self):
        names = [row["name"] for row in ROWS]
        self.assertEqual(len(set(names)), len(names))
        self.assertTrue(all(name.isascii() and " - Korok" in name for name in names))

    def test_what_the_puzzles_take(self):
        self.assertEqual(collections.Counter(tuple(row["requires"]) for row in ROWS),
                         {(): 745, ("Progressive Remote Bomb",): 53, ("Magnesis",): 100,
                          ("Magnesis", "Paraglider"): 1, ("Gerudo Set",): 1})
        self.assertEqual(collections.Counter(row["no_progression"] for row in ROWS),
                         {None: 862, "fire": 20, "ice": 18})
        town = next(row for row in ROWS if row["requires"] == ["Gerudo Set"])
        self.assertEqual(town["name"], "Gerudo Town - Korok 1")
        gliding = [row["name"] for row in ROWS if "Paraglider" in row["requires"]]
        self.assertEqual(gliding, ["Mount Hylia - Korok 4"])

    @unittest.skipUnless(HAS_DLC, "requires the DLC")
    @full_build
    def test_the_world_data_is_the_games(self):
        from tools import cemu_profile
        from tools.build_resources_from_source import game_files
        game = game_files(cemu_profile.update() / "content")
        with game.active():
            expected = korok_locations.encode(korok_locations.rows(game))
        self.assertEqual((ROOT / "botw_world/data/koroks.json").read_bytes().decode("utf-8"), expected)


if __name__ == "__main__":
    unittest.main()

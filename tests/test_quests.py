"""The side and shrine quests as locations (side_quest_sanity, shrine_quest_sanity):
botw_world/data/quests.json, made from the game's quest list by tools/quest_locations.py,
tracked by their finish flags."""
from __future__ import annotations

import collections
import json
from pathlib import Path
import unittest

from tests.full_build import full_build
from tools import quest_locations

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
AOC = UPDATE.parents[2] / "0005000c/101c9500/content/0010"
HAS_DLC = (AOC / "Map/MainField").is_dir()
ROWS = json.loads((ROOT / "botw_world/data/quests.json").read_text(encoding="utf-8"))
SHRINES = {row["name"]: row["region"] for row in json.loads(
    (ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8")) if "Shrine" in row["category"]}


class QuestDataTests(unittest.TestCase):
    def test_the_quests_kept_numbered_among_every_saved_finish_flag(self):
        self.assertEqual(collections.Counter(row["kind"] for row in ROWS), {"Side": 73, "Shrine": 42})
        numbers = [row["number"] for row in ROWS]
        self.assertEqual(numbers, sorted(set(numbers)))
        self.assertTrue(1 <= numbers[0] and numbers[-1] <= quest_locations.SAVED)
        self.assertEqual([row["flag"] for row in ROWS], sorted(row["flag"] for row in ROWS))
        self.assertFalse({row["quest"] for row in ROWS} & set(quest_locations.LEFT_OUT))

    def test_a_quest_is_named_after_its_place_uniquely_in_ascii(self):
        names = [row["name"] for row in ROWS]
        self.assertEqual(len(set(names)), len(names))
        self.assertTrue(all(name.isascii() and " - " in name for name in names))
        self.assertIn("Hateno Village - Hylian Homeowner", names)

    def test_a_shrine_quest_raises_a_shrine_of_its_region(self):
        shrines = [row["shrine"] for row in ROWS if row["kind"] == "Shrine"]
        self.assertEqual(len(set(shrines)), 42)
        for row in ROWS:
            if row["kind"] == "Shrine":
                self.assertEqual(SHRINES[row["shrine"]], row["region"])
                self.assertEqual(row["requires"], [])
            else:
                self.assertNotIn("shrine", row)

    def test_what_the_side_quests_take(self):
        town = sorted(row["name"] for row in ROWS if row["requires"])
        self.assertEqual(len(town), 6)
        self.assertTrue(all(name.startswith("Gerudo Town - ") for name in town))
        self.assertEqual({row["quest"]: row["no_progression"] for row in ROWS if row["no_progression"]},
                         {"HatenoMini_MyHome": "rupees", "UMiiMini_MakeVillage": "long"})

    @unittest.skipUnless(HAS_DLC, "requires the DLC")
    @full_build
    def test_the_world_data_is_the_games(self):
        from tools import cemu_profile
        from tools.build_resources_from_source import game_files
        game = game_files(cemu_profile.update() / "content")
        with game.active():
            expected = quest_locations.encode(quest_locations.rows(game))
        self.assertEqual((ROOT / "botw_world/data/quests.json").read_bytes().decode("utf-8"), expected)


if __name__ == "__main__":
    unittest.main()

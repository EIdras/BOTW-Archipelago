"""The field bosses as locations (boss_sanity): botw_world/data/bosses.json, made
from the game's GameData and maps by tools/boss_locations.py, tracked by their flags."""
from __future__ import annotations

import collections
import json
from pathlib import Path
import re
import unittest

from tests.full_build import full_build
from tools import boss_locations

ROOT = Path(__file__).resolve().parents[1]
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
AOC = UPDATE.parents[2] / "0005000c/101c9500/content/0010"
HAS_DLC = (AOC / "Map/MainField").is_dir()
ROWS = json.loads((ROOT / "botw_world/data/bosses.json").read_text(encoding="utf-8"))


class BossDataTests(unittest.TestCase):
    def test_every_boss_numbered_in_the_order_of_its_flag(self):
        self.assertEqual(len(ROWS), boss_locations.COUNT)
        self.assertEqual([row["number"] for row in ROWS], list(range(1, boss_locations.COUNT + 1)))
        self.assertEqual([row["flag"] for row in ROWS], sorted(row["flag"] for row in ROWS))
        for row in ROWS:
            self.assertRegex(row["flag"], r"^MainField_IsDefeat_Enemy_(Giant|Golem|Sandworm)[A-Za-z_]*_\d+$")
        self.assertEqual(collections.Counter(row["kind"] for row in ROWS), {
            "Blue Hinox": 16, "Stone Talus (Luminous)": 12, "Stone Talus": 11, "Stalnox": 10, "Hinox": 7,
            "Black Hinox": 7, "Stone Talus (Rare)": 7, "Igneo Talus": 5, "Frost Talus": 5, "Molduga": 4,
            "Igneo Talus Titan": 1, "Molduking": 1})

    def test_a_boss_is_named_after_its_place_uniquely_in_ascii(self):
        names = [row["name"] for row in ROWS]
        self.assertEqual(len(set(names)), len(names))
        for row in ROWS:
            self.assertTrue(row["name"].isascii())
            self.assertRegex(row["name"], rf"^[^-]+ - {re.escape(row['kind'])}( \d)?$")

    def test_only_the_heat_or_a_ballad_trial_is_asked(self):
        self.assertTrue(all(row["requires"] == [] and row["no_progression"] is None for row in ROWS))
        self.assertEqual(sorted(row["kind"] for row in ROWS if row["heat"]), ["Igneo Talus"] * 5 + ["Igneo Talus Titan"])
        self.assertEqual({row["name"]: row["ballad"] for row in ROWS if "ballad" in row},
                         {"Lake Darman - Igneo Talus Titan": "Daruk's Song", "East Barrens - Molduking": "Urbosa's Song"})

    @unittest.skipUnless(HAS_DLC, "requires the DLC")
    @full_build
    def test_the_world_data_is_the_games(self):
        from tools import cemu_profile
        from tools.build_resources_from_source import game_files
        game = game_files(cemu_profile.update() / "content")
        with game.active():
            expected = boss_locations.encode(boss_locations.rows(game))
        self.assertEqual((ROOT / "botw_world/data/bosses.json").read_bytes().decode("utf-8"), expected)


if __name__ == "__main__":
    unittest.main()

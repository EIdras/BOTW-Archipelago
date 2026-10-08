"""The locations' regions are the game's map: the tower whose map shows each one (tools/map_regions.py)."""
import json
from pathlib import Path
import struct
import unittest

from tools import map_regions
from tools.build_poptracker import update_content

ROOT = Path(__file__).resolve().parents[1]
CONTENT = update_content()


def grid(rows: list[list[tuple[int, int]]], divisor: int = 2) -> bytes:
    """A .beco file of these rows of (value, length) segments."""
    body, offsets = b"", []
    for row in rows:
        offsets.append(len(body) // 2)
        body += b"".join(struct.pack(">HH", value, length) for value, length in row)
    return struct.pack(">IIII", 0x00112233, len(rows), divisor, 0) + struct.pack(f">{len(rows)}I", *offsets) + body


class BecoTests(unittest.TestCase):
    def test_a_point_falls_in_the_segment_under_it(self):
        beco = map_regions.Beco(grid([[(3, 4000), (7, 6000)]] * 4000))
        self.assertEqual(beco.at(-5000, -4000), 3)
        self.assertEqual(beco.at(-1001, 0), 3)
        self.assertEqual(beco.at(-1000, 0), 7)
        self.assertEqual(beco.at(4999, 3999), 7)

    def test_rows_follow_z(self):
        beco = map_regions.Beco(grid([[(1, 10000)]] * 2000 + [[(2, 10000)]] * 2000))
        self.assertEqual(beco.at(0, -1), 1)
        self.assertEqual(beco.at(0, 0), 2)

    def test_another_file_is_refused(self):
        with self.assertRaises(ValueError):
            map_regions.Beco(b"\0" * 32)


class DataTests(unittest.TestCase):
    def test_a_tower_is_in_its_own_region(self):
        rows = json.loads((ROOT / "botw_world/data/locations.json").read_text(encoding="utf-8"))
        towers = [row for row in rows if "Tower" in row["category"].split("|")]
        self.assertEqual(len(towers), 15)
        self.assertEqual({row["name"] for row in towers}, {f"{row['region']} Tower" for row in towers})

    @unittest.skipUnless(CONTENT is not None and (CONTENT / "Pack/Bootup.pack").is_file(), "update content absent")
    def test_the_regions_are_the_game_map(self):
        self.assertEqual(map_regions.differences(CONTENT), [])


if __name__ == "__main__":
    unittest.main()

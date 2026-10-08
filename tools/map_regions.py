"""The region of each location: the tower whose map shows it, as the game cuts its map.

    venv\\Scripts\\python tools\\map_regions.py [--content <update content folder>]

A tower reveals one area of the map. The game cuts the map in Bootup.pack >
Ecosystem/MapTower.sbeco, one area per tower: the area numbered n is revealed by
MapTower_{n + 1:02d}, the flag of the tower standing in it. A location's region
(data/locations_master.csv, botw_world/data/locations.json, the shop and stall
catalogues) is the area at its position on the map (data/location_positions.json),
named after its tower; Defeat Calamity Ganon keeps a region of its own, Hyrule
Castle. Regions are data, kept in the repository: a test checks them against the
game's file when the update is installed. Run alone, the tool prints the locations
whose region differs from the game's.

A .beco file: a header (magic 0x00112233, rows, divisor, padding), then one u32
offset per row, in 2-byte units after the offset table; a row is a run of
segments (u16 value, u16 length). Row r covers z = r * divisor - 4000; lengths are
world units from x = -5000.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

POSITIONS = ROOT / "data/location_positions.json"
LOCATIONS = ROOT / "botw_world/data/locations.json"
MAP_TOWER = "Ecosystem/MapTower.sbeco"
OWN_REGIONS = {"Defeat Calamity Ganon": "Hyrule Castle"}
_MAGIC = 0x00112233


class Beco:
    """An Ecosystem .beco grid: the value at a point of the MainField."""

    def __init__(self, data: bytes):
        magic, self.rows, self.divisor, _padding = struct.unpack_from(">IIII", data, 0)
        if magic != _MAGIC:
            raise ValueError(f"not a .beco file (magic {magic:#x})")
        self.offsets = struct.unpack_from(f">{self.rows}I", data, 16)
        self.base = 16 + 4 * self.rows
        self.data = data

    def row(self, index: int) -> list[tuple[int, int]]:
        start = self.base + 2 * self.offsets[index]
        end = self.base + 2 * self.offsets[index + 1] if index + 1 < self.rows else len(self.data)
        return [struct.unpack_from(">HH", self.data, at) for at in range(start, end, 4)]

    def at(self, x: float, z: float) -> int:
        index = max(0, min(self.rows - 1, int((z + 4000) / self.divisor)))
        column, edge = x + 5000, 0
        for value, length in self.row(index):
            edge += length
            if column < edge:
                return value
        raise ValueError(f"({x}, {z}) is outside the map")


def map_towers(content: Path) -> Beco:
    """The tower areas of the update's Bootup.pack."""
    bootup = oead.Sarc((content / "Pack/Bootup.pack").read_bytes())
    return Beco(oead.yaz0.decompress(bytes(bootup.get_file(MAP_TOWER).data)))


def regions(content: Path) -> dict[str, str]:
    """{location: region}: the area at each location's position, named after its tower."""
    rows = json.loads(LOCATIONS.read_text(encoding="utf-8"))
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    grid = map_towers(content)
    named = {}
    for row in rows:
        if "Tower" in row["category"].split("|"):
            area = grid.at(*positions[row["name"]])
            if area != int(row["gamedata_flag"].rsplit("_", 1)[1]) - 1:
                raise ValueError(f"{row['name']} stands in the area {area}, not its own")
            named[area] = row["region"]
    return {row["name"]: OWN_REGIONS.get(row["name"]) or named[grid.at(*positions[row["name"]])]
            for row in rows}


def differences(content: Path) -> list[tuple[str, str, str]]:
    """(location, its region, the game's) for each location whose region is not the game's."""
    found = regions(content)
    return [(row["name"], row["region"], found[row["name"]])
            for row in json.loads(LOCATIONS.read_text(encoding="utf-8")) if row["region"] != found[row["name"]]]


if __name__ == "__main__":
    from tools.build_poptracker import update_content

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", type=Path, default=None, help="the update's content folder")
    args = parser.parse_args()
    content = args.content or update_content()
    if content is None:
        sys.exit("no update content found: pass --content")
    moves = differences(content)
    for name, region, game in moves:
        print(f"{name}: {region} -> {game}")
    print(f"{len(moves)} location(s) differ from the game's map")

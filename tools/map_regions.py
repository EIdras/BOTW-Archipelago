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

Two regions are neighbours where their areas touch on the map. The borders are
data too (botw_world/data/region_borders.json, checked against the game's file
the same way): --borders writes them. The world's region_lock enters a region
from its neighbours.

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
BORDERS = ROOT / "botw_world/data/region_borders.json"
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

    def borders(self) -> dict[tuple[int, int], int]:
        """{(area, area): length}: where two areas touch, in world units along the
        grid's edges (between two segments of a row, where two rows overlap)."""
        found: dict[tuple[int, int], int] = {}

        def touch(a: int, b: int, length: int) -> None:
            if a != b and length > 0:
                key = (min(a, b), max(a, b))
                found[key] = found.get(key, 0) + length

        above: list[tuple[int, int, int]] = []
        for index in range(self.rows):
            row, start = [], 0
            for value, length in self.row(index):
                if row:
                    touch(row[-1][2], value, self.divisor)
                row.append((start, start + length, value))
                start += length
            i = j = 0
            while i < len(above) and j < len(row):
                (start1, end1, value1), (start2, end2, value2) = above[i], row[j]
                touch(value1, value2, min(end1, end2) - max(start1, start2))
                if end1 <= end2:
                    i += 1
                else:
                    j += 1
            above = row
        return found


def map_towers(content: Path) -> Beco:
    """The tower areas of the update's Bootup.pack."""
    bootup = oead.Sarc((content / "Pack/Bootup.pack").read_bytes())
    return Beco(oead.yaz0.decompress(bytes(bootup.get_file(MAP_TOWER).data)))


def area_regions(grid: Beco) -> dict[int, str]:
    """{area: region}: each area named after the tower standing in it."""
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    named = {}
    for row in json.loads(LOCATIONS.read_text(encoding="utf-8")):
        if "Tower" in row["category"].split("|"):
            area = grid.at(*positions[row["name"]])
            if area != int(row["gamedata_flag"].rsplit("_", 1)[1]) - 1:
                raise ValueError(f"{row['name']} stands in the area {area}, not its own")
            named[area] = row["region"]
    return named


def regions(content: Path) -> dict[str, str]:
    """{location: region}: the area at each location's position, named after its tower."""
    rows = json.loads(LOCATIONS.read_text(encoding="utf-8"))
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    grid = map_towers(content)
    named = area_regions(grid)
    return {row["name"]: OWN_REGIONS.get(row["name"]) or named[grid.at(*positions[row["name"]])]
            for row in rows}


def region_borders(content: Path) -> list[dict]:
    """The borders between regions on the game's map, as region_borders.json keeps
    them: {"regions": [a, b], "length": world units}, in the order of the names."""
    grid = map_towers(content)
    named = area_regions(grid)
    return sorted(({"regions": sorted((named[a], named[b])), "length": length}
                   for (a, b), length in grid.borders().items()), key=lambda border: border["regions"])


def write_borders(content: Path, path: Path = BORDERS) -> None:
    """region_borders.json, one border a line."""
    lines = [json.dumps(border) for border in region_borders(content)]
    path.write_bytes(("[\n  " + ",\n  ".join(lines) + "\n]\n").encode("utf-8"))


def differences(content: Path) -> list[tuple[str, str, str]]:
    """(location, its region, the game's) for each location whose region is not the game's."""
    found = regions(content)
    return [(row["name"], row["region"], found[row["name"]])
            for row in json.loads(LOCATIONS.read_text(encoding="utf-8")) if row["region"] != found[row["name"]]]


if __name__ == "__main__":
    from tools.build_poptracker import update_content

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", type=Path, default=None, help="the update's content folder")
    parser.add_argument("--borders", action="store_true", help=f"write {BORDERS.relative_to(ROOT).as_posix()}")
    args = parser.parse_args()
    content = args.content or update_content()
    if content is None:
        sys.exit("no update content found: pass --content")
    if args.borders:
        write_borders(content)
        print(f"{len(region_borders(content))} borders written to {BORDERS}")
        sys.exit()
    moves = differences(content)
    for name, region, game in moves:
        print(f"{name}: {region} -> {game}")
    print(f"{len(moves)} location(s) differ from the game's map")

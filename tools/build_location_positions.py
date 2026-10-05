"""Where each of the world's locations is on the map, from the game's map units.

    venv\\Scripts\\python tools\\build_location_positions.py [--aoc <DLC content/0010 folder>]

The PopTracker pack (tools/build_poptracker.py) places its squares from these
positions; positions are data, not game files, so the result is kept in the
repository: data/location_positions.json, {name: [x, z]} in world units (the
MainField spans x -6000..6000, z -5000..5000). Each kind of location is found
by what the map holds for it:
  * shrines and towers: their LocationMarker (MessageID DungeonNNN, TowerNN);
  * a rune terminal: the marker of the plateau shrine it stands before;
  * a Divine Beast and its heart: the beast's marker during its quest (the
    second RemainsX marker; the first is where it rests once freed);
  * a Great Fairy: her fountain (GreatFairyBeforeRevival);
  * Beedle: his NPC (Npc_TripMaster_NN); a stall: its merchant;
  * the Master Sword: its pedestal; Calamity Ganon: Hyrule Castle's marker.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

from botw_client.shop_catalog import MERCHANTS as BEEDLES  # noqa: E402
from botw_client.stall_catalog import BY_NAME as STALL_LOCATIONS, MERCHANTS as STALLS  # noqa: E402
from botw_patch.resources import unpack  # noqa: E402

AOC = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000c/101c9500/content/0010"
MASTER = ROOT / "data/locations_master.csv"
OUTPUT = ROOT / "data/location_positions.json"
FAIRIES = {"Great Fairy Cotera": "G-5", "Great Fairy Kaysa": "B-4",
           "Great Fairy Mija": "J-3", "Great Fairy Tera": "A-8"}
BEASTS = {"Water": "Ruta", "Fire": "Rudania", "Wind": "Medoh", "Electric": "Naboris"}
PEDESTAL = ("F-2", 2427157272)       # Weapon_Sword_070 in its pedestal


def xz(translate) -> list[float]:
    if isinstance(translate, (oead.byml.Hash, dict)):
        x, z = translate["X"], translate["Z"]
    else:
        x, z = translate[0], translate[2]
    return [round(float(x.v if hasattr(x, "v") else x), 1),
            round(float(z.v if hasattr(z, "v") else z), 1)]


def unit(aoc: Path, cell: str, kind: str = "Static"):
    path = aoc / f"Map/MainField/{cell}/{cell}_{kind}.smubin"
    return oead.byml.from_binary(unpack(path.read_bytes()))["Objs"]


def build(aoc: Path = AOC) -> dict[str, list[float]]:
    static = oead.byml.from_binary(unpack((aoc / "Map/MainField/Static.smubin").read_bytes()))
    markers: dict[str, list] = {}
    for marker in static["LocationMarker"]:
        if "MessageID" in marker:
            markers.setdefault(str(marker["MessageID"]), []).append(xz(marker["Translate"]))
        elif "Icon" in marker and str(marker["Icon"]).startswith("Remains"):
            markers.setdefault(str(marker["Icon"]), []).append(xz(marker["Translate"]))
    cells: dict[str, list] = {}

    def objects(cell):
        if cell not in cells:
            cells[cell] = list(unit(aoc, cell)) + list(unit(aoc, cell, "Dynamic"))
        return cells[cell]

    def by_hash(cell, hash_id):
        found = [o for o in objects(cell) if int(o["HashId"].v) == hash_id]
        if len(found) != 1:
            raise ValueError(f"{cell}: {len(found)} objects with HashId {hash_id}")
        return xz(found[0]["Translate"])

    def by_actor(cell, actor):
        found = [o for o in objects(cell) if str(o["UnitConfigName"]) == actor]
        if len(found) != 1:
            raise ValueError(f"{cell}: {len(found)} {actor}")
        return xz(found[0]["Translate"])

    def marker(message):
        places = markers.get(message, [])
        if len(places) != 1:
            raise ValueError(f"marker {message}: {len(places)} found")
        return places[0]

    beedles = {}
    for cell_dir in sorted((aoc / "Map/MainField").iterdir()):
        if not cell_dir.is_dir():
            continue
        for obj in objects(cell_dir.name):
            name = str(obj["UnitConfigName"])
            if name.startswith("Npc_TripMaster_"):
                beedles.setdefault(name, []).append(xz(obj["Translate"]))
    stalls = {merchant.index: by_hash(merchant.cell, merchant.hash_id) for merchant in STALLS}
    beedle_of = {merchant.place: merchant.actor for merchant in BEEDLES}

    with MASTER.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    positions = {}
    for row in rows:
        name, category, notes = row["name"], row["category"], row["notes"]
        if "Shrine" in category:
            place = marker(notes.split()[0])
        elif category == "Tower":
            place = marker("Tower" + row["gamedata_flag"].rsplit("_", 1)[1])
        elif category == "Rune Terminal":
            place = marker(notes.split("/")[0])
        elif category in ("Divine Beast", "Divine Beast Heart"):
            element = row["gamedata_flag"].rsplit("_", 1)[1]
            if element.startswith("Remains"):
                element = element[len("Remains"):]
            place = markers["Remains" + element][1]
        elif category == "Great Fairy":
            place = by_actor(FAIRIES[name], "GreatFairyBeforeRevival")
        elif category == "Master Sword":
            place = by_hash(*PEDESTAL)
        elif category == "Goal":
            place = marker("HyruleCastle")
        elif category == "Shop":
            actor = beedle_of[name.rsplit(" - ", 1)[0]]
            found = beedles.get(actor, [])
            if len(found) != 1:
                raise ValueError(f"{actor}: {len(found)} placements")
            place = found[0]
        elif category == "Stall":
            place = stalls[STALL_LOCATIONS[name].merchant.index]
        else:
            raise ValueError(f"{name}: no position rule for {category}")
        positions[name] = place
    if len(positions) != len(rows):
        raise ValueError("a location has no position")
    return positions


def encode(positions: dict) -> str:
    lines = ",\n".join(f"  {json.dumps(name)}: [{x}, {z}]" for name, (x, z) in positions.items())
    return "{\n" + lines + "\n}\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aoc", type=Path, default=AOC)
    args = parser.parse_args()
    OUTPUT.write_bytes(encode(build(args.aoc)).encode("utf-8"))
    print(OUTPUT)

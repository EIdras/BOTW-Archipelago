"""The Koroks as locations of the world (botw_world/data/koroks.json), from the game's maps.

    venv\\Scripts\\python tools\\korok_locations.py [--check]

One row per Korok of the main field (the DLC's map units, which hold all 900:
567 hidden under or behind something, 333 to catch or follow), numbered in the
order of their flags from 1:

  * flag: the saved bool the game sets once the Korok is found and gives its
    seed, MainField_<actor>_<HashId>; the seed stays (the location is a check);
  * kind: Ground (Npc_HiddenKorokGround) or Fly (Npc_HiddenKorokFly);
  * region: the tower area at its position (tools/map_regions.py);
  * name: "<place> - Korok", numbered from the place's name on the map outwards
    when the place has several, as the chests' (tools/chest_locations.py);
  * heat: an Eldin climate that sets Link on fire at its position;
  * requires: what its puzzle takes, from the actors linked to it, either way and
    through link tags (LINK_TAGS), or right next to it: bombs for a cracked wall or
    breakable rocks (the chests' BREAKABLE), Magnesis for an iron plate, box, block or
    chain (IRON: by a Korok well, a chained iron ball to lift out of the mud into a stump); the Gerudo Set inside Gerudo Town (the chests' GUARDED);
  * no_progression: "ice" (behind an ice wall) or "fire" (behind ivy to burn): no
    fire source is an item of the world.

The world reads this file only: it cannot read the game's files.
--check compares the file with the game's.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

from botw_patch import chests  # noqa: E402
from botw_patch.resources import unpack  # noqa: E402
from tools.chest_locations import (BOMBS, BREAKABLE, GUARDED, NEAR, burning, encode, inside,  # noqa: E402
                                   name_rows, places)
from tools.map_regions import area_regions, map_towers  # noqa: E402

OUTPUT = ROOT / "botw_world/data/koroks.json"
ACTORS = {"Npc_HiddenKorokGround": "Ground", "Npc_HiddenKorokFly": "Fly"}
COUNT = 900
MAIN_FIELD = "Map/MainField"
# The actors a puzzle's links go through to the Korok, and how many links deep.
LINK_TAGS = ("LinkTag", "SwitchTag", "AreaObserver", "EventTag", "TimerTag", "SignalFlowchart", "Area",
             "LocationTag")
DEPTH = 4
IRON = ("Obj_BoxIron", "Obj_BoardIron", "FldObj_Chain", "FldObj_PushRockIron")
NO_PROGRESSION = {"IceWall": "ice", "Obj_Plant_IvyBurn": "fire"}


def units(game) -> list[str]:
    """The main field's map units, in the DLC (which has every one of them)."""
    if game.aoc is None:
        raise FileNotFoundError("the Koroks are read in the DLC's maps")
    return sorted(path.relative_to(game.aoc).as_posix() for path in (game.aoc / MAIN_FIELD).glob("*/*.smubin"))


def puzzle(korok, by: dict, links: dict) -> set[str]:
    """The actors linked to a Korok, either way, through link tags."""
    seen, frontier, names = {int(korok["HashId"])}, [int(korok["HashId"])], set()
    for _ in range(DEPTH):
        reached = []
        for key in frontier:
            for other in links.get(key, ()):
                if other in seen or other not in by:
                    continue
                seen.add(other)
                name = str(by[other]["UnitConfigName"])
                if name not in ACTORS:
                    names.add(name)
                    if name.startswith(LINK_TAGS):
                        reached.append(other)
        frontier = reached
    return names


def requirements(korok, names: set[str], nearby: list, guarded: list) -> tuple[list[str], str | None]:
    """What a Korok's puzzle takes, and why no progression can wait on it."""
    x, y, z = (float(v) for v in korok["Translate"])
    close = {str(obj["UnitConfigName"]) for obj in nearby if obj is not korok
             and abs(float(obj["Translate"][0]) - x) < NEAR[0] and abs(float(obj["Translate"][2]) - z) < NEAR[0]
             and abs(float(obj["Translate"][1]) - y) < NEAR[1]}
    requires = {BOMBS for name in names | close if name.startswith(BREAKABLE)}
    requires |= {"Magnesis" for name in names | close if name.startswith(IRON)}
    requires |= {item for area, item in guarded if inside(area, x, z)}
    reason = next((why for actor, why in NO_PROGRESSION.items() if any(n.startswith(actor) for n in names)), None)
    return sorted(requires), reason


def rows(game) -> list[dict]:
    content = game.content
    bootup = oead.Sarc(unpack((content / "Pack/Bootup.pack").read_bytes()))
    heat = burning(bootup)
    towers = map_towers(content)
    named = area_regions(towers)
    sections, grid = {}, {}
    for name in units(game):
        objs = sections.setdefault(name.rsplit("/", 1)[0], [])
        objs.extend(oead.byml.from_binary(unpack(game.read_aoc(name)))["Objs"])
    found, puzzles = [], {}
    for objs in sections.values():
        by, links = {int(obj["HashId"]): obj for obj in objs}, {}
        for obj in objs:
            grid.setdefault(cell(obj), []).append(obj)
            for link in (obj["LinksToObj"] if "LinksToObj" in obj else []):
                ends = int(obj["HashId"]), int(link["DestUnitHashId"])
                links.setdefault(ends[0], []).append(ends[1])
                links.setdefault(ends[1], []).append(ends[0])
        for obj in objs:
            if str(obj["UnitConfigName"]) in ACTORS:
                found.append((chests.flag(obj), ACTORS[str(obj["UnitConfigName"])], obj))
                puzzles[chests.flag(obj)] = puzzle(obj, by, links)
    every = {int(obj["HashId"]): obj for objs in sections.values() for obj in objs}
    if not set(GUARDED) <= set(every):
        raise ValueError("an area of GUARDED is not in the main field's maps")
    guarded = [(every[key], item) for key, item in GUARDED.items()]
    flags = sorted(flag for flag, _kind, _obj in found)
    if len(set(flags)) != COUNT or len(flags) != COUNT:
        raise ValueError(f"{len(set(flags))} Korok flags, {COUNT} expected")
    numbers = {flag: number for number, flag in enumerate(flags, 1)}
    out = []
    for flag, kind, obj in found:
        x, y, z = (float(v) for v in obj["Translate"])
        nearby = [other for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                  for other in grid.get((cell(obj)[0] + dx, cell(obj)[1] + dz), ())]
        requires, reason = requirements(obj, puzzles[flag], nearby, guarded)
        out.append({"number": numbers[flag], "flag": flag, "kind": kind, "region": named[towers.at(x, z)],
                    "name": None,                       # name_rows
                    "position": [round(x, 1), round(y, 1), round(z, 1)],
                    "heat": heat(x, z), "requires": requires, "no_progression": reason})
    name_rows(out, places(game, bootup), lambda x, z: named[towers.at(x, z)], lambda _row: "Korok")
    return sorted(out, key=lambda row: row["number"])


def cell(obj) -> tuple[int, int]:
    """The 10 m square of the map an actor stands in, seen from above."""
    return int(float(obj["Translate"][0]) // 10), int(float(obj["Translate"][2]) // 10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare, write nothing")
    args = parser.parse_args()
    from tools import cemu_profile
    from tools.build_resources_from_source import game_files
    game = game_files(cemu_profile.update() / "content")
    with game.active():
        text = encode(rows(game))
    if args.check:
        same = OUTPUT.read_bytes().decode("utf-8") == text
        print("koroks.json matches the game" if same else "koroks.json differs from the game")
        raise SystemExit(0 if same else 1)
    OUTPUT.write_bytes(text.encode("utf-8"))
    print(f"{OUTPUT.relative_to(ROOT)}: {text.count(chr(10)) - 2} Koroks")


if __name__ == "__main__":
    main()

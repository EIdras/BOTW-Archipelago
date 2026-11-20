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
  * requires: what the map says its puzzle takes (none read yet).

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
from tools.chest_locations import burning, encode, name_rows, places  # noqa: E402
from tools.map_regions import area_regions, map_towers  # noqa: E402

OUTPUT = ROOT / "botw_world/data/koroks.json"
ACTORS = {"Npc_HiddenKorokGround": "Ground", "Npc_HiddenKorokFly": "Fly"}
COUNT = 900
MAIN_FIELD = "Map/MainField"


def units(game) -> list[str]:
    """The main field's map units, in the DLC (which has every one of them)."""
    if game.aoc is None:
        raise FileNotFoundError("the Koroks are read in the DLC's maps")
    return sorted(path.relative_to(game.aoc).as_posix() for path in (game.aoc / MAIN_FIELD).glob("*/*.smubin"))


def rows(game) -> list[dict]:
    content = game.content
    bootup = oead.Sarc(unpack((content / "Pack/Bootup.pack").read_bytes()))
    heat = burning(bootup)
    towers = map_towers(content)
    named = area_regions(towers)
    found = [(chests.flag(obj), ACTORS[str(obj["UnitConfigName"])], obj) for name in units(game)
             for obj in oead.byml.from_binary(unpack(game.read_aoc(name)))["Objs"]
             if str(obj["UnitConfigName"]) in ACTORS]
    flags = sorted(flag for flag, _kind, _obj in found)
    if len(set(flags)) != COUNT or len(flags) != COUNT:
        raise ValueError(f"{len(set(flags))} Korok flags, {COUNT} expected")
    numbers = {flag: number for number, flag in enumerate(flags, 1)}
    out = []
    for flag, kind, obj in found:
        x, y, z = (float(v) for v in obj["Translate"])
        out.append({"number": numbers[flag], "flag": flag, "kind": kind, "region": named[towers.at(x, z)],
                    "name": None,                       # name_rows
                    "position": [round(x, 1), round(y, 1), round(z, 1)],
                    "heat": heat(x, z), "requires": []})
    name_rows(out, places(game, bootup), lambda x, z: named[towers.at(x, z)], lambda _row: "Korok")
    return sorted(out, key=lambda row: row["number"])


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

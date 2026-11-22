"""The field bosses as locations of the world (botw_world/data/bosses.json), from the game's files.

    venv\\Scripts\\python tools\\boss_locations.py [--check]

One row per boss of the main field whose defeat the game saves: the saved bools
MainField_IsDefeat_<actor>_<HashId> of the game's GameData (86: Hinoxes, Stalnoxes,
Stone Taluses and Moldugas), numbered in the order of their flags from 1. A
defeated boss comes back with a Blood Moon; its flag stays. The six of the Trial
of the Sword's maps (AocField_IsDefeat_*) are left out.

  * flag: that saved bool;
  * kind: the boss's name in the game (ActorType/Enemy.msbt, English);
  * region: the tower area at its position (tools/map_regions.py);
  * name: "<place> - <kind>", numbered from the place's name on the map outwards
    when the place has several, as the chests' (tools/chest_locations.py);
  * heat: an Eldin climate that sets Link on fire at its position;
  * ballad: the boss of a Champion's Ballad trial, created once the trial begins
    (BalladOfHero<X>_Activated): that song's location, whose logic it takes;
  * requires, no_progression: none; fighting is the player's (no weapon is
    progression).

What creates or deletes a boss (its map unit's Create and Delete links, through link
tags) must be known (CREATING, HIDING): the Stalnoxes come at night; the Great
Plateau's Stone Talus is away during the One-Hit Obliterator's trial only. Any other
saved flag stops the build.

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

from botw_patch.resources import unpack  # noqa: E402
from tools.chest_locations import ENGLISH, burning, encode, name_rows, places  # noqa: E402
from tools.korok_locations import units  # noqa: E402
from tools.map_regions import area_regions, map_towers  # noqa: E402
from tools.quest_locations import saved_bools  # noqa: E402

OUTPUT = ROOT / "botw_world/data/bosses.json"
PREFIX = "MainField_IsDefeat_"
COUNT = 86
NAMES = ("ActorType/GiantEnemy.msbt", "ActorType/Sandworm.msbt")
# The saved flags of the link tags that create a boss: what the location takes (the
# song whose trial creates it), or None (the night's, which comes).
CREATING = {"WM_IsNightA": None, "WM_IsNightB": None,
            "BalladOfHeroGoron_Activated": "Daruk's Song", "BalladOfHeroGerudo_Activated": "Urbosa's Song",
            "BalladOfHeroRito_Activated": "Revali's Song", "BalladOfHeroZora_Activated": "Mipha's Song"}
# Those of the tags that delete a boss for a while: the One-Hit Obliterator's trial
# on the Great Plateau (from its step 2 to its step 3).
HIDING = ("BalladOfHeroes_Step02", "BalladOfHeroes_Step03")
LINKS = ("Create", "Delete")
DEPTH = 3


def conditions(key: int, objs: dict, into: dict) -> tuple[set[str], set[str]]:
    """The saved flags of the link tags that create, then delete, a boss."""
    out: dict[str, set[str]] = {kind: set() for kind in LINKS}
    for kind, source in into.get(key, ()):
        if kind not in LINKS:
            continue
        frontier, seen = [source], {source}
        for _ in range(DEPTH):
            reached = []
            for tag in frontier:
                parameters = objs[tag]["!Parameters"] if "!Parameters" in objs[tag] else {}
                if "SaveFlag" in parameters and str(parameters["SaveFlag"]):
                    out[kind].add(str(parameters["SaveFlag"]))
                reached += [other for _kind, other in into.get(tag, ())
                            if other not in seen and str(objs[other]["UnitConfigName"]).startswith("LinkTag")]
                seen.update(reached)
            frontier = reached
    return out["Create"], out["Delete"]


def kinds(game) -> dict[str, str]:
    """The bosses' English names, by actor."""
    from botw_patch.shop_items import read_labels
    from tools.chest_locations import plain
    language = next(code for code in ENGLISH if (game.content / f"Pack/Bootup_{code}.pack").is_file())
    texts = oead.Sarc((game.content / f"Pack/Bootup_{language}.pack").read_bytes())
    messages = oead.Sarc(unpack(bytes(texts.get_file(f"Message/Msg_{language}.product.ssarc").data)))
    return {label[:-len("_Name")]: plain(text.strip("\0").strip()) for name in NAMES
            for label, text in read_labels(bytes(messages.get_file(name).data)).items() if label.endswith("_Name")}


def kind(names: dict[str, str], actor: str) -> str:
    """An actor's name, or its family's (Enemy_Giant_Bone_AllDay, a Stalnox, has none of its own)."""
    family = max((known for known in names if actor == known or actor.startswith(known + "_")), key=len, default=None)
    if family is None:
        raise ValueError(f"{actor}: no English name")
    return names[family]


def rows(game) -> list[dict]:
    bootup = oead.Sarc(unpack((game.content / "Pack/Bootup.pack").read_bytes()))
    flags = sorted(flag for flag in saved_bools(bootup) if flag.startswith(PREFIX))
    if len(flags) != COUNT:
        raise ValueError(f"{len(flags)} saved {PREFIX} flags, {COUNT} expected")
    objs = {int(obj["HashId"]): obj for name in units(game)
            for obj in oead.byml.from_binary(unpack(game.read_aoc(name)))["Objs"]}
    into: dict[int, list[tuple[str, int]]] = {}
    for obj in objs.values():
        for link in (obj["LinksToObj"] if "LinksToObj" in obj else []):
            into.setdefault(int(link["DestUnitHashId"]), []).append((str(link["DefinitionName"]), int(obj["HashId"])))
    heat = burning(bootup)
    towers = map_towers(game.content)
    named = area_regions(towers)
    names = kinds(game)
    out = []
    for number, flag in enumerate(flags, 1):
        actor, _, hash_id = flag[len(PREFIX):].rpartition("_")
        obj = objs.get(int(hash_id))
        if obj is None or str(obj["UnitConfigName"]) != actor:
            raise ValueError(f"{flag}: no {actor} of that HashId in the main field's maps")
        creating, deleting = conditions(int(hash_id), objs, into)
        unknown = (creating - set(CREATING)) | (deleting - set(HIDING))
        if unknown:
            raise ValueError(f"{flag}: created or deleted by {sorted(unknown)}, not in CREATING or HIDING")
        songs = {CREATING[name] for name in creating} - {None}
        if len(songs) > 1:
            raise ValueError(f"{flag}: created by several trials: {sorted(songs)}")
        x, y, z = (float(v) for v in obj["Translate"])
        out.append({"number": number, "flag": flag, "kind": kind(names, actor), "region": named[towers.at(x, z)],
                    "name": None,                       # name_rows
                    "position": [round(x, 1), round(y, 1), round(z, 1)],
                    "heat": heat(x, z), **({"ballad": songs.pop()} if songs else {}),
                    "requires": [], "no_progression": None})
    name_rows(out, places(game, bootup), lambda x, z: named[towers.at(x, z)], lambda row: row["kind"])
    return out


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
        same = OUTPUT.is_file() and OUTPUT.read_bytes().decode("utf-8") == text
        print("bosses.json matches the game" if same else "bosses.json differs from the game")
        raise SystemExit(0 if same else 1)
    OUTPUT.write_bytes(text.encode("utf-8"))
    print(f"{OUTPUT.relative_to(ROOT)}: {text.count(chr(10)) - 2} bosses")


if __name__ == "__main__":
    main()

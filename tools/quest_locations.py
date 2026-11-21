"""The side quests and shrine quests as locations of the world (botw_world/data/quests.json), from the game's
quest list.

    venv\\Scripts\\python tools\\quest_locations.py [--check]

TitleBG.pack > Quest/QuestProduct.sbquestpack lists the quests; the flag the last step of each sets (its
NextFlag, <Quest>_Finish mostly) is a bool the game saves for 155 of them. Those 155 are numbered from 1 in
the order of their flags: a quest left out keeps its number unused, for a later version. One row per quest
kept, each a check: the quest still gives its reward.

  * flag: the finish flag;
  * quest: the quest's name in the game's files;
  * kind: "Side" (a side quest, Mini) or "Shrine" (a shrine quest, Sub);
  * shrine: a shrine quest's shrine, a location already (SHRINES), whose logic the quest takes;
  * region: a side quest's, the tower area of the place its entry of the Adventure Log names (or of its
    giver, GIVERS); a shrine quest's, its shrine's;
  * name: "<place> - <quest>", that place and the quest's English name;
  * position: the place on the map;
  * heat: an Eldin climate that sets Link on fire at the place;
  * requires: a side quest's items and events: the Gerudo Set inside Gerudo Town (GUARDED), then its
    logic (below);
  * maps: the maps of the other regions a side quest goes through;
  * no_progression: why no progression can wait on the quest (NO_PROGRESSION), or on the quest it follows.

A side quest's logic is written by hand (SIDE_LOGIC), from what its flows check on the way to each of its
steps (items, equipment, pictures) and from where the map holds what they check; then what the flag it
depends on asks (QuestProduct's QuestDependencyFlag): another quest's finish flag brings that quest's
logic, any other flag its DEPENDENCIES entry. A new dependency flag fails the build.

Left out: the main quests, the shrine quests' records of mini-games (Sub quests without a shrine), and
LEFT_OUT. The world reads this file only: it cannot read the game's files. --check compares the file with
the game's.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

from botw_patch.resources import unpack  # noqa: E402
from tools.chest_locations import AREAS, ENGLISH, MARKERS, PLACE_TEXTS, burning, encode, plain  # noqa: E402
from tools.map_regions import area_regions, map_towers  # noqa: E402

OUTPUT = ROOT / "botw_world/data/quests.json"
LOCATIONS = ROOT / "botw_world/data/locations.json"
QUESTS = "Quest/QuestProduct.sbquestpack"
QUEST_TEXTS = "QuestMsg/"
KINDS = {"Mini": "Side", "Sub": "Shrine"}
SAVED = 155
# The shrine each shrine quest raises, from the reward of its zeldawiki page; for the 13 whose steps name
# their DungeonNNN, the same shrine (checked).
SHRINES = {
    "DokuroEye": "Zuna Kai Shrine", "MacuseIseki": "Ritaag Zumo Shrine", "Solitary_Maze": "Tu Ka'loh Shrine",
    "HigakkareMini_RedDragon": "Tutsuwa Nima Shrine", "GoronCamp": "Gorae Torr Shrine",
    "GoronsRock": "Kayra Mah Shrine", "MtMotelMini_Landscape": "Tah Muhl Shrine",
    "Gerudo_CarryIce": "Misae Suma Shrine", "Gaman": "Joloo Nah Shrine", "Shadow_Sign": "Sasa Kai Shrine",
    "MagneticFld": "Kema Zoos Shrine", "Desert_Maze": "Dila Maag Shrine", "KnightDoll": "Korsh O'hu Shrine",
    "SandStorm": "Dako Tah Shrine", "SecretofObject": "Suma Sahma Shrine", "SunazarashiRace": "Raqa Zunzo Shrine",
    "DontDamageFlower": "Hila Rao Shrine", "Threebros_giant": "Tawa Jinn Shrine",
    "HatenoMini_ThreeTree": "Tahno O'ah Shrine", "CursedStatue": "Kam Urog Shrine", "SearchStone": "Kah Yah Shrine",
    "StolenBook": "Lakna Rokee Shrine", "Remains_Fancier": "Shoqa Tatone Shrine",
    "Thunder_Sword": "Qukah Nata Shrine", "MouthofDragon": "Shae Katha Shrine", "NakedIsland": "Korgu Chideh Shrine",
    "RitoRabitMountain": "Mozo Shenno Shrine", "Rito_BrosRock": "Voo Lota Shrine",
    "RitoSongMystery": "Bareeda Naag Shrine", "Cliff_Maze": "Qaza Tokki Shrine",
    "HatenoMini_WhiteDragon": "Jitan Sa'mi Shrine", "StatueofZora": "Dagah Keek Shrine",
    "Animal_Forest": "Mezza Lo Shrine", "Relief_Landing": "Shai Yota Shrine", "FirstOhenro": "Daag Chokah Shrine",
    "TwoWheels": "Sheem Dagoze Shrine", "DarkWoods": "Ketoh Wawai Shrine", "BloodyMoonRelief": "Mijah Rokee Shrine",
    "SeekerEye": "Keeha Yoog Shrine", "GodTree": "Kuhn Sidajj Shrine", "ShieldofKolog": "Maag Halan Shrine",
    "FourJewel": "Toh Yahsa Shrine",
}
# Side quests that are no location, and why.
LEFT_OUT = {
    "Hateno_SheikPad_PowerUp": "Purah's three upgrades are locations already",
    "CompleteDungeon": "takes the 120 shrines",
    "HatenoMini_DevilSeal": "trades hearts and stamina, which the Master Sword's 13 hearts rule counts",
    "bf2_collabo": "the Xenoblade Chronicles 2 chest, not on the Wii U",
    "100enemy": "the Trial of the Sword, hours long, for an option of its own",
    **{f"TreasureHunt0{n}": "ends as an EX chest opens, a chest location" for n in range(1, 5)},
    **{f"TreasureHunt_touzoku0{n}": "ends as an EX chest opens, a chest location" for n in range(1, 9)},
}
# The places where the logic asks the Gerudo Set: inside Gerudo Town.
GUARDED = {"Gerudo": "Gerudo Set"}
NO_PROGRESSION = {"HatenoMini_MyHome": "rupees", "UMiiMini_MakeVillage": "long",
                  "HatenoMini_WeaponMania": "weapons",          # eight given weapons from all over Hyrule
                  "TabantaBridgeMini_Sundial": "rupees"}        # a Great Fairy, up to 10,000 rupees
# The Camera: Purah restores it at Hateno's lab (Demo032_0), in the quest Impa gives in Kakariko; the
# maps of the lab's Rune Upgrade locations and of Kah Yah's.
CAMERA = "Camera"
CAMERA_MAPS = ("Hateno Map", "Dueling Peaks Map")
# What a side quest asks beyond its region: items, events ("Freed - <Divine Beast>", "Cleared - <shrine>"),
# CAMERA, other regions' maps ("<region> Map") and the quests it follows (by name, their logic in turn).
SIDE_LOGIC = {
    "FironeMini_TerribleThunder": ("Magnesis",),        # the iron chest that draws the lightning
    "GoronMini_WallCrackTBox": ("Progressive Remote Bomb",),     # the Drillshaft behind a cracked wall
    "HateeluMini_Treasure": ("Magnesis",),              # iron chests, as the chests' rule
    "UotoriMini_SinkTreasure": ("Magnesis",),
    "isso_treasure_mini": ("Magnesis",),
    "HyruleDepthMini_WhiteHorse": ("Ridgeland Map",),   # GameRomHorseZelda
    "MinakkareMini_Dragonfly": ("Ridgeland Map",),      # Animal_Insect_I, placed in Ridgeland only
    "OneHundred": ("Gerudo Map",),
    "RitoMini_IceGolem": ("Hebra Map",),                # the Frost Talus
    "ZoraMini_FlowedWife": ("Lake Map",),
    "My_Hero": ("Master Sword",),                       # Weapon_Sword_070 in the pouch, on every path
    "ZoraMini_DiveChallenge": ("Zora Set",),            # back up the waterfall
    # The three Korok trials of the forest, shrine quests whose shrines' logic the events hold.
    "KorokMini_KorokShiren": ("Cleared - Daag Chokah Shrine", "Cleared - Kuhn Sidajj Shrine",
                              "Cleared - Maag Halan Shrine"),
    # Pictures: Kilton, a Blupee (Dueling Peaks), a Lynel (Hateno), the three Leviathans, a Stalhorse
    # (placed in Lake), the Eighth Heroine's statue and her sword (both in the Gerudo Highlands, the
    # quests given outside Gerudo Town by Bozai, who asks for the Gerudo outfit), Purah to meet Robbie.
    "HigakkareMini_StrangeMan": (CAMERA,),
    "KorokMini_UMAShiren": (CAMERA,),
    "RinelSearch": (CAMERA,),
    "MarittaMini_BigWhales": ("Hebra Map", "Wasteland Map", "Eldin Map"),
    "SetugenUmayadoMini_Umahonephoto": ("Lake Map",),
    "Gerudo_Ch_SnowMT": ("Gerudo Set", "Gerudo Map"),
    "Gerudo_Ch_SnowBoots": ("Gerudo Set", "Gerudo Map"),
    "HatenoMini_BlueFire": (CAMERA, "Akkala Map"),
    # Tarrey Town's people, there once From the Ground Up has built it.
    "UMiiMini_GiveCake": ("UMiiMini_MakeVillage",),
    "UMiiMini_RichmansHobby": ("UMiiMini_MakeVillage",),
}
# What a dependency flag that is no quest's finish flag asks; nothing when it is set where the quest
# is given (a talk there).
DEPENDENCIES = {
    "Water_Relic_Finished": ("Freed - Divine Beast Vah Ruta",),
    "Electric_Relic_Finished": ("Freed - Divine Beast Vah Naboris",),
    "Clear_RemainsFire": ("Freed - Divine Beast Vah Rudania",),
    "Clear_RemainsWind": ("Freed - Divine Beast Vah Medoh",),
    "IsGet_Obj_Camera": (CAMERA,),
    # Set by Purah after her Sheikah Sensor upgrade (Npc_AncientDoctor Event398): that location's map.
    "AncientLabo_AncientAssistant001_SSLv2Get": ("Dueling Peaks Map",),
    # The first try at the Master Sword's pull (botw_patch/pedestal.py), with any hearts.
    "IsPlayed_Demo104_0": (),
    "Find_Impa_Finish": (), "Gerudo_Ch_Helmet_Activated": (),
    "Water_Relic_Activated": (), "Water_Relic_Step1_1": (),
    "Water_Relic_ArmorSend": (),        # set past the Zora King's gift, which build.py only empties
}
# A quest whose Adventure Log place is a region's name marked in another tower's area: its giver's
# place (map unit, actor). Wabbin stands at the Lover's Pond, west of Lurelin.
GIVERS = {"FironeMini_HeartPond": ("H-8", "Npc_SouthernVillage016")}
# Regions without a map.
MAPLESS = ("Great Plateau", "Hyrule Castle")
# The marks of a place, by preference: a marker of the map, a pointer, an area.
MARK_KINDS = ("LocationMarker", "LocationPointer", "area")


def quest_list(content: Path) -> list[dict]:
    title = oead.Sarc(unpack((content / "Pack/TitleBG.pack").read_bytes()))
    return list(oead.byml.from_binary(unpack(bytes(title.get_file(QUESTS).data))))


def finish_flag(quest) -> str:
    return str(quest["Steps"][-1]["NextFlag"])


def saved_bools(bootup: oead.Sarc) -> set[str]:
    out = set()
    for file in oead.Sarc(unpack(bytes(bootup.get_file("GameData/gamedata.ssarc").data))).get_files():
        data = oead.byml.from_binary(bytes(file.data))
        out |= {str(entry["DataName"]) for entry in (data["bool_data"] if "bool_data" in data else ())
                if "IsSave" in entry and bool(entry["IsSave"])}
    return out


def texts(game) -> tuple[dict[str, str], dict[str, str]]:
    """The English names of the places and of the quests, by their labels."""
    from botw_patch.shop_items import read_labels
    language = next(code for code in ENGLISH if (game.content / f"Pack/Bootup_{code}.pack").is_file())
    pack = oead.Sarc((game.content / f"Pack/Bootup_{language}.pack").read_bytes())
    messages = oead.Sarc(unpack(bytes(pack.get_file(f"Message/Msg_{language}.product.ssarc").data)))
    places = {key: plain(text.strip("\0").strip())
              for key, text in read_labels(bytes(messages.get_file(PLACE_TEXTS).data)).items()}
    quests = {key[len("QL_"):-len("_Name")]: plain(text.strip("\0").strip())
              for file in messages.get_files() if file.name.startswith(QUEST_TEXTS)
              for key, text in read_labels(bytes(file.data)).items()
              if key.startswith("QL_") and key.endswith("_Name")}
    return places, quests


def marks(game, bootup: oead.Sarc) -> dict[str, tuple[float, float, float]]:
    """Where the map puts each place, by its MessageID (MARK_KINDS)."""
    static = oead.byml.from_binary(unpack(game.read_aoc(MARKERS)))
    lists = {"LocationMarker": static["LocationMarker"], "LocationPointer": static["LocationPointer"],
             "area": oead.byml.from_binary(unpack(bytes(bootup.get_file(AREAS).data)))}
    out = {}
    for kind in reversed(MARK_KINDS):
        for mark in reversed(list(lists[kind])):
            if "MessageID" in mark:
                at = mark["Translate"]
                out[str(mark["MessageID"])] = tuple(round(float(at[axis]), 1) if axis in at else 0.0
                                                    for axis in ("X", "Y", "Z"))
    return out


def shrine_regions() -> dict[str, str]:
    return {row["name"]: row["region"] for row in json.loads(LOCATIONS.read_text(encoding="utf-8"))
            if "Shrine" in row["category"]}


def check_shrines(quests: list) -> None:
    """A shrine quest whose steps name a DungeonNNN names the shrine of SHRINES."""
    import csv
    with (ROOT / "data/locations_master.csv").open(encoding="utf-8") as file:
        dungeons = {row["gamedata_flag"][len("Clear_"):]: row["name"] for row in csv.DictReader(file)
                    if row["gamedata_flag"].startswith("Clear_Dungeon")}
    for quest in quests:
        name = str(quest["Name"])
        named = set(re.findall(r"Dungeon\d{3}", json.dumps(oead.byml.to_text(quest))))
        if name in SHRINES and len(named) == 1 and dungeons[named.pop()] != SHRINES[name]:
            raise ValueError(f"{name}: its steps name another shrine than {SHRINES[name]}")


def rows(game) -> list[dict]:
    content = game.content
    bootup = oead.Sarc(unpack((content / "Pack/Bootup.pack").read_bytes()))
    quests = quest_list(content)
    saved = saved_bools(bootup)
    flags = sorted({finish_flag(quest) for quest in quests} & saved)
    if len(flags) != SAVED:
        raise ValueError(f"{len(flags)} saved finish flags, {SAVED} expected")
    numbers = {flag: number for number, flag in enumerate(flags, 1)}
    check_shrines(quests)
    heat, towers = burning(bootup), map_towers(content)
    named = area_regions(towers)
    places, names = texts(game)
    where = marks(game, bootup)
    regions = shrine_regions()
    out, dependencies = [], {}
    for quest in quests:
        quest_id, kind = str(quest["Name"]), KINDS.get(str(quest["Type"]))
        if kind is None or quest_id in LEFT_OUT or kind == "Shrine" and quest_id not in SHRINES:
            continue
        flag, place = finish_flag(quest), str(quest["Location"])
        if flag not in numbers:
            raise ValueError(f"{quest_id}: its finish flag {flag} is not saved")
        x, y, z = giver(game, *GIVERS[quest_id]) if quest_id in GIVERS else where[place]
        shrine = SHRINES.get(quest_id)
        if kind == "Side" and "QuestDependencyFlag" in quest:
            dependencies[quest_id] = str(quest["QuestDependencyFlag"])
        out.append({"number": numbers[flag], "flag": flag, "quest": quest_id, "kind": kind,
                    **({"shrine": shrine} if shrine else {}),
                    "region": regions[shrine] if shrine else named[towers.at(x, z)],
                    "name": f"{places[place]} - {names[quest_id]}", "position": [x, y, z],
                    "heat": heat(x, z), "requires": [GUARDED[place]] if place in GUARDED and not shrine else [],
                    "maps": [], "no_progression": NO_PROGRESSION.get(quest_id)})
    if {row["quest"] for row in out if row["kind"] == "Shrine"} != set(SHRINES):
        raise ValueError("SHRINES names a quest the game does not list as a shrine quest")
    side_logic(out, dependencies)
    return sorted(out, key=lambda row: row["number"])


def giver(game, unit: str, actor: str) -> tuple[float, float, float]:
    """Where a map unit of the main field holds an actor, its only one."""
    found = [obj["Translate"] for obj in oead.byml.from_binary(
        unpack(game.read_aoc(f"Map/MainField/{unit}/{unit}_Static.smubin")))["Objs"]
        if str(obj["UnitConfigName"]) == actor]
    if len(found) != 1:
        raise ValueError(f"{unit} holds {len(found)} {actor}")
    return tuple(round(float(found[0][axis]), 1) for axis in range(3))


def side_logic(rows: list[dict], dependencies: dict[str, str]) -> None:
    """Each side quest's requires, maps and no_progression: its SIDE_LOGIC, and what its dependency flag
    asks, with the logic of the quests it follows (whose regions' maps it needs as well)."""
    by_quest = {row["quest"]: row for row in rows}
    quest_of = {row["flag"]: row["quest"] for row in rows}
    unknown = sorted(set(dependencies.values()) - set(quest_of) - set(DEPENDENCIES))
    if unknown or not set(SIDE_LOGIC) <= {row["quest"] for row in rows if row["kind"] == "Side"}:
        raise ValueError(f"a dependency flag without logic ({unknown}) or SIDE_LOGIC names no side quest")

    def resolve(quest: str, path: tuple[str, ...]) -> tuple[set[str], set[str], str | None]:
        if quest in path:
            raise ValueError(f"{quest}: its dependencies loop")
        row = by_quest[quest]
        requires, maps, reason = set(row["requires"]), set(), row["no_progression"]
        flag = dependencies.get(quest)
        for term in (*SIDE_LOGIC.get(quest, ()),
                     *((quest_of[flag],) if flag in quest_of else DEPENDENCIES.get(flag, ()))):
            if term in by_quest:
                needs, through, why = resolve(term, path + (quest,))
                if by_quest[term]["region"] != row["region"]:
                    if by_quest[term]["region"] in MAPLESS:
                        raise ValueError(f"{quest} follows a quest of {by_quest[term]['region']}")
                    through.add(f"{by_quest[term]['region']} Map")
                requires, maps, reason = requires | needs, maps | through, reason or why
            elif term == CAMERA:
                maps |= set(CAMERA_MAPS)
            elif term.endswith(" Map"):
                maps.add(term)
            else:
                requires.add(term)
        return requires, maps - {f"{row['region']} Map"}, reason

    for row in rows:
        if row["kind"] == "Side":
            requires, maps, reason = resolve(row["quest"], ())
            row.update(requires=sorted(requires), maps=sorted(maps), no_progression=reason)


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
        print("quests.json matches the game" if same else "quests.json differs from the game")
        raise SystemExit(0 if same else 1)
    OUTPUT.write_bytes(text.encode("utf-8"))
    print(f"{OUTPUT.relative_to(ROOT)}: {text.count(chr(10)) - 2} quests")


if __name__ == "__main__":
    main()

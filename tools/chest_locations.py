"""The chests as locations of the world (botw_world/data/chests.json), from the game's files.

    venv\\Scripts\\python tools\\chest_locations.py [--check]

One row per chest of botw_patch/chests.py, in its numbering (the chests' flags in
order): its number, flag, kind, region, name and position, what the map says
reaching it takes, and why it should hold no progression, when the map cannot
tell what opens it. The world reads this file only: it cannot read the game's files.

  * region: the tower area at the chest's position (tools/map_regions.py);
  * name: "<place> - <kind> Chest", numbered from the place's name on the map
    outwards when the place has several of the kind. The place is the nearest
    name the map shows in the chest's region (places): its areas, landmarks,
    villages, stables and labs, never a shrine, tower or Divine Beast, nor a name
    several places share. In English (the US and European texts name the places
    alike) and in ASCII;
  * heat: an Eldin climate that sets Link on fire (EldinClimateLv1 and Lv2: the two
    of TitleBG.pack > WorldMgr/normal.bwinfo with an IgnitedLevel) at its position
    (Bootup.pack > Ecosystem/FieldMapArea.sbeco, then AreaData.sbyml);
  * dungeon: the shrine (shrine_rows) or Divine Beast (beast_rows) a chest is
    in, its location's name; the chest is named after it and numbered from its
    entrance, and the world asks for its row of logic.csv with every rune (what
    a side chest takes is the layout, which no data tells). Its heat is None. The
    chests of a small key are left out: the key opens the way;
  * sent_with: a Divine Beast's chest, which cannot be opened once the beast is
    freed (no beast can be entered again, and the Champions' Ballad deletes its
    chests): the location whose check also sends it, by the client;
  * requires: Magnesis for an iron chest (buried, sunk or under an iron block);
    bombs behind a cracked wall or under breakable rocks (BREAKABLE); what the
    saved flag that creates a chest stands for (CREATING_FLAGS: a Divine Beast
    freed, every shrine cleared, Master Kohga beaten); what the guards of an
    area ask for (GUARDED: Gerudo Town's, the Gerudo Set);
  * no_progression: "quest" (EX treasures, and chests a side quest creates),
    "fight" (created once a Lynel or a Stalnox is beaten), "spawned" (a puzzle
    of its own creates it), "ice" (frozen: no fire source is an item of the
    world), "rock" (under a boulder to push).

Left out, so that no location waits on them (the pack leaves their contents):
chests nobody can reach (INACCESSIBLE); those that something the player does
can take away, a Delete link or a negated or exclusive condition in what creates
them (NEGATING): the Warm Doublet's, there only if the old man did not give it,
and two of a Lake Saria puzzle's; and the Xenoblade Chronicles 2 collaboration's
(COLLABORATION), which the Wii U was never seen to show.

The Master Mode chests (botw_patch/chests.py is_master_chest: 118, each on the platform
of an Octorok balloon) go to botw_world/data/master_chests.json (MASTER_OUTPUT), by the
same rules, as "Master Mode <kind>" chests: the world's master_mode.
--check compares the files with the game's (a test does when the DLC is installed
and Cemu launches the base game from a folder).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

from botw_patch import chests  # noqa: E402
from botw_patch.resources import unpack  # noqa: E402
from tools.map_regions import Beco, area_regions, map_towers  # noqa: E402

OUTPUT = ROOT / "botw_world/data/chests.json"
MASTER_OUTPUT = ROOT / "botw_world/data/master_chests.json"
MASTER_KIND = "Master Mode "
FIELD_AREAS = "Ecosystem/FieldMapArea.sbeco"
AREA_DATA = "Ecosystem/AreaData.sbyml"
BURNING = ("EldinClimateLv1", "EldinClimateLv2")
# Out of reach in every game (The Cutting Room Floor), and Aris Beach's two
# candidates until the Sensor+ says which one is its unreachable chest.
INACCESSIBLE = {
    "MainField_TBox_Field_Wood_3940677724": "under the map",
    "MainField_TBox_Field_Iron_1429812883": "inside a rock",
    "MainField_TBox_Field_Iron_797448374": "Aris Beach, one of two candidates",
    "MainField_TBox_Field_Iron_2325715544": "Aris Beach, one of two candidates",
}
# A chest created when one of these breaks (a Create link fed by it through tags),
# one within NEAR of a cracked wall or rocks (across, then up or down) and one
# under a rock cover take bombs: a hammer is a sequence break.
BREAKABLE = ("WallCrack", "Obj_RockBroken_", "Obj_RockCover")
NEAR = (2.5, 3.0)
TAGS = ("LinkTag", "SwitchTimeLag", "EventTag", "AreaCulling")
NEGATING = ("LinkTagNAnd", "LinkTagNOr", "LinkTagXOr")
BOMBS = "Progressive Remote Bomb"
# The world's (botw_world/catalog.py): every shrine cleared.
ALL_SHRINES = "All Shrines"
# The saved flags that create chests (the start of their names): what the logic asks
# for, or why it cannot (no_progression). A flag missing here stops the build.
CREATING_FLAGS = {
    "HasAoCVer1": (),                                   # the DLC, which every game has
    "AoC_HardMode_Enabled": (),                         # Master Mode, which master_mode asks for
    "Wind_Relic_": ("Freed - Divine Beast Vah Medoh",),
    "Fire_Relic_": ("Freed - Divine Beast Vah Rudania",),
    "AssassinBoss_": ("Magnesis",),                     # Master Kohga's fight
    "CompleteDungeon_": (ALL_SHRINES,),
    "HatenoMini_": "quest", "TaiyoBox_": "quest", "KorinBox_": "quest",
    "Gerudo_tsukamidake_": "quest", "OneHundred_": "quest",
}
COLLABORATION = "CollaborationShootingStar_"
# The areas whose guards turn Link out (a box Area, by its HashId): what entering
# asks. Gerudo Town's, the largest of the boxes around the town, as its stalls.
GUARDED = {740973166: "Gerudo Set"}
# The actors whose end creates chests, through tags: what each asks.
CREATING_ACTORS = {"Animal_Dog_": None, "Enemy_": "fight", **{name: BOMBS for name in BREAKABLE}}
KINDS = {"TBox_Field_Wood": "Wooden", "TBox_Field_Stone": "Stone", "TBox_Field_Enemy": "Skull"}
QUEST_KINDS = ("_Aoc", "_Collabo")
# The map's names: its areas (Bootup.pack, at each zoom level that shows them, the
# regions' own levels 1 and 2 left out), its landmarks and its markers (the DLC's
# Static.smubin, the markers of these icons), named by LocationMarker.msbt.
AREAS = "Map/MainField/Location.smubin"
AREA_LEVELS = (4, 8)
MARKERS = "Map/MainField/Static.smubin"
MARKER_ICONS = ("Village", "Hatago", "Labo", "Castle", "CheckPoint", "StartPoint")
PLACE_TEXTS = "StaticMsg/LocationMarker.msbt"
ENGLISH = ("USen", "EUen")
# A name the map gives to several distinct places: the four Great Fairies' fountains.
SHARED_NAMES = ("Great Fairy Fountain",)
# The shrines' chests: their kinds, their shrine's entrance (in each static unit),
# what a small key's chest holds, and the links to a chest known to change nothing
# (a tag that brings back a chest fallen off, a sound area).
LOCATIONS = ROOT / "botw_world/data/locations.json"
DUNGEON_KINDS = {"TBox_Dungeon_Wood": "Wooden", "TBox_Dungeon_Stone": "Stone", "TBox_Dungeon_Iron": "Iron"}
ENTRANCE = "DgnObj_EntranceElevator_A_01"
SHRINE_KEY = "KeySmall"
SHRINE_LINKS = ("Recreate", "Reference")
SHRINE_PARAMETERS = ("DropActor", "DropTable", "EnableRevival", "IsInGround", "SharpWeaponJudgeType",
                     "FieldBodyGroup", "StartNoDraw")
# The Divine Beasts' chests: their travel point inside, and the links known to
# them. Each is deleted once its Champion's Ballad begins (BALLAD, after the four
# beasts are freed), and no beast can be entered again once freed: the client
# sends the chests left inside when the beast's location is checked (sent_with).
# Some are created when a malice eye dies, or after a cutscene of the beast
# (BEAST_CREATING); the others are a cutscene's, hang from a rope, or stop the
# Sheikah Sensor or attention while inside an area.
BEAST_ENTRANCE = "DgnObj_WarpPoint_Remains"
BALLAD = ("BalladOfHero", "_Activated")
BEAST_CREATING = {"IsPlayed_Demo115_0", "IsPlayed_Demo118_0", "TwnObj_GanonGrudgeSolid_Eyeball_A_01"}
BEAST_LINKS = ("Delete", "Create", "DemoMember", "BAndSLimitAngYCs", "ModelBind", "SensorBind", "ForbidAttention")


def label(obj, parameters) -> str:
    """The kind of chest a player sees: wooden, stone, iron, buried, skull or EX."""
    actor = str(obj["UnitConfigName"])
    if any(part in actor for part in QUEST_KINDS):
        return "EX"
    if "IsInGround" in parameters and bool(parameters["IsInGround"]):
        return "Buried"
    return next((kind for prefix, kind in KINDS.items() if actor.startswith(prefix)),
                "Iron" if actor.startswith("TBox_Field_Iron") else actor)


def plain(text: str) -> str:
    """A name in ASCII, as players type it in a YAML (Boné Pond: Bone Pond)."""
    text = text.replace("’", "'")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def places(game, bootup: oead.Sarc) -> list[tuple[str, float, float]]:
    """The names the map shows and where: [(name, x, z)]."""
    from botw_patch.shop_items import read_labels
    language = next(code for code in ENGLISH if (game.content / f"Pack/Bootup_{code}.pack").is_file())
    texts = oead.Sarc((game.content / f"Pack/Bootup_{language}.pack").read_bytes())
    messages = oead.Sarc(unpack(bytes(texts.get_file(f"Message/Msg_{language}.product.ssarc").data)))
    names = {key: plain(text.strip("\0").strip())
             for key, text in read_labels(bytes(messages.get_file(PLACE_TEXTS).data)).items()}
    static = oead.byml.from_binary(unpack(game.read_aoc(MARKERS)))
    marks = [*(area for area in oead.byml.from_binary(unpack(bytes(bootup.get_file(AREAS).data)))
               if int(area["ShowLevel"]) in AREA_LEVELS),
             *static["LocationPointer"],
             *(marker for marker in static["LocationMarker"]
               if "Icon" in marker and str(marker["Icon"]) in MARKER_ICONS)]
    out = []
    for mark in marks:
        name = names.get(str(mark["MessageID"]) if "MessageID" in mark else "", "")
        if name and name not in SHARED_NAMES:
            out.append((name, float(mark["Translate"]["X"]), float(mark["Translate"]["Z"])))
    return out


def name_chests(out: list[dict], marks: list[tuple[str, float, float]], region_of) -> None:
    """Each row's name: its place and its kind (name_rows)."""
    name_rows(out, marks, region_of, lambda row: f"{row['kind']} Chest")


def name_rows(out: list[dict], marks: list[tuple[str, float, float]], region_of, noun) -> None:
    """Each row's name: its place, the nearest of the region's marks, and noun(row),
    numbered from the place's nearest mark outwards when several share both."""
    by_region: dict[str, list[tuple[str, float, float]]] = {}
    for mark in marks:
        by_region.setdefault(region_of(mark[1], mark[2]), []).append(mark)
    groups: dict[tuple[str, str], list[tuple[float, int, dict]]] = {}
    for row in out:
        x, _y, z = row["position"]
        place, px, pz = min(by_region.get(row["region"]) or marks,
                            key=lambda mark: (mark[1] - x) ** 2 + (mark[2] - z) ** 2)
        groups.setdefault((place, noun(row)), []).append(
            (round((px - x) ** 2 + (pz - z) ** 2, 1), row["number"], row))
    for (place, what), members in groups.items():
        for index, (_distance, _number, row) in enumerate(sorted(members, key=lambda m: m[:2]), 1):
            row["name"] = f"{place} - {what}" + (f" {index}" if len(members) > 1 else "")


def burning(bootup: oead.Sarc):
    """(x, z) -> whether an Eldin climate there sets Link on fire (BURNING)."""
    fields = Beco(unpack(bytes(bootup.get_file(FIELD_AREAS).data)))
    climates = {int(a["AreaNumber"]): str(a["Climate"])
                for a in oead.byml.from_binary(unpack(bytes(bootup.get_file(AREA_DATA).data)))}
    return lambda x, z: climates[fields.at(x, z)] in BURNING


def base_content() -> Path:
    """The base game's content/ (the shrines' packs are the base game's, not the
    update's): where Cemu lists the game it launches, as a folder."""
    from tools import cemu_profile
    content = cemu_profile.base_content()
    if content is None:
        raise FileNotFoundError("the shrines' chests are read in the base game as a folder")
    return content


def owners(prefix: str) -> dict[str, dict]:
    """{DungeonNNN or RemainsXXX: its location's row} (botw_world/data/locations.json),
    by the flag its clearing sets (Clear_<name>)."""
    return {row["gamedata_flag"].removeprefix("Clear_"): row
            for row in json.loads(LOCATIONS.read_text(encoding="utf-8"))
            if row["gamedata_flag"].startswith("Clear_" + prefix)}


def links_into(objects: dict[int, object]) -> dict[int, list[tuple[str, object]]]:
    into: dict[int, list[tuple[str, object]]] = {}
    for obj in objects.values():
        for link in (obj["LinksToObj"] if "LinksToObj" in obj else []):
            into.setdefault(int(link["DestUnitHashId"]), []).append((str(link["DefinitionName"]), obj))
    return into


def inside_row(obj, flag: str, number: int, owner: dict) -> dict:
    """The row of a chest inside a shrine or a Divine Beast (`owner`, its location's
    row): its logic is the owner's (the world reads its row of logic.csv)."""
    actor = str(obj["UnitConfigName"])
    kind = next((kind for prefix, kind in DUNGEON_KINDS.items() if actor.startswith(prefix)), None)
    if kind is None:
        raise ValueError(f"{flag}: a kind of chest not known")
    return {"number": number, "flag": flag, "kind": kind, "region": owner["region"],
            "dungeon": owner["name"], "name": None,
            "position": [round(float(v), 1) for v in obj["Translate"]],
            "heat": None, "requires": [], "no_progression": None}


def name_inside(rows: list[dict], entrance, place: str) -> None:
    """The names of one shrine's or beast's rows: "<place> - <kind> Chest", numbered
    from its entrance outwards when it has several of a kind."""
    groups: dict[str, list[tuple[float, int, dict]]] = {}
    for row in rows:
        distance = sum((float(a) - b) ** 2 for a, b in zip(entrance["Translate"], row["position"]))
        groups.setdefault(row["kind"], []).append((round(distance, 1), row["number"], row))
    for kind, members in groups.items():
        for index, (_distance, _number, row) in enumerate(sorted(members, key=lambda m: m[:2]), 1):
            row["name"] = f"{place} - {kind} Chest" + (f" {index}" if len(members) > 1 else "")


def only(objects: dict[int, object], actor: str):
    found = [obj for obj in objects.values() if str(obj["UnitConfigName"]) == actor]
    if len(found) != 1:
        raise ValueError(f"{len(found)} {actor} where one was expected")
    return found[0]


def shrine_rows(game, base: Path) -> list[dict]:
    """The rows of the base game's shrines' chests (Pack/DungeonNNN.pack), but
    those of a small key, which opens the way: named after their shrine. The
    DLC's shrines (its own Pack/) are numbered with them, not yet locations."""
    shrines = owners("Dungeon")
    units = {}
    for number in range(chests.SHRINES):
        dungeon = f"Dungeon{number:03d}"
        packed = unpack((base / f"Pack/{dungeon}.pack").read_bytes() if number < chests.BASE_SHRINES
                        else game.read_aoc(f"Pack/{dungeon}.pack"))
        archive = oead.Sarc(packed)             # kept: a member's data is a view of it
        units[dungeon] = bytes(archive.get_file(chests.shrine_unit(dungeon)).data)
    items = chests.shrine_numbering(units)
    if len(items) != chests.SHRINE_CHEST_COUNT:
        raise ValueError(f"{len(items)} shrine chests found, {chests.SHRINE_CHEST_COUNT} expected")
    out = []
    for dungeon, raw in units.items():
        if int(dungeon[len("Dungeon"):]) >= chests.BASE_SHRINES:
            continue
        objects = {int(obj["HashId"]): obj for obj in oead.byml.from_binary(unpack(raw))["Objs"]}
        into = links_into(objects)
        rows = []
        for obj in objects.values():
            if not str(obj["UnitConfigName"]).startswith(chests.DUNGEON_PREFIX):
                continue
            flag, parameters = chests.shrine_flag(obj), obj["!Parameters"]
            unknown = {definition for definition, _source in into.get(int(obj["HashId"]), [])}
            unknown = (unknown - set(SHRINE_LINKS)) | {str(name) for name in parameters.keys()
                                                       if str(name) not in SHRINE_PARAMETERS}
            if unknown or any(bool(parameters[name]) for name in ("IsInGround", "EnableRevival")):
                raise ValueError(f"{flag}: {sorted(unknown) or 'buried or coming back'}, not known")
            if str(parameters["DropActor"]) != SHRINE_KEY:
                rows.append(inside_row(obj, flag, int(items[flag].rsplit("_", 1)[1]), shrines[dungeon]))
        name_inside(rows, only(objects, ENTRANCE), plain(shrines[dungeon]["name"]))
        out += rows
    return out


def beast_rows(game) -> list[dict]:
    """The rows of the Divine Beasts' chests that have a flag (the DLC's
    Pack/RemainsXXX.pack), named after their beast ("Vah Ruta") and sent with it."""
    beasts = owners("Remains")
    units = {}
    for beast in chests.BEASTS:
        archive = oead.Sarc(unpack(game.read_aoc(f"Pack/{beast}.pack")))
        units[beast] = bytes(archive.get_file(chests.beast_units(beast)[0]).data)
    items = chests.beast_numbering(units)
    if len(items) != chests.BEAST_CHEST_COUNT:
        raise ValueError(f"{len(items)} Divine Beast chests found, {chests.BEAST_CHEST_COUNT} expected")
    out = []
    for beast, raw in units.items():
        objects = {int(obj["HashId"]): obj for obj in oead.byml.from_binary(unpack(raw))["Objs"]}
        into = links_into(objects)
        rows = []
        for obj in objects.values():
            if not str(obj["UnitConfigName"]).startswith(chests.DUNGEON_PREFIX):
                continue
            flag, parameters = chests.beast_flag(obj), obj["!Parameters"]
            links = into.get(int(obj["HashId"]), [])
            unknown = ({definition for definition, _source in links} - set(BEAST_LINKS)) | {
                str(name) for name in parameters.keys() if str(name) not in SHRINE_PARAMETERS}
            for definition, source in links:
                saved = str(source["!Parameters"]["SaveFlag"]) if "!Parameters" in source \
                    and "SaveFlag" in source["!Parameters"] else ""
                if definition == "Delete" and not (saved.startswith(BALLAD[0]) and saved.endswith(BALLAD[1])):
                    unknown.add(f"Delete by {saved or source['UnitConfigName']}")
                if definition == "Create":
                    flags, actors, negated = creation(source, into)
                    if negated or not (flags | actors) or not (flags | actors) <= BEAST_CREATING:
                        unknown.add(f"Create by {sorted(flags | actors)}")
            if unknown or any(bool(parameters[name]) for name in ("IsInGround", "EnableRevival")):
                raise ValueError(f"{flag}: {sorted(unknown) or 'buried or coming back'}, not known")
            row = inside_row(obj, flag, int(items[flag].rsplit("_", 1)[1]), beasts[beast])
            rows.append({**row, "sent_with": beasts[beast]["name"]})
        name_inside(rows, only(objects, BEAST_ENTRANCE), plain(beasts[beast]["name"].removeprefix("Divine Beast ")))
        out += rows
    return out


def inside(area, x: float, z: float) -> bool:
    """Whether (x, z) is in a box Area seen from above: its Scale is half its
    size, turned about the vertical by its Rotate."""
    turn = area["Rotate"]
    turn = float(turn[1]) if isinstance(turn, list) else float(turn)
    dx, dz = x - float(area["Translate"][0]), z - float(area["Translate"][2])
    across = dx * math.cos(turn) - dz * math.sin(turn)
    along = dx * math.sin(turn) + dz * math.cos(turn)
    return abs(across) <= float(area["Scale"][0]) and abs(along) <= float(area["Scale"][2])


def creation(tag, into: dict) -> tuple[set[str], set[str], bool]:
    """What a tag that creates a chest listens to, through other tags: (the saved
    flags of the tags, the actors that are not tags, whether one negates)."""
    flags, actors, seen, todo, negated = set(), set(), {int(tag["HashId"])}, [tag], False
    while todo:
        current = todo.pop()
        negated |= str(current["UnitConfigName"]).startswith(NEGATING)
        parameters = current["!Parameters"] if "!Parameters" in current else {}
        if "SaveFlag" in parameters and str(parameters["SaveFlag"]):
            flags.add(str(parameters["SaveFlag"]))
        for _definition, source in into.get(int(current["HashId"]), ()):
            if int(source["HashId"]) in seen:
                continue
            seen.add(int(source["HashId"]))
            if str(source["UnitConfigName"]).startswith(TAGS):
                todo.append(source)
            else:
                actors.add(str(source["UnitConfigName"]))
    return flags, actors, negated


def rule(table: dict, name: str, chest: str):
    """What `table` (CREATING_FLAGS, CREATING_ACTORS) says of `name`, by its start."""
    for start, ask in table.items():
        if name.startswith(start):
            return ask
    raise ValueError(f"{chest}: created by {name}, which the logic does not know")


def rows(game, base: Path, master: bool = False) -> list[dict]:
    """The chests' rows, from the update's Bootup.pack and the DLC's map units,
    then the shrines' (shrine_rows, `base`: the base game's content/) and the
    Divine Beasts' (beast_rows); with `master`, the Master Mode chests' only."""
    content = game.content
    bootup = oead.Sarc(unpack((content / "Pack/Bootup.pack").read_bytes()))
    heat = burning(bootup)
    towers = map_towers(content)
    named = area_regions(towers)
    maps = {name: game.read_aoc(chests.unit(name))
            for name in {**chests.MAP_HASHES, **(chests.MASTER_MAP_HASHES if master else {})}}
    items = chests.master_numbering(maps) if master else chests.numbering(maps)
    chest_of = chests.is_master_chest if master else chests.is_chest
    objects, into = {}, {}
    for raw in maps.values():
        for obj in oead.byml.from_binary(unpack(raw))["Objs"]:
            objects[int(obj["HashId"])] = obj
    for obj in objects.values():
        for link in (obj["LinksToObj"] if "LinksToObj" in obj else []):
            into.setdefault(int(link["DestUnitHashId"]), []).append((str(link["DefinitionName"]), obj))
    breakables = [obj for obj in objects.values() if str(obj["UnitConfigName"]).startswith(BREAKABLE[:2])]
    out = []
    for obj in objects.values():
        if not chest_of(obj):
            continue
        flag = chests.flag(obj)
        links = into.get(int(obj["HashId"]), [])
        flags, actors, negated = set(), set(), False
        for definition, source in links:
            if definition == "Create":
                created = creation(source, into)
                if not (created[0] or created[1]):
                    raise ValueError(f"{flag}: created by nothing the map names")
                flags, actors, negated = flags | created[0], actors | created[1], negated or created[2]
        if flag in INACCESSIBLE or negated or any(definition == "Delete" for definition, _source in links) \
                or any(name.startswith(COLLABORATION) for name in flags):
            continue
        parameters = obj["!Parameters"]
        x, y, z = (float(v) for v in obj["Translate"])
        below = [str(objects[int(link["DestUnitHashId"])]["UnitConfigName"])
                 for link in (obj["LinksToObj"] if "LinksToObj" in obj else [])
                 if str(link["DefinitionName"]) == "StackLink" and int(link["DestUnitHashId"]) in objects]
        kind = label(obj, parameters)
        asks = [rule(CREATING_FLAGS, name, flag) for name in flags] + \
               [rule(CREATING_ACTORS, name, flag) for name in actors]
        requires = {name for ask in asks if isinstance(ask, tuple) for name in ask}
        requires |= {ask for ask in asks if ask == BOMBS}
        if str(obj["UnitConfigName"]).startswith("TBox_Field_Iron") or kind == "Buried" \
                or any(name.startswith("FldObj_PushRockIron") for name in below):
            requires.add("Magnesis")
        if "Obj_RockCover" in below or any(
                abs(float(other["Translate"][0]) - x) < NEAR[0] and abs(float(other["Translate"][2]) - z) < NEAR[0]
                and abs(float(other["Translate"][1]) - y) < NEAR[1] for other in breakables):
            requires.add(BOMBS)
        requires |= {item for area, item in GUARDED.items() if inside(objects[area], x, z)}
        frozen = any(definition == "Freeze" or str(source["UnitConfigName"]).startswith("IceWall")
                     for definition, source in links)
        reason = ("quest" if kind == "EX" and "HasAoCVer1" not in flags or "quest" in asks else
                  "ice" if frozen else
                  "fight" if "fight" in asks else
                  "spawned" if "spawned" in asks else
                  "rock" if any(name.startswith("FldObj_PushRock_") for name in below) else None)
        number = int(items[flag].rsplit("_", 1)[1])
        region = named[towers.at(x, z)]
        out.append({"number": number, "flag": flag, "kind": (MASTER_KIND if master else "") + kind,
                    "region": region,
                    "name": None,                       # name_chests
                    "position": [round(x, 1), round(y, 1), round(z, 1)],
                    "heat": heat(x, z),
                    "requires": sorted(requires), "no_progression": reason})
    name_chests(out, places(game, bootup), lambda x, z: named[towers.at(x, z)])
    if master:
        return sorted(out, key=lambda row: row["number"])
    return sorted(out + shrine_rows(game, base) + beast_rows(game), key=lambda row: row["number"])


def encode(data: list[dict]) -> str:
    return "[\n" + ",\n".join(json.dumps(row, ensure_ascii=False) for row in data) + "\n]\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare, write nothing")
    args = parser.parse_args()
    from tools import cemu_profile
    from tools.build_resources_from_source import game_files
    game = game_files(cemu_profile.update() / "content")
    with game.active():
        texts = {OUTPUT: encode(rows(game, base_content())), MASTER_OUTPUT: encode(rows(game, None, master=True))}
    if args.check:
        same = {output: output.is_file() and output.read_bytes().decode("utf-8") == text
                for output, text in texts.items()}
        for output, matches in same.items():
            print(f"{output.name} " + ("matches the game" if matches else "differs from the game"))
        raise SystemExit(0 if all(same.values()) else 1)
    for output, text in texts.items():
        output.write_bytes(text.encode("utf-8"))
        print(f"{output.relative_to(ROOT)}: {text.count(chr(10)) - 2} chests")


if __name__ == "__main__":
    main()

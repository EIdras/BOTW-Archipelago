"""What reaching a field chest takes, read from the game's data (tools/build_extra_locations.py).

  * Under water: the terrain's water (Terrain/A/MainField.tscb, the tiles' index in the
    base game; <tile>.water.extm.sstera in the update: 64 x 64 cells of 8 bytes, a
    little-endian u16 height of 800 m full scale, the last byte 1 where the cell holds
    water). The finest tile with water at the chest's place gives the surface; a metal
    chest 0.3 to 20 m below it is pulled out with Magnesis. Checked on the Great
    Plateau: the two metal chests of the Gatepost Town Ruins' pond, 3 m down. A stone
    or wooden chest below a surface, or one deeper than 20 m, is in a cave under a
    lake: no requirement, on the list to check (UNCERTAIN).
  * Buried (IsInGround): Magnesis, as before.
  * Behind a cracked wall or under breakable rocks or a rock cover: the chest created
    when the wall or rocks break (a Create link through tags from WallCrack,
    Obj_RockBroken_*), or one of those within NEAR, or the cover stacked on it:
    Remote Bombs (the user's choice: a hammer is a sequence break).
  * Under an iron boulder (StackLink to FldObj_PushRockIron_*): Magnesis; under a stone
    one (FldObj_PushRock_*): Stasis or Remote Bombs. Also when the boulder is the actor an
    ActorObserverTag watches, whose tags release the chest or an invisible wall around it
    (AirWall within WALL): the Great Plateau's chest under a boulder, sealed by an
    AirWallForE3 until the boulder moves. Another observed actor: on the list to check.
  * In ice (an IceWall referring to it): nothing, fire is found everywhere (the user's choice).
  * Created by a saved flag (FLAGS): its requirement, or never drawn (NEVER), or on the
    list to check.
  * Created when enemies are beaten (a camp's, a castle guard's) or a dog is fed:
    nothing, noted. A camp's chest (TBox_Field_Enemy) stays shut until its camp is
    cleared: nothing, noted.
  * Never drawn (the user's choice): the DLC's EX Treasure chests
    (TBox_Field_*_Aoc*: shown only once their EX quest is started, which the logic
    cannot follow); a chest created by a quest flag the logic does not follow, or by
    a condition the data does not name.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import struct

import oead

from botw_patch.resources import unpack

BOMB = "Progressive Remote Bomb"
# A stone boulder (FldObj_PushRock_*) over a chest: Stasis launches it, a bomb blows it off.
BOULDER = "Progressive Stasis/Progressive Remote Bomb"
WALL = 6.0                  # metres from the chest an invisible wall sealing it stands within
# The objects observed before a chest or its wall is released, other than boulders: for the report.
OBSERVED: list[tuple[str, object]] = []
NEAR = 2.5                  # metres, on the ground's plane; 3 m up or down
SHALLOW = (0.3, 20.0)       # metres below the surface a metal chest is fished out from
TAGS = ("LinkTag", "SwitchTimeLag", "EventTag", "AreaCulling")
BREAKABLE = ("WallCrack", "Obj_RockBroken_", "Obj_RockCover")
# The saved flags that create chests (the first parts of their names): (runes, extra, note).
# extra "All Shrines": every shrine cleared (botw_world/catalog.py ALL_SHRINES).
FLAGS = {
    "AoC_HardMode": ("", "", ""),                                   # master_mode
    "HasAoCVer1": ("", "", "the DLC's"),
    "CompleteDungeon_Activated": ("", "All Shrines", "once all 120 shrines are cleared"),
    "Wind_Relic": ("", "Freed - Divine Beast Vah Medoh", "once Vah Medoh is freed"),
    "Fire_Relic": ("", "Freed - Divine Beast Vah Rudania", "once Vah Rudania is freed"),
    "AssassinBoss_TreasureBoxCreate": ("Magnesis", "", "once Master Kohga is defeated (Magnesis)"),
    "HatenoMini_GoatThief": ("", "", "a side quest's reward"),
}
# Never drawn: a chest the Wii U game cannot show.
NEVER = {"CollaborationShootingStar_Xenoblade2": "the Xenoblade Chronicles 2 collaboration (Switch only)"}
# Never drawn: what makes a chest appear that the logic cannot follow.
EX_TREASURE = "a DLC EX Treasure chest, shown only once its EX quest is started"


class Water:
    """The terrain's water surface at a point of the MainField."""

    def __init__(self, base: Path, update: Path):
        data = (base / "Terrain/A/MainField.tscb").read_bytes()
        table = 0x30 + struct.unpack(">I", data[0x30:0x34])[0]
        count = struct.unpack(">I", data[0x1C:0x20])[0]
        folder = update / "Terrain/A/MainField"
        tiles = {p.name.split(".")[0] for p in folder.glob("*.water.extm.sstera")}
        self.folder, self.areas, self.cache = folder, [], {}
        for index in range(count):
            at = table + 4 * index
            offset = at + struct.unpack(">I", data[at:at + 4])[0]
            x, z, size = struct.unpack(">3f", data[offset:offset + 12])
            name_at = offset + 32 + struct.unpack(">I", data[offset + 32:offset + 36])[0]
            name = data[name_at:data.index(b"\0", name_at)].decode()
            if name in tiles:
                self.areas.append((size, x * 500, z * 500, size * 500, name))
        self.areas.sort()

    def grid(self, name: str) -> bytes:
        if name not in self.cache:
            archive = oead.Sarc(unpack((self.folder / f"{name}.water.extm.sstera").read_bytes()))
            self.cache[name] = bytes(next(iter(archive.get_files())).data)
        return self.cache[name]

    def surface(self, x: float, z: float) -> float | None:
        """The water's height at (x, z), from the finest tile there; None: no water."""
        for _size, ax, az, side, name in self.areas:
            if abs(x - ax) <= side / 2 and abs(z - az) <= side / 2:
                column = min(63, int((x - (ax - side / 2)) / side * 64))
                row = min(63, int((z - (az - side / 2)) / side * 64))
                at = 8 * (row * 64 + column)
                height, _fx, _fz, _material, wet = struct.unpack("<HHHBB", self.grid(name)[at:at + 8])
                return height / 65536 * 800 if wet else None
        return None


@dataclass
class Reach:
    runes: set[str] = field(default_factory=set)
    extra: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    uncertain: str = ""
    never: str = ""


def classify(chest, objects: list, into: dict, water: Water) -> Reach:
    """What the field chest `chest` (a map unit object) needs. objects: its map cell's;
    into: {HashId: [(link name, source object)]} of the cell."""
    actor = str(chest["UnitConfigName"])
    params = chest["!Parameters"] if "!Parameters" in chest else {}
    x, y, z = (float(v) for v in chest["Translate"])
    reach = Reach()
    if "_Aoc" in actor:
        reach.never = EX_TREASURE
    if actor == "TBox_Field_Enemy":
        reach.notes.append("shut until its camp is cleared")
    if "IsInGround" in params and bool(params["IsInGround"]):
        reach.runes.add("Magnesis")
    surface = water.surface(x, z)
    if surface is not None and surface - y > SHALLOW[0]:
        depth = surface - y
        if "Iron" in actor and depth < SHALLOW[1]:
            reach.runes.add("Magnesis")
            reach.notes.append("under water")
        else:
            reach.uncertain = f"{depth:.0f} m below a water surface: a cave under water, or in the water?"
    # Created by something breaking, or by a saved flag.
    creators = [source for definition, source in into.get(int(chest["HashId"]), ()) if definition == "Create"]
    for tag in creators:
        fed = feeders(tag, into)
        for name in fed:
            if name.startswith(BREAKABLE):
                reach.runes.add(BOMB)
                reach.notes.append("behind a cracked wall" if name == "WallCrack" else "under rocks")
            elif name.startswith("Animal_Dog"):
                reach.notes.append("once its dog is fed")
            elif name.startswith("Enemy_"):
                reach.notes.append("once its guards are beaten")
        saved = str(tag["!Parameters"]["SaveFlag"]) if "!Parameters" in tag and "SaveFlag" in tag["!Parameters"] else ""
        if saved:
            family = next((key for key in (*FLAGS, *NEVER) if saved.startswith(key)), None)
            if family in NEVER:
                reach.never = NEVER[family]
            elif family:
                runes, extra, note = FLAGS[family]
                reach.runes.update(filter(None, runes.split("|")))
                reach.extra += [extra] if extra else []
                reach.notes += [note] if note else []
            elif not fed:
                reach.never = f"appears once the game's flag {saved} is set, by a side quest the logic does not follow"
        elif not fed:
            reach.never = "appears under a condition the game's data does not name"
    # On it or around it.
    for link in (chest["LinksToObj"] if "LinksToObj" in chest else []):
        target = next((o for o in objects if int(o["HashId"]) == int(link["DestUnitHashId"])), None)
        name = str(target["UnitConfigName"]) if target is not None else ""
        if str(link["DefinitionName"]) == "StackLink":
            if name.startswith("Obj_RockCover"):
                reach.runes.add(BOMB)
                reach.notes.append("under a rock cover")
            elif name.startswith("FldObj_PushRockIron"):
                reach.runes.add("Magnesis")
                reach.notes.append("under an iron boulder")
            elif name.startswith("FldObj_PushRock"):
                reach.runes.add(BOULDER)
                reach.notes.append("under a boulder")
    # Released when an observed object moves: an ActorObserverTag feeding the tags that
    # let the chest (or an invisible wall around it) be (AirWall, ForbidAttention...).
    walls = [o for o in objects if str(o["UnitConfigName"]).startswith("AirWall")
             and abs(float(o["Translate"][0]) - x) < WALL and abs(float(o["Translate"][2]) - z) < WALL]
    for target in [chest, *walls]:
        for _definition, source in into.get(int(target["HashId"]), ()):
            for observed in observers(source, into):
                if observed.startswith("FldObj_PushRockIron"):
                    reach.runes.add("Magnesis")
                    reach.notes.append("under an iron boulder")
                elif observed.startswith("FldObj_PushRock"):
                    reach.runes.add(BOULDER)
                    reach.notes.append("under a boulder")
                else:
                    OBSERVED.append((observed, reach))
                    reach.uncertain = f"released once {observed} moves: by what?"
    for other in objects:
        name = str(other["UnitConfigName"])
        if other is chest or not name.startswith(("WallCrack", "Obj_RockBroken_", "FldObj_PushRock")):
            continue
        ox, oy, oz = (float(v) for v in other["Translate"])
        if not (abs(ox - x) < NEAR and abs(oz - z) < NEAR and abs(oy - y) < 3):
            continue
        if name.startswith("FldObj_PushRockIron"):
            if oy >= y - 0.5:                       # on it, not beside it below
                reach.runes.add("Magnesis")
                reach.notes.append("under an iron boulder")
        elif name.startswith("FldObj_PushRock"):
            if oy >= y - 0.5:
                reach.runes.add(BOULDER)
                reach.notes.append("under a boulder")
        else:
            reach.runes.add(BOMB)
            reach.notes.append("behind a cracked wall" if name == "WallCrack" else "under rocks")
    if any(str(source["UnitConfigName"]).startswith("IceWall") for _d, source in into.get(int(chest["HashId"]), ())):
        reach.notes.append("in ice")
    reach.notes = list(dict.fromkeys(reach.notes))
    return reach


def observers(tag, into: dict, depth: int = 0, seen: set | None = None) -> set[str]:
    """The actors an ActorObserverTag feeding `tag` (through other tags) watches (its ActorName)."""
    seen = seen if seen is not None else set()
    found = set()
    if int(tag["HashId"]) in seen or not str(tag["UnitConfigName"]).startswith(TAGS + ("ActorObserverTag",)):
        return found
    seen.add(int(tag["HashId"]))
    name = str(tag["UnitConfigName"])
    if name == "ActorObserverTag":
        params = tag["!Parameters"] if "!Parameters" in tag else {}
        if "ActorName" in params:
            found.add(str(params["ActorName"]))
        return found
    if depth < 4:
        for _definition, source in into.get(int(tag["HashId"]), ()):
            found |= observers(source, into, depth + 1, seen)
    return found


def feeders(tag, into: dict, depth: int = 0, seen: set | None = None) -> set[str]:
    """The actors (not tags) that feed a tag, through other tags."""
    seen = seen if seen is not None else set()
    found = set()
    for _definition, source in into.get(int(tag["HashId"]), ()):
        if int(source["HashId"]) in seen:
            continue
        seen.add(int(source["HashId"]))
        name = str(source["UnitConfigName"])
        if name.startswith(TAGS):
            if depth < 4:
                found |= feeders(source, into, depth + 1, seen)
        else:
            found.add(name)
    return found


def links_into(objects: list) -> dict:
    """{HashId: [(link name, source object)]} of a map cell."""
    into: dict[int, list] = {}
    for obj in objects:
        for link in (obj["LinksToObj"] if "LinksToObj" in obj else []):
            into.setdefault(int(link["DestUnitHashId"]), []).append((str(link["DefinitionName"]), obj))
    return into


def distance(a, b) -> float:
    return math.dist(a, b)

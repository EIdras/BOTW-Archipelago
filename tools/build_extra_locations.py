"""The chests and bosses of world schema 6, from the game's map units.

    venv\\Scripts\\python tools\\build_extra_locations.py --content <update content> --base <base content>
        --aoc <DLC content/0010> [--write]

Three kinds of location, each tracked by the saved bool the game sets for it
(MakeActorFlag: <map>_<actor>_<HashId>), each kind behind an option of its own
(botw_world/options.py):
  * Shrine Chest: the treasure chests (TBox_*) of the 120 shrines, in the
    shrines' own packs (Pack/DungeonNNN.pack, Map/CDungeon/DungeonNNN/
    DungeonNNN_Static.smubin; flag CDungeon_<actor>_<HashId>). A chest holding
    its shrine's small key (KeySmall) is left out: its key opens the way. The
    contents of the chests a seed draws are replaced (botw_patch/shrine_chests.py).
    Region, position and logic are the shrine's: what clears it reaches its chests.
  * Chest: the treasure chests of the Great Plateau and Hyrule (TBox_Field_*,
    flag MainField_<actor>_<HashId>), check-only: their contents stay. The
    gambling chests (TBox_Field_Gamble) keep no saved flag: left out.
  * Boss: the Hinoxes, Stone Taluses and Moldugas of the field (Enemy_Giant_*,
    Enemy_Golem_* but the Pebblits, Enemy_Sandworm; flag
    MainField_IsDefeat_<actor>_<HashId>), check-only.
A field location's region is the tower area at its position (tools/map_regions.py),
its climate "heat" where the area's climate is EldinClimateLv1 or Lv2
(Ecosystem/AreaData, the burning slopes of Death Mountain), and a buried chest
(IsInGround) asks for Magnesis. Names are stable: the map cell, then a number
in the cell by HashId.

Without --write, prints what it found; with it, appends the rows after the 220
of world schema 5 (data/locations_master.csv, botw_world/data/locations.json,
botw_world/data/logic.csv, data/location_positions.json), replacing any rows it
wrote before.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

from botw_patch.resources import unpack  # noqa: E402
from tools.map_regions import Beco, area_regions  # noqa: E402

MASTER = ROOT / "data/locations_master.csv"
LOCATIONS = ROOT / "botw_world/data/locations.json"
LOGIC = ROOT / "botw_world/data/logic.csv"
POSITIONS = ROOT / "data/location_positions.json"
LANDMARKS = ROOT / "data/chest_landmarks.json"
SCHEMA_5_ROWS = 220
SHRINES = 120
HOT = ("EldinClimateLv1", "EldinClimateLv2")
BOSSES = {
    "Enemy_Giant_Junior": "Hinox", "Enemy_Giant_Middle": "Blue Hinox", "Enemy_Giant_Senior": "Black Hinox",
    "Enemy_Giant_Bone": "Stalnox", "Enemy_Golem_Junior": "Stone Talus",
    "Enemy_Golem_Middle": "Luminous Stone Talus", "Enemy_Golem_Senior": "Rare Stone Talus",
    "Enemy_Golem_Fire": "Igneo Talus", "Enemy_Golem_Ice": "Frost Talus", "Enemy_Sandworm": "Molduga",
    "Enemy_SandwormR": "Molduga",
}
CATEGORY_ORDER = ("Shrine Chest", "Chest", "Boss")


def signed(value: int) -> int:
    return value - (1 << 32) if value >= 1 << 31 else value


def flag_hash(flag: str) -> int:
    return signed(zlib.crc32(flag.encode()))


def xz(translate) -> list[float]:
    return [round(float(translate[0]), 1), round(float(translate[2]), 1)]


def boss_kind(actor: str) -> str | None:
    """The boss an actor is, by its longest known prefix (Enemy_Golem_Fire_R is an Igneo Talus)."""
    for prefix in sorted(BOSSES, key=len, reverse=True):
        if actor == prefix or actor.startswith(prefix + "_"):
            rest = actor[len(prefix):]
            # Parts of a Talus (its arms) and the Pebblits are no bosses.
            if "Arm" in rest or "Little" in actor:
                return None
            return BOSSES[prefix]
    return None


def read_bootup(content: Path):
    boot = oead.Sarc((content / "Pack/Bootup.pack").read_bytes())
    def beco(name):
        return Beco(unpack(bytes(boot.get_file(name).data)))
    areas = oead.byml.from_binary(unpack(bytes(boot.get_file("Ecosystem/AreaData.sbyml").data)))
    climate = {int(area["AreaNumber"]): str(area["Climate"]) for area in areas}
    return beco("Ecosystem/MapTower.sbeco"), beco("Ecosystem/FieldMapArea.sbeco"), climate


def shrine_pack(content: Path, base: Path, number: int) -> bytes:
    for root in (content, base):
        path = root / f"Pack/Dungeon{number:03d}.pack"
        if path.exists():
            return path.read_bytes()
    raise FileNotFoundError(f"Dungeon{number:03d}.pack")


def shrine_chests(content: Path, base: Path, shrines: dict[str, dict]) -> list[dict]:
    """Every shrine chest but those of a small key, by shrine then HashId."""
    rows = []
    for number in range(SHRINES):
        dungeon = f"Dungeon{number:03d}"
        shrine = shrines[dungeon]
        sarc = oead.Sarc(unpack(shrine_pack(content, base, number)))
        member = f"Map/CDungeon/{dungeon}/{dungeon}_Static.smubin"
        objects = oead.byml.from_binary(unpack(bytes(sarc.get_file(member).data)))["Objs"]
        chests = sorted((o for o in objects if str(o["UnitConfigName"]).startswith("TBox_")),
                        key=lambda o: int(o["HashId"]))
        index = 0
        for obj in chests:
            drop = str(obj["!Parameters"]["DropActor"])
            if drop == "KeySmall":
                continue
            index += 1
            flag = f"CDungeon_{obj['UnitConfigName']}_{int(obj['HashId'])}"
            rows.append({"name": f"{shrine['name']} Chest {index}", "region": shrine["region"],
                         "category": "Shrine Chest", "gamedata_flag": flag,
                         "notes": f"{dungeon}, {drop}", "shrine": shrine["name"]})
    return rows


def field_locations(aoc: Path, towers: Beco, areas: Beco, climates: dict[int, str],
                    named: dict[int, str]) -> list[dict]:
    """The chests, then the bosses, of every map cell, in cell then HashId order."""
    chests, bosses = [], []
    cells = sorted(p.name for p in (aoc / "Map/MainField").iterdir() if p.is_dir() and "-" in p.name)
    for cell in cells:
        objects = []
        for kind in ("Static", "Dynamic"):
            path = aoc / f"Map/MainField/{cell}/{cell}_{kind}.smubin"
            objects += list(oead.byml.from_binary(unpack(path.read_bytes()))["Objs"])
        objects.sort(key=lambda o: int(o["HashId"]))
        counts: dict[str, int] = {}
        for obj in objects:
            actor = str(obj["UnitConfigName"])
            if actor.startswith("TBox_Field_") and "Gamble" not in actor:
                label, flag, out = "Chest", f"MainField_{actor}_{int(obj['HashId'])}", chests
            elif boss_kind(actor):
                label = boss_kind(actor)
                flag, out = f"MainField_IsDefeat_{actor}_{int(obj['HashId'])}", bosses
            else:
                continue
            x, z = xz(obj["Translate"])
            region = named[towers.at(x, z)]
            counts[label] = counts.get(label, 0) + 1
            params = obj["!Parameters"] if "!Parameters" in obj else {}
            buried = label == "Chest" and "IsInGround" in params and bool(params["IsInGround"])
            out.append({"name": f"{label} {cell} #{counts[label]}", "region": region,
                        "category": "Chest" if label == "Chest" else "Boss", "gamedata_flag": flag,
                        "position": [x, z], "climate": "heat" if climates.get(areas.at(x, z)) in HOT else "none",
                        "runes": "Magnesis" if buried else "none",
                        "notes": f"{cell}, {actor}" + (", buried" if buried else "")})
    return chests + bosses


def build(content: Path, base: Path, aoc: Path) -> list[dict]:
    with MASTER.open(encoding="utf-8", newline="") as stream:
        master = list(csv.DictReader(stream))[:SCHEMA_5_ROWS]
    logic = {row["location"]: row for row in csv.DictReader(LOGIC.read_text(encoding="utf-8").splitlines())}
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    shrines = {row["notes"].split()[0].rstrip(","): row for row in master if "Shrine" in row["category"].split("|")}
    towers, areas, climates = read_bootup(content)
    named = area_regions(towers)
    rows = []
    for row in shrine_chests(content, base, shrines):
        shrine = logic[row["shrine"]]
        rows.append({**row, "position": positions[row["shrine"]], "climate": shrine["climate"],
                     "runes": shrine["runes"], "extra": shrine["extra"]})
    rows += field_locations(aoc, towers, areas, climates, named)
    hashes = {flag_hash(row["gamedata_flag"]) for row in rows}
    if len(hashes) != len(rows) or len({row["name"] for row in rows}) != len(rows):
        raise ValueError("duplicate flags or names")
    for row in rows:
        if row["name"].endswith(" Shrine") or row["name"].startswith("Divine Beast"):
            raise ValueError(f"{row['name']}: such a name counts for a goal")
    rows.sort(key=lambda row: CATEGORY_ORDER.index(row["category"]))
    return rows


def head(raw: bytes) -> tuple[list[str], str]:
    """The physical lines of a CSV's header and its schema-5 rows (a quoted field
    may hold a line break: records are counted by the csv reader), each keeping
    its own ending but the last; and the ending of that last row, which the new
    rows take (the files mix CRLF and LF)."""
    text = raw.decode("utf-8")
    reader = csv.reader(io.StringIO(text, newline=""))
    for _ in range(SCHEMA_5_ROWS + 1):
        next(reader)
    lines = text.split("\n")[:reader.line_num]
    newline = "\r\n" if lines[-1].endswith("\r") else "\n"
    lines[-1] = lines[-1].removesuffix("\r")
    return lines, newline


def append_rows(path: Path, rows: list[list[str]]) -> None:
    """The CSV's schema-5 rows, byte for byte, then `rows`."""
    lines, newline = head(path.read_bytes())
    out = io.StringIO()
    writer = csv.writer(out, lineterminator=newline)
    writer.writerows(rows)
    path.write_bytes(("\n".join(lines) + newline + out.getvalue()).encode("utf-8"))


def write(rows: list[dict]) -> None:
    append_rows(MASTER, [[row["name"], row["region"], row["category"], "", row["gamedata_flag"],
                          str(flag_hash(row["gamedata_flag"])), row["notes"]] for row in rows])

    world = json.loads(LOCATIONS.read_text(encoding="utf-8"))[:SCHEMA_5_ROWS]
    for index, row in enumerate(rows, start=SCHEMA_5_ROWS + 1):
        world.append({"name": row["name"], "region": row["region"], "category": row["category"],
                      "requires": "", "gamedata_flag": row["gamedata_flag"],
                      "flag_hash": str(flag_hash(row["gamedata_flag"])), "notes": row["notes"], "id": index})
    raw = LOCATIONS.read_bytes()
    text = json.dumps(world, ensure_ascii=False, indent=2) + "\n"
    LOCATIONS.write_bytes(text.replace("\n", "\r\n").encode() if b"\r\n" in raw else text.encode())

    append_rows(LOGIC, [[row["name"], row["region"], row["category"], row["climate"], row["runes"],
                         row.get("extra", ""), "no", row["notes"]] for row in rows])

    raw = POSITIONS.read_bytes()
    positions = json.loads(raw)
    names = [row["name"] for row in json.loads(LOCATIONS.read_text(encoding="utf-8"))]
    kept = {name: positions[name] for name in names[:SCHEMA_5_ROWS] if name in positions}
    kept.update({row["name"]: row["position"] for row in rows})
    # One location a line, as the file is kept.
    body = ",\n".join(f"  {json.dumps(name, ensure_ascii=False)}: [{x}, {z}]" for name, (x, z) in kept.items())
    text = "{\n" + body + "\n}\n"
    POSITIONS.write_bytes(text.replace("\n", "\r\n").encode() if b"\r\n" in raw else text.encode())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--content", type=Path, required=True, help="the update's content folder")
    parser.add_argument("--base", type=Path, required=True, help="the base game's content folder")
    parser.add_argument("--aoc", type=Path, required=True, help="the DLC's content/0010 folder")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    rows = build(args.content, args.base, args.aoc)
    for category in CATEGORY_ORDER:
        print(category, sum(row["category"] == category for row in rows))
    if args.write:
        write(rows)
        text = json.dumps(landmarks(args.content, args.aoc), ensure_ascii=False, indent=1) + "\n"
        LANDMARKS.write_bytes(text.encode("utf-8"))
    return 0


def landmarks(content: Path, aoc: Path) -> dict:
    """The tracker's landmarks (tools/build_poptracker.py, its overview map): the places the
    game's map names, LocationPointer (Hebra Great Skeleton...) and the LocationMarker
    of no shrine nor tower (villages, stables...), named in English
    (StaticMsg/LocationMarker.msbt); and the landmark of each field chest, the nearest.
    {"places": {name: [x, z]}, "chests": {chest: name}}."""
    from botw_patch.shop_items import read_labels
    static = oead.byml.from_binary(unpack((aoc / "Map/MainField/Static.smubin").read_bytes()))
    boot = oead.Sarc((content / "Pack/Bootup_USen.pack").read_bytes())
    messages = oead.Sarc(unpack(bytes(boot.get_file("Message/Msg_USen.product.ssarc").data)))
    labels = read_labels(bytes(messages.get_file("StaticMsg/LocationMarker.msbt").data))
    places: dict[str, list[float]] = {}
    for kind in ("LocationPointer", "LocationMarker"):
        for marker in static[kind]:
            message = str(marker["MessageID"]) if "MessageID" in marker else ""
            name = labels.get(message, "").strip("\0").strip()
            if not name or message.startswith(("Dungeon", "Tower", "Remains")):
                continue
            translate = marker["Translate"]
            where = [round(float(translate["X"]), 1), round(float(translate["Z"]), 1)]
            places.setdefault(name, where)      # a name twice: its first place
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    rows = json.loads(LOCATIONS.read_text(encoding="utf-8"))
    chests = {}
    for row in rows:
        if row["category"] == "Chest":
            x, z = positions[row["name"]]
            chests[row["name"]] = min(places, key=lambda name: (places[name][0] - x) ** 2 + (places[name][1] - z) ** 2)
    used = set(chests.values())
    return {"places": {name: where for name, where in sorted(places.items()) if name in used}, "chests": chests}


if __name__ == "__main__":
    raise SystemExit(main())

"""The shared shrines: the base game's shrines, each chest that is a location
holding its Archipelago item (the world's shrine_chest_items).

A shrine's chests are in its Pack/DungeonNNN.pack, with everything else of the
shrine (models, collision, navigation): the game loads a changed one only when
a graphic pack ships the whole pack, about 7 MB a shrine, 954 MB for the 120
of the base game. Their items, AP_Chest_<nnnn> (botw_patch/chests.py), are the
same in every seed: only their names change, and those are in the seed's pack.
So these packs are built once, from the player's own base game (a folder: a
.wua or .wud is not read), into a graphic pack of their own that every seed
enables next to its pack, and built again only when what they hold or the
game's copy changes (key()): a few seconds, then nothing but the disk space.

Each chest of chests.json among the shrines' gets its item as DropActor, and
nothing else of the shrine changes; its static unit must still fit its entry in
the resource size table the game loads (the seed pack's).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import oead

from botw_patch import chests
from botw_patch.resources import canonical, unpack

PREFIX = "AP_Shrines_"
RECORD = "shrines.json"
FORMAT = 1
RULES = """[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = Archipelago Shrine Chests
path = "The Legend of Zelda: Breath of the Wild/Archipelago/Shrine Chests"
description = The shrines whose chests hold their Archipelago items, shared by every seed
version = 7
fsPriority = 1999
"""


def listed() -> dict[str, int]:
    """{flag: number} of the shrines' chests that are locations."""
    first, last = chests.SHRINES_HELD
    rows = json.loads(chests.LOCATIONS.read_text(encoding="utf-8"))
    return {row["flag"]: row["number"] for row in rows if first <= row["number"] <= last}


def key(base: Path | None = None) -> str:
    """What the shrines hold: their chests' numbers, how an item is named, this
    file's code and, from the base game's content/ `base`, the size of each
    shrine's pack (another copy of the game, without hashing 954 MB)."""
    sizes = ([(base / shrine_pack(f"Dungeon{n:03d}")).stat().st_size for n in range(chests.BASE_SHRINES)]
             if base is not None else None)
    record = json.dumps({"format": FORMAT, "chests": sorted(listed().items()), "item": chests.actor(1),
                         "code": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "sizes": sizes},
                        sort_keys=True)
    return hashlib.sha256(record.encode("utf-8")).hexdigest()[:16]


def shrine_pack(dungeon: str) -> str:
    return f"Pack/{dungeon}.pack"


def changed_unit(raw: bytes, flags: dict[str, int]) -> tuple[bytes, list[str]]:
    """The static unit with each listed chest's DropActor its item; the flags given."""
    data = oead.byml.from_binary(unpack(raw))
    given = []
    for obj in data["Objs"]:
        if not str(obj["UnitConfigName"]).startswith(chests.DUNGEON_PREFIX):
            continue
        number = flags.get(chests.shrine_flag(obj))
        if number is not None:
            obj["!Parameters"]["DropActor"] = chests.actor(number)
            given.append(chests.shrine_flag(obj))
    body = bytes(oead.byml.to_binary(data, big_endian=True))
    return (bytes(oead.yaz0.compress(body)) if raw[:4] == b"Yaz0" else body), given


def generate(base: Path, table) -> dict[str, bytes]:
    """{path in the graphic pack: bytes}, from the base game's content/ `base`;
    `table` is the resource size table the game loads (rstb.ResourceSizeTable)."""
    flags = listed()
    files, given = {"rules.txt": RULES.encode("utf-8")}, []
    for number in range(chests.BASE_SHRINES):
        dungeon = f"Dungeon{number:03d}"
        source = (base / shrine_pack(dungeon)).read_bytes()
        archive = oead.Sarc(unpack(source))
        member = chests.shrine_unit(dungeon)
        new, flagged = changed_unit(bytes(archive.get_file(member).data), flags)
        if not flagged:
            continue
        size, entry = len(unpack(new)), table.get_size(canonical(member))
        if entry is None or size > entry:
            raise ValueError(f"{member}: {size} bytes for an entry of {entry}")
        writer = oead.SarcWriter.from_sarc(archive)
        writer.files[member] = new
        packed = bytes(writer.write()[1])
        files["content/" + shrine_pack(dungeon)] = (bytes(oead.yaz0.compress(packed))
                                                     if source[:4] == b"Yaz0" else packed)
        given += flagged
    if sorted(given) != sorted(flags):
        missing = sorted(set(flags) - set(given))
        raise ValueError(f"{len(given)} shrine chests found, {len(flags)} expected: {missing[:5]}")
    return files


def _intact(folder: Path, wanted: str) -> bool:
    try:
        record = json.loads((folder / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (record.get("key") == wanted and isinstance(record.get("files"), dict)
            and all((folder / name).is_file() and (folder / name).stat().st_size == size
                    for name, size in record["files"].items()))


def install(base: Path, table, graphic_packs: Path) -> Path:
    """The shared shrines' graphic pack under `graphic_packs`, built if it is
    missing or holds something else; the other versions are removed."""
    wanted = key(base)
    folder = graphic_packs / (PREFIX + wanted)
    if not _intact(folder, wanted):
        files = generate(base, table)
        building = folder.with_name(folder.name + ".building")
        shutil.rmtree(building, ignore_errors=True)
        for name, data in files.items():
            path = building / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (building / RECORD).write_text(json.dumps(
            {"key": wanted, "files": {name: len(data) for name, data in files.items()}}, indent=1), encoding="utf-8")
        shutil.rmtree(folder, ignore_errors=True)
        building.rename(folder)
    for other in graphic_packs.glob(PREFIX + "*"):
        if other != folder and other.is_dir():
            shutil.rmtree(other, ignore_errors=True)
    return folder

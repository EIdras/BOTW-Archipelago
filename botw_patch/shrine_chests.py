"""The shrine chests a seed draws (the world's shrine_chests): their treasure replaced.

A shrine chest is an Archipelago location (tools/build_extra_locations.py): the
client sends it once the game sets its saved flag, CDungeon_<actor>_<HashId>, as
the chest opens. Its own treasure would then come on top of the Archipelago item:
in the shrine's map unit (Pack/DungeonNNN.pack, Map/CDungeon/DungeonNNN/
DungeonNNN_Static.smubin), the chest's DropActor, what it gives, becomes a green
rupee (PutRupee). Read in the game's files: every shrine chest names its
treasure there, in DropActor (174 of them, the 12 holding a small key apart).

A green rupee rather than an Archipelago item of its own: an item made for AP
goes into the pouch, and only a flow can take it out again (the shops' purchase
record, botw_patch/shop_items.py), while the chest's opening is the game's own,
with no flow of ours. A rupee needs no cleaning. Not yet seen in play.

Only for seeds that draw shrine chests, so that the others keep their identity.
"""
from __future__ import annotations

import json
from pathlib import Path

import oead

from botw_patch.resources import unpack

ROOT = Path(__file__).resolve().parents[1]
LOCATIONS = ROOT / "botw_world/data/locations.json"
CATEGORY = "Shrine Chest"
REPLACEMENT = "PutRupee"
SOURCE_FILES = ("botw_patch/shrine_chests.py", "botw_world/data/locations.json")


def chests() -> dict[int, dict]:
    """{location id: row} of every shrine chest."""
    rows = json.loads(LOCATIONS.read_text(encoding="utf-8"))
    return {row["id"]: row for row in rows if row["category"] == CATEGORY}


def drawn(status: dict | None) -> list[dict]:
    """The seed's shrine chests (slot_data extra_locations), by location id."""
    ids = set((status or {}).get("slot_data", {}).get("extra_locations", ()))
    return [row for location_id, row in sorted(chests().items()) if location_id in ids]


def enabled(status: dict | None) -> bool:
    return bool(drawn(status))


def dungeon(row: dict) -> str:
    """DungeonNNN, the shrine of a chest (its notes: "DungeonNNN, <treasure>")."""
    return row["notes"].split(",", 1)[0]


def treasure(row: dict) -> str:
    return row["notes"].split(",", 1)[1].strip()


def hash_id(row: dict) -> int:
    return int(row["gamedata_flag"].rsplit("_", 1)[1])


def member(name: str) -> str:
    return f"Map/CDungeon/{name}/{name}_Static.smubin"


def pack(name: str) -> str:
    return f"Pack/{name}.pack"


def base_content(update: Path) -> Path:
    """The base game's content/ beside the update's in Cemu's mlc01 folder
    (usr/title/0005000e/<title>/content -> usr/title/00050000/<title>/content): the
    shrines' packs are the base game's, the update has none."""
    update = Path(update).resolve()
    title, kind = update.parent, update.parent.parent
    base = kind.parent / "00050000" / title.name / "content"
    if kind.name.lower() != "0005000e" or not base.is_dir():
        raise FileNotFoundError(f"the shrine chests need the base game's files, beside the update in Cemu's "
                                f"mlc01 folder (looked for {base})")
    return base


def read_pack(game, name: str) -> bytes:
    """A shrine's pack as the game loads it: a graphic pack's, or the base game's."""
    if game.exists(name):
        return game.read(name)
    return (base_content(game.content) / name).read_bytes()


def patch_unit(raw: bytes, rows: list[dict]) -> tuple[bytes, list[dict]]:
    """One shrine's map unit with its drawn chests' DropActor replaced."""
    doc = oead.byml.from_binary(unpack(raw))
    by_hash = {int(o["HashId"]): o for o in doc["Objs"]}
    edits = []
    for row in rows:
        obj = by_hash.get(hash_id(row))
        flag = f"CDungeon_{obj['UnitConfigName']}_{hash_id(row)}" if obj is not None else None
        if flag != row["gamedata_flag"]:
            raise ValueError(f"{row['name']}: chest not found in {dungeon(row)}")
        params = obj["!Parameters"]
        if str(params["DropActor"]) != treasure(row):
            raise ValueError(f"{row['name']}: holds {params['DropActor']}, not {treasure(row)}")
        params["DropActor"] = REPLACEMENT
        edits.append({"chest": row["name"], "hash_id": hash_id(row), "from": treasure(row), "to": REPLACEMENT})
    out = bytes(oead.byml.to_binary(doc, big_endian=True, version=2))
    return (bytes(oead.yaz0.compress(out)) if raw[:4] == b"Yaz0" else out), edits


def stages(status: dict | None) -> list[tuple[str, dict]]:
    """(pack, {member: transform}) of each shrine holding a drawn chest."""
    by_shrine: dict[str, list[dict]] = {}
    for row in drawn(status):
        by_shrine.setdefault(dungeon(row), []).append(row)
    return [(pack(name), {member(name): (lambda raw, rows=rows: patch_unit(raw, rows))})
            for name, rows in sorted(by_shrine.items())]

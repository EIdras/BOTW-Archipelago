"""The shrine chests a seed draws (the world's shrine_chests): their treasure replaced.

A shrine chest is an Archipelago location (tools/build_extra_locations.py): the
client sends it once the game sets its saved flag, CDungeon_<actor>_<HashId>, as
the chest opens. Its own treasure would then come on top of the Archipelago item:
in the shrine's map unit (Pack/DungeonNNN.pack, Map/CDungeon/DungeonNNN/
DungeonNNN_Static.smubin), the chest's DropActor, what it gives, becomes a green
rupee of its own. Read in the game's files: every shrine chest names its
treasure there, in DropActor (174 of them, the 12 holding a small key apart).

A green rupee rather than an Archipelago item of its own: an item made for AP
goes into the pouch, and only a flow can take it out again (the shops' purchase
record, botw_patch/shop_items.py), while the chest's opening is the game's own,
with no flow of ours. A rupee goes to the purse: nothing to clean.

Each drawn chest has its own rupee, PutRupee_AP<location id>: PutRupee's actor
pack and ActorInfo entry cloned (its model, parameters and behaviour shared; the
name keeps the PutRupee prefix, should the game tell rupees by name), named in
ActorType/Item.msbt after what the chest holds: "<slot>'s <item>", the same
English text in every language, as the shop items. Not yet seen in play.

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
MODEL = "PutRupee"
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
MSBT = "ActorType/Item.msbt"
NAME_LIMIT = 30
# PutRupee's parameters, and the icon its clones name (UI/StockItem/Item_AP.sbitemico,
# in every pack: tools/build_resource_base_from_source.py).
PARAMS = "Rupee_Green"
ICON = "Item_AP"
SOURCE_FILES = ("botw_patch/shrine_chests.py", "botw_world/data/locations.json")


def actor(row: dict) -> str:
    """The green rupee of a drawn chest."""
    return f"{MODEL}_AP{row['id']:04d}"


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


def base_content(update: Path, launched=None) -> Path:
    """The base game's content/: the shrines' packs are the base game's, the
    update has none. Beside the update in Cemu's mlc01 folder
    (usr/title/0005000e/<title>/content -> usr/title/00050000/<title>/content),
    else where Cemu lists the game it launches: the launcher's profile copies
    only the update and the DLC into its own mlc01 (tools/cemu_profile.py), the
    base game stays in the player's game paths. `launched`: what Cemu launches
    (its U-King.rpx), found by tools/cemu_profile.game() when not given."""
    update = Path(update).resolve()
    title, kind = update.parent, update.parent.parent
    beside = kind.parent / "00050000" / title.name / "content"
    if kind.name.lower() == "0005000e" and beside.is_dir():
        return beside
    if launched is None:
        try:
            from tools import cemu_profile
            launched = cemu_profile.game()
        except Exception:  # noqa: BLE001 - no profile or no game listed: the message below
            launched = None
    listed = None
    if launched is not None and Path(launched).name.lower() == "u-king.rpx":
        listed = Path(launched).resolve().parent.parent / "content"
        if listed.is_dir():
            return listed
    where = f"looked for {beside}" + (f" and {listed}" if listed is not None else "")
    raise FileNotFoundError(
        "the shrine chests need the base game's files as a folder (code, content, meta): beside the "
        f"update in Cemu's mlc01 folder, or where Cemu lists the game; a .wud/.wua is not read ({where})")


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
        params["DropActor"] = actor(row)
        edits.append({"chest": row["name"], "hash_id": hash_id(row), "from": treasure(row), "to": actor(row)})
    out = bytes(oead.byml.to_binary(doc, big_endian=True, version=2))
    return (bytes(oead.yaz0.compress(out)) if raw[:4] == b"Yaz0" else out), edits


def stages(status: dict | None) -> list[tuple[str, dict]]:
    """(pack, {member: transform}) of each shrine holding a drawn chest."""
    by_shrine: dict[str, list[dict]] = {}
    for row in drawn(status):
        by_shrine.setdefault(dungeon(row), []).append(row)
    return [(pack(name), {member(name): (lambda raw, rows=rows: patch_unit(raw, rows))})
            for name, rows in sorted(by_shrine.items())]


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def texts(placement: dict) -> tuple[str, str]:
    """(name, description) of a chest's rupee: "<slot>'s <item>", then "You got
    <slot>'s <item>!" and its tier: important (progression), useful, or junk (filler,
    and a trap, which the shops too describe as an ordinary item)."""
    from botw_patch.shop_items import wrap_description
    from botw_patch.shops import PROGRESSION, TRAP, USEFUL
    player, item, flags = placement["recipient_name"], placement["item_name"], int(placement.get("flags", 0))
    tier = ("Seems like junk." if flags & TRAP else "Seems important." if flags & PROGRESSION
            else "Seems useful." if flags & USEFUL else "Seems like junk.")
    name = _short(f"{player}'s {item}", NAME_LIMIT)
    for item_limit, player_limit in ((80, 32), (40, 16), (24, 12)):
        body = f"You got {_short(player, player_limit)}'s {_short(item, item_limit)}! {tier}"
        try:
            return name, wrap_description(body)
        except ValueError:
            continue
    raise ValueError(f"description does not fit: {placement['location_name']}")


def items(status: dict) -> list:
    """The ApShopItem of each drawn chest's rupee (no price: not sold)."""
    from botw_patch.shop_items import ApShopItem
    placements = {row["location_id"]: row for row in status.get("placements", [])}
    out = []
    for row in drawn(status):
        placement = placements.get(row["id"])
        if placement is None:
            raise ValueError(f"shrine chest without an item: {row['name']}")
        out.append(ApShopItem(actor(row), None, *texts(placement), model_actor=MODEL))
    return out


def with_icon(pack: bytes, actor: str) -> bytes:
    """The cloned rupee's pack with parameters of its own (PutRupee's, Rupee_Green), whose
    Item.UseIconActorName is ICON: the icon its get window shows, the one AP logo of every
    pack, by reference (as the Gerudo jewelry names Obj_Head_024...), not a copy a chest.
    Seen in play: a rupee of its own, named otherwise, showed no icon."""
    archive = oead.Sarc(unpack(pack))
    writer = oead.SarcWriter.from_sarc(archive)
    link_name = f"Actor/ActorLink/{actor}.bxml"
    link = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(link_name).data))
    target = link.objects["LinkTarget"].params
    if str(target["GParamUser"].v) != PARAMS:
        raise ValueError(f"{actor}: unexpected parameters {target['GParamUser'].v}")
    target["GParamUser"] = oead.aamp.Parameter(actor)
    old = f"Actor/GeneralParamList/{PARAMS}.bgparamlist"
    params = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(old).data))
    params.objects["Item"].params["UseIconActorName"] = oead.aamp.Parameter(oead.FixedSafeString64(ICON))
    del writer.files[old]
    writer.files[f"Actor/GeneralParamList/{actor}.bgparamlist"] = bytes(params.to_binary())
    writer.files[link_name] = bytes(link.to_binary())
    return bytes(oead.yaz0.compress(bytes(writer.write()[1])))


def add_rupees(files: dict[str, bytes], game, status: dict) -> tuple[dict[str, bytes], list[dict]]:
    """The rupees' ActorInfo entries and actor packs, with their size table entries
    (PutRupee's), into `files`, which holds the size table."""
    import io
    import rstb
    from botw_patch.shop_items import add_declarations, clone_actor_pack
    files = dict(files)
    rupees = items(status)
    info = files[ACTOR_INFO] if ACTOR_INFO in files else game.read(ACTOR_INFO)
    files[ACTOR_INFO], detail = add_declarations(info, rupees)
    table = rstb.ResourceSizeTable(unpack(files[TABLE]), True)
    model = game.read(f"Actor/Pack/{MODEL}.sbactorpack")
    for rupee in rupees:
        cloned, _ = clone_actor_pack(model, MODEL, rupee.actor)
        files[f"Actor/Pack/{rupee.actor}.sbactorpack"] = with_icon(cloned, rupee.actor)
        for kind, ext in (("Actor/Pack", "bactorpack"), ("Actor/ActorLink", "bxml")):
            table.set_size(f"{kind}/{rupee.actor}.{ext}", table.get_size(f"{kind}/{MODEL}.{ext}"))
        table.set_size(f"Actor/GeneralParamList/{rupee.actor}.bgparamlist",
                       table.get_size(f"Actor/GeneralParamList/{PARAMS}.bgparamlist"))
    stream = io.BytesIO()
    table.write(stream, True)
    files[TABLE] = bytes(oead.yaz0.compress(stream.getvalue()))
    return files, [{"resource": ACTOR_INFO, "declarations": detail},
                   {"resource": "actors", "actors": [rupee.actor for rupee in rupees], "cloned_from": MODEL}]


def messages(status: dict, language: str) -> dict:
    """{member: transform} of Bootup_<language>.pack: the rupees' names."""
    from botw_patch.shop_items import add_item_texts
    rupees = items(status)

    def transform(raw):
        archive = oead.Sarc(unpack(raw))
        writer = oead.SarcWriter.from_sarc(archive)
        new, detail = add_item_texts(bytes(archive.get_file(MSBT).data), rupees)
        writer.files[MSBT] = new
        packed = bytes(writer.write()[1])
        return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), detail
    return {f"Message/Msg_{language}.product.ssarc": transform}

"""Archipelago items on the 3D stalls (DisplayShop), built per seed.

The item actor, its model, icon, price, texts and flags are the shops' (the
same AP_Shop_<id> scheme, botw_patch/shops.py builds them for every placement).
What is proper to a stall (botw_client/stall_catalog.py):
  * in the DLC map unit, the stall object turns into the AP actor: same
    HashId and links (ForSale to its merchant, DeadUp to the stall's sold-out
    tag). The jewel (assets/models/ap_item) stands on its origin, its faces
    along Z. Its pose and yaw are the location's, chosen in the game
    (botw_client/stall_catalog.py): lying on its back, face up (Rotate
    [-pi/2, yaw, 0], the pitch first), centred on the object it replaces and
    resting on its level (half its thickness up); or standing on the object,
    facing the customer (Rotate [0, yaw, 0]);
  * a new LinkTagAnd reading the saved bool IsGet_AP_Shop_<id> creates the
    object: true until bought, so a bought one is never created again, blood
    moon included. It is the vanilla pattern of 956 tags of these maps (no
    input, a SaveFlag, Create links, e.g. BalladOfHeroGerudo_Activated);
  * the merchant's flow records the purchase after DisplayShop:Multiple
    (APShop_<id> = 1, IsGet_AP_Shop_<id> = 0, item out of the pouch), as
    Beedle's does.
"""
from __future__ import annotations

import math
import zlib

import oead

from botw_client.stall_catalog import StallLocation
from botw_patch.resources import digest, unpack
from botw_patch.shop_items import add_purchase_record

AOC_PREFIX = "aoc/0010/"          # files at the pack root, under aoc/
TABLE_PREFIX = "Aoc/0010/"        # their key in the resource size table
TAG = "LinkTagAnd"
# As on the 956 vanilla tags that create objects from a saved flag alone.
TAG_PARAMETERS = {"IncrementSave": False, "MakeSaveFlag": oead.S32(0),
                  "NoChangeSignal": False, "SaveFlag": "",
                  "SaveFlagOnOffType": oead.S32(0)}

INPUT_HASHES = {
    "Event/Npc_HighMountain021.sbeventpack": "b9713dca413ab83605385376294cd26b3c25bc9bff794273bd266dfbacbe5295",
    "Event/Npc_oasis045.sbeventpack": "ccee6a4f036e4151197bcf8dd1c01d0cf14392ada6d4c51b64fe985255bb573c",
    "Event/Npc_oasis002.sbeventpack": "a28bc64429bf1f2957f265cead22fcb5b920620df6abf790c8391cff84c0eed6",
    "Event/Npc_SmallOasis010.sbeventpack": "e558842a06478425f83e2aff1eecb04aaa52b941cfdd367ef45b0e33b326abcf",
    "Event/Npc_oasis044.sbeventpack": "c01d0aff8c129cea4c8521a034684d0ce3d53281c6d673e7a43b776646bab2e0",
    "Event/Npc_kokiri004.sbeventpack": "6e744095116806553b4b3f210a1eaecef7039b29c37a55558a539e93ff2fbd92",
    "Event/Npc_kokiri003.sbeventpack": "4699f48c4ab5889294513d084774efaa05eba66cf033a5204bae20163dad1a8a",
    "Event/Npc_goron002.sbeventpack": "68a9b7dd394df5659eeec8dea0618ca532ed0f09b9055325a03e329251f73e32",
    "Event/Npc_Kakariko010.sbeventpack": "40ded675c6699528fe60e57f1b98b8eb27511e95f7cba63e7f1dd8700a9a9b63",
    "Event/Npc_Kakariko014.sbeventpack": "7d82de18b41f7f999ff4516ddd6e8e425f4f5de236c044c9a23e421e2305d6bd",
    "Event/Npc_SouthernVillage005.sbeventpack": "01fefc408657817ac26a0a34e25575d2cd8b0268aa680fb4b2c4f59edba8af31",
    "Event/Npc_HighMountain010.sbeventpack": "cadc02f83fe630547a532bc4153b7960123ea8b8f11c71f9468a512ede967757",
    "Event/Npc_Zora002.sbeventpack": "68f0fc76728e86d5c991525796fd2276d55ed73d5505d5f75ef36929a1e98ecb",
    "Event/Npc_HatenoVillage002.sbeventpack": "64335815a9595aedd8b4fd37ddc85dbad1d5deef1236a022b427f2a53b73fb3b",
}
MAP_HASHES = {
    "Map/MainField/B-3/B-3_Static.smubin": "7c3e86af0c9e509f72440bdde0720e2050aed4591aca985268315d07dc4139b9",
    "Map/MainField/B-7/B-7_Static.smubin": "a92a406e27fa0226c9bd43c462ff2982040f9d25bff65785aa024400d22f533f",
    "Map/MainField/F-2/F-2_Static.smubin": "dfcb7349770d4ddf48d67e69baa75cf52f0cf18da2c43934009210dc0de3996a",
    "Map/MainField/G-2/G-2_Static.smubin": "a793d3795c27ec406152852d382423dd5d3e72afb2ece5c37ebcf52bf74b346c",
    "Map/MainField/G-6/G-6_Static.smubin": "2aebf7fd5192aae8b4cfce6ef9a4eb201445917a762c06dd6c2ac976e26addb3",
    "Map/MainField/H-8/H-8_Static.smubin": "641b827e4e3d28e9373c2bee205959c3ce9c954c60264d69717581c26f7848aa",
    "Map/MainField/I-3/I-3_Static.smubin": "d2fc9160bba05cb95a1b083cdf873de7d7d74b0025fe178768ac6338830ab5cd",
    "Map/MainField/I-4/I-4_Static.smubin": "6cadc2c717023be64311738ffe022abd1a8867f81c2fab2c8babf50e082b6552",
    "Map/MainField/I-7/I-7_Static.smubin": "0d8808b7eb5e7297bbe027e671513733e5d379169f96396bd467269416638ef8",
}
SOURCE_FILES = ("botw_patch/stalls.py", "botw_client/stall_catalog.py")


def tag_hash(location: StallLocation) -> int:
    """HashId of the location's tag: derived from its name, checked unique."""
    return zlib.crc32(f"AP_Stall_Tag_{location.id:03d}".encode()) & 0xFFFFFFFF


def _srt_hash(location: StallLocation) -> int:
    value = zlib.crc32(f"AP_Stall_Tag_{location.id:03d}_SRT".encode())
    return value - (1 << 32) if value >= 1 << 31 else value


def clone(node):
    """A fresh copy of a byml node (oead nodes are not deep-copyable)."""
    if isinstance(node, oead.byml.Hash):
        out = oead.byml.Hash()
        for key, value in node.items():
            out[key] = clone(value)
        return out
    if isinstance(node, oead.byml.Array):
        return oead.byml.Array([clone(value) for value in node])
    return node


def _link_nodes(obj) -> list:
    return list(obj["LinksToObj"]) if "LinksToObj" in obj else []


def _links(obj) -> list[tuple[str, int]]:
    return [(str(link["DefinitionName"]), int(link["DestUnitHashId"]))
            for link in _link_nodes(obj)]


def patch_map(raw: bytes, locations: list[StallLocation],
              jewel: tuple[float, float]) -> tuple[bytes, dict]:
    """One map unit with its stall locations: objects turned, tags added.
    jewel: the model's (height, thickness), in metres."""
    height, thickness = jewel
    doc = oead.byml.from_binary(unpack(raw))
    objects = list(doc["Objs"])
    hashes = [int(o["HashId"]) for o in objects]
    if hashes != sorted(hashes):
        raise ValueError("map objects not sorted by HashId")
    by_hash = {int(o["HashId"]): o for o in objects}
    create = next((link for o in objects for link in _link_nodes(o)
                   if str(link["DefinitionName"]) == "Create" and "!Parameters" in link), None)
    # Field types of a tag reading a saved flag, from one of this unit.
    model = next((o for o in objects if str(o["UnitConfigName"]) == TAG
                  and "!Parameters" in o
                  and set(o["!Parameters"].keys()) == set(TAG_PARAMETERS)), None)
    if create is None or model is None:
        raise ValueError("no Create link or flag tag to copy in this map")
    detail = {}
    for location in locations:
        merchant = location.merchant
        obj = by_hash.get(location.object_hash)
        if obj is None or str(obj["UnitConfigName"]) != location.vanilla_actor:
            raise ValueError(f"stall object not found or unexpected: {location.name}")
        if ("ForSale", merchant.hash_id) not in _links(obj):
            raise ValueError(f"object not for sale by {merchant.actor}: {location.name}")
        # Its links (ForSale, sold-out tags) stay as they are.
        obj["UnitConfigName"] = location.actor
        yaw = location.yaw
        x, y, z = (float(v) for v in obj["Translate"])
        if location.pose == "standing":
            obj["Rotate"] = oead.byml.Array([oead.F32(0.0), oead.F32(yaw), oead.F32(0.0)])
            obj["Translate"] = oead.byml.Array([oead.F32(x), oead.F32(y + location.lift), oead.F32(z)])
        elif location.pose == "lying":
            obj["Rotate"] = oead.byml.Array([oead.F32(-math.pi / 2), oead.F32(yaw), oead.F32(0.0)])
            # Lying, its middle is height/2 from its origin, towards its top.
            obj["Translate"] = oead.byml.Array([oead.F32(x + height / 2 * math.sin(yaw)),
                                                oead.F32(y + thickness / 2 + location.lift),
                                                oead.F32(z + height / 2 * math.cos(yaw))])
        else:
            raise ValueError(f"unknown pose for {location.name}: {location.pose}")

        tag = clone(model)
        new_hash = tag_hash(location)
        if new_hash in by_hash:
            raise ValueError(f"tag HashId already taken: {new_hash}")
        tag["HashId"] = oead.U32(new_hash)
        tag["SRTHash"] = oead.S32(_srt_hash(location))
        tag["Translate"] = clone(obj["Translate"])
        if "Rotate" in tag:
            del tag["Rotate"]
        params = tag["!Parameters"]
        for key, value in TAG_PARAMETERS.items():
            params[key] = value
        params["SaveFlag"] = location.shown_flag
        link = clone(create)
        link["DestUnitHashId"] = oead.U32(location.object_hash)
        tag["LinksToObj"] = oead.byml.Array([link])
        objects.append(tag)
        by_hash[new_hash] = tag
        detail[location.id] = {"object": location.object_hash, "from": location.vanilla_actor,
                               "to": location.actor, "tag": new_hash,
                               "flag": location.shown_flag, "pose": location.pose, "yaw": location.yaw}
    objects.sort(key=lambda o: int(o["HashId"]))
    new = oead.byml.Hash()
    for key in doc.keys():
        new[key] = oead.byml.Array(objects) if key == "Objs" else doc[key]
    out = bytes(oead.byml.to_binary(new, big_endian=True, version=2))
    return bytes(oead.yaz0.compress(out)), detail


def generate(builder, files: dict[str, bytes], content, aoc, locations: list[StallLocation],
             jewel: tuple[float, float]) -> list[dict]:
    """Map units and merchant flows of the seed's stall locations, into a
    ResourceBuilder whose stage holds `files`. Returns the changes; the map
    units go to files[aoc/0010/...]."""
    changes = []
    units: dict[str, list[StallLocation]] = {}
    for location in locations:
        units.setdefault(location.merchant.map_unit, []).append(location)
    for unit, located in sorted(units.items()):
        raw = (aoc / unit).read_bytes()
        if digest(raw) != MAP_HASHES[unit]:
            raise ValueError(f"unexpected DLC map: {unit}")
        new, detail = patch_map(raw, located, jewel)
        builder.account(TABLE_PREFIX + unit, new, raw)
        files[AOC_PREFIX + unit] = new
        changes.append({"resource": AOC_PREFIX + unit, "stalls": detail})
    merchants: dict[str, list[StallLocation]] = {}
    for location in locations:
        merchants.setdefault(location.merchant.actor, []).append(location)
    for actor, located in sorted(merchants.items()):
        pack = f"Event/{actor}.sbeventpack"
        records = [(l.actor, l.flag, l.shown_flag) for l in located]
        builder.patch_archive(pack, {f"EventFlow/{actor}.bfevfl": lambda raw, records=records,
                                     event=located[0].merchant.buy_event:
                                     add_purchase_record(raw, event, records)})
    return changes


def stage_inputs(content) -> dict[str, bytes]:
    """The merchants' event packs, checked."""
    out = {}
    for name, expected in INPUT_HASHES.items():
        raw = (content / name).read_bytes()
        if digest(raw) != expected:
            raise ValueError(f"unexpected update resource: {name}")
        out[name] = raw
    return out

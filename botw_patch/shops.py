"""Archipelago shops, built per seed: Beedle sells the AP items of his locations.

Everything is resources (docs/reference/shops.md):
  * one item actor per shop location, AP_Shop_<id> (ActorInfo declaration,
    actor pack cloned from amber, the Archipelago icon, the Archipelago 3D
    model), priced by the seed, named and described after its
    placement in every EU language;
  * each Beedle's stock table lists his AP items first (the first entry is
    selected when the list opens, which tells the client which shop is seen);
  * his flow, once the buy list returns, records each AP item bought in its
    saved s32 flag APShop_<id> and removes it from the pouch; the client tracks
    those flags like every location flag;
  * Beedle restocks at every opening: each AP entry carries ItemLookGetFlg,
    which lists it only while IsGet_AP_Shop_<id> is true; that saved bool
    starts true and the purchase clears it;
  * the flags are declared in GameData and in the save format.

Placements come from the slot manifest (botw_world generate_output):
manifest["shops"] lists {location_id, price}; manifest["placements"] gives the
item placed at each of them.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import textwrap

import oead

from botw_client.shop_catalog import BY_ID as SHOP_BY_ID, LOCATIONS, MERCHANTS, KEPT, ShopLocation
from botw_client.stall_catalog import BY_ID as STALL_BY_ID, StallLocation
from botw_patch.resources import ResourceBuilder, digest, unpack
from botw_patch.shop_items import (DESCRIPTION_LINES, DESCRIPTION_WIDTH, MODEL_PARTS, MSBT,
                                   ApShopItem, add_declarations, add_item_texts,
                                   add_purchase_record, arrange_stock, check_model,
                                   clone_actor_pack, model_size, rename_model)

ROOT = Path(__file__).resolve().parents[1]
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
TITLE = "Pack/TitleBG.pack"
BOOTUP = "Pack/Bootup.pack"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
MODEL_ACTOR = "Item_Ore_F"                  # amber: actor pack, model and material
MODEL_FOLDER = "AP_Item_00"                 # Model/AP_Item_00.*, internal names too
MODEL_SOURCE = ROOT / "assets/models/ap_item/wiiu"
MODEL_SOURCE_NAME = "AP_Item"
# Amber's own model files (Item_Ore_F, base game): what the model check and
# the size table need from them, measured on the originals (their SHA-256
# below), so that the project ships no game file.
_AMBER_TEXTURES = {
    "Item_Ore_F_Alb": {"size": [256, 256], "mips": 9, "format": 1073,
                       "image_bytes": 32768, "mip_bytes": 13312},
    "Item_Ore_F_Bright_Alb": {"size": [128, 128], "mips": 8, "format": 1073,
                              "image_bytes": 8192, "mip_bytes": 5120},
    "Item_Ore_F_Emm": {"size": [128, 128], "mips": 8, "format": 52,
                       "image_bytes": 8192, "mip_bytes": 5120},
    "Item_Ore_F_Nrm": {"size": [128, 128], "mips": 8, "format": 49,
                       "image_bytes": 8192, "mip_bytes": 5120},
    "Item_Ore_F_Spm": {"size": [64, 64], "mips": 7, "format": 52,
                       "image_bytes": 4096, "mip_bytes": 3072},
}
MODEL_REFERENCE = {
    "": {"sha256": "605884eaed24c320711c3a637c428ce46cbb94593af63efcf17d5f30ed71db2d",
         "unpacked_size": 48896,
         "summary": {"version": 67436547, "models": ["Item_Ore_F"], "textures": {}}},
    ".Tex1": {"sha256": "578e9a1081b8df42e9c6d2ac59352991cda82e76f854329b2c0803d5bcbd02e1",
              "unpacked_size": 65536,
              "summary": {"version": 67436547, "models": [], "textures": _AMBER_TEXTURES}},
    ".Tex2": {"sha256": "2ddd63f9e76eede080741e0d36b865017289b48584f282d9b8679733075f4038",
              "unpacked_size": 49408,
              "summary": {"version": 67436547, "models": [], "textures": _AMBER_TEXTURES}},
}
ICON = ROOT / "assets/wiiu/Item_AP.sbitemico"
ICON_TABLE_MARGIN = 8192
STOCK = 1                                   # one of each AP item
BUY_EVENT = "Event18"                       # Yorozuya_Kaiwa:Zucchi_Konyu, then Event150
FLOW = "EventFlow/Npc_TripMaster_00.bfevfl"  # identical copy in the 16 event packs
LANGUAGES = ("EUde", "EUen", "EUes", "EUfr", "EUit", "EUnl", "EUru")
NAME_LIMIT = 30                              # characters shown in the list (to measure)

INPUT_HASHES = {
    "Actor/ActorInfo.product.sbyml": "07f440eadb27109f9fa6511a12a9f6c8b76047ca539b24b32a301ba27183e6a2",
    "Actor/Pack/Npc_TripMaster_00.sbactorpack": "369afa4da598e7425e8495e610eb667a0781036f78a9e1915259f516116f35df",
    "Actor/Pack/Npc_TripMaster_01.sbactorpack": "90f33b767da91047c0bd80ad7e2378e705b5973f3f5d80a8b71dbe40f6019fe4",
    "Actor/Pack/Npc_TripMaster_02.sbactorpack": "81f301ef62b427c061c10c690efe4ddbd5369934db6237a6798433e7e62bc22a",
    "Actor/Pack/Npc_TripMaster_03.sbactorpack": "86b4f0266c2d4430b8b694e2de7018ebfc45544d7f01a13ed138a72677d33bb2",
    "Actor/Pack/Npc_TripMaster_04.sbactorpack": "8669b32deed256d9129d3190b8d9faba382c33ce0be5cc44a6fff75471485cb8",
    "Actor/Pack/Npc_TripMaster_05.sbactorpack": "9027f2a16d88e3100ea576cf89079a8e4bf07247176947a0f0d7b9136a4ffa1d",
    "Actor/Pack/Npc_TripMaster_06.sbactorpack": "50b83144b55c27ec647c9451cdc81099f66613455feef330b428b8115c875cf9",
    "Actor/Pack/Npc_TripMaster_07.sbactorpack": "2536668e65b76afdebcc3dbcd94d7781830506e923470238f86659d941434718",
    "Actor/Pack/Npc_TripMaster_08.sbactorpack": "90068e5813dce3c615cee3ab3c6b918df3f31951bd8f9f15f2b361c424d33370",
    "Actor/Pack/Npc_TripMaster_09.sbactorpack": "58384229289dc7440644410826d837f4d06d4b757c6d9721709ce86ad6ed3e0e",
    "Actor/Pack/Npc_TripMaster_10.sbactorpack": "1f1e430c7aedc4fe410cc1e95dafc7efc529e0b8b61634bbe11a8d0a8420cdb3",
    "Actor/Pack/Npc_TripMaster_11.sbactorpack": "d433f490a48388dd2f0c641339fcc141196618d5619d5e9195f82b34d0e17b4d",
    "Actor/Pack/Npc_TripMaster_12.sbactorpack": "2266b0e72957ff2f442985e8a5c61013b70ac3820a870d3a1b23e7ffbff17104",
    "Actor/Pack/Npc_TripMaster_13.sbactorpack": "f98be40f24832c78bbb2fa23167a824be808346d486873b33ca86b6c34cd570c",
    "Actor/Pack/Npc_TripMaster_14.sbactorpack": "27cb036c39a0237519babd2b119a28e938e5fcd820d7a2865d9bfc394e84dfcd",
    "Actor/Pack/Npc_TripMaster_15.sbactorpack": "5644b5590f54883465b8ee1792ce7ad74021fdd2fde1d688ea1cc5ef751db3c6",
    "Event/Npc_TripMaster_00.sbeventpack": "8781b78d9676a8504d9244fd9298451c96c236ffa3c0225c02ac5a44d4d8fae0",
    "Event/Npc_TripMaster_01.sbeventpack": "5acda67a70653a45bd0c136938f73ea728efec50ea3796c1aae2e1d3f77ed639",
    "Event/Npc_TripMaster_02.sbeventpack": "8781b78d9676a8504d9244fd9298451c96c236ffa3c0225c02ac5a44d4d8fae0",
    "Event/Npc_TripMaster_03.sbeventpack": "f6e91f4c4e32e1b0ca1fd900d3b2a2bb8285f9d0c1042b061f25147b1368cb8b",
    "Event/Npc_TripMaster_04.sbeventpack": "82ecda1763409f7c3f2ad25d3a05f3bec293581227c4f954ef13a8f066af5e59",
    "Event/Npc_TripMaster_05.sbeventpack": "1bcf62084ee2b91e8027a9a68629943cead315df7b2cda82e1c2d92d5cd857a5",
    "Event/Npc_TripMaster_06.sbeventpack": "8364a63cf6bfff15e5dacb480150a1d54f73e509cda4e2e4c069f0cb494bc49f",
    "Event/Npc_TripMaster_07.sbeventpack": "0e1d17dc123622ed1c135ae73d0fb7f413eec67ee7f7792819cdf493df350af3",
    "Event/Npc_TripMaster_08.sbeventpack": "14d449ac23059ac948049023478118ed0caadbdb4d62f86e6ce92a679bfcbbd3",
    "Event/Npc_TripMaster_09.sbeventpack": "5bc74f310c05e746571d98fdea2575351657b0c7e81acd34772ced4f2e696fae",
    "Event/Npc_TripMaster_10.sbeventpack": "5549361809c7eb2357ed857a23f754834d12e0d359efb4f532f23d2993cd7e55",
    "Event/Npc_TripMaster_11.sbeventpack": "ec53bf074c42c7bdbed20fe3af6f960d3f159f4174e12597e630369733838ae4",
    "Event/Npc_TripMaster_12.sbeventpack": "99e1b28f3cae596503af2cbc040d5f31b278719d099e1fd26ce07dfdcf07e6b3",
    "Event/Npc_TripMaster_13.sbeventpack": "e2a7d66417c2a62e7bc418ad7b87b92e1e0804621672b8be66e6b7cbd91c2d9f",
    "Event/Npc_TripMaster_14.sbeventpack": "1eb3580da9f8d2e3ca11a2ba9d2682fa5b184433a8e9db84842f39744e550cab",
    "Event/Npc_TripMaster_15.sbeventpack": "8781b78d9676a8504d9244fd9298451c96c236ffa3c0225c02ac5a44d4d8fae0",
    "Pack/Bootup_EUde.pack": "d68f8d06da6542d7bbb5c4437ce291306a53a053e5860e427ccae0664b352aaf",
    "Pack/Bootup_EUen.pack": "e6e7593fb7e5aba3858fa3ff6d646585dd08d83562551ed392d28a9515dfd5f8",
    "Pack/Bootup_EUes.pack": "8a4dbf21d7ea474d2673d8d7d2c55a8d93d5831fb621b501fc5e73afb235eff0",
    "Pack/Bootup_EUfr.pack": "8597171f9053fad2da85584cb8f9496bf3ffabecb5b27d61e517b3ca0066cdb7",
    "Pack/Bootup_EUit.pack": "fa768b456a3b078b4588e25c16e4b623cc6d27da67552de907425ad3958b5632",
    "Pack/Bootup_EUnl.pack": "2e3472118604e27bb026650293ac94f340af7530131ce8f4fda6deccb28c264c",
    "Pack/Bootup_EUru.pack": "baccba9b2ea127eb94024a506beacf532a886d7ce36229e58e20f3f066eb4eaf",
}
TITLE_SHA256 = "12f9925add7d855bad95fbd85cbfbdf760b932e2361c8b306943a6fa0b8e3234"
SOURCE_FILES = ("botw_patch/shops.py", "botw_patch/shop_items.py", "botw_client/shop_catalog.py",
                *(f"assets/models/ap_item/wiiu/{MODEL_SOURCE_NAME}{part}.sbfres"
                  for part in MODEL_PARTS), "assets/wiiu/Item_AP.sbitemico")

# AP classification bits (NetworkItem.flags).
PROGRESSION, USEFUL, TRAP = 1, 2, 4


@dataclass(frozen=True)
class ShopPlacement:
    location: ShopLocation
    price: int
    item: str
    player: str
    game: str
    flags: int
    own: bool           # the item is for this BOTW slot


def plan_from_manifest(manifest: dict) -> list[ShopPlacement]:
    """The shop placements of a slot manifest (empty for a seed without shops)."""
    placements = {row["location_id"]: row for row in manifest.get("placements", [])}
    out = []
    for row in manifest.get("shops", []):
        location = SHOP_BY_ID.get(row["location_id"]) or STALL_BY_ID[row["location_id"]]
        placed = placements.get(location.id)
        if placed is None:
            raise ValueError(f"shop location without an item: {location.name}")
        price = row["price"]
        if type(price) is not int or not 1 <= price <= 999:
            raise ValueError(f"invalid price for {location.name}: {price}")
        out.append(ShopPlacement(location, price, placed["item_name"],
                                 placed["recipient_name"], placed["recipient_game"],
                                 int(placed["flags"]), placed["recipient"] == manifest["slot"]))
    if len({p.location.id for p in out}) != len(out):
        raise ValueError("duplicate shop location")
    return sorted(out, key=lambda p: p.location.id)


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def texts(placement: ShopPlacement) -> tuple[str, str]:
    """(name, description) shown by the shop, in English in every language.

    Traps are described as ordinary items, as AP shops usually do.
    """
    name = _short(placement.item, NAME_LIMIT)
    importance = ("" if placement.flags & TRAP else
                  " Needed to progress." if placement.flags & PROGRESSION else
                  " Useful." if placement.flags & USEFUL else "")
    for item_limit, game_limit in ((80, 60), (40, 30), (24, 18)):
        item, game = _short(placement.item, item_limit), _short(placement.game, game_limit)
        if placement.own:
            body = f"Archipelago item for you: {item}."
        else:
            player = _short(placement.player, 16)
            body = f"Archipelago item for {player} ({game}): {item}."
        lines = textwrap.wrap(body + importance, DESCRIPTION_WIDTH)
        if len(lines) <= DESCRIPTION_LINES:
            return name, "\n".join(lines)
    raise ValueError(f"description does not fit: {placement.location.name}")


def items(placements: list[ShopPlacement]) -> list[ApShopItem]:
    return [ApShopItem(p.location.actor, p.price, *texts(p),
                       model_actor=MODEL_ACTOR, model_folder=MODEL_FOLDER,
                       model_unit=MODEL_FOLDER) for p in placements]


def model_files(source: Path = MODEL_SOURCE) -> dict[str, bytes]:
    return {part: (source / f"{MODEL_SOURCE_NAME}{part}.sbfres").read_bytes()
            for part in MODEL_PARTS}


def stock_entries(merchant, locations: list[ShopLocation]) -> list:
    """AP items first, then the arrows, then the vanilla entries left."""
    ap = [(location.actor, STOCK, 0, True) for location in locations]
    return [*ap, *merchant.stock[:KEPT], *merchant.stock[KEPT + len(ap):]]


def generate(files: dict[str, bytes], content: Path,
             placements: list[ShopPlacement],
             model: dict[str, bytes] | None = None,
             aoc: Path | None = None) -> tuple[dict[str, bytes], list[dict]]:
    """Add the shops of `placements` to an overlay being built.

    `files` must already hold the size table and Bootup.pack (with the other AP
    flags); every other input is read from the Wii U update `content` and
    checked against INPUT_HASHES first. Returns the updated files and the
    changes, one entry per resource.
    """
    if not placements:
        return files, []
    for name in (TABLE, BOOTUP):
        if name not in files:
            raise ValueError(f"{name} expected in the overlay")
    inputs = {}
    for name, expected in INPUT_HASHES.items():
        if name in files:
            raise ValueError(f"the overlay already replaces {name}")
        raw = (content / name).read_bytes()
        if digest(raw) != expected:
            raise ValueError(f"unexpected update resource: {name}")
        inputs[name] = raw
    title_raw = files.get(TITLE) or (content / TITLE).read_bytes()
    source_title = (content / TITLE).read_bytes()
    if digest(source_title) != TITLE_SHA256:
        raise ValueError(f"unexpected update resource: {TITLE}")
    title = oead.Sarc(unpack(source_title))
    model = model if model is not None else model_files()
    changes: list[dict] = []
    shop_items = items(placements)
    # Beedle's lists and the 3D stalls (botw_patch/stalls.py): the item actors,
    # texts and flags below are common, the rest proper to each.
    beedle = [p for p in placements if isinstance(p.location, ShopLocation)]
    stall = [p.location for p in placements if isinstance(p.location, StallLocation)]
    by_merchant = {m: [p.location for p in beedle if p.location.merchant == m]
                   for m in MERCHANTS}
    if stall:
        from botw_patch import stalls as stall_stage
        if aoc is None:
            raise ValueError("stalls: the DLC's aoc/0010 folder is required")
        for name in stall_stage.INPUT_HASHES:
            if name in files:
                raise ValueError(f"the overlay already replaces {name}")
        inputs.update(stall_stage.stage_inputs(content))

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        for name, raw in {**inputs, **files, TITLE: title_raw}.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)

        # Declarations (ActorInfo has no size table entry in vanilla).
        builder.outputs[ACTOR_INFO], detail = add_declarations(inputs[ACTOR_INFO], shop_items)
        changes.append({"resource": ACTOR_INFO, "declarations": detail})

        # Actor packs, icons, model lists.
        amber = bytes(title.get_file(f"Actor/Pack/{MODEL_ACTOR}.sbactorpack").data)
        icon = ICON.read_bytes()
        table = builder.table
        for item in shop_items:
            pack = f"Actor/Pack/{item.actor}.sbactorpack"
            builder.outputs[pack], _detail = clone_actor_pack(
                amber, MODEL_ACTOR, item.actor, MODEL_FOLDER, MODEL_FOLDER, item.price)
            for kind, ext in (("Actor/Pack", "bactorpack"), ("Actor/ActorLink", "bxml"),
                              ("Actor/ModelList", "bmodellist"),
                              ("Actor/GeneralParamList", "bgparamlist")):
                table.set_size(f"{kind}/{item.actor}.{ext}",
                               table.get_size(f"{kind}/{MODEL_ACTOR}.{ext}"))
            builder.outputs[f"UI/StockItem/{item.actor}.sbitemico"] = icon
            table.set_size(f"UI/StockItem/{item.actor}.bitemico",
                           len(unpack(icon)) + ICON_TABLE_MARGIN)
        changes.append({"resource": "actors", "actors": [i.actor for i in shop_items],
                        "model": MODEL_FOLDER, "icon_sha256": digest(icon)})

        # The Archipelago model, checked against amber's, internal names renamed.
        report = check_model(model, {part: MODEL_REFERENCE[part]["summary"]
                                     for part in MODEL_PARTS})
        renamed, rename_detail = rename_model(model, MODEL_ACTOR, MODEL_FOLDER)
        for part in MODEL_PARTS:
            builder.outputs[f"Model/{MODEL_FOLDER}{part}.sbfres"] = renamed[part]
            table.set_size(f"Model/{MODEL_FOLDER}{part}.bfres", model_size(
                table.get_size(f"Model/{MODEL_ACTOR}{part}.bfres"),
                MODEL_REFERENCE[part]["unpacked_size"], renamed[part]))
        changes.append({"resource": "model", "check": report, "renamed": rename_detail,
                        "source_sha256": {part or "model": digest(raw)
                                          for part, raw in model.items()}})

        # Stock tables: the sheet never grows, the actor pack is accounted.
        for merchant, locations in by_merchant.items():
            if not locations:
                continue
            pack = f"Actor/Pack/{merchant.actor}.sbactorpack"
            member = f"Actor/ShopData/{merchant.actor}.bshop"
            archive = oead.Sarc(unpack(inputs[pack]))
            writer = oead.SarcWriter.from_sarc(archive)
            writer.files[member], detail = arrange_stock(
                bytes(archive.get_file(member).data), "Normal", merchant.stock,
                stock_entries(merchant, locations))
            packed = bytes(oead.yaz0.compress(bytes(writer.write()[1])))
            builder.account(pack, packed, inputs[pack])
            builder.outputs[pack] = packed
            changes.append({"resource": pack, "stock": detail})

        # Names and descriptions, the same English text in every EU language.
        for language in LANGUAGES:
            language_items = shop_items

            def messages(raw, language_items=language_items):
                archive = oead.Sarc(unpack(raw))
                writer = oead.SarcWriter.from_sarc(archive)
                new, detail = add_item_texts(bytes(archive.get_file(MSBT).data), language_items)
                writer.files[MSBT] = new
                packed = bytes(writer.write()[1])
                return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), detail

            builder.patch_archive(f"Pack/Bootup_{language}.pack",
                                  {f"Message/Msg_{language}.product.ssarc": messages})

        # Purchase record in every Beedle flow copy (which pack each Beedle
        # loads is not measured): all the seed's Beedle items, any merchant.
        records = [(p.location.actor, p.location.flag, p.location.shown_flag)
                   for p in beedle]
        if beedle:
            for merchant in MERCHANTS:
                builder.patch_archive(f"Event/{merchant.actor}.sbeventpack", {
                    FLOW: lambda raw: add_purchase_record(raw, BUY_EVENT, records)})
        aoc_files: dict[str, bytes] = {}
        if stall:
            changes.extend(stall_stage.generate(builder, aoc_files, content, aoc, stall))

        # Saved flags.
        from tools.build_game_data_mod import modify_gamedata_flags, modify_saveformat
        flags = tuple(p.location.flag for p in placements)
        shown = tuple(p.location.shown_flag for p in placements)
        builder.patch_archive(BOOTUP, {
            "GameData/gamedata.ssarc": lambda raw: (
                modify_gamedata_flags(modify_gamedata_flags(raw, flags, is_save=True),
                                      shown, is_save=True, kind="bool", init=1),
                [*flags, *shown]),
            "GameData/savedataformat.ssarc": lambda raw: (
                modify_saveformat(raw, flags + shown), ["register saved shop flags"]),
        })
        changes.extend(builder.changes)
        outputs = builder.finish()
    expected = {ACTOR_INFO, TABLE, BOOTUP, *(f"Pack/Bootup_{l}.pack" for l in LANGUAGES),
                *(f"Event/{m.actor}.sbeventpack" for m in (MERCHANTS if beedle else ())),
                *(f"Event/{l.merchant.actor}.sbeventpack" for l in stall),
                *(f"Actor/Pack/{m.actor}.sbactorpack" for m, locs in by_merchant.items() if locs),
                *(f"Model/{MODEL_FOLDER}{part}.sbfres" for part in MODEL_PARTS),
                *(f"Actor/Pack/{p.location.actor}.sbactorpack" for p in placements),
                *(f"UI/StockItem/{p.location.actor}.sbitemico" for p in placements)}
    if set(outputs) != expected:
        raise ValueError(f"unexpected outputs: {sorted(set(outputs) ^ expected)}")
    files = {**files, **outputs, **aoc_files}
    return files, changes


__all__ = ["LOCATIONS", "ShopPlacement", "plan_from_manifest", "texts", "items", "generate",
           "INPUT_HASHES", "SOURCE_FILES", "MODEL_FOLDER"]

"""Archipelago shop items: actors created for AP, sold by vanilla merchants.

Measured in the game (docs/reference/shops.md):
  * a merchant's stock sheet (.bshop) can sell any existing item; the price
    shown is the item's ActorInfo `itemBuyingPrice` plus the sheet's
    `ItemAdjustPrice`;
  * an actor created for AP is shown and sold like a vanilla item when it
    has an ActorInfo declaration, an actor pack, an icon and a name; it then
    goes into the pouch, which an AP item must not do.

This module holds the pieces, each checked on its own output:
  * declarations in Actor/ActorInfo.product.sbyml;
  * the actor pack, cloned from a model item with its ActorLink renamed;
  * name and description labels in ActorType/Item.msbt;
  * stock sheet entries;
  * the purchase cleanup in a merchant's own flow: once its buy list returns,
    every AP item of that merchant is deleted from the pouch with the game's
    own action (Demo_DeletePorchItemInEquip, as the Ballad end uses it).
  * the purchase record (real shops): the same place, but each AP item held
    is first recorded in its saved flag, then deleted (add_purchase_record);
  * stock tables rearranged with AP entries first (arrange_stock).
"""
from __future__ import annotations

from dataclasses import dataclass
import struct
import textwrap
import zlib

import oead

from botw_patch.events import (add_action_after, branch_with_query, graph_snapshot, read_flow,
                               write_flow)
from botw_patch.resources import unpack

MSBT = "ActorType/Item.msbt"
DESCRIPTION_WIDTH = 44      # vanilla descriptions break lines at about 44-48 characters
DESCRIPTION_LINES = 4
DELETE_ACTION = "Demo_DeletePorchItemInEquip"


@dataclass(frozen=True)
class ApShopItem:
    actor: str
    price: int | None           # None: an actor that is no item (no buying price)
    name: str
    description: str
    model_actor: str = "Item_Ore_F"
    # Model file folder (Model/<folder>.sbfres, .Tex1, .Tex2) of its own; None
    # keeps the model item's. The model inside keeps its name (mainModel).
    model_folder: str | None = None
    # Name of the model inside its file (ActorInfo mainModel, ModelList
    # UnitName); None keeps the model item's.
    model_unit: str | None = None


def crc(name: str) -> int:
    return zlib.crc32(name.encode()) & 0xFFFFFFFF


def wrap_description(text: str, width: int = DESCRIPTION_WIDTH,
                     lines: int = DESCRIPTION_LINES) -> str:
    """Explicit line breaks, as vanilla descriptions have (the game does not wrap)."""
    out = textwrap.wrap(text, width)
    if len(out) > lines:
        raise ValueError(f"description too long ({len(out)} lines, at most {lines})")
    return "\n".join(out)


# --- declarations ------------------------------------------------------------

def add_declarations(raw: bytes, items: list[ApShopItem]) -> tuple[bytes, dict]:
    """Insert one ActorInfo entry per item, cloned from its model item.

    Actors and Hashes stay aligned and sorted by crc32 of the name.
    """
    doc = oead.byml.from_binary(unpack(raw))
    actors, hashes = list(doc["Actors"]), list(doc["Hashes"])
    count = len(actors)     # replacing doc["Actors"] empties the old oead array
    names = [str(a["name"]) for a in actors]
    values = [int(h) for h in hashes]
    if values != sorted(values):
        raise ValueError("Hashes not sorted in the source")
    detail = {}
    for item in items:
        if item.actor in names:
            raise ValueError(f"actor already declared: {item.actor}")
        model = actors[names.index(item.model_actor)]
        clone = oead.byml.Hash()
        for key in model.keys():
            clone[key] = model[key]
        clone["name"] = item.actor
        if item.price is not None:
            clone["itemBuyingPrice"] = oead.S32(item.price)
        if item.model_folder:
            clone["bfres"] = item.model_folder
        if item.model_unit:
            clone["mainModel"] = item.model_unit
        value = crc(item.actor)
        index = next((i for i, v in enumerate(values) if v > value), len(values))
        actors.insert(index, clone)
        hashes.insert(index, oead.U32(value) if value > 0x7FFFFFFF else oead.S32(value))
        values.insert(index, value)
        names.insert(index, item.actor)
        detail[item.actor] = {"hash": hex(value), "price": item.price,
                              "cloned_from": item.model_actor}
    # A new document: replacing doc's arrays would free the elements that
    # `actors` still refers to (an intermittent KeyError in the test suite).
    if set(doc.keys()) != {"Actors", "Hashes"}:
        raise ValueError(f"unexpected ActorInfo: {sorted(doc.keys())}")
    new = oead.byml.Hash()
    new["Actors"], new["Hashes"] = oead.byml.Array(actors), oead.byml.Array(hashes)
    out = bytes(oead.byml.to_binary(new, big_endian=True))
    check = oead.byml.from_binary(out)
    check_names = [str(a["name"]) for a in check["Actors"]]
    check_values = [int(h) for h in check["Hashes"]]
    if (len(check_names) != count + len(items) or check_values != sorted(check_values)
            or [crc(n) for n in check_names] != check_values
            or any(check_names.count(item.actor) != 1 for item in items)):
        raise ValueError("declarations inserted wrongly")
    return bytes(oead.yaz0.compress(out)), detail


# --- actor pack --------------------------------------------------------------

def clone_actor_pack(model_pack: bytes, model_actor: str, actor: str,
                     model_folder: str | None = None,
                     model_unit: str | None = None,
                     price: int | None = None) -> tuple[bytes, dict]:
    """The model's actor pack with its ActorLink renamed; every other member as is.

    With `model_folder`, the actor also gets a model list of its own,
    Actor/ModelList/<actor>.bmodellist, pointing to Model/<model_folder>: a
    member of the same path as the model item's would share its cache entry.
    With `price`, the same for its general parameters,
    Actor/GeneralParamList/<actor>.bgparamlist, with Item.BuyingPrice = price:
    3D stalls read the price there, not in ActorInfo (they would sell at amber's 120).
    """
    archive = oead.Sarc(unpack(model_pack))
    writer = oead.SarcWriter.from_sarc(archive)
    old_link = f"Actor/ActorLink/{model_actor}.bxml"
    new_link = f"Actor/ActorLink/{actor}.bxml"
    link = bytes(archive.get_file(old_link).data)
    detail = {"renamed": [old_link, new_link]}
    renamed_users = (["ModelUser"] if model_folder else []) + (
        ["GParamUser"] if price is not None else [])
    if renamed_users:
        pio = oead.aamp.ParameterIO.from_binary(link)
        target = pio.objects["LinkTarget"].params
        for user in renamed_users:
            if str(target[user].v) != model_actor:
                raise ValueError(f"unexpected {user}")
            before_type = target[user].type()
            target[user] = oead.aamp.Parameter(actor)
            if target[user].type() != before_type:
                raise ValueError(f"type of {user} changed")
        link = bytes(pio.to_binary())
    if model_folder:
        old_list = f"Actor/ModelList/{model_actor}.bmodellist"
        models = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(old_list).data))
        base = models.lists["ModelData"].lists["ModelData_0"].objects["Base"].params
        base["Folder"] = oead.aamp.Parameter(oead.FixedSafeString64(model_folder))
        if model_unit:
            unit = models.lists["ModelData"].lists["ModelData_0"].lists["Unit"]
            unit.objects["Unit_0"].params["UnitName"] = oead.aamp.Parameter(
                oead.FixedSafeString64(model_unit))
        del writer.files[old_list]
        writer.files[f"Actor/ModelList/{actor}.bmodellist"] = bytes(models.to_binary())
        detail.update(model_list=f"Actor/ModelList/{actor}.bmodellist", folder=model_folder)
    if price is not None:
        old_params = f"Actor/GeneralParamList/{model_actor}.bgparamlist"
        params = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(old_params).data))
        item = params.objects["Item"].params
        if type(item["BuyingPrice"].v) is not int:
            raise ValueError("unexpected BuyingPrice")
        item["BuyingPrice"] = oead.aamp.Parameter(int(price))
        del writer.files[old_params]
        writer.files[f"Actor/GeneralParamList/{actor}.bgparamlist"] = bytes(params.to_binary())
        detail.update(general_params=f"Actor/GeneralParamList/{actor}.bgparamlist",
                      buying_price=price)
    del writer.files[old_link]
    writer.files[new_link] = link
    packed = bytes(writer.write()[1])
    return bytes(oead.yaz0.compress(packed)), detail


# --- models ------------------------------------------------------------------

MODEL_PARTS = ("", ".Tex1", ".Tex2")     # Model/<folder>{part}.sbfres on Wii U


def bfres_summary(raw: bytes) -> dict:
    """Model and texture names of a Wii U BFRES (FRES v4), textures with size and format."""
    data = unpack(raw)
    if data[:4] != b"FRES":
        raise ValueError("not a BFRES file")

    def name(off):
        return data[off:data.index(b"\0", off)].decode("ascii")

    def group(at):
        count = struct.unpack_from(">I", data, at + 4)[0]
        out = []
        for i in range(count):
            entry = at + 8 + 16 * (i + 1)
            name_rel, data_rel = struct.unpack_from(">ii", data, entry + 8)
            out.append((name(entry + 8 + name_rel), entry + 12 + data_rel))
        return out

    groups = []
    for i in range(2):                  # 0: models, 1: textures
        rel = struct.unpack_from(">i", data, 0x20 + 4 * i)[0]
        groups.append(group(0x20 + 4 * i + rel) if rel else [])
    textures = {}
    for tex_name, off in groups[1]:
        if data[off:off + 4] != b"FTEX":
            raise ValueError(f"texture {tex_name} unreadable")
        (_dim, width, height, _depth, mips, fmt, _aa, _use, image_bytes, _image_ptr,
         mip_bytes) = struct.unpack_from(">11I", data, off + 4)
        textures[tex_name] = {"size": [width, height], "mips": mips, "format": fmt,
                              "image_bytes": image_bytes, "mip_bytes": mip_bytes}
    return {"version": struct.unpack_from(">I", data, 4)[0],
            "models": [n for n, _ in groups[0]], "textures": textures}


def model_bounds(raw: bytes) -> dict:
    """Bounds of the vertex positions (attribute _p0) of every shape, in model units."""
    data = unpack(raw)

    def rel(at):
        value = struct.unpack_from(">i", data, at)[0]
        return at + value if value else 0

    low, high = [float("inf")] * 3, [float("-inf")] * 3
    at = data.find(b"FVTX")
    while at >= 0:
        attribs, count = data[at + 4], struct.unpack_from(">I", data, at + 8)[0]
        attr_array, buf_array = rel(at + 0x10), rel(at + 0x18)
        for a in range(attribs):
            entry = attr_array + 12 * a
            name_off = rel(entry)
            if data[name_off:data.index(b"\0", name_off)] != b"_p0":
                continue
            offset = struct.unpack_from(">H", data, entry + 6)[0]
            fmt = struct.unpack_from(">I", data, entry + 8)[0]
            buffer = buf_array + 0x18 * data[entry + 4]
            stride = struct.unpack_from(">H", data, buffer + 0xC)[0]
            start = rel(buffer + 0x14)
            for v in range(count):
                p = start + v * stride + offset
                if fmt == 0x811:
                    xyz = struct.unpack_from(">3f", data, p)
                elif fmt == 0x80F:
                    xyz = struct.unpack_from(">3e", data, p)
                else:
                    raise ValueError(f"unknown position format: {hex(fmt)}")
                low = [min(a, b) for a, b in zip(low, xyz)]
                high = [max(a, b) for a, b in zip(high, xyz)]
        at = data.find(b"FVTX", at + 4)
    if low[0] == float("inf"):
        raise ValueError("no vertex position found")
    return {"min": [round(x, 4) for x in low], "max": [round(x, 4) for x in high],
            "size": [round(b - a, 4) for a, b in zip(low, high)]}


def index_group(data: bytes, slot: int) -> list[tuple[int, int, int, str]]:
    """Entries (reference, left, right, name) of index group `slot`; entry 0 is the root."""
    rel = struct.unpack_from(">i", data, 0x20 + 4 * slot)[0]
    if not rel:
        return []
    group = 0x20 + 4 * slot + rel
    rows = []
    for i in range(struct.unpack_from(">I", data, group + 4)[0] + 1):
        entry = group + 8 + 16 * i
        ref, left, right, name_rel = struct.unpack_from(">IHHi", data, entry)
        name = ("" if not name_rel else
                data[entry + 8 + name_rel:data.index(b"\0", entry + 8 + name_rel)].decode("ascii"))
        rows.append((ref, left, right, name))
    return rows


def index_lookup(rows, key: str) -> str:
    """The game's search in a Wii U index group (a Patricia trie): references
    decrease downwards from the root (0xFFFFFFFF); bit `ref` is bit ref & 7
    (least significant first) of byte ref >> 3, counted from the start of the
    name. Checked on amber's model and texture groups."""
    raw = key.encode("ascii")
    parent, node = 0, rows[0][1]
    while rows[node][0] < rows[parent][0]:
        ref = rows[node][0]
        bit = (raw[ref >> 3] >> (ref & 7)) & 1 if (ref >> 3) < len(raw) else 0
        parent, node = node, (rows[node][2] if bit else rows[node][1])
    return rows[node][3]


def single_entry_reference(name: str) -> int:
    """Reference of the only entry of an index group: the highest set bit of the
    name (checked on amber's model and on five other models of TitleBG.pack:
    Item_Ore_F 78, Skeleton 62, Link 30, Weapon_Arrow_005 125)."""
    raw = name.encode("ascii")
    return max(i for i in range(len(raw) * 8) if (raw[i >> 3] >> (i & 7)) & 1)


def rename_model(parts: dict[str, bytes], old: str, new: str) -> tuple[dict[str, bytes], dict]:
    """Rename a model's internal names (the files' own names, the model, its
    textures and the material references to them) from `old` to `new`.

    A custom model left with amber's internal names shows amber's textures
    in the game, while Switch Toolbox shows its own. The names keep the
    same length, so no offset moves; every name of the model and texture groups
    must then still be found by the game's search.
    """
    if len(old) != len(new):
        raise ValueError("an internal rename must keep the same length")
    out, counts = {}, {}
    for part, raw in parts.items():
        data = unpack(raw)
        counts[part or "model"] = data.count(old.encode("ascii"))
        renamed = bytearray(data.replace(old.encode("ascii"), new.encode("ascii")))
        if old.encode("ascii") in renamed:
            raise ValueError(f"{old} remains in {part or 'the model'}")
        for slot in (0, 1):
            # A group of several names branches on bits where the names differ;
            # a prefix of the same length leaves them in place. A group of one
            # name tests its highest set bit, which the new name changes.
            rows = index_group(bytes(renamed), slot)
            if len(rows) == 2:
                rel = struct.unpack_from(">i", renamed, 0x20 + 4 * slot)[0]
                struct.pack_into(">I", renamed, 0x20 + 4 * slot + rel + 8 + 16,
                                 single_entry_reference(rows[1][3]))
        renamed = bytes(renamed)
        for slot in (0, 1):
            rows = index_group(renamed, slot)
            for _ref, _left, _right, name in rows[1:]:
                if index_lookup(rows, name) != name:
                    raise ValueError(f"{name} not found after renaming ({part or 'model'})")
        out[part] = bytes(oead.yaz0.compress(renamed)) if raw[:4] == b"Yaz0" else renamed
    summary = bfres_summary(out[""])
    if summary["models"] != [new]:
        raise ValueError(f"internal model: {summary['models']}")
    for part in (".Tex1", ".Tex2"):
        names = bfres_summary(out[part])["textures"]
        if any(not name.startswith(new) for name in names):
            raise ValueError(f"textures{part} renamed wrongly: {sorted(names)}")
    return out, {"from": old, "to": new, "occurrences": counts}


# A game item: 10 cm to 1 m across (amber: 0.59), resting on its origin
# (an FBX exported in centimetres makes the medallion 28 m wide, and a
# mesh below its origin sinks into the ground).
ITEM_SIZE = (0.10, 1.0)
GROUND_TOLERANCE = 0.01


def check_model(custom: dict[str, bytes], reference: dict[str, dict]) -> dict:
    """A custom model must keep what the actor and its material expect: the same
    format version, the same model name inside, the same texture names and
    formats (sizes may change). Parts are keyed by MODEL_PARTS; `reference`
    holds the bfres_summary of each part of the original model."""
    report = {}
    for part in MODEL_PARTS:
        mine, ref = bfres_summary(custom[part]), reference[part]
        if mine["version"] != ref["version"] or mine["models"] != ref["models"]:
            raise ValueError(f"model{part}: format version or model name differs from the original")
        if set(mine["textures"]) != set(ref["textures"]):
            raise ValueError(f"textures{part}: names differ from the original")
        for tex, info in mine["textures"].items():
            # A 512 px texture that keeps the 256 px mip chain sizes: the game draws
            # garbage. Keep the original layout. One known Switch Toolbox habit is
            # accepted and reported: Tex2 (which carries only the mipmaps; the
            # image itself is in Tex1) saved with an image size of 0. The Tex1
            # swizzle it picks is not read here (not part of the layout).
            expected = dict(ref["textures"][tex])
            if part == ".Tex2" and info["image_bytes"] == 0:
                expected["image_bytes"] = 0
                report.setdefault("toolbox_tex2_image_size_zero", []).append(tex)
            if info != expected:
                raise ValueError(
                    f"texture {tex}{part}: layout differs from the original "
                    f"(expected {ref['textures'][tex]['size'][0]} px, "
                    f"{ref['textures'][tex]['mips']} mipmaps, "
                    f"{ref['textures'][tex]['image_bytes']} + {ref['textures'][tex]['mip_bytes']} "
                    f"bytes; got {info['size'][0]} px, {info['mips']} mipmaps, "
                    f"{info['image_bytes']} + {info['mip_bytes']} bytes)")
        report[part or "model"] = {"models": mine["models"],
                                   "textures": {t: i["size"] for t, i in mine["textures"].items()}}
    tex1, tex2 = bfres_summary(custom[".Tex1"]), bfres_summary(custom[".Tex2"])

    def shape(textures):
        return {name: (t["size"], t["mips"], t["format"], t["mip_bytes"])
                for name, t in textures.items()}

    if shape(tex1["textures"]) != shape(tex2["textures"]):
        raise ValueError("Tex1 and Tex2 do not describe the same textures")
    bounds = model_bounds(custom[""])
    widest = max(bounds["size"])
    if not ITEM_SIZE[0] <= widest <= ITEM_SIZE[1]:
        raise ValueError(f"model size: {widest:.2f} units, a game item is "
                         f"{ITEM_SIZE[0]} to {ITEM_SIZE[1]} (FBX exported in centimeters?)")
    if bounds["min"][1] < -GROUND_TOLERANCE:
        raise ValueError(f"the model goes below its origin (y min {bounds['min'][1]}): "
                         "it will sink into the ground")
    report["bounds"] = bounds
    return report


def model_size(reference_size: int, reference_unpacked: int, raw: bytes) -> int:
    """Size table entry of a custom model file: the model item's own ratio of
    declared to real size (`reference_unpacked`: its decompressed size), 10 %
    above it, never below the model item's entry (too small crashes, too big
    only costs memory)."""
    ratio = reference_size / reference_unpacked
    return max(reference_size, int(len(unpack(raw)) * ratio * 1.1) + 31 & ~31)


# --- texts -------------------------------------------------------------------

def label_bucket(label: str, buckets: int) -> int:
    """MSBT label hash (checked on the 599 vanilla labels of Item.msbt)."""
    value = 0
    for byte in label.encode():
        value = (value * 0x492 + byte) & 0xFFFFFFFF
    return value % buckets


def read_sections(raw: bytes) -> list[tuple[bytes, bytes, bytes]]:
    count = struct.unpack_from(">H", raw, 0x0E)[0]
    off, out = 0x20, []
    for _ in range(count):
        head = raw[off:off + 0x10]
        size = struct.unpack_from(">I", head, 4)[0]
        out.append((head[:4], head, raw[off + 0x10:off + 0x10 + size]))
        off += 0x10 + size
        off += (-off) % 16
    return out


def read_labels(raw: bytes) -> dict[str, str]:
    """{label: text}; raises if a label sits outside its hash bucket."""
    sections = {magic: data for magic, _h, data in read_sections(raw)}
    lbl, txt = sections[b"LBL1"], sections[b"TXT2"]
    count = struct.unpack_from(">I", txt, 0)[0]
    offs = [struct.unpack_from(">I", txt, 4 + 4 * i)[0] for i in range(count)] + [len(txt)]
    out = {}
    buckets = struct.unpack_from(">I", lbl, 0)[0]
    for b in range(buckets):
        n_entries, off = struct.unpack_from(">II", lbl, 4 + b * 8)
        for _ in range(n_entries):
            n = lbl[off]
            name = lbl[off + 1:off + 1 + n].decode("ascii")
            idx = struct.unpack_from(">I", lbl, off + 1 + n)[0]
            if label_bucket(name, buckets) != b:
                raise ValueError(f"label in the wrong bucket: {name}")
            out[name] = txt[offs[idx]:offs[idx + 1]].decode("utf-16-be", "replace")
            off += 1 + n + 4
    return out


def add_labels(raw: bytes, entries: dict[str, str], model_label: str) -> tuple[bytes, dict]:
    """Add labels; `_Name` texts reuse the model name's grammar control code."""
    sections = read_sections(raw)
    body = {magic: data for magic, _h, data in sections}
    lbl, txt, atr = body[b"LBL1"], body[b"TXT2"], body[b"ATR1"]
    buckets = struct.unpack_from(">I", lbl, 0)[0]
    table: list[list[tuple[str, int]]] = []
    for b in range(buckets):
        count, off = struct.unpack_from(">II", lbl, 4 + b * 8)
        row = []
        for _ in range(count):
            n = lbl[off]
            row.append((lbl[off + 1:off + 1 + n].decode("ascii"),
                        struct.unpack_from(">I", lbl, off + 1 + n)[0]))
            off += 1 + n + 4
        table.append(row)
    count = struct.unpack_from(">I", txt, 0)[0]
    offs = [struct.unpack_from(">I", txt, 4 + 4 * i)[0] for i in range(count)] + [len(txt)]
    blobs = [txt[offs[i]:offs[i + 1]] for i in range(count)]
    index_of = {name: idx for row in table for name, idx in row}
    if any(label in index_of for label in entries):
        raise ValueError("label already present")
    model = blobs[index_of[model_label]]
    # In languages with grammar (fr, de, es, it) a vanilla name starts with one
    # control code: 0x000E, group, type, size, then `size` bytes of payload;
    # en, nl and ru names have none.
    prefix = (model[:8 + struct.unpack_from(">H", model, 6)[0]]
              if model[:2] == b"\x00\x0e" else b"")
    added = {}
    for label, text in entries.items():
        payload = text.encode("utf-16-be") + b"\x00\x00"
        index = len(blobs)
        blobs.append((prefix + payload) if label.endswith("_Name") else payload)
        table[label_bucket(label, buckets)].append((label, index))
        added[label] = index
    head = bytearray(struct.pack(">I", buckets))
    data = bytearray()
    base = 4 + 8 * buckets
    for row in table:
        head += struct.pack(">II", len(row), base + len(data))
        for name, idx in row:
            data += bytes([len(name)]) + name.encode("ascii") + struct.pack(">I", idx)
    new_lbl = bytes(head + data)
    cur, pointers = 4 + 4 * len(blobs), []
    for blob in blobs:
        pointers.append(cur)
        cur += len(blob)
    new_txt = (struct.pack(">I", len(blobs)) + b"".join(struct.pack(">I", p) for p in pointers)
               + b"".join(blobs))
    if struct.unpack_from(">I", atr, 4)[0]:
        raise ValueError("ATR1 with per-entry data: not supported")
    new_atr = struct.pack(">II", len(blobs), 0) + atr[8:]
    out = bytearray(raw[:0x20])
    for magic, head_bytes, old in sections:
        new = {b"LBL1": new_lbl, b"TXT2": new_txt, b"ATR1": new_atr}.get(magic, old)
        out += head_bytes[:4] + struct.pack(">I", len(new)) + head_bytes[8:0x10] + new
        out += b"\xab" * ((-len(out)) % 16)
    struct.pack_into(">I", out, 0x12, len(out))
    return bytes(out), {"added": added, "entries": len(blobs), "buckets": buckets}


def add_item_texts(msbt: bytes, items: list[ApShopItem]) -> tuple[bytes, dict]:
    entries, models = {}, {item.model_actor for item in items}
    if len(models) != 1:
        raise ValueError("one model item per batch of texts")
    for item in items:
        entries[f"{item.actor}_Name"] = item.name
        entries[f"{item.actor}_Desc"] = item.description
    out, detail = add_labels(msbt, entries, f"{models.pop()}_Name")
    before, after = read_labels(msbt), read_labels(out)
    if (len(after) != len(before) + len(entries)
            or any(after[k] != v for k, v in before.items())
            or any(not after[f"{i.actor}_Name"].endswith(i.name + "\x00") for i in items)
            or any(after[f"{i.actor}_Desc"] != i.description + "\x00" for i in items)):
        raise ValueError("texts added wrongly")
    return out, detail


# --- stock sheet -------------------------------------------------------------

def set_stock_entries(raw: bytes, table: str,
                      entries: dict[int, tuple[str, str, int, int]]) -> tuple[bytes, dict]:
    """entries: {index: (expected vanilla name, actor, stock, price adjustment)}.

    The size calculator has no allocation model for .bshop: the sheet must not
    grow, so that its size table entry stays valid.
    """
    pio = oead.aamp.ParameterIO.from_binary(raw)
    params = pio.objects[table].params
    detail = {}
    for index, (expected, actor, stock, adjust) in entries.items():
        key = f"ItemName{index:03d}"
        if str(params[key].v) != expected:
            raise ValueError(f"unexpected entry {index}: {params[key].v}")
        params[key] = oead.aamp.Parameter(oead.FixedSafeString64(actor))
        params[f"ItemNum{index:03d}"] = oead.aamp.Parameter(stock)
        params[f"ItemAdjustPrice{index:03d}"] = oead.aamp.Parameter(adjust)
        detail[index] = {"before": expected, "after": actor, "stock": stock, "adjust": adjust}
    out = bytes(pio.to_binary())
    if len(out) > len(raw):
        raise ValueError("the sheet grows: size not modeled")
    return out, detail


STOCK_FIELDS = ("ItemSort", "ItemName", "ItemNum", "ItemAdjustPrice", "ItemLookGetFlg",
                "ItemAmount")


def arrange_stock(raw: bytes, table: str, expected: tuple[str, ...],
                  entries: list[str | tuple[str, int, int]]) -> tuple[bytes, dict]:
    """Rewrite a stock table in a new order, with as many entries as before.

    `expected` is the vanilla list of names (checked). Each of `entries` is
    either a vanilla name, moved with every one of its fields, or
    (actor, stock, price adjustment[, ItemLookGetFlg]) for a new item. ItemSort follows the new
    order, as in vanilla sheets (0, 1, 2...). The sheet must not grow (see
    set_stock_entries).
    """
    pio = oead.aamp.ParameterIO.from_binary(raw)
    params = pio.objects[table].params
    count = int(params["ColumnNum"].v)
    names = tuple(str(params[f"ItemName{i:03d}"].v) for i in range(1, count + 1))
    if names != tuple(expected):
        raise ValueError(f"unexpected table {table}: {names}")
    if len(entries) != count:
        raise ValueError(f"{len(entries)} entries for {count} columns")
    def copy(field, index):
        # New parameters: the map's own are overwritten while the table is rewritten.
        value = params[f"{field}{index:03d}"].v
        return oead.aamp.Parameter(oead.FixedSafeString64(str(value))
                                   if field == "ItemName" else value)

    vanilla = {name: {field: copy(field, i) for field in STOCK_FIELDS}
               for i, name in enumerate(names, 1)}
    rows = []
    for index, entry in enumerate(entries, 1):
        if isinstance(entry, str):
            fields = dict(vanilla[entry])
        else:
            actor, stock, adjust, *look = entry
            fields = {"ItemName": oead.aamp.Parameter(oead.FixedSafeString64(actor)),
                      "ItemNum": oead.aamp.Parameter(stock),
                      "ItemAdjustPrice": oead.aamp.Parameter(adjust),
                      "ItemLookGetFlg": oead.aamp.Parameter(bool(look and look[0])),
                      "ItemAmount": oead.aamp.Parameter(0)}
        fields["ItemSort"] = oead.aamp.Parameter(index - 1)
        rows.append(fields)
    for index, fields in enumerate(rows, 1):
        for field in STOCK_FIELDS:
            params[f"{field}{index:03d}"] = fields[field]
    out = bytes(pio.to_binary())
    if len(out) > len(raw):
        raise ValueError("the sheet grows: size not modeled")
    after = tuple(str(oead.aamp.ParameterIO.from_binary(out).objects[table]
                      .params[f"ItemName{i:03d}"].v) for i in range(1, count + 1))
    wanted = tuple(e if isinstance(e, str) else e[0] for e in entries)
    if after != wanted:
        raise ValueError(f"unexpected rewritten table: {after}")
    return out, {"before": list(names), "after": list(after)}


# --- purchase cleanup --------------------------------------------------------

def add_purchase_cleanup(raw: bytes, buy_event: str, actors: list[str]) -> tuple[bytes, dict]:
    """After the merchant's buy list returns, delete each AP item from the pouch.

    The deletes are inserted between `buy_event` (the SubFlowEvent of the buy
    list) and its successor; nothing else of the flow moves.
    """
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    event = before["events"][buy_event]
    if event.get("type") != "SubFlowEvent" or not event.get("nxt"):
        raise ValueError(f"{buy_event} is not a followed sub-flow")
    successor, previous, names = event["nxt"], buy_event, []
    for index, actor in enumerate(actors):
        name = f"APShopDelete{index:02d}"
        add_action_after(flow, previous, name, "EventSystemActor", DELETE_ACTION,
                         {"IsWaitFinish": True, "DeleteNum": -1, "PorchItemName": actor})
        previous = name
        names.append(name)
    after = graph_snapshot(flow)
    if set(after["events"]) - set(before["events"]) != set(names):
        raise ValueError("unexpected events")
    chain = [after["events"][buy_event]["nxt"]]
    while chain[-1] in names:
        chain.append(after["events"][chain[-1]]["nxt"])
    if chain != [*names, successor]:
        raise ValueError(f"delete chain wired wrongly: {chain}")
    for name, node in before["events"].items():
        if name != buy_event and after["events"][name] != node:
            raise ValueError(f"event changed: {name}")
    if after["entry_points"] != before["entry_points"]:
        raise ValueError("entry points changed")
    return write_flow(flow), {"after": buy_event, "deletes": dict(zip(names, actors)),
                              "then": successor}


RECORD_QUERY = "HasPorchItem"
RECORD_ACTION = "Demo_SetGameDataInt"
HIDE_ACTION = "Demo_FlagOFF"


def add_purchase_record(raw: bytes, buy_event: str,
                        records: list[tuple[str, str, str]]) -> tuple[bytes, dict]:
    """After the merchant's buy list returns, record and remove each AP item bought.

    For each (actor, flag, shown flag): if the pouch holds the actor
    (HasPorchItem, as the Ballad condition asks it), set the saved s32 `flag`
    to 1, clear the saved bool `shown flag` (the stock entry is listed only
    while it is true), then delete the
    actor (Demo_DeletePorchItemInEquip); in both cases go on to the next
    check. The checks are
    chained between `buy_event` and its successor, in order; every other
    reference to that successor goes through them too (harmless: nothing is
    held). The flag is what the client tracks, so a purchase counts even when
    the client is not running.
    """
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    event = before["events"][buy_event]
    if event.get("type") != "SubFlowEvent" or not event.get("nxt"):
        raise ValueError(f"{buy_event} is not a followed sub-flow")
    successor = event["nxt"]
    added, switches = [], []
    for index, (actor, flag, shown) in enumerate(records):
        switch = f"APShopBought{index:02d}"
        chain = [(f"APShopRecord{index:02d}", RECORD_ACTION,
                  {"GameDataIntName": flag, "Value": 1, "IsWaitFinish": True}),
                 (f"APShopHide{index:02d}", HIDE_ACTION,
                  {"FlagName": shown, "IsWaitFinish": True}),
                 (f"APShopDelete{index:02d}", DELETE_ACTION,
                  {"IsWaitFinish": True, "DeleteNum": -1, "PorchItemName": actor})]
        branch_with_query(flow, successor, switch, "EventSystemActor", RECORD_QUERY,
                          {"PorchItemName": actor, "Count": 1}, chain, successor)
        added += [switch, *(name for name, _a, _p in chain)]
        switches.append(switch)
    after = graph_snapshot(flow)
    if set(after["events"]) - set(before["events"]) != set(added):
        raise ValueError("unexpected events")
    # Walk the "not bought" path: buy_event -> every switch in order -> successor.
    path, node = [], after["events"][buy_event]["nxt"]
    while node in switches:
        path.append(node)
        cases = after["events"][node]["cases"]
        bought = [cases[1]]
        for _ in range(2):
            bought.append(after["events"][bought[-1]]["nxt"])
        actor, flag, shown = records[len(path) - 1]
        if (after["events"][bought[0]]["params"]["GameDataIntName"] != flag
                or after["events"][bought[1]]["params"]["FlagName"] != shown
                or after["events"][bought[2]]["params"]["PorchItemName"] != actor
                # after a delete, the next check (then the successor), like "not bought"
                or after["events"][bought[2]]["nxt"] != cases[0]):
            raise ValueError(f"purchase wired wrongly: {node}")
        node = cases[0]
    if path != switches or node != successor:
        raise ValueError(f"purchase chain wired wrongly: {path} -> {node}")
    for name, old in before["events"].items():
        new = after["events"][name]
        if name != buy_event and new != old and not _only_redirected(old, new, successor,
                                                                      switches[0]):
            raise ValueError(f"event changed: {name}")
    return write_flow(flow), {"after": buy_event, "then": successor,
                              "records": {actor: [flag, shown] for actor, flag, shown in records}}


def _only_redirected(old: dict, new: dict, successor: str, first: str) -> bool:
    """True when `new` differs from `old` only by links to `successor` now
    pointing at the first inserted check."""
    def swap(value):
        if value == successor:
            return first
        if isinstance(value, dict):
            return {k: swap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [swap(v) for v in value]
        return value
    return {k: (swap(v) if k in ("nxt", "cases", "forks", "join") else v)
            for k, v in old.items()} == new

"""The Gerudo outfit, a key item: Vilia no longer sells it.

Gerudo Town's guards let Link in wearing the three pieces of the Gerudo outfit
(Armor_053_Head, _Upper, _Lower: CheckEquipArmorSeriesType GerudoCloth). In the
game, Vilia sells them at Kara Kara Bazaar: the three for 600 rupees in her quest
(Drag_Hero), then one for 200 rupees (her own flow, copied in the quest's pack).
Every one of these sales first passes a CheckRupee: this stage sets each above
what a purse can hold, so that she never sells them, and the outfit comes from the
multiworld only, as the item "Gerudo Set". Her lines still offer it, at the
price she now asks: 1,000,000 rupees in every language (generate_texts), so that
a player sees why Link never has enough.
"""
from __future__ import annotations

from pathlib import Path
import struct
import tempfile

import oead

from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import ResourceBuilder, digest, unpack

# The purse holds 999,999 rupees at most.
UNPAYABLE = 1_000_000
QUEST = "EventFlow/Drag_Hero.bfevfl"
VILIA = "EventFlow/Npc_SmallOasis008.bfevfl"
PACKS = {"Event/Npc_SmallOasis008.sbeventpack":
         "d8b6f8946fa5d208d67783f5540e51a44100f5116f395b18295a91e5d94756a1",
         "Event/Drag_Hero.sbeventpack":
         "bebcad3d13b95abf2723c87a3a190dba0c9ab4ef9a922912bbf36ba6aa914adf"}
# Each flow, its vanilla digest and the prices of its CheckRupee, in event order.
FLOWS = {QUEST: ("cdcfe2b38655fa75a4e74ceea75e0094f094872c5382eed60beb1af328b0e2a6", [600]),
         VILIA: ("e21f976268a8c0265fb87bf4388b34849787bfeaa7b8008e29dd0657f8c02947", [200, 200, 200])}
STAGES = {"Event/Npc_SmallOasis008.sbeventpack": (VILIA,),
          "Event/Drag_Hero.sbeventpack": (QUEST, VILIA)}
SOURCE_FILES = ("botw_patch/gerudo_outfit.py",)
# The lines that quote her prices, each once, in a coloured run of every
# language: the outfit for 600 in the quest, a piece for 200 in her own talk.
PRICE_LINES = {"EventFlowMsg/Drag_Hero.msbt": {"Npc_SmallOasis008_S1_002": "600"},
               "EventFlowMsg/Npc_SmallOasis008.msbt": {"talk09": "200", "talk10": "200",
                                                       "talk11": "200"}}
# 1,000,000 as each language writes its numbers.
SHOWN_PRICE = {"EUde": "1.000.000", "EUen": "1,000,000", "EUes": "1.000.000",
               "EUfr": "1 000 000", "EUit": "1.000.000", "EUnl": "1.000.000",
               "EUru": "1 000 000"}


def transform_for(member: str):
    expected_digest, prices = FLOWS[member]

    def transform(raw: bytes) -> tuple[bytes, list[str]]:
        if digest(raw) != expected_digest:
            raise ValueError(f"Vilia's flow changed: {member}")
        flow = read_flow(raw)
        before = graph_snapshot(flow)
        checks = [event for event in flow.flowchart.events
                  if type(event.data).__name__ == "SwitchEvent"
                  and event.data.actor_query.v.v == "CheckRupee"]
        if [event.data.params.data["Value"] for event in checks] != prices:
            raise ValueError(f"Vilia's prices changed: {member}")
        for event in checks:
            event.data.params.data["Value"] = UNPAYABLE
        after = graph_snapshot(flow)
        if before["entry_points"] != after["entry_points"] or set(before["events"]) != set(after["events"]):
            raise ValueError(f"Vilia's flow graph changed: {member}")
        return write_flow(flow), [f"{member}: {event.name} CheckRupee {price} -> {UNPAYABLE}"
                                  for event, price in zip(checks, prices)]
    return transform


def set_price(msbt: bytes, prices: dict[str, str], shown: str) -> tuple[bytes, dict]:
    """The price of each label, written once in its text, replaced by `shown`.
    Worked on the UTF-16 units themselves: the control codes around the price
    carry arbitrary values that a decoding would not keep."""
    from botw_patch.shop_items import read_sections
    sections = read_sections(msbt)
    body = {magic: data for magic, _head, data in sections}
    lbl, txt = body[b"LBL1"], body[b"TXT2"]
    index = {}
    for bucket in range(struct.unpack_from(">I", lbl, 0)[0]):
        count, off = struct.unpack_from(">II", lbl, 4 + bucket * 8)
        for _ in range(count):
            n = lbl[off]
            index[lbl[off + 1:off + 1 + n].decode("ascii")] = struct.unpack_from(">I", lbl, off + 1 + n)[0]
            off += 1 + n + 4
    count = struct.unpack_from(">I", txt, 0)[0]
    offs = [struct.unpack_from(">I", txt, 4 + 4 * i)[0] for i in range(count)] + [len(txt)]
    blobs = [txt[offs[i]:offs[i + 1]] for i in range(count)]
    detail = {}
    for label, price in prices.items():
        units = list(struct.unpack(f">{len(blobs[index[label]]) // 2}H", blobs[index[label]]))
        old, new = [ord(c) for c in price], [ord(c) for c in shown]
        digit = lambda at: 0 <= at < len(units) and 0x30 <= units[at] <= 0x39
        found = [at for at in range(len(units) - len(old) + 1)
                 if units[at:at + len(old)] == old and not digit(at - 1) and not digit(at + len(old))]
        if len(found) != 1:
            raise ValueError(f"Vilia's price {price} found {len(found)} times in {label}")
        units[found[0]:found[0] + len(old)] = new
        blobs[index[label]] = struct.pack(f">{len(units)}H", *units)
        detail[label] = f"{price} -> {shown}"
    pointers, cursor = [], 4 + 4 * len(blobs)
    for blob in blobs:
        pointers.append(cursor)
        cursor += len(blob)
    new_txt = struct.pack(f">I{len(blobs)}I", len(blobs), *pointers) + b"".join(blobs)
    out = bytearray(msbt[:0x20])
    for magic, head, data in sections:
        data = new_txt if magic == b"TXT2" else data
        out += head[:4] + struct.pack(">I", len(data)) + head[8:0x10] + data
        out += b"\xab" * ((-len(out)) % 16)
    struct.pack_into(">I", out, 0x12, len(out))
    return bytes(out), detail


def text_inputs() -> dict[str, str]:
    """The message archives read (the same versions as the shop stage's)."""
    from botw_patch.ap_quest import INPUT_HASHES, LANGUAGES
    return {f"Pack/Bootup_{language}.pack": INPUT_HASHES[f"Pack/Bootup_{language}.pack"]
            for language in LANGUAGES}


def generate_texts(files: dict[str, bytes], content: Path) -> tuple[dict[str, bytes], list[dict]]:
    """Vilia's lines at her new price, in every language of the overlay being
    built (after the stages that already changed the message archives)."""
    from botw_patch.ap_quest import LANGUAGES
    hashes = text_inputs()
    table = "System/Resource/ResourceSizeTable.product.srsizetable"
    if table not in files:
        raise ValueError(f"{table} expected in the overlay")
    inputs = {}
    for language in LANGUAGES:
        name = f"Pack/Bootup_{language}.pack"
        if name in files:           # already changed by an earlier stage
            inputs[name] = files[name]
            continue
        raw = (content / name).read_bytes()
        if digest(raw) != hashes[name]:
            raise ValueError(f"unexpected update resource: {name}")
        inputs[name] = raw
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name, raw in {**inputs, table: files[table]}.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)
        for language in LANGUAGES:
            def messages(raw, language=language):
                archive = oead.Sarc(unpack(raw))
                writer = oead.SarcWriter.from_sarc(archive)
                detail = {}
                for member, prices in PRICE_LINES.items():
                    writer.files[member], detail[member] = set_price(
                        bytes(archive.get_file(member).data), prices, SHOWN_PRICE[language])
                packed = bytes(writer.write()[1])
                return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), detail

            builder.patch_archive(f"Pack/Bootup_{language}.pack",
                                  {f"Message/Msg_{language}.product.ssarc": messages})
        out = builder.finish()
        changes = builder.changes
    files = dict(files)
    files.update(out)
    return files, changes
